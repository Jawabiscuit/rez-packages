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

uuid = "applications.{}-{}".format(name, version)


@early()
def build_command():
    import os

    if os.name == "nt":
        os.environ["REZ_BUILD_MAYA_INSTALL_PATH"] = os.path.join(
            "C:", os.sep, "Program Files", "Autodesk",
            "{}{}".format(
                str(this.name).capitalize(), this.version.split(".", 1)[0]
            )
        )

        command = 'pwsh -File "{0}"'
        prefix = "%REZ_BUILD_SOURCE_PATH%"
        script = "rezbuild.ps1"

        return command.format(os.path.join(prefix, script))


def commands():
    import os

    if os.name == "nt":
        maya_install_path = os.path.join(
            "C:", os.sep, "Program Files", "Autodesk",
            "{}{}".format(
                str(this.name).capitalize(), this.version.major
            )
        )

        no_color_mgmt_file = os.path.join("{root}", "MayaNoColorManagement.xml")
        if os.path.exists(no_color_mgmt_file):
            env.MAYA_COLOR_MANAGEMENT_POLICY_FILE = no_color_mgmt_file
            env.MAYA_COLOR_MANAGEMENT_POLICY_LOCK = 1
        
        env.PSModulePath.append("{root}")

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
