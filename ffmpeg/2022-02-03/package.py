# -*- coding: utf-8 -*-

name = "ffmpeg"

version = "2022-02-03"

authors = [
    "Baptiste Coudurier",
]

description = \
    """
    FFmpeg is the leading multimedia framework, able to decode, encode, transcode, mux, demux,
    stream, filter and play pretty much anything that humans and machines have created.
    """

help = "https://ffmpeg.org/about.html"

tools = [
    "ffmpeg",
    "ffplay",
    "ffprobe",
]

variants = [
    ["platform-windows", "arch-AMD64"],
]

requires = []

private_build_requires = [
    "python-2+<3",
]

uuid = "packages.{}-{}".format(name, version)


@early()
def build_command():
    import os

    if os.name == "nt":
        command = 'pwsh -File "{0}"'
        prefix = "%REZ_BUILD_SOURCE_PATH%"
        script = "build.ps1"
        return command.format(os.path.join(prefix, script))


def commands():
    import os

    env.PATH.append(os.path.join("{root}", "bin"))