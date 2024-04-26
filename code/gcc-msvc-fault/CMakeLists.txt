cmake_minimum_required(VERSION 3.22)
project(GCC-MSVC-FAULT)

set(CMAKE_CXX_STANDARD 17)

add_library(msvc STATIC msvc.cpp)
target_compile_options(msvc PRIVATE /W4 /WX /O2)