# -*- coding: utf-8 -*-

name = "msvc"

description = "Bare minimum build tools for C/C++"

help = "https://devblogs.microsoft.com/cppblog/introducing-the-visual-studio-build-tools"

version = "14.29.30133"

requires = [
    "platform-windows",
]

private_build_requires = [
    "python-2.7+<3"
]


@early()
def build_command():
    import os

    command = 'pwsh -File "{0}"'
    prefix = "%REZ_BUILD_SOURCE_PATH%"
    script = "build.ps1"
    return command.format(os.path.join(prefix, script))


def commands():
    import os

    msvc_version = str(this.version)
    vs_version = "16.11"
    win_sdk_version = "10.0.19041.0"
    cmake_version = "3.20"
    install_dir = os.path.join(this.root, "vs_BuildTools")
    sdk_dir = os.path.join("C:", os.sep, "Program Files (x86)", "Windows Kits", "10")
    sdk_lib_dir = os.path.join(sdk_dir, "Lib", win_sdk_version)
    sdk_include_dir = os.path.join(sdk_dir, "Include", win_sdk_version)
    sdk_bin_dir = os.path.join(sdk_dir, "bin", win_sdk_version)
    vc_tools_dir = os.path.join(install_dir, "VC", "Tools", "MSVC", msvc_version)

    # Path to kernel32.Lib
    env.LIB.append(os.path.join(sdk_lib_dir, "um", "x64"))
    # Path to msvcrtd.lib
    env.LIB.append(os.path.join(vc_tools_dir, "lib", "x64"))
    # Path to ucrtd.lib
    env.LIB.append(os.path.join(sdk_lib_dir, "ucrt", "x64"))
    # Others
    env.LIB.append(os.path.join(sdk_lib_dir, "ucrt_enclave", "x64"))

    # Path to type_traits for Maya Qt dev
    env.INCLUDE.append(os.path.join(vc_tools_dir, "include"))
    # Path to stddef.h for Maya Qt dev
    env.INCLUDE.append(os.path.join(sdk_include_dir, "ucrt"))
    # Path to basetsd.h for Maya Qt dev
    env.INCLUDE.append(os.path.join(sdk_include_dir, "shared"))
    # Others
    env.INCLUDE.append(os.path.join(sdk_include_dir, "cppwinrt"))
    env.INCLUDE.append(os.path.join(sdk_include_dir, "um"))
    env.INCLUDE.append(os.path.join(sdk_include_dir, "winrt"))


    # Path to VsDevCmd.bat and VsMsBuildCmd.bat
    env.PATH.append(os.path.join(install_dir, "Common7", "Tools"))
    # Path to vcvarsall.bat
    env.PATH.append(os.path.join(install_dir, "VC", "Auxiliary", "Build"))
    # Path to MSBuild.exe
    env.PATH.append(os.path.join(install_dir, "MSBuild", "Current", "Bin"))
    # Path to cl.exe and link.exe
    env.PATH.append(os.path.join(vc_tools_dir, "bin", "Hostx64", "x64"))
    # Path to mt.exe required by the linker
    env.PATH.append(os.path.join(sdk_bin_dir, "x64"))
    # Path to cmake.exe
    cmake_dir = os.path.join(
        install_dir, "Common7", "IDE", "CommonExtensions",
        "Microsoft", "CMake", "CMake"
    )
    env.PATH.append(os.path.join(cmake_dir, "bin"))
    # Path to cmake modules
    cmake_module_path = os.path.join(cmake_dir, "share", "cmake-" + cmake_version, "Modules")
    if "cmake" not in resolve:
        env.CMAKE_MODULE_PATH.append(
            cmake_module_path.replace("\\", "/")
        )
    # Path to ninja.exe
    env.PATH.append(os.path.join(
            install_dir, "Common7", "IDE", "CommonExtensions",
            "Microsoft", "CMake", "Ninja"
        )
    )

    env.CMAKE_GENERATOR.append("Visual Studio 16 2019")
    env.EnterpriseWDK.append("true")
    env.VisualStudioVersion.append(vs_version)
    env.VSINSTALLDIR.append(install_dir)
    env.VCToolsVersion.append(msvc_version)
    env.VCToolsInstallDir.append(vc_tools_dir)
    env.VCToolsInstallDir_160.append(vc_tools_dir)
