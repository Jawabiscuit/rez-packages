if(NOT tbb_COMPONENTS)
    set(tbb_COMPONENTS tbb)
endif(NOT tbb_COMPONENTS)

set(tbb_INCLUDE_DIRS $ENV{REZ_TBB_ROOT}/include)
set(tbb_LIBRARY_DIRS $ENV{REZ_TBB_ROOT}/lib)
set(tbb_LIBRARIES ${tbb_COMPONENTS})
