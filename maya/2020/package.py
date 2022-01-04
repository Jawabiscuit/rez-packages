# -*- coding: utf-8 -*-

name = "maya"

version = "2020.4"

authors = [
    "Autodesk",
]

description = \
    """
    Digital content creation app for vfx and games.
    """

tools = ["fcheck", "imgcvt", "maya", "mayapy"]

variants = [
    ["platform-windows", "arch-AMD64"],
]

private_build_requires = [
    "python-2+<3"
]

uuid = "applications.maya-2020"

build_command = "python {root}/package.py {install}"


def build(
    source_path,
    build_path,
    install_path,
    targets,
    build_args=None
):
    import shutil

    install_mode = "install" in targets

    def _build():
        src = os.path.join(source_path, "MayaNoColorManagement.xml")
        dest = os.path.join(build_path, "MayaNoColorManagement.xml")
        _copyfile(src, dest)
    
    def _install():
        src = os.path.join(build_path, "MayaNoColorManagement.xml")
        dest = os.path.join(install_path, "MayaNoColorManagement.xml")
        _copyfile(src, dest)
    
    def _copyfile(src, dest):
        if os.path.exists(dest):
            os.remove(dest)
        if os.path.exists(src):
            shutil.copy2(src, dest)

    _build()
    if install_mode:
        _install()


def commands():
    import os

    if os.name == "nt":
        maya_install_path = os.path.join("C:", os.sep, "Program Files", "Autodesk",
        "{}{}".format(
            str(this.name).capitalize(), this.version.major
            )
        )
        env.MAYA_COLOR_MANAGEMENT_POLICY_FILE = os.path.join("{root}", "MayaNoColorManagement.xml")
        env.MAYA_COLOR_MANAGEMENT_POLICY_LOCK = 1
        alias("maya2020", r'maya -proj %cd% $*')

    env.MAYA_VERSION = str(this.version)
    env.MAYA_INSTALL_PATH = maya_install_path
    env.MAYA_LOCATION = maya_install_path
    env.LIB.prepend(os.path.join(maya_install_path, "lib"))
    env.INCLUDE.prepend(os.path.join(maya_install_path, "include"))
    env.PATH.prepend(os.path.join(maya_install_path, "bin"))
    env.PYTHONPATH.prepend(
        os.path.join(
            maya_install_path,
            os.path.join("Python", "Lib", "site-packages")
        )
    )
    env.MAYA_VP2_USE_GPU_MAX_TARGET_SIZE = 1
    # Cloud login utilities
    env.MAYA_DISABLE_CLIC_IPM = 1
    # Customer error reporting
    env.MAYA_DISABLE_CER = 1

    # Network license settings
    # Print in the Output Window when Maya is busy or idle
    # env.MAYA_DEBUG_IDLE_LICENSE = 1
    # Time in seconds it takese for Maya to consider itself idle, default=15
    # env.MAYA_DEBUG_IDLE_LICENSE_TIME = 15
    # Disable idle license checking
    # env.MAYA_DISABLE_IDLE_LICENSE = 1


if __name__ == "__main__":
    import os
    import sys
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--install", action="store_true", dest="install")
    if "install" in sys.argv:
        sys.argv.remove("install")
        sys.argv.append("--install")
    args = parser.parse_args(sys.argv[1:])
    _targets = ["install"] if args.install else []

    build(source_path=os.environ["REZ_BUILD_SOURCE_PATH"],
          build_path=os.environ["REZ_BUILD_PATH"],
          install_path=os.environ["REZ_BUILD_INSTALL_PATH"],
          targets=_targets,
          build_args=[])
