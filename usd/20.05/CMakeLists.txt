CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

# rez_find_packages(PREFIX pkgs AUTO)

set(usd_version ${USD_VERSION})
set(url_usd https://github.com/PixarAnimationStudios/USD/archive/refs/tags/v${usd_version}.zip)

# execute_process(COMMAND "${CMAKE_COMMAND}" "-E" "environment")

if(${REZ_BUILD_INSTALL})
    set(install_cmd "")
else()
    set(install_cmd "")
endif()

# set(build_cmd "python build_scripts/build_usd.py $ENV{REZ_BUILD_PATH}")
set(build_cmd "")

ExternalProject_add(
    usd
    PREFIX usd
    URL ${url_usd}
    # CMAKE_ARGS -DCMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX} ${CMAKE_ARGS}
    CONFIGURE_COMMAND = ""
    BUILD_COMMAND "${build_cmd}"
    INSTALL_COMMAND "${install_cmd}"
)