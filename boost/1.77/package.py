# -*- coding: utf-8 -*-

name = "boost"

description = "A C++14 reflection library, from Peter Dimov. Provides macros for describing enumerators and struct/class members, and primitives for querying this information."

help = "https://www.boost.org"

version = "1.77.0"

uuid = "packages.{}-{}".format(name, version)


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "arch-**", "os-**"]
    return [expand_requires(*requires)]


@early()
def private_build_requires():
    import os

    if os.name == "nt":
        return ["msvc-14+<15"]


def commands():
    import os

    env.BOOST = os.path.join("{root}", this.name)
    env.BOOST_INCLUDEDIR = os.path.join("{root}", this.name, this.name)
