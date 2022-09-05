# -*- coding: utf-8 -*-

name = 'usd'

version = '20.05'

authors = ['fredrik.brannbacka']

requires = [
	# "boost-1",
	# "tbb-4",
	# "openexr-2.2",
	# "oiio-1",
	# "glew-2",
	# "opensubdiv",
	"PySide-1+<2",
	"PyOpenGL",
	"Jinja2",
]


@early()
def private_build_requires():
    import os

    requires = ["cmake-3.17"]
    if os.name == "nt":
        return requires + ["msvc-14+<15"]
    return requires


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "os-*.*", "python-2.7"]
    return [expand_requires(*requires)]


def commands():
    env.PATH.prepend("{root}/bin")
    env.LD_LIBRARY_PATH.append("{root}/lib")
    env.PYTHONPATH.prepend("{root}/lib/python/")
