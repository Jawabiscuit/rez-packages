# -*- coding: utf-8 -*-

name = "msvc"

version = "14.29.30133"

requires = [
    "platform-windows",
]

private_build_requires = [
    "python-2.7+<3"
]

build_command = "python {root}/package.py {install}"


def commands():
    import os

    msvc_version = "14.29.30133"
    vs_version = "16.0"
    install_dir = os.path.normpath("C:/Program Files (x86)/Microsoft Visual Studio/2019/Community")
    vc_tools_dir = os.path.join(install_dir, "VC", "Tools", "MSVC", msvc_version)

    # Path to vsdevcmd.bat and VsMsBuildCmd.bat
    env.PATH.append(os.path.join(install_dir, "Common7", "Tools"))
    # Path to vcvarsall.bat
    env.PATH.append(os.path.join(install_dir, "VC", "Auxilliary", "Build"))
    # Path to MSBuild.exe
    env.PATH.append(os.path.join(install_dir, "MSBuild", "Current", "Bin"))
    # Path to cl.exe and link.exe
    env.PATH.append(os.path.join(vc_tools_dir, "bin", "Hostx64", "x64"))
    # Path to mt.exe required by the linker
    env.PATH.append(os.path.normpath("C:/Program Files (x86)/Windows Kits/10/bin/10.0.19041.0/x64"))

    env.CMAKE_GENERATOR.append("Visual Studio 16 2019")

    env.EnterpriseWDK.append("true")
    env.VisualStudioVersion.append(vs_version)
    env.VSINSTALLDIR.append(install_dir)
    env.VCToolsVersion.append(vs_version)
    env.VCToolsInstallDir.append(vc_tools_dir)
    env.VCToolsInstallDir_160.append(vc_tools_dir)

