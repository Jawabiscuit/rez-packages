# -*- coding: utf-8 -*-

name = "maya_devkit"

version = "2020.4"

authors = [
    "Autodesk",
]

description = \
    """
    Maya developer examples.
    """

tools = []

variants = [
    ["platform-windows", "arch-AMD64"],
]

requires = [
    "~maya-2020",
]

private_build_requires = [
    "python-2+<3",
    "maya-2020.4",
    "msvc-14+<15",
]

uuid = "packages.maya-devkit-2020"


@early()
def build_command():
    import os

    if os.name == "nt":
        command = 'pwsh -File "{0}" "{1}" "{2}" "{3}"'
        prefix = "%REZ_BUILD_SOURCE_PATH%"
        script = "build.ps1"
        docopy = 0  # Set this to 1 to enable copying the extracted devkit to install dir
    
        return command.format(
            os.path.join(prefix, script),
            this.version.split(".")[0],
            this.version.split(".")[1],
            docopy
        )


def commands():
    import os

    if os.name == "nt":
        devkit_location = os.path.join(this.root, "devkitBase")

        # Better for cmake if slashes are unix-style
        env.DEVKIT_LOCATION = devkit_location.replace("\\", "/")
        env.MAYA_PLUG_IN_PATH.prepend(os.path.join(devkit_location, "devkit", "plug-ins", "scripted"))
        env.MAYA_PLUG_IN_PATH.prepend(os.path.join(devkit_location, "plug-ins"))
        env.PYTHONPATH.prepend(os.path.join(devkit_location, "devkit", "pythonScripts"))
        env.XBMLANGPATH.prepend(os.path.join(devkit_location, "devkit", "icons"))
        env.LIB.prepend(os.path.join(devkit_location, "lib"))
        env.INCLUDE.prepend(os.path.join(devkit_location, "include"))
        env.PATH.prepend(os.path.join(devkit_location, "devkit", "bin"))
