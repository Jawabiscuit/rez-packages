# -*- coding: utf-8 -*-

name = "boost"

description = "A C++14 reflection library, from Peter Dimov. Provides macros for describing enumerators and struct/class members, and primitives for querying this information."

help = "https://www.boost.org"

version = "1.70.0"

uuid = "packages.{}-{}".format(name, version)


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "arch-**", "os-**"]
    return [expand_requires(*requires)]


@early()
def private_build_requires():
    import os

    requires = ["zlib-1+<2"]
    if os.name == "nt":
        return ["msvc-14+<15"] + requires


def commands():
    import os

    env.BOOST = "{root}"
    env.BOOST_ROOT = "{root}"
    env.BOOST_INCLUDEDIR = os.path.join("{root}", "include")
    env.BOOST_LIBRARYDIR = os.path.join("{root}", "lib")
