cmake_minimum_required(VERSION 2.8)

include(RezBuild)

# For now
if(NOT WIN32)
  message(FATAL_ERROR "This cmake script only supports running on Windows")
endif()

# Print Installing but not Up-to-date messages.
set(CMAKE_INSTALL_MESSAGE LAZY)

set(project_version $ENV{REZ_BUILD_PROJECT_VERSION})

# Major, minor, patch numbers
string(REPLACE "." ";" version_list ${project_version})
list(GET version_list 0 major)
list(GET version_list 1 minor)
list(GET version_list 2 patch)

# For boost.cmake
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/cmake")

set(SRC_DIR $ENV{REZ_BUILD_SOURCE_PATH})
set(BUILD_ROOT $ENV{REZ_BUILD_PATH})
set(NUMBER_OF_PROCESSORS $ENV{NUMBER_OF_PROCESSORS})

find_program(TAR "tar" REQUIRED)

if(NOT $ENV{USERPROFILE} STREQUAL "")
  file(TO_NATIVE_PATH $ENV{USERPROFILE}/Downloads file_path)
  set(DOWNLOADS ${file_path})
elseif(NOT $ENV{HOME} STREQUAL "")
  file(TO_NATIVE_PATH $ENV{HOME}/Downloads file_path)
  set(DOWNLOADS ${file_path})
else()
  set(DOWNLOADS $ENV{TEMP})
endif()

set(BOOST_DOT_VERSION ${BOOST_VERSION})
set(BOOST_VERSION "${major}_${minor}_${patch}")
file(TO_NATIVE_PATH ${BUILD_ROOT}/boost_${BOOST_VERSION} BOOST_SOURCE_DIR)

set(BZIP2_VERSION 1.0.6)
file(TO_NATIVE_PATH ${BUILD_ROOT}/bzip2-${BZIP2_VERSION} BZIP2_SOURCE_DIR)

set(ZLIB_VERSION 1.2.11)
file(TO_NATIVE_PATH ${BUILD_ROOT}/zlib-${ZLIB_VERSION} ZLIB_SOURCE_DIR)

message(STATUS "VISUAL STUDIO VERSION: $ENV{VisualStudioVersion}")
if($ENV{VisualStudioVersion} VERSION_LESS "15.0")
  set(BJAM_TOOLSET "msvc-14.0")
  message(FATAL_ERROR "Visual Studio Version $ENV{VisualStudioVersion} too old" )
elseif($ENV{VisualStudioVersion} VERSION_GREATER_EQUAL "15.0" AND $ENV{VisualStudioVersion} VERSION_LESS "16.0")
  set(GENERATOR "Visual Studio 15 2017 Win64")
  set(BJAM_TOOLSET "msvc-14.1")
elseif($ENV{VisualStudioVersion} VERSION_GREATER_EQUAL "16.0" AND $ENV{VisualStudioVersion} VERSION_LESS "17.0")
  set(GENERATOR "Visual Studio 16 2019")
  set(BJAM_TOOLSET "msvc-14.2")
elseif($ENV{VisualStudioVersion} VERSION_GREATER_EQUAL "17.0" AND $ENV{VisualStudioVersion} VERSION_LESS "18.0")
  set(GENERATOR "Visual Studio 17 2022")
  set(BJAM_TOOLSET "msvc-14.3")
else()
  message(FATAL_ERROR "Visual Studio Version `$ENV{VisualStudioVersion}` not supported" )
endif()

message(STATUS "GENERATOR: ${GENERATOR}")
message(STATUS "BJAM TOOLSET: ${BJAM_TOOLSET}")

file(TO_CMAKE_PATH "${BUILD_ROOT}/boost-install-log.txt" boost_install_log )
file(TO_CMAKE_PATH "${BUILD_ROOT}/boost-error-log.txt" boost_error_log )
add_custom_command(OUTPUT ${boost_install_log}
    COMMAND touch ${boost_install_log}
    COMMAND touch ${boost_error_log}
    COMMENT "Creating ${boost_install_log} ${boost_error_log}"
)

add_custom_target(boost ALL
  COMMAND ${CMAKE_COMMAND}
    -DCURRENT_SOURCE_DIR="${CMAKE_CURRENT_SOURCE_DIR}"
    -DBOOST_VERSION="${BOOST_VERSION}"
    -DBOOST_SOURCE_DIR="${BOOST_SOURCE_DIR}"
    -DBZIP2_VERSION="${BZIP2_VERSION}"
    -DBZIP2_SOURCE_DIR="${BZIP2_SOURCE_DIR}"
    -DZLIB_VERSION="${ZLIB_VERSION}"
    -DZLIB_SOURCE_DIR="${ZLIB_SOURCE_DIR}"
    -DDOWNLOADS="${DOWNLOADS}"
    -P "${CMAKE_CURRENT_SOURCE_DIR}/cmake/boost.cmake"
  COMMAND cmd /c "echo ####################################################################################"
  COMMAND cmd /c "echo boost.cmake done."
  COMMAND cmd /c "echo ####################################################################################"
  COMMAND cmd /c "cd ${BOOST_SOURCE_DIR} && bootstrap.bat"
  COMMAND cmd /c "echo ####################################################################################"
  COMMAND cmd /c "cd ${BOOST_SOURCE_DIR} && boost-build.bat static dynamic"
  DEPENDS ${boost_install_log} ${boost_error_log}
)

file(TO_CMAKE_PATH ${BOOST_SOURCE_DIR} boost_source_dir)
file(TO_CMAKE_PATH ${BZIP2_SOURCE_DIR} bzip2_source_dir)
file(TO_CMAKE_PATH ${ZLIB_SOURCE_DIR} zlib_source_dir)
install(CODE "execute_process(
    COMMAND b2 install -d1 -j${NUMBER_OF_PROCESSORS} address-model=64 -s BZIP2_SOURCE=${bzip2_source_dir}
      -s ZLIB_SOURCE_DIR=${zlib_source_dir} --prefix=${CMAKE_INSTALL_PREFIX} link=static,shared --toolset=msvc
    WORKING_DIRECTORY ${boost_source_dir}
    OUTPUT_FILE ${boost_install_log}
    ERROR_FILE ${boost_error_log}
  )"
)
