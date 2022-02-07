# -*- coding: utf-8 -*-

name = "vfxcmake"

description = "Cmake Find modules for common vfx software, and general Cmake utility code"

help = "https://github.com/nerdvegas/vfxcmake"

version = "1.0.0"

requires = [
    "platform-windows",
]

private_build_requires = [
    "msvc-14+<15",
]

uuid = "packages.{}-{}".format(name, version)


def commands():
    import os

    # CMake likes unix-style paths
    env.CMAKE_MODULE_PATH.append(os.path.join(this.root, "cmake").replace("\\", "/"))
