# -*- coding: utf-8 -*-

name = "emacs"

version = "27"

authors = [
    "gnu",
]

description = \
    """
    Emacs is the extensible, customizable, self-documenting real-time display editor.
    """

help = "https://www.emacswiki.org/emacs/GccEmacs"

tools = [
    "emacs",
    "emacsclient",
    "emacsclientw",
]

variants = [
    ["os-Windows-10"],
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
        prefix = "$REZ_BUILD_SOURCE_PATH"
        script = "build.ps1"
        return command.format(os.path.join(prefix, script))


def commands():
    import os

    if os.name == "nt":
        env.HOME.prepend(os.environ["USERPROFILE"])
        env.PATH.append(os.path.join("{root}", "bin"))
