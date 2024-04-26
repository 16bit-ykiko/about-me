cmake_minimum_required(VERSION 3.22)
project(CRT-FAULT)

set(CMAKE_CXX_STANDARD 17)

add_library(sample SHARED sample.cpp)
target_compile_options(sample PRIVATE "/MT")

add_executable(main main.cpp)
target_link_libraries(main sample)
