CMAKE_MINIMUM_REQUIRED(VERSION 2.8)

include(RezBuild)

set(vs_version 2017)

set(project_version $ENV{REZ_BUILD_PROJECT_VERSION})
string(REPLACE "." ";" version_list ${project_version})
list(GET version_list 0 major)
list(GET version_list 1 minor)

set(src_dir "src/oneTBB-${major}_${minor}")
set(release_dir "${src_dir}/build/vs${vs_version}/x64/Release")

file(
    GLOB_RECURSE dll_files 
    "${release_dir}/*.dll"
)
file(
    GLOB_RECURSE library_files 
    "${release_dir}/*.lib"
)
file(
    GLOB_RECURSE include_files 
    "src/oneTBB-${major}_${minor}/include/*.h"
)

rez_install_files(
    ${dll_files}
    RELATIVE ${release_dir}
    DESTINATION "bin"
)

rez_install_files(
    ${library_files}
    RELATIVE ${release_dir}
    DESTINATION "lib"
)

rez_install_files(
    ${include_files}
    RELATIVE ${src_dir}
    DESTINATION .
)
