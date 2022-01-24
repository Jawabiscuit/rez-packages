cmake_minimum_required(VERSION 2.8)

include(RezBuild)

file(GLOB_RECURSE modules "*.mod")
rez_install_files(${modules} DESTINATION .)

file(GLOB mod_dirs "Ragdoll*")
set(dirlist "")
foreach(child ${mod_dirs})
    if(IS_DIRECTORY ${child})
        list(APPEND dirlist ${child})
    endif()
endforeach()

install_dirs_(
	${dirlist}
	DESTINATION .
)