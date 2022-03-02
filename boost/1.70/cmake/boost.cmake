if (NOT BOOST_VERSION)
  message(FATAL_ERROR "Empty BOOST_VERSION")
endif()

if (NOT DOWNLOADS)
  message(FATAL_ERROR "Empty DOWNLOADS")
endif()

if (NOT BOOST_SOURCE_DIR)
  message(FATAL_ERROR "Empty BOOST_SOURCE_DIR")
endif()

if (NOT BZIP2_VERSION)
  message(FATAL_ERROR "Empty BZIP2_VERSION")
endif()

if (NOT BZIP2_SOURCE_DIR)
  message(FATAL_ERROR "Empty BZIP2_SOURCE_DIR")
endif()

if (NOT ZLIB_VERSION)
  message(FATAL_ERROR "Empty ZLIB_VERSION")
endif()

if (NOT ZLIB_SOURCE_DIR)
  message(FATAL_ERROR "Empty ZLIB_SOURCE_DIR")
endif()

message(STATUS "BOOST_VERSION: ${BOOST_VERSION}")
message(STATUS "BOOST_SOURCE_DIR: ${BOOST_SOURCE_DIR}")
message(STATUS "BZIP2_SOURCE_DIR: ${BZIP2_SOURCE_DIR}")
message(STATUS "ZLIB_SOURCE_DIR: ${ZLIB_SOURCE_DIR}")
message(STATUS "DOWNLOADS: ${DOWNLOADS}")

string(REPLACE "_" ";" version_list ${BOOST_VERSION})
list(GET version_list 0 major)
list(GET version_list 1 minor)
list(GET version_list 2 patch)

set(BOOST_DOT_VERSION "${major}.${minor}.${patch}")
set(BOOST_TARBALL "boost_${BOOST_VERSION}.tar.bz2")
set(BOOST_DOWNLOAD_URL "https://boostorg.jfrog.io/artifactory/main/release/${BOOST_DOT_VERSION}/source/${BOOST_TARBALL}")

set(BZIP2_TARBALL "bzip2-${BZIP2_VERSION}.tar.gz")
set(BZIP2_DOWNLOAD_URL "https://sourceforge.net/projects/bzip2/files/latest/download")

set(ZLIB_TARBALL "zlib-${ZLIB_VERSION}.tar.gz")
set(ZLIB_DOWNLOAD_URL "https://www.zlib.net/${ZLIB_TARBALL}")

get_filename_component(BOOST_PARENT ${BOOST_SOURCE_DIR} DIRECTORY)
get_filename_component(BZIP2_PARENT ${BZIP2_SOURCE_DIR} DIRECTORY)
get_filename_component(ZLIB_PARENT ${ZLIB_SOURCE_DIR} DIRECTORY)

file(TO_NATIVE_PATH ${DOWNLOADS}/${BOOST_TARBALL} DOWNLOADED_TARBALL)
if(NOT EXISTS ${DOWNLOADED_TARBALL})
  message(STATUS "DOWNLOAD ${BOOST_DOWNLOAD_URL} -> ${DOWNLOADED_TARBALL}")
  file(DOWNLOAD ${BOOST_DOWNLOAD_URL} ${DOWNLOADED_TARBALL} SHOW_PROGRESS STATUS BOOST_DL_STATUS)
  message(STATUS "#### BOOST_DL_STATUS: " ${BOOST_DL_STATUS})
else()
  message(STATUS "${DOWNLOADED_TARBALL} Exists.")
endif()

file(TO_NATIVE_PATH ${DOWNLOADS}/${BZIP2_TARBALL} BZIP2_DOWNLOADED_TARBALL)
if(NOT EXISTS ${BZIP2_DOWNLOADED_TARBALL})
  file(DOWNLOAD ${BZIP2_DOWNLOAD_URL} ${BZIP2_DOWNLOADED_TARBALL} SHOW_PROGRESS)
else()
  message(STATUS "${BZIP2_DOWNLOADED_TARBALL} Exists.")
endif()

file(TO_NATIVE_PATH ${DOWNLOADS}/${ZLIB_TARBALL} ZLIB_DOWNLOADED_TARBALL)
if(NOT EXISTS ${ZLIB_DOWNLOADED_TARBALL})
  file(DOWNLOAD ${ZLIB_DOWNLOAD_URL} ${ZLIB_DOWNLOADED_TARBALL} SHOW_PROGRESS)
else()
  message(STATUS "${ZLIB_DOWNLOADED_TARBALL} Exists.")
endif()

file(TO_NATIVE_PATH ${BOOST_SOURCE_DIR}/boost TEST_DIR)
if(NOT EXISTS ${TEST_DIR})
  message(STATUS "tar xf ${DOWNLOADED_TARBALL} -C ${BOOST_SOURCE_DIR}")
  execute_process(COMMAND ${CMAKE_COMMAND} -E tar xf ${DOWNLOADED_TARBALL} WORKING_DIRECTORY ${BOOST_PARENT})
else()
  message(STATUS "${TEST_DIR} Exists.")
endif()

if(NOT EXISTS ${BZIP2_SOURCE_DIR})
  message(STATUS "tar xf ${BZIP2_DOWNLOADED_TARBALL} -C ${BZIP2_SOURCE_DIR}")
  execute_process(COMMAND ${CMAKE_COMMAND} -E tar xf ${BZIP2_DOWNLOADED_TARBALL} WORKING_DIRECTORY ${BZIP2_PARENT})
endif()

if(NOT EXISTS ${ZLIB_SOURCE_DIR})
  message(STATUS "tar xf ${ZLIB_DOWNLOADED_TARBALL} -C ${ZLIB_SOURCE_DIR}")
  execute_process(COMMAND ${CMAKE_COMMAND} -E tar xf ${ZLIB_DOWNLOADED_TARBALL} WORKING_DIRECTORY ${ZLIB_PARENT})
endif()

configure_file(
  ${CURRENT_SOURCE_DIR}/cmake/boost-build.bat.in
  ${BOOST_SOURCE_DIR}/boost-build.bat
)
