CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

set(tbb_ARGS
    -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
    -DCMAKE_INSTALL_PREFIX=${CMAKE_INSTALL_PREFIX}
    -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE}
)

ExternalProject_add(
    tbb
    PREFIX tbb
    GIT_REPOSITORY https://github.com/oneapi-src/oneTBB
    GIT_TAG "v${TBB_VERSION}"
    CMAKE_ARGS ${tbb_ARGS}
)