cmake_minimum_required(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

ExternalProject_add(
    vfxcmake
    PREFIX vfxcmake
    GIT_REPOSITORY git@github.com:Jawabiscuit/vfxcmake.git
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ""
    INSTALL_COMMAND ""
)

if (${REZ_BUILD_INSTALL})
    file(GLOB_RECURSE modules "build/vfxcmake/src/*.cmake")
    rez_install_files(${modules} RELATIVE "build/vfxcmake/src/vfxcmake" DESTINATION .)
endif()