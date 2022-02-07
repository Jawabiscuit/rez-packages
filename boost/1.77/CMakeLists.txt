cmake_minimum_required(VERSION 2.8)

include(RezBuild)
include(ExternalProject)

# Print Installing but not Up-to-date messages.
set(CMAKE_INSTALL_MESSAGE LAZY)

get_filename_component(PKG_CMAKE_PATH "cmake" ABSOLUTE)
set(CMAKE_MODULE_PATH $ENV{CMAKE_MODULE_PATH} ${PKG_CMAKE_PATH})

set(project_version $ENV{REZ_BUILD_PROJECT_VERSION})
string(REPLACE "." ";" version_list ${project_version})

list(GET version_list 0 major)
list(GET version_list 1 minor)
list(GET version_list 2 patch)

set(boost_url "https://boostorg.jfrog.io/artifactory/main/release/${project_version}/source/boost_${major}_${minor}_${patch}.zip")
message(STATUS "boost_url: ${boost_url}")

ExternalProject_add(
    boost
    PREFIX boost
    URL ${boost_url}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND ""
    INSTALL_COMMAND ""
)

if (${REZ_BUILD_INSTALL})
    file(TO_CMAKE_PATH $ENV{REZ_BUILD_PATH} build_path)
    rez_install_dirs("${build_path}/boost/src/boost" DESTINATION .)
endif()
