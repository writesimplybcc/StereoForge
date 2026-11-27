cmake_minimum_required(VERSION 3.16)
project(stereoforge_core VERSION 0.1.0 LANGUAGES C)

# Set C standard
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Optimization and warning flags
if(MSVC)
    add_compile_options(/W4 /O2 /Oi /Ot)
    add_definitions(-D_CRT_SECURE_NO_WARNINGS)
else()
    add_compile_options(-Wall -Wextra -O3 -fPIC)
    # Enable AVX2 if available on host x86_64
    if(CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|AMD64")
        add_compile_options(-mavx2)
    endif()
endif()

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Source files
set(CORE_SOURCES
    src/stereoforge_mvc.c
    src/annex_h_writer.c
    src/inter_view_encoder.c
)

# Shared library (DLL on Windows, .so on Linux, .dylib on macOS)
add_library(stereoforge_mvc SHARED ${CORE_SOURCES})

# Target definitions for Windows DLL export
if(WIN32)
    target_compile_definitions(stereoforge_mvc PRIVATE STEREOFORGE_EXPORTS)
endif()

set_target_properties(stereoforge_mvc PROPERTIES
    PUBLIC_HEADER include/stereoforge_mvc.h
    OUTPUT_NAME "stereoforge_mvc"
)

# Native unit test executable
add_executable(test_mvc_core tests/main_test.c)
target_link_libraries(test_mvc_core PRIVATE stereoforge_mvc)

# Install rules
install(TARGETS stereoforge_mvc
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
    RUNTIME DESTINATION bin
    PUBLIC_HEADER DESTINATION include
)
