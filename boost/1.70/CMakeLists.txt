cmake_minimum_required(VERSION 2.8)

include(RezBuild)

# For now
if(NOT WIN32)
  message(FATAL_ERROR "This cmake script only supports running on Windows")
endif()

# Print Installing but not Up-to-date messages.
set(CMAKE_INSTALL_MESSAGE LAZY)

set(project_version $ENV{REZ_BUILD_PROJECT_VERSION})
# set(CMAKE_GENERATOR $ENV{CMAKE_GENERATOR})
set(SRC_DIR $ENV{REZ_BUILD_SOURCE_PATH})
set(BUILD_ROOT $ENV{REZ_BUILD_PATH})
set(NUMBER_OF_PROCESSORS $ENV{NUMBER_OF_PROCESSORS})
set(VS_VERSION $ENV{VisualStudioVersion})

# Major, minor, patch numbers
string(REPLACE "." ";" version_list ${project_version})
list(GET version_list 0 major)
list(GET version_list 1 minor)
list(GET version_list 2 patch)

set(BOOST_DOT_VERSION ${BOOST_VERSION})
set(BOOST_VERSION "${major}_${minor}_${patch}")

# For boost.cmake
list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_LIST_DIR}/cmake")

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

file(TO_NATIVE_PATH ${BUILD_ROOT}/boost_${BOOST_VERSION} BOOST_SOURCE_DIR)

set(BZIP2_VERSION 1.0.6)
file(TO_NATIVE_PATH ${BUILD_ROOT}/bzip2-${BZIP2_VERSION} BZIP2_SOURCE_DIR)

set(ZLIB_VERSION 1.2.11)
file(TO_NATIVE_PATH ${BUILD_ROOT}/zlib-${ZLIB_VERSION} ZLIB_SOURCE_DIR)

# Major, minor, patch numbers
string(REPLACE "." ";" version_list $ENV{REZ_MSVC_VERSION})
list(GET version_list 0 major)
list(GET version_list 1 minor)
list(GET version_list 2 patch)
string(SUBSTRING ${minor} 0 1 minor_short)
string(JOIN . msvc_short_version ${major} ${minor_short})

set(BJAM_TOOLSET "msvc-${msvc_short_version}")

if(${VS_VERSION} VERSION_LESS "15.0")
  message(FATAL_ERROR "Visual Studio Version ${VS_VERSION} too old" )
elseif(${VS_VERSION} VERSION_GREATER_EQUAL "18.0")
  message(FATAL_ERROR "Visual Studio Version `${VS_VERSION}` not supported" )
endif()

file(TO_CMAKE_PATH "${BUILD_ROOT}/boost-install-log.txt" boost_install_log )
file(TO_CMAKE_PATH "${BUILD_ROOT}/boost-error-log.txt" boost_error_log )
add_custom_command(OUTPUT ${boost_install_log} ${boost_error_log}
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
  COMMAND cmd /c "echo VISUAL STUDIO VERSION: $ENV{VisualStudioVersion}"
  COMMAND cmd /c "echo MSVC VERSION: $ENV{REZ_MSVC_VERSION}"
  COMMAND cmd /c "echo BJAM TOOLSET: ${BJAM_TOOLSET}"
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
      -s ZLIB_SOURCE_DIR=${zlib_source_dir} --prefix=${CMAKE_INSTALL_PREFIX} link=static,shared --toolset=msvc-${msvc_short_version}
    WORKING_DIRECTORY ${boost_source_dir}
    OUTPUT_FILE ${boost_install_log}
    ERROR_FILE ${boost_error_log}
  )"
)
