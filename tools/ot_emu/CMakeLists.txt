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
add_subdirectory("${OT_VENDOR}/mc68k" "${CMAKE_CURRENT_BINARY_DIR}/mc68k" EXCLUDE_FROM_ALL)

add_library(ot_machine STATIC machine.cpp machine.h v4e.cpp v4e.h)
target_include_directories(ot_machine PUBLIC "${OT_VENDOR}" "${CMAKE_CURRENT_SOURCE_DIR}")
target_link_libraries(ot_machine PUBLIC 68kEmu)

add_executable(ot_emu main.cpp)
target_link_libraries(ot_emu PRIVATE ot_machine)
