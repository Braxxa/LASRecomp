cmake_minimum_required(VERSION 3.22)
project(LASRecompAndroid LANGUAGES C CXX)
if(NOT ANDROID OR NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Android arm64-v8a is required")
endif()
get_filename_component(LAS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)
set(LAS_DEPS "${LAS_ROOT}/build/android/deps" CACHE PATH "Android public dependencies")
set(SDL_AAR "${LAS_ROOT}/build/android/sdl/aar" CACHE PATH "Extracted official SDL3 AAR")
option(LAS_BUILD_GAME "Build personal game library from local generated sources" OFF)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${LAS_ROOT}/tools/android/game_id.py"
    OUTPUT_VARIABLE GAME_ID OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
set(IMGUI "${LAS_ROOT}/third_party/imgui")

add_library(SDL3 SHARED IMPORTED)
set_target_properties(SDL3 PROPERTIES IMPORTED_LOCATION "${SDL_AAR}/prefab/modules/SDL3-shared/libs/android.arm64-v8a/libSDL3.so"
    INTERFACE_INCLUDE_DIRECTORIES "${SDL_AAR}/prefab/modules/SDL3-Headers/include")
foreach(dep avformat avcodec avutil swscale shaderc_shared)
    if(NOT EXISTS "${LAS_DEPS}/lib/lib${dep}.so")
        message(FATAL_ERROR "Missing public dependency: ${LAS_DEPS}/lib/lib${dep}.so")
    endif()
    add_library(${dep} SHARED IMPORTED)
    set_target_properties(${dep} PROPERTIES IMPORTED_LOCATION "${LAS_DEPS}/lib/lib${dep}.so")
endforeach()

file(GLOB RT CONFIGURE_DEPENDS "${LAS_ROOT}/runtime/*.c" "${LAS_ROOT}/runtime/hle/*.c"
    "${LAS_ROOT}/runtime/services/*.c" "${LAS_ROOT}/runtime/nvn/*.c" "${LAS_ROOT}/runtime/nvn/maxwell/*.c"
    "${LAS_ROOT}/runtime/nvn/vulkan/*.c" "${LAS_ROOT}/runtime/nvn/vulkan/*.cpp")
file(GLOB UI CONFIGURE_DEPENDS "${LAS_ROOT}/runtime/ui/*.mm")
set_source_files_properties(${UI} PROPERTIES LANGUAGE CXX COMPILE_FLAGS "-x c++")
file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/inc")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${LAS_ROOT}/tools/android/embed_smaa.py"
    "${LAS_ROOT}/third_party/smaa/SMAA.hlsl" "${CMAKE_CURRENT_BINARY_DIR}/inc/smaa_hlsl.inc"
    COMMAND_ERROR_IS_FATAL ANY)

add_library(main SHARED ${RT} ${UI} "${LAS_ROOT}/runtime/platform/android.c"
    "${CMAKE_CURRENT_LIST_DIR}/probe.c"
    "${CMAKE_CURRENT_LIST_DIR}/game_setup.c"
    "${IMGUI}/imgui.cpp" "${IMGUI}/imgui_draw.cpp" "${IMGUI}/imgui_tables.cpp" "${IMGUI}/imgui_widgets.cpp"
    "${IMGUI}/backends/imgui_impl_sdl3.cpp" "${IMGUI}/backends/imgui_impl_vulkan.cpp")
target_include_directories(main PRIVATE "${LAS_ROOT}/runtime" "${LAS_ROOT}/runtime/nvn"
    "${LAS_DEPS}/include" "${IMGUI}" "${IMGUI}/backends" "${CMAKE_CURRENT_BINARY_DIR}/inc"
    "${LAS_ROOT}/third_party/smaa/Textures")
target_compile_features(main PRIVATE c_std_11 cxx_std_17)
target_compile_definitions(main PRIVATE GAMELIB_ID="${GAME_ID}")
target_compile_options(main PRIVATE -O2 -g -fno-strict-aliasing -Wno-format -Wno-unused-function)
target_link_options(main PRIVATE -Wl,--export-dynamic -Wl,--no-undefined -Wl,-z,max-page-size=16384 -Wl,-z,nostart-stop-gc)
target_link_libraries(main PRIVATE SDL3 avformat avcodec avutil swscale shaderc_shared vulkan android log dl m)

if(LAS_BUILD_GAME)
    file(GLOB GAME CONFIGURE_DEPENDS "${LAS_ROOT}/generated-android/main/*.c" "${LAS_ROOT}/generated-android/sdk/*.c")
    if(NOT GAME)
        message(FATAL_ERROR "Generate the personal game sources locally first")
    endif()
    add_library(lasgame SHARED ${GAME} "${LAS_ROOT}/tools/gamelib_entry.c")
    target_include_directories(lasgame PRIVATE "${LAS_ROOT}/runtime")
    target_compile_definitions(lasgame PRIVATE GAMELIB_ID="${GAME_ID}")
    target_compile_options(lasgame PRIVATE -O1 -fno-strict-aliasing -fvisibility=hidden -Wno-return-type -Wno-unused-label)
    target_link_options(lasgame PRIVATE -Wl,--no-undefined -Wl,-z,max-page-size=16384)
    target_link_libraries(lasgame PRIVATE main)
endif()
