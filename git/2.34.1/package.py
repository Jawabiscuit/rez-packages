# -*- coding: utf-8 -*-

name = "git"

version = "2.34.1"

authors = [
    "gnu",
]

description = \
    """
    Version control system.
    """

tools = [
    "git",
    "git-gui",
    "gitk",
    "git-lfs",
    "git-bash",
    "git-cmd",
]

variants = [
    ["platform-windows", "arch-AMD64"],
]

requires = []

private_build_requires = [
    "python-2+<3",
]

uuid = "packages.{}-{}".format(name, version)

build_command = "python {root}/package.py {install}"


def commands():
    import os

    if os.name == "nt":
        env.PATH.append(os.path.join(os.environ["PROGRAMFILES"], "Git", "cmd"))
        env.PATH.append(os.path.join(os.environ["PROGRAMFILES"], "Git", "mingw64"))
        env.PATH.append(os.path.join(os.environ["PROGRAMFILES"], "Git", "usr", "bin"))
