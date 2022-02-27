# -*- coding: utf-8 -*-

name = "tbb"

version = "2018.U6"

description = "a flexible performance library that let you break computation into parallel running tasks"

help = "https://oneapi-src.github.io/oneTBB/"


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "os-*.*"]
    return [expand_requires(*requires)]


@early()
def private_build_requires():
    import platform

    requires = []
    if platform.system() == "Windows":
        return requires + ["msvc-14.16"]
    return requires


def commands():
    import os
    import platform

    env.PATH.prepend(os.path.join("{root}", "bin"))

    if platform.system() == "Linux":
        env.LD_LIBRARY_PATH.append(os.path.join("{root}", "lib"))
    
    if building:
        env.CMAKE_MODULE_PATH.append(os.path.join(this.root, "cmake").replace("\\", "/"))
