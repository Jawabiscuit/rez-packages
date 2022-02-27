cmake_minimum_required(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

ExternalProject_add(
    nasm
    PREFIX nasm
    URL "https://www.nasm.us/pub/nasm/releasebuilds/${NASM_VERSION}/win64/nasm-${NASM_VERSION}-win64.zip"
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ""
    INSTALL_COMMAND ""
)

if (${REZ_BUILD_INSTALL})
    file(GLOB_RECURSE _files "build/nasm/src/nasm/*.exe")
    message(STATUS "FILES: ${_files}")
    rez_install_files(${_files} RELATIVE "build/nasm/src/nasm" DESTINATION .)
endif()