from maya import cmds
from .. import constants
from ..legacy import commands
from ..legacy.tools import chain_tool
from ..vendor import cmdx
from . import _play, _new, _step, _rewind

from nose.tools import (
    assert_equals,
    assert_true,
    assert_almost_equals,
)


def test_defaults():
    _new()

    cube, _ = cmds.polyCube()
    cube = cmdx.encode(cube)  # Convert to cmdx
    cube["translateY"] = 10
    cube["rotate", cmdx.Degrees] = (35, 50, 30)

    cmds.currentTime(1)

    scene = commands.create_scene()
    commands.create_rigid(cube, scene)

    for frame in range(1, 30):
        cube["ty"].read()  # Trigger evaluation
        cmds.currentTime(frame)

    # It'll be resting on the ground at this point
    assert_almost_equals(cube["ty"].read(), 0.500, 3)


def test_delete_all():
    _new()

    a = cmdx.createNode("transform")
    b = cmdx.createNode("transform", parent=a)
    c = cmdx.createNode("transform", parent=b)
    d = cmdx.createNode("transform", parent=c)

    a["ty"] = 5.0
    b["tx"] = 5.0
    c["tx"] = 5.0
    d["tx"] = 5.0

    scene = commands.create_scene()

    operator = chain_tool.Chain([a, b, c, d], scene)
    assert operator.pre_flight()
    operator.do_it()
    assert_equals(len(cmds.ls(type="rdRigid")), 4)

    result = commands.delete_physics([scene, a, b, c, d])

    # 1 scene, 4 rigids, 3 constraints, 1 multiplier
    assert_equals(result["deletedRagdollNodeCount"], 9)

    # (1) Scene node transform
    # (3) multMatrix
    # (3) composeMatrix
    assert_equals(result["deletedExclusiveNodeCount"], 7)

    assert_equals(len(cmds.ls(type="rdRigid")), 0)

    cmds.undo()

    assert_equals(len(cmds.ls(type="rdRigid")), 4)

    commands.delete_physics([a, b, c, d])
    assert_equals(len(cmds.ls(type="rdRigid")), 0)


def test_scene_clean():
    """rdScene.clean accurately tells us whether it has been evaluated"""

    _new()

    parent = cmdx.create_node("transform", name="parent")
    child = cmdx.create_node("transform", name="child", parent=parent)

    scene = commands.create_scene()
    commands.create_rigid(child, scene)

    # Trigger evaluation
    child["translateX"].read()
    assert not scene["clean"].read()

    def part_of_scene(transform, scene):
        """We'll know whether `transform` is involved via scene.clean"""
        scene["clean"] = True
        transform["translateX"].read()
        return not scene["clean"].read()

    assert part_of_scene(child, scene), (
        "%s should have been part of scene" % child
    )

    assert not part_of_scene(parent, scene), (
        "%s should NOT have been part of scene" % parent
    )


def test_scene_clean_passive():
    """rdScene.clean understands active versus passive rigids"""

    _new()

    parent = cmdx.create_node("transform", name="parent")
    child = cmdx.create_node("transform", name="child", parent=parent)

    scene = commands.create_scene()

    commands.create_rigid(parent, scene, opts={"passive": True})
    commands.create_rigid(child, scene, opts={"passive": False})

    # Trigger evaluation
    child["translateX"].read()
    assert not scene["clean"].read()

    def part_of_scene(transform, scene):
        """We'll know whether `transform` is involved via scene.clean"""
        scene["clean"] = True
        transform["translateX"].read()
        return not scene["clean"].read()

    assert part_of_scene(child, scene), (
        "%s should have been part of scene" % child
    )

    assert not part_of_scene(parent, scene), (
        "%s should NOT have been part of scene" % parent
    )


def test_convert_constraint():
    _new()

    parent = cmdx.create_node("transform", name="parent")
    child = cmdx.create_node("transform", name="child", parent=parent)

    scene = commands.create_scene()
    parent_rigid = commands.create_rigid(parent, scene)
    child_rigid = commands.create_rigid(child, scene)

    con = commands.point_constraint(parent_rigid, child_rigid)

    def almost_equals(e1, e2):
        assert_almost_equals(e1[0], e2[0], 4)
        assert_almost_equals(e1[1], e2[1], 4)
        assert_almost_equals(e1[2], e2[2], 4)

    almost_equals(con["linearLimit"].as_vector(), (-1, -1, -1))
    almost_equals(con["angularLimit"].as_euler(), cmdx.Euler(0, 0, 0))

    commands.convert_to_parent(con)
    al = cmdx.radians(-1)  # Angular Locked
    almost_equals(con["linearLimit"].as_vector(), (-1, -1, -1))
    almost_equals(con["angularLimit"].as_euler(), cmdx.Euler(al, al, al))

    commands.convert_to_socket(con)
    a45 = cmdx.radians(45)
    almost_equals(con["linearLimit"].as_vector(), (-1, -1, -1))
    almost_equals(con["angularLimit"].as_euler(), cmdx.Euler(a45, a45, a45))


def test_edit_constraint_pivot():
    _new()

    parent = cmdx.create_node("transform")
    child = cmdx.create_node("transform", parent=parent)
    parent["ty"] = 5.0
    child["tx"] = 5.0

    scene = commands.create_scene()
    parent_rigid = commands.create_rigid(parent, scene, opts={"passive": True})
    child_rigid = commands.create_rigid(child, scene)

    con = commands.point_constraint(parent_rigid, child_rigid)

    child["worldMatrix"][0].pull()

    # Before
    assert_almost_equals(parent_rigid["owty"].read(), 5.0, 2)
    assert_almost_equals(child_rigid["owty"].read(), 5.0, 2)

    _step(child_rigid, 30)

    # Point constaint holds it in place
    assert_almost_equals(parent_rigid["owty"].read(), 5.0, 2)
    assert_almost_equals(child_rigid["owty"].read(), 5.0, 2)

    cmdx.currentTime(scene["startTime"].as_time())
    child["worldMatrix"][0].pull()

    # Move pivot to parent
    #
    #  |<---------   |
    #  o-------------o
    #
    pframe, cframe = commands.edit_constraint_frames(con)
    pframe["tx"] = 0.0
    cframe["tx"] = -5.0

    _step(child_rigid, 30)

    # o
    #  \
    #   \
    #    \
    #     o
    assert_almost_equals(child_rigid["owtx"].read(), 3.0, 2)
    assert_almost_equals(child_rigid["owty"].read(), 1.0, 2)


def test_edit_shape():
    _new()

    tm = cmdx.create_node("transform")
    scene = commands.create_scene()
    rigid = commands.create_rigid(tm, scene)

    assert_almost_equals(rigid["shapeOffsetX"], 0.0, 3)

    editor = commands.edit_shape(rigid)
    editor["tx"] = 5.0

    assert_almost_equals(rigid["shapeOffsetX"], 5.0, 3)

    # Editor is optional
    cmdx.delete(editor)

    assert_almost_equals(rigid["shapeOffsetX"], 5.0, 3)


def test_convert_rigid():
    _new()

    tm = cmdx.create_node("transform")
    scene = commands.create_scene()
    rigid = commands.create_rigid(tm, scene)

    # Active -> Active
    assert_equals(rigid["kinematic"].read(), False)
    commands.convert_rigid(rigid, opts={"passive": False})
    assert_equals(rigid["kinematic"].read(), False)

    # Active -> Passive
    commands.convert_rigid(rigid, opts={"passive": True})
    assert_equals(rigid["kinematic"].read(), True)

    # Passive -> Active
    commands.convert_rigid(rigid, opts={"passive": False})
    assert_equals(rigid["kinematic"].read(), False)

    # Passive -> Passive
    commands.convert_rigid(rigid, opts={"passive": False})
    assert_equals(rigid["kinematic"].read(), False)


def test_rotate_pivot():
    _new()

    #   /\     +
    #  /  \
    #  \  /
    #   \/
    #
    #
    # ______

    box, _ = map(cmdx.encode, cmds.polyCube())
    box["ty"] = 10
    box["rz", cmdx.Degrees] = 46
    box["rotatePivotX"] = 5

    scene = commands.create_scene()
    rigid = commands.create_rigid(box, scene)

    _step(rigid, 30)

    assert_almost_equals(box["tx"].read(), -4.0, 1)


def test_rotate_order():
    _new()

    #   /\     +
    #  /  \
    #  \  /
    #   \/
    #
    #
    # ______

    box, _ = map(cmdx.encode, cmds.polyCube())
    box["ty"] = 2
    box["rotateX", cmdx.Degrees] = 180
    box["rotateZ", cmdx.Degrees] = 50

    scene = commands.create_scene()
    rigid = commands.create_rigid(box, scene)

    _step(rigid, 30)

    assert_almost_equals(box["rx", cmdx.Degrees].read(), -180.0, 0)
    assert_almost_equals(box["rz", cmdx.Degrees].read(), 90.0, 0)

    box["rotateOrder"] = 1  # YZX

    assert_almost_equals(box["rx", cmdx.Degrees].read(), -90.0, 0)
    assert_almost_equals(box["ry", cmdx.Degrees].read(), -90.0, 0)
    assert_almost_equals(box["rz", cmdx.Degrees].read(), -90.0, 0)


def test_rotate_axis():
    _new()

    #   /\     +
    #  /  \
    #  \  /
    #   \/
    #
    #
    # ______

    box, _ = map(cmdx.encode, cmds.polyCube())
    box["ty"] = 10
    box["rotateAxisX", cmdx.Degrees] = 46

    scene = commands.create_scene()
    rigid = commands.create_rigid(box, scene)

    _step(rigid, 30)

    assert_almost_equals(box["tz"].read(), 0.5, 1)


def test_joint_orient():
    _new()

    joint1 = cmdx.create_node("joint")
    joint2 = cmdx.create_node("joint", parent=joint1)
    joint3 = cmdx.create_node("joint", parent=joint2)
    joint4 = cmdx.create_node("joint", parent=joint3)

    joint1["ty"] = 5.0
    joint2["tx"] = 5.0
    joint3["tx"] = 5.0
    joint4["tx"] = 5.0

    joint1["jointOrient", cmdx.Degrees] = (0, 0, -45)
    joint2["jointOrient", cmdx.Degrees] = (0, 0, 90)
    joint3["jointOrient", cmdx.Degrees] = (0, 0, -45)

    scene = commands.create_scene()
    scene["gravity"] = (0, 0, 0)

    parent_rigid = None
    for joint in (joint1, joint2, joint3, joint4):
        rigid = commands.create_rigid(joint, scene)

        if parent_rigid:
            commands.socket_constraint(parent_rigid, rigid)

        parent_rigid = rigid

    # Simulation doesn't change anything, because gravity is off
    _step(rigid, 10)

    assert_almost_equals(joint1["jointOrientZ", cmdx.Degrees].read(), -45, 3)
    assert_almost_equals(joint1["rx", cmdx.Degrees].read(), 0, 3)


def test_stable_no_gravity():
    """Without gravity and contacts, a constrained hierarchy does not move"""
    _new()

    joint1 = cmdx.create_node("joint")
    joint2 = cmdx.create_node("joint", parent=joint1)
    joint3 = cmdx.create_node("joint", parent=joint2)
    joint4 = cmdx.create_node("joint", parent=joint3)

    joint1["ty"] = 5.0
    joint2["tx"] = 5.0
    joint3["tx"] = 5.0
    joint4["tx"] = 5.0

    joint1["jointOrient", cmdx.Degrees] = (0, 0, -45)
    joint2["jointOrient", cmdx.Degrees] = (0, 0, 90)
    joint3["jointOrient", cmdx.Degrees] = (0, 0, -45)

    scene = commands.create_scene()
    scene["gravity"] = (0, 0, 0)

    parent_rigid = None
    for joint in (joint1, joint2, joint3, joint4):
        rigid = commands.create_rigid(joint, scene)

        if parent_rigid:
            commands.socket_constraint(parent_rigid, rigid)

        parent_rigid = rigid

    # Simulation doesn't change anything, because gravity is off
    _step(rigid, 100)

    assert_almost_equals(joint1["tx"].read(), 0.0, 3)


def test_clear_initial_state():
    """Clear initial state snaps a simulation back into creation state"""
    _new()

    tm = cmdx.create_node("transform")
    tm["ty"] = 10.0
    scene = commands.create_scene()
    rigid = commands.create_rigid(tm, scene)

    _step(rigid, 10)
    _rewind(scene)

    assert_almost_equals(tm["tx"].read(), 0.0, 3)
    assert_almost_equals(tm["ty"].read(), 10.0, 3)

    tm["tx"] = 5.0
    commands.set_initial_state(rigids=[rigid])

    _step(rigid, 10)

    assert_almost_equals(tm["tx"].read(), 5.0, 3)

    _rewind(scene)

    # This should immediately snap the object back to the creation matrix
    commands.clear_initial_state(rigids=[rigid])
    assert_almost_equals(tm["tx"].read(), 0.0, 3)


def test_animation_constraint_1():
    """Animation constraint to passive parent"""

    _new(1, 120)

    a = cmdx.createNode("transform")
    b = cmdx.createNode("transform", parent=a)

    a["ty"] = 5.0
    b["tx"] = 5.0

    scene = commands.create_scene()
    scene["gravity"] = 0

    commands.create_rigid(a, scene, opts={"passive": True})
    rb = commands.create_rigid(b, scene)

    commands.animation_constraint(rb)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    _step(b, 3)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    a["ty"] = 10.0

    _step(b, 100)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 10.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 10.0, 2)


def test_animation_constraint_2():
    """Animation constraint to dynamic parent"""

    _new(1, 120)

    a = cmdx.createNode("transform")
    b = cmdx.createNode("transform", parent=a)

    a["ty"] = 5.0
    b["tx"] = 5.0

    scene = commands.create_scene()
    scene["gravity"] = 0

    ra = commands.create_rigid(a, scene)
    rb = commands.create_rigid(b, scene)

    commands.animation_constraint(ra)
    commands.animation_constraint(rb)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    _step(b, 3)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    pb = a["tx"].connection(type="pairBlend")
    pb["inTranslateY1"] = {1: 10.0}  # Keyframe it

    _step(b, 100)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 10.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 10.0, 2)


def test_animation_constraint_3():
    """Animation constraint to kinematic parent"""

    _new(1, 120)

    a = cmdx.createNode("transform")
    b = cmdx.createNode("transform", parent=a)

    a["ty"] = 5.0
    b["tx"] = 5.0

    scene = commands.create_scene()
    scene["gravity"] = 0

    rb = commands.create_rigid(b, scene)

    commands.animation_constraint(rb)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    _step(b, 3)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 5.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 5.0, 2)

    a["ty"] = 10.0

    _step(b, 100)

    assert_almost_equals(a.translation(cmdx.sWorld).y, 10.0, 2)
    assert_almost_equals(b.translation(cmdx.sWorld).y, 10.0, 2)


def test_scale_transform():
    _new()

    cube, _ = map(cmdx.encode, cmds.polyCube())
    cube["translateY"] = 2
    cube["scale"] = (0.5, 2, 0.5)

    scene = commands.create_scene()
    rigid = commands.create_rigid(cube, scene)

    # Inferred from polyCube
    assert_equals(rigid["shapeType"].read(), constants.BoxShape)

    # Extents are local to the overall transform, so the physics shape
    # will be elongated along Y, but the internal values will remain 1
    assert_equals(rigid["shapeExtents"].read(), (1, 1, 1))

    _play(rigid, start=1, end=10)

    assert_almost_equals(cube["translateY"].read(), 1.0, 2)


def test_scale_after_authoring():
    _new()

    cube, _ = map(cmdx.encode, cmds.polyCube())
    cube["translateY"] = 2

    scene = commands.create_scene()
    rigid = commands.create_rigid(cube, scene)

    _play(rigid, start=1, end=20)

    assert_almost_equals(cube["translateY"].read(), 0.5, 2)

    # After creating it
    cube["scale"] = (0.5, 2, 0.5)

    _play(rigid, start=1, end=20)

    # Trigger the new size (also happens on auto initial state)
    commands.set_initial_state([rigid])

    _play(rigid, start=1, end=20)
    assert_almost_equals(cube["translateY"].read(), 1.0, 2)


def test_unique_names():
    _new()

    scene = commands.create_scene()

    for i in range(3):
        node = cmdx.create_node("transform")
        rigid = commands.create_rigid(node, scene)
        assert_equals(len(cmds.ls(rigid.name())), 1)

    for i in range(3):
        node = cmdx.create_node("transform")
        rigid = commands.create_rigid(node, scene)
        assert_equals(len(cmds.ls(rigid.name())), 1)


def test_infer_geometry_free():
    _new()
    a, b, c, d = [cmdx.create_node("transform") for i in range(4)]
    [n["displayLocalAxis"].write(True) for n in (a, b, c, d)]

    #   c
    #    o-----o d
    #   /
    #  /
    # o  b
    # |
    # |
    # |
    # o a
    #
    a["t"] = (0, 0, 0)
    b["t"] = (0, 2, 0)
    c["t"] = (1, 3, 0)
    d["t"] = (3, 3, 0)

    # a
    g = commands.infer_geometry(a, parent=None, children=[b])
    assert_true(g.orient.as_euler().is_equivalent(
                cmdx.Euler(0, 0, cmdx.pi / 2)))
    assert_true(g.shape_offset.is_equivalent(
                cmdx.Vector(0, 1, 0)))
    assert_equals(g.length, 2.0)  # 2 - 0
    assert_true(g.shape_rotation.is_equivalent(
                cmdx.Euler(0, 0, cmdx.pi / 2)))  # 90 degrees

    # b
    g = commands.infer_geometry(b, parent=a, children=[c])
    assert_true(g.orient.as_euler().is_equivalent(
                cmdx.Euler(0, 0, cmdx.pi / 4)))  # 45 degrees
    assert_true(g.shape_offset.is_equivalent(
                cmdx.Vector(0.5, 0.5, 0)))
    assert_almost_equals(g.length, 1.4, 1)  # 45 degree triangle
    assert_true(g.shape_rotation.is_equivalent(
                cmdx.Euler(0, 0, cmdx.pi / 4)))  # 45 degrees

    # c
    g = commands.infer_geometry(c, parent=b, children=[d])
    assert_true(g.orient.as_euler().is_equivalent(
                cmdx.Euler(cmdx.pi, 0, 0)))  # 180 degrees
    assert_true(g.shape_offset.is_equivalent(
                cmdx.Vector(1.0, 0, 0)))
    assert_almost_equals(g.length, 2.0, 1)
    assert_true(g.shape_rotation.is_equivalent(
                cmdx.Euler(cmdx.pi, 0, 0)))  # 45 degrees


def test_infer_geometry_single_joint():
    # These are special in that they (a) have no rotate pivot
    # and (b) don't need no length.
    _new()

    joint = cmdx.create_node("joint")
    joint["t"] = (0, 5, 0)
    geo = commands.infer_geometry(joint)

    assert_true(geo.shape_offset.is_equivalent(cmdx.Vector(0, 0, 0)))
    assert_equals(geo.length, 0.0)
    assert_true(geo.shape_rotation.is_equivalent(cmdx.Euler(0, 0, 0)))
    assert_true(geo.orient.as_euler().is_equivalent(cmdx.Euler(0, 0, 0)))


if cmdx.__maya_version__ <= 2020:
    # These aren't happy with Maya 2022

    def test_extract_scene():
        _new()

        scene = commands.create_scene()
        nodes = [cmdx.create_node("transform") for i in range(3)]
        rigids = [commands.create_rigid(nodes[i], scene) for i in range(3)]

        assert_equals(rigids[0]["nextState"].connection(), scene)
        assert_equals(rigids[1]["nextState"].connection(), scene)
        assert_equals(rigids[2]["nextState"].connection(), scene)

        scene2 = commands.extract_from_scene(rigids[0:1])
        scene3 = commands.extract_from_scene(rigids[1:2])

        assert_equals(rigids[0]["nextState"].connection(), scene2)
        assert_equals(rigids[1]["nextState"].connection(), scene3)
        assert_equals(rigids[2]["nextState"].connection(), scene)

    def test_move_scene():
        _new()

        scene1 = commands.create_scene()
        scene2 = commands.create_scene()
        scene3 = commands.create_scene()

        nodes = [cmdx.create_node("transform") for i in range(3)]
        rigids = [commands.create_rigid(nodes[i], scene1) for i in range(3)]

        assert_equals(rigids[0]["nextState"].connection(), scene1)
        assert_equals(rigids[1]["nextState"].connection(), scene1)
        assert_equals(rigids[2]["nextState"].connection(), scene1)

        scene2 = commands.move_to_scene(rigids[0:1], scene2)
        scene3 = commands.move_to_scene(rigids[1:2], scene3)

        assert_equals(rigids[0]["nextState"].connection(), scene2)
        assert_equals(rigids[1]["nextState"].connection(), scene3)
        assert_equals(rigids[2]["nextState"].connection(), scene1)

    def test_combine_scenes():
        _new()

        scene1 = commands.create_scene()
        scene2 = commands.create_scene()

        node1 = cmdx.create_node("transform")
        node2 = cmdx.create_node("transform")
        rigid1 = commands.create_rigid(node1, scene1)
        rigid2 = commands.create_rigid(node2, scene2)

        assert_equals(rigid1["nextState"].connection(), scene1)
        assert_equals(rigid2["nextState"].connection(), scene2)

        commands.combine_scenes([scene1, scene2])

        assert_equals(rigid1["nextState"].connection(), scene1)
        assert_equals(rigid2["nextState"].connection(), scene1)


if cmdx.__maya_version__ >= 2019:
    def test_up_axes():
        """Both Z and Y-up axes behave as you would expect"""

        def new(axis):
            _new()
            cmdx.setUpAxis(axis)
            box, _ = map(cmdx.encode, cmds.polyCube())
            box["translateY"] = 10
            box["translateZ"] = 10

            scene = commands.create_scene()
            rigid = commands.create_rigid(box, scene)
            rigid["shapeType"] = constants.BoxShape
            rigid["shapeExtents"] = (1, 1, 1)
            return rigid

        rigid = new(cmdx.Y)
        _play(rigid, start=1, end=50)
        assert_almost_equals(rigid["outputTranslateY"].read(), 0.5, 2)

        # It may bounce around a little, that's OK
        assert_almost_equals(rigid["outputTranslateZ"].read(), 10.0, 1)

        # Test Z
        rigid = new(cmdx.Z)
        _play(rigid, start=1, end=50)
        assert_almost_equals(rigid["outputTranslateY"].read(), 10.0, 1)
        assert_almost_equals(rigid["outputTranslateZ"].read(), 0.5, 2)


def manual():
    import sys
    import time

    t0 = time.time()

    mod = sys.modules[__name__]
    tests = list(
        func
        for name, func in mod.__dict__.items()
        if name.startswith("test_")
    )

    errors = []
    for test in tests:
        test()

    # Cleanup
    _new()
    t1 = time.time()
    duration = t1 - t0

    if not errors:
        print("Successfully ran %d tests in %.2fs" % (len(tests), duration))
    else:
        print("Ran %d tests with %d errors in %.2fs" % (
            len(tests), len(errors), duration)
        )
