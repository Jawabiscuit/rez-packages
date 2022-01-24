import os
from maya import cmds
from ..vendor import cmdx

__ = type("internal", (object,), {})()
__.fname = cmds.file("test.ma", expandName=True, query=True)
__.export = cmds.file("tempexport.rag", expandName=True, query=True)

# Bah
__.fname = __.fname.replace("/", os.sep)
__.export = __.export.replace("/", os.sep)


def _new(start=1, end=120):
    cmdx.setUpAxis(cmdx.Y)
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=start, maxTime=end)
    cmds.playbackOptions(animationStartTime=start, animationEndTime=end)
    cmds.currentTime(start)


def _play(node, start=1, end=5):
    if node.type() == "rdRigid":
        attr = "outputTranslateY"
    elif node.isA(cmdx.kTransform):
        attr = "translateY"
    else:
        raise TypeError("How do I evaluate %s?" % node)

    for frame in range(start, end):
        node[attr].read()  # Trigger evaluation
        cmds.currentTime(frame, update=True)


def _step(node, steps=1):
    if node.type() == "rdRigid":
        attr = "outputTranslateY"
    elif node.isA(cmdx.kTransform):
        attr = "translateY"
    else:
        raise TypeError("How do I evaluate %s?" % node)

    ct = int(cmds.currentTime(query=True))
    for time in range(ct, ct + steps + 1):
        cmds.currentTime(time, update=True)
        node[attr].read()  # Trigger evaluation


def _rewind(scene):
    cmds.currentTime(scene["startTime"].as_time().value, update=True)


def _save(name="test.ma"):
    __.fname = cmds.file(rename=name)
    cmds.file(type="mayaAscii", save=True, force=True)
    return __.fname.replace("/", os.sep)


def _load():
    cmds.file(__.fname, open=True, force=True)


def _scene(name):
    scenesdir = os.path.dirname(__file__)
    scenesdir = os.path.join(scenesdir, "scenes")
    return os.path.join(scenesdir, name)


def _open(fname):
    cmds.file(fname, open=True, force=True, ignoreVersion=True)
