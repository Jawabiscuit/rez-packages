# -*- coding: utf-8 -*-

name = "python"

version = "3.9"

description = "Python is a programming language that lets you work more quickly and integrate your systems more effectively."

authors = ["Guido Van Rossum"]

tools = ["python"]

help = "https://www.python.org/doc"

extra = {
    "vendor_version": "3.9.7150.0",
    "winget_package_name": "Python.Python.3",
}


@early()
def variants():
    from rez.package_py_utils import expand_requires
    requires = ["platform-**", "arch-**"]
    return [expand_requires(*requires)]


@early()
def build_command():
    import os

    os.environ["REZ_BUILD_PROJECT_VENDOR_VERSION"] = this.extra["vendor_version"]
    os.environ["REZ_BUILD_PROJECT_PACKAGE_NAME"] = this.extra["winget_package_name"]

    if os.name == "nt":
        command = 'pwsh -File "{0}"'
        prefix = "%REZ_BUILD_SOURCE_PATH%"
        script = "rezbuild.ps1"

        return command.format(os.path.join(prefix, script))


def commands():
    import os

    env.PATH.prepend(os.path.join(this.root, this.name))
    env.PATH.prepend(os.path.join(this.root, this.name, "Scripts"))
    env.PYTHONPATH.prepend(os.path.join(this.root, this.name, "Lib", "site-packges"))
