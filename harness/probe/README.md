# UE4SS probes (modder's PC only; never shipped)

Read-only diagnostics that log game state to `ue4ss\UE4SS.log` while the tester plays. Rules in
`../docs/diagnostics.md`. Examples here are real probes from earlier mods, kept as starting points:

- `example/ImmCampProbe.cpp`: C++ probe (ImmersiveCampfires). Shows the patterns that worked: SEH-guarded raw reads
  split into a destructor-free function, reading `TArray<FEnhancedActionKeyMapping>` via reflection offsets,
  `ForEachUObject` only on state edges (sit +0.5 s, +3 s), a 1 s change-only live log, reading mod actor
  variables (ints, bools, object refs) by name so Blueprint counters can be checked without Print String.
- `example/ImmDlgProbe.lua`: Lua probe (ImmersiveDialogue). Fine for object/class/name enumeration; cannot read
  struct field values.

## Build a C++ probe
1. Copy an example to `<mod repo>/zonekit/tools/probe/<Short>ProbeCpp/probe.cpp`, rename the class, log tag and
   `ModName`, and cut it down to what the question needs.
2. `CMakeLists.txt` next to it:
   ```cmake
   cmake_minimum_required(VERSION 3.22)
   set(TARGET <Short>ProbeCpp)
   project(${TARGET})
   add_library(${TARGET} SHARED "probe.cpp")
   target_include_directories(${TARGET} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
   target_link_libraries(${TARGET} PUBLIC UE4SS)
   set_target_properties(${TARGET} PROPERTIES OUTPUT_NAME "main")
   ```
3. Build it inside an RE-UE4SS CMake tree (`ue4ss_source` in the machine settings; add the probe folder to that tree's root `CMakeLists.txt` with
   `add_subdirectory(<path to probe> <Short>ProbeCpp)`): `cmake --build Output --config Game__Shipping__Win64 --target <Short>ProbeCpp`.
4. Install `main.dll` to `<game>\Stalker2\Binaries\Win64\ue4ss\Mods\<Short>ProbeCpp\dlls\main.dll`, add
   `<Short>ProbeCpp : 1` to `mods.txt` **above** `UObjectCacheMod`, ASCII without BOM.
5. Prove it logs (heartbeat / main-menu line) before asking for a run. Remove it (folder + `mods.txt` line) when the
   question is answered, and tell the tester.
