name = "Qt_py"

version = "1.3.6"

description = "Minimal Python 2 & 3 shim around all Qt bindings - PySide, PySide2, PyQt4, PyQt5"

authors = ["mottosso"]

requires = ["python-2.7+<4"]

@early()
def private_build_requires():
    import os

    requires = ["pip-19+"]
    if os.name == "nt":
        return ["msvc-14.16+<14.20"] + requires
    return ["cmake-3"] + requires


def commands():
    import os

    env.PYTHONPATH.prepend(os.path.join("{root}", "python", "Qt_py"))
   