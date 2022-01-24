# -*- coding: utf-8 -*-

name = "ragdoll"

description = "Ragdoll is a real-time physics solver for Maya"

help = "https://learn.ragdolldynamics.com/"

version = "2022.01.21"

requires = [
    "platform-windows",
    "~maya-2020",
]

private_build_requires = [
    "msvc-14.16.27023",
]

uuid = "packages.ragdoll-2-0"


def commands():
    import os

    env.MAYA_MODULE_PATH.append("{root}")
