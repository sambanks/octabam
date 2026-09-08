# The headless Octatrack machine: a ColdFire and (later) two DSP56300 cores in
# one process, driven from a CLI. No JUCE, no plugin, no audio device -- the
# deliverable is a library and a program you can script and intercept.
#
#   cmake -B out/emu -S tools/ot_emu && cmake --build out/emu -j8
#   out/emu/ot_emu --image out/raw/section_3_MAIN_OS.bin
cmake_minimum_required(VERSION 3.16)
project(ot_emu CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
	set(CMAKE_BUILD_TYPE Release)
endif()

set(OT_VENDOR "${CMAKE_CURRENT_SOURCE_DIR}/../../vendor" CACHE PATH "vendored emulator cores")

# mc68k: Musashi plus the ColdFire mode, the HI08 host-port register file and
# the on-chip peripheral scaffolding. Vendored, GPLv3 -- the same posture as
# vendor/dsp56300: tooling and patches are shared, built binaries never are.
# Not EXCLUDE_FROM_ALL: the vendored core registers its own ColdFire timing,
# divide and HI08 tests, and they are the contract this port stands on.
add_subdirectory("${OT_VENDOR}/mc68k" "${CMAKE_CURRENT_BINARY_DIR}/mc68k")

# dsp56300: the vendored DSP56300 emulator `tools/dsp_host` is built on, with
# the shared-window patch (tools/dsp56300.patch). Its own tree adds a test
# runner, a disassembler and dsp_host; EXCLUDE_FROM_ALL keeps them out of this
# build and links only the library (O8, 8 Sep 2026).
add_subdirectory("${OT_VENDOR}/dsp56300/source" "${CMAKE_CURRENT_BINARY_DIR}/dsp56300" EXCLUDE_FROM_ALL)

add_library(ot_machine STATIC machine.cpp machine.h v4e.cpp v4e.h periph.cpp periph.h card.cpp card.h rtos.cpp rtos.h dsp.cpp dsp.h)
target_include_directories(ot_machine PUBLIC "${OT_VENDOR}" "${CMAKE_CURRENT_SOURCE_DIR}")
target_include_directories(ot_machine PUBLIC "${OT_VENDOR}/dsp56300/source")
target_link_libraries(ot_machine PUBLIC 68kEmu dsp56kEmu)

add_executable(ot_emu main.cpp)
target_link_libraries(ot_emu PRIVATE ot_machine)

# THE GATE. `docs/RTOS_FORK.md` section 10.16: three defects in Unicorn's EMAC
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

# The run loop: route A's M6a gate, self-contained (the full oracle diff needs
# route A itself -- see tools/ot_emu/oracle.py). Runs from the repo root so it
# finds the operator's own stock image; skips cleanly if it is absent.
add_executable(ot_rtos_test test_rtos.cpp)
target_link_libraries(ot_rtos_test PRIVATE ot_machine)
add_test(NAME rtos COMMAND ot_rtos_test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../..)

# O8: the firmware's own DSP upload, through the emulated host port, lands the
# bytes the image carries -- both bootstrap ROMs and both payloads, record for
# record, parsed independently from the image (docs/DSP.md section 2).
add_executable(ot_dsp_test test_dsp.cpp)
target_link_libraries(ot_dsp_test PRIVATE ot_machine)
add_test(NAME dsp COMMAND ot_dsp_test WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../..)
