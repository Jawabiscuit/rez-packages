# -*- coding: utf-8 -*-

name = "nasm"

description = "An asssembler for the x86 CPU architecture portable to nearly every modern platform, and with code generation for many platforms old and new"

help = "nasm.us"

version = "2.15.05"

requires = [
    "platform-windows",
]

private_build_requires = [
    "msvc-14+<15",
]

uuid = "packages.{}-{}".format(name, version)

tools = ["nasm", "ndisasm"]


def commands():
    import os

    env.PATH.append(this.root)
    env.PATH.append(os.path.join(this.root, "rdoff"))
