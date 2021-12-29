# -*- coding: utf-8 -*-

name = "houdini"

version = "19.0.455"

authors = [
    "SideFX",
]

description = \
    """
    Digital content creation app for vfx and games.
    """

tools = [
    "HARS", "abcconvert", "abcecho", "abcinfo", "aconvert", "app_init.sh",
    "args2hda.py", "basehoudini", "builduicode", "chchan", "chcp", "chinfo",
    "claudio", "clchan", "clchn", "clcp", "cldiff", "clinfo",
    "clphone", "ds2hda.py", "dsmconvert", "dsmmerge", "dsparse", "easy",
    "finddeprecated.py", "gabc", "gconvert", "gdxf", "geodiff", "geps",
    "gicon", "giges", "ginfo", "glightwave", "gpdb", "gplay",
    "gply", "gptex", "greduce", "gstat", "gstl", "gwavefront",
    "happrentice", "hbatch", "hbrickmap", "hcollapse", "hcommand", "hcompile",
    "hconfig", "hcpio", "hcustom", "hescape", "hexpand", "hexper",
    "hgpuinfo", "hhalo", "hhalo-ng", "hhelp", "hhelp2.6", "hhelp2.7",
    "hidx", "hindie", "hkey", "hmaster", "hmaster-ng", "hotl",
    "hotlview", "houdini", "houdinicore", "houdinifx", "hremove", "hrender", "hrender.py",
    "hrmanshader", "hsc", "hscript", "hselect", "hserver", "hview",
    "hwatermark", "hython", "hython2.6", "hython2.7", "i3dconvert", "i3ddsmgen",
    "i3dgen", "i3dinfo", "i3diso", "iautocrop", "ic", "icineon",
    "icomposite", "iconvert", "icp", "idiff", "iflip", "ihot",
    "iinfo", "ilut", "ilutcomp", "ilutinfo", "ilutiridas", "imdisplay",
    "iprint", "iquantize", "isixpack", "itilestitch", "izg", "izmatte",
    "mantra", "mcacclaim", "mcbiovision", "mcmotanal", "mcp", "minfo",
    "mplay", "mview", "orbolt_url", "otldiff", "pcfilter", "pcmerge", "pilotpdg",
    "proto_install", "proto_install.sh", "qsvg", "rscript", "sdl2otl.py",
    "sesitag", "siminfo", "slo2otl.py", "spiff", "spy", "thrift", "uiparse",
    "usdcat", "usdchecker", "usddiff", "usddumpcrate", "usdedit", "usdrecord",
    "usdresolve", "usdstitch", "usdstitchclips", "usdtree", "usdview", "usdzip",
    "vcc", "vcc12", "vexexec", "vmantra", "wren", "zmore",
]

variants = [
    ["platform-windows", "arch-AMD64"],
]

private_build_requires = [
    "python-2+<3"
]

uuid = "applications.{}-{}".format(name, version)

build_command = "python {root}/package.py {install}"


def commands():
    import os

    if os.name == "nt":
        hou_install_path = os.path.join(
            "C:", os.sep, "PROGRA~1", "SIDEEF~1",
            "{}~1.{}".format(
                str(this.name).upper()[:6], this.version.patch
            )
        )
    
    hfs = os.path.normpath(hou_install_path)

    env.HOUDINI_MAJOR_RELEASE = str(this.version.major)
    env.HOUDINI_MINOR_RELEASE = str(this.version.minor)
    env.HOUDINI_BUILD_VERSION = str(this.version.patch)
    env.HOUDINI_VERSION = "{}.{}.{}".format(
        this.version.major,
        this.version.minor,
        this.version.patch
    )
    env.HFS = hfs
    env.PATH.prepend(os.path.join(hfs, "bin"))
    env.PATH.prepend(os.path.join(hfs, os.path.join("python37", "Scripts")))
    env.PYTHONPATH.prepend(os.path.join(hfs, os.path.join("houdini", "python3.7libs")))
    env.PYTHONPATH.prepend(os.path.join(hfs, os.path.join("python37", "lib", "site-packages")))
    env.PYTHONPATH.prepend(os.path.join(hfs, os.path.join("python37", "lib", "site-packages-forced", "PySide2")))
