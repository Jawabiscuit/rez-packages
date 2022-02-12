# -*- coding: utf-8 -*-

name = "cmake"

description = "CMake is an open-source, cross-platform family of tools designed to build, test and package software."

help = "https://cmake.org/"

version = "3.17.0"

uuid = "packages.{}-{}".format(name, version)

private_build_requires = [
    "python-2.7+<3"
]

build_command = "python {root}/rezbuild.py {install}"

tools = [
    "cmake-gui", "cmake", "cmcldeps", "cpack", "ctest"
]


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "arch-**", "os-**"]
    return [expand_requires(*requires)]


def commands():
    import os

    env.PATH.append(os.path.join(this.root, "bin"))
    env.CMAKE_MODULE_PATH.prepend(
        os.path.join(
            this.root,
            "share", "{}-{}.{}".format(
                this.name, this.version.major, this.version.minor
            ),
            "Modules"
        ).replace("\\", "/")
    )
