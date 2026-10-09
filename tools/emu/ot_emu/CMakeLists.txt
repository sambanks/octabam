# The headless Octatrack machine: a ColdFire and (later) two DSP56300 cores in
# one process, driven from a CLI. No JUCE, no plugin, no audio device -- the
# deliverable is a library and a program you can script and intercept.
#
#   cmake -B out/emu -S tools/emu/ot_emu && cmake --build out/emu -j8
#   out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin
cmake_minimum_required(VERSION 3.16)
project(ot_emu CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
	set(CMAKE_BUILD_TYPE Release)
endif()

set(OT_VENDOR "${CMAKE_CURRENT_SOURCE_DIR}/../../../vendor" CACHE PATH "vendored emulator cores")

# O15b: link-time optimisation for Release builds. The run loop crosses the
# library boundary on every instruction (m68kops.c -> m68k_read_memory_* ->
# Machine::read*, Musashi's execute_one -> Machine::stepFast); LTO lets the
# linker inline across the vendored core, ot_machine and ot_emu, which the
# per-translation-unit build cannot. Full `-flto` (one module at link time)
# measured faster than CMake's AppleClang default `-flto=thin` (O15b); the
# switch is here so either can be re-measured. OT_LTO=OFF restores the plain
# build (the bisect knob: the bytes the emulator produces must not depend on
# it). Set before add_subdirectory so the vendored targets inherit it; the
# CheckIPOSupported guard keeps a toolchain without LTO building as before.
option(OT_LTO "link-time optimisation for Release builds (O15b)" ON)
set(OT_LTO_MODE "full" CACHE STRING "LTO flavour: full (-flto) or thin (-flto=thin)")
if(OT_LTO)
	include(CheckIPOSupported)
	check_ipo_supported(RESULT _ot_ipo OUTPUT _ot_ipo_msg LANGUAGES C CXX)
	if(_ot_ipo)
		if(OT_LTO_MODE STREQUAL "full")
			foreach(_lang C CXX)
				set(CMAKE_${_lang}_COMPILE_OPTIONS_IPO "-flto")
			endforeach()
		endif()
		set(CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE ON)
		set(CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELWITHDEBINFO ON)
		message(STATUS "ot_emu: LTO ${OT_LTO_MODE} (${CMAKE_C_COMPILE_OPTIONS_IPO}) for Release builds")
	else()
		message(STATUS "ot_emu: LTO not supported by this toolchain, building without: ${_ot_ipo_msg}")
	endif()
endif()

# O15d: profile-guided optimisation, opt-in. Two knobs, both OFF by default
# (a default configure builds exactly as before: LTO only):
#   -DOT_PGO_GENERATE=ON        the instrumented build (-fprofile-instr-generate
#                               on every compile and link line, the cores
#                               included); running it writes an LLVM .profraw
#                               to $LLVM_PROFILE_FILE at exit (`quit` / EOF /
#                               end of batch -- main returns, atexit runs).
#   -DOT_PGO_PROFILE=<.profdata> the optimised build (-fprofile-instr-use=<path>
#                               on every compile and link line): the merged
#                               profile steers inlining, block layout and
#                               branch weights on top of LTO. It changes code
#                               placement only, never what the code computes
#                               (no fast-math, no reassociation); the oracle is
#                               run on it all the same.
# tools/emu/ot_emu/pgo.sh does the whole ritual (instrumented build, the two
# training runs, `llvm-profdata merge`, the optimised build into out/emu).
# The profile is BUILD-HOST SPECIFIC (compiler version, flags, the source
# bytes it was collected on): after any source change under tools/emu/ot_emu
# or the vendored cores regenerate it; a stale profile is matched function by
# function by name and CFG hash, a changed function simply gets no weights,
# so it only loses speed, never correctness (O15d measured that with the
# oracle on a deliberately stale profile). Set before add_subdirectory so the
# vendored targets inherit both; directory-scoped so nothing here needs to
# know the vendored target names.
option(OT_PGO_GENERATE "PGO: build instrumented for profile collection (O15d)" OFF)
set(OT_PGO_PROFILE "" CACHE FILEPATH "PGO: merged .profdata to optimise with (O15d); empty = no PGO")
option(OT_PGO_WARNINGS "PGO: show clang's per-file profile warnings (unprofiled / out-of-date / hash mismatch)" OFF)
if(OT_PGO_GENERATE AND OT_PGO_PROFILE)
	message(FATAL_ERROR "ot_emu: OT_PGO_GENERATE and OT_PGO_PROFILE are exclusive (instrument, train, then optimise)")
endif()
if(OT_PGO_GENERATE)
	add_compile_options(-fprofile-instr-generate)
	add_link_options(-fprofile-instr-generate)
	message(STATUS "ot_emu: PGO instrumented build (-fprofile-instr-generate); set LLVM_PROFILE_FILE when running it")
elseif(OT_PGO_PROFILE)
	if(NOT EXISTS "${OT_PGO_PROFILE}")
		message(FATAL_ERROR "ot_emu: OT_PGO_PROFILE=${OT_PGO_PROFILE} does not exist (run tools/emu/ot_emu/pgo.sh)")
	endif()
	add_compile_options("-fprofile-instr-use=${OT_PGO_PROFILE}")
	add_link_options("-fprofile-instr-use=${OT_PGO_PROFILE}")
	# Every object must come from the SAME profile: an object compiled with
	# profile A cannot be LTO-linked with one compiled with profile B ("ld:
	# LTO codegen error: linking module flags 'ProfileSummary': IDs have
	# conflicting values"). The build system only sees the flag text, and the
	# path is the same whatever the bytes at it -- so a tree that already
	# holds objects from an earlier profile (the vendored cores, whose sources
	# did not change; 156 of 171 objects on the second `pgo.sh` run) would
	# keep them and the link would fail. Two things make the tree follow the
	# profile's BYTES: its SHA-256 goes into every compile line as a define
	# nothing reads, so every flags.make changes with the profile and every
	# object is recompiled (`cmake --fresh` alone does not do that: it clears
	# the cache, not the objects); and the profile is a configure dependency,
	# so a plain `cmake --build` after the profile changed re-runs cmake by
	# itself. The define does not reach the bytes: the same profile gives the
	# same binary in any tree (O15d, fix1).
	file(SHA256 "${OT_PGO_PROFILE}" _ot_pgo_sha256)
	add_compile_definitions("OT_PGO_PROFILE_SHA256=${_ot_pgo_sha256}")
	set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${OT_PGO_PROFILE}")
	if(NOT OT_PGO_WARNINGS)
		# -Wprofile-instr-unprofiled: every file the training never ran (the
		# test programs, asmjit, the JIT, the DSP disassembler) would warn once;
		# -Wbackend-plugin: clang's per-function "control flow change detected
		# (hash mismatch)" for a stale profile, hundreds of lines. Both are
		# expected noise; -Wprofile-instr-out-of-date (one line per file whose
		# functions no longer match: "the profile is stale, regenerate") stays
		# visible. OT_PGO_WARNINGS=ON shows all three (the acceptance check:
		# no `profile-instr-unprofiled` on machine/rtos/periph/v4e/dsp/m68kops).
		add_compile_options(-Wno-profile-instr-unprofiled -Wno-backend-plugin)
	endif()
	message(STATUS "ot_emu: PGO optimised build with ${OT_PGO_PROFILE}")
endif()

# mc68k: Musashi plus the ColdFire mode, the HI08 host-port register file and
# the on-chip peripheral scaffolding. Vendored, GPLv3 -- the same posture as
# vendor/dsp56300: tooling and patches are shared, built binaries never are.
# Not EXCLUDE_FROM_ALL: the vendored core registers its own ColdFire timing,
# divide and HI08 tests, and they are the contract this port stands on.
add_subdirectory("${OT_VENDOR}/mc68k" "${CMAKE_CURRENT_BINARY_DIR}/mc68k")

# dsp56300: the vendored DSP56300 emulator `tools/harness/dsp_host` is built on, with
# the shared-window patch (tools/patches/dsp56300.patch). Its own tree adds a test
# runner, a disassembler and dsp_host; EXCLUDE_FROM_ALL keeps them out of this
# build and links only the library (O8, 8 Sep 2026).
add_subdirectory("${OT_VENDOR}/dsp56300/source" "${CMAKE_CURRENT_BINARY_DIR}/dsp56300" EXCLUDE_FROM_ALL)

add_library(ot_machine STATIC machine.cpp machine.h v4e.cpp v4e.h periph.cpp periph.h card.cpp card.h rtos.cpp rtos.h dsp.cpp dsp.h usb.cpp usb.h)
target_include_directories(ot_machine PUBLIC "${OT_VENDOR}" "${CMAKE_CURRENT_SOURCE_DIR}")
target_include_directories(ot_machine PUBLIC "${OT_VENDOR}/dsp56300/source")
target_link_libraries(ot_machine PUBLIC 68kEmu dsp56kEmu)

add_executable(ot_emu main.cpp)
target_link_libraries(ot_emu PRIVATE ot_machine)

# THE GATE. `docs/history/RTOS_FORK.md` section 10.16: three defects in Unicorn's EMAC
# cost a week, each producing a confident wrong finding. Nothing this emulator
# computes is trustworthy until this passes.
include(CTest)
add_executable(ot_emac_test test_emac.cpp)
target_link_libraries(ot_emac_test PRIVATE ot_machine)
add_test(NAME emac COMMAND ot_emac_test)

# The peripheral rules, each one a silent failure in route A before it was
# found (RTOS_FORK sections 8.2 and 4).
add_executable(ot_periph_test test_periph.cpp)
target_link_libraries(ot_periph_test PRIVATE ot_machine)
add_test(NAME periph COMMAND ot_periph_test)

# The run loop: route A's M6a gate (every task created and run once),
# self-contained. Runs from the repo root so it
# finds the operator's own stock image; skips cleanly if it is absent.
add_executable(ot_rtos_test test_rtos.cpp)
target_link_libraries(ot_rtos_test PRIVATE ot_machine)
add_test(NAME rtos COMMAND ot_rtos_test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../../..)

# O8: the firmware's own DSP upload, through the emulated host port, lands the
# bytes the image carries -- both bootstrap ROMs and both payloads, record for
# record, parsed independently from the image (docs/firmware/DSP.md section 2).
add_executable(ot_dsp_test test_dsp.cpp)
target_link_libraries(ot_dsp_test PRIVATE ot_machine)
add_test(NAME dsp COMMAND ot_dsp_test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../../..)

# Repitch's firmware patch relies on stock TSTR value numbers, descriptor
# bounds and one rate-selection block. Keep those reverse-engineered facts
# executable so a different base image cannot silently invalidate the hook.
add_executable(ot_repitch_stock_test ../../harness/repitch_probe.cpp)
target_link_libraries(ot_repitch_stock_test PRIVATE ot_machine)
add_test(NAME repitch-stock COMMAND ot_repitch_stock_test
	WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../../..)
add_test(NAME repitch-patch COMMAND ot_repitch_stock_test --patched out/mainos_bus.bin
	WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../../..)

# Euclid's sequencer-to-filter adapter, including its compiled control engine.
add_executable(ot_euclid_test ../../harness/euclid_probe.cpp)
target_link_libraries(ot_euclid_test PRIVATE ot_machine)

# fxlive's CPU stage: the ColdFire frame routine on one track, streamed
# (tools/harness/fxlive/README.md).
add_executable(ot_cf_host ../../harness/fxlive/cf_host.cpp)
target_link_libraries(ot_cf_host PRIVATE ot_machine)

add_executable(ot_tapeecho_cpu_test ../../harness/tapeecho_cpu_probe.cpp
    ../../../modules/tapeecho/cpu.c)
target_compile_definitions(ot_tapeecho_cpu_test PRIVATE TE_HOST=1)
# The host oracle is Tape Echo's cpu.c compiled natively; its mix arithmetic
# overflows int32 on a steep negative MIX ramp (cpu.c 251/303/305, UBSan
# 27 Sep 2026), which is undefined in C and which clang's optimiser exploits
# ("tape output mismatch 3/16 (mode 3)") while the ColdFire kernel wraps.
# -fwrapv makes the oracle wrap the way the target does.
target_compile_options(ot_tapeecho_cpu_test PRIVATE -fwrapv)
target_link_libraries(ot_tapeecho_cpu_test PRIVATE ot_machine)
