from maya import cmds
from ..legacy import interactive, commands
from ..vendor import cmdx
from .. import constants as c
from . import _new, _play

from nose.tools import (
    assert_equals,
    assert_true,
    assert_almost_equals,
)

# A simple arm
#
# o     o----o
#  \   /
#   \ /
#    o
#
JOINT_3CHAIN = (
    # translation
    [
        [-6.21, 9.98, 0.08],
        [7.62, 0.0, 0.00],
        [7.21, 0.0, 0.00],
        [3.80, 0.0, 0.00]
    ],
    # orientation
    [
        [1.57, -0.0, -0.66],
        [0.0, 1.33, 0.0],
        [0.0, -0.58, 0.0],
        [0.0, -0.09, 0.0]
    ],
)

CONTROL_3CHAIN = (
    # translation
    [
        [-6.21, 9.98, 0.08],
        [7.62, 0.0, 0.00],
        [7.21, 0.0, 0.00],
        [3.80, 0.0, 0.00]
    ],
    # orientation
    [
        [1.57, -0.0, -0.66],
        [0.0, 1.33, 0.0],
        [0.0, -0.58, 0.0],
        [0.0, -0.09, 0.0]
    ],
)


def setup():
    pass


def create_joint_arm():
    joints = []

    parent = None

    for translate, orient in zip(*JOINT_3CHAIN):
        joint = cmdx.create_node("joint", parent=parent)
        joint["translate"] = translate
        joint["jointOrient"] = orient

        parent = joint

        joints += [joint]

    return joints


def create_arm_rig():
    ctrls = []

    parent = None

    for translate, orient in zip(*JOINT_3CHAIN):
        ctrl, _ = cmds.circle()
        ctrl = cmdx.encode(ctrl)
        ctrl["translate"] = translate
        ctrl["rotate"] = orient

        if parent:
            parent.add_child(ctrl)

        parent = ctrl

        ctrls += [ctrl]

    return ctrls


def test_create_rigid():
    _new()

    cube, _ = cmds.polyCube()
    cmds.select(cube)
    assert_true(interactive.create_active_rigid())

    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdScene")), 1)


def test_compute_mass():
    _new()

    cube, _ = cmds.polyCube(width=1, height=1, depth=1)
    cmds.select(cube)

    opts = {"computeMass2": c.WaterDensity}
    assert_true(interactive.create_active_rigid(**opts))
    rigid = cmdx.ls(type="rdRigid")[0]
    assert_almost_equals(rigid["mass"].read(), 0.01, 3)


def test_create_rigid_initial_shape():
    _new()
    cube, _ = cmds.polyCube()
    cmds.select(cube)

    def assert_shape_type(shapetype):
        rigid = cmdx.ls(type="rdRigid")[0]
        assert_equals(rigid["shapeType"].read(), shapetype)

        _new()
        cube, _ = cmds.polyCube()
        cmds.select(cube)

    # Default shape type
    assert_true(interactive.create_active_rigid())
    assert_shape_type(c.BoxShape)  # Since it's a polyCube

    opts = {"initialShape": c.InitialShapeBox}
    assert_true(interactive.create_active_rigid(**opts))
    assert_shape_type(c.BoxShape)

    opts = {"initialShape": c.InitialShapeSphere}
    assert_true(interactive.create_active_rigid(**opts))
    assert_shape_type(c.SphereShape)

    opts = {"initialShape": c.InitialShapeCapsule}
    assert_true(interactive.create_active_rigid(**opts))
    assert_shape_type(c.CapsuleShape)

    opts = {"initialShape": c.InitialShapeMesh}
    assert_true(interactive.create_active_rigid(**opts))
    assert_shape_type(c.MeshShape)


def test_undo1():
    _new()

    cube, _ = cmds.polyCube()
    cmds.select(cube)
    assert_true(interactive.create_active_rigid())

    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdScene")), 1)

    cmds.undo()

    assert_equals(len(cmds.ls(type="rdRigid")), 0)
    assert_equals(len(cmds.ls(type="rdScene")), 0)


def test_create_muscle():
    _new()

    arm = create_joint_arm()
    a = cmdx.create_node("joint", parent=arm[0])
    b = cmdx.create_node("joint", parent=arm[1])

    a["translateY"] = 2
    b["translateY"] = 2

    cmds.select(str(a), str(b))
    assert_true(interactive.create_muscle())

    # Two colliders, one muscle
    assert_equals(len(cmds.ls(type="rdRigid")), 3)
    assert_equals(len(cmds.ls(type="rdScene")), 1)

    # One per anchor
    assert_equals(len(cmds.ls(type="rdConstraint")), 2)


def test_create_passive():
    _new()

    # Nothing needs to be selected
    assert_true(interactive.create_passive_rigid())

    # Two colliders, one muscle
    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdScene")), 1)

    # Channels are unlocked/unconnected
    rigid = cmdx.ls(type="rdRigid")[0]
    tm = rigid.parent()

    assert_true(tm["translateX"].editable)
    assert_true(tm["rotateX"].editable)


def test_create_constraint():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    sphere1, _ = map(cmdx.encode, cmds.polySphere())

    cube1["translate"] = (1, 2, 0)
    sphere1["translate"] = (1, 4, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    commands.create_rigid(cube1, scene)
    commands.create_rigid(sphere1, scene)

    cmds.select(str(cube1), str(sphere1))
    opts = {"constraintSelect": False}
    assert_true(interactive.create_point_constraint(**opts))
    assert_true(interactive.create_orient_constraint(**opts))
    assert_true(interactive.create_parent_constraint(**opts))
    assert_true(interactive.create_hinge_constraint(**opts))
    assert_true(interactive.create_socket_constraint(**opts))

    assert_equals(len(cmds.ls(type="rdRigid")), 2)
    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdConstraint")), 5)


def test_convert_active_rigid():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())

    cube1["translate"] = (1, 2, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    rigid = commands.create_rigid(cube1, scene)

    cmds.select(str(cube1))
    opts = {"convertRigidType": c.ConvertPassive}
    assert_true(interactive.convert_rigid(**opts))
    assert_equals(rigid["kinematic"].read(), True)

    cmds.select(str(cube1))
    opts = {"convertRigidType": c.ConvertActive}
    assert_true(interactive.convert_rigid(**opts))
    assert_equals(rigid["kinematic"].read(), False)


def test_convert_constraint():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    sphere1, _ = map(cmdx.encode, cmds.polySphere())

    cube1["translate"] = (1, 2, 0)
    sphere1["translate"] = (1, 4, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    a = commands.create_rigid(cube1, scene)
    b = commands.create_rigid(sphere1, scene)
    con = commands.point_constraint(a, b)

    cmds.select(str(con))
    opts = {"constraintType": c.PointConstraint}
    assert_true(interactive.convert_constraint(**opts))


def test_transfer_attributes():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    sphere1, _ = map(cmdx.encode, cmds.polySphere())

    cube1["translate"] = (1, 2, 0)
    sphere1["translate"] = (1, 4, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    a = commands.create_rigid(cube1, scene)
    b = commands.create_rigid(sphere1, scene)

    # Transfer this
    a["shapeRadius"] = 5.6

    assert_equals(b["shapeRadius"].read(), 1.0)

    cmds.select(str(a), str(b))
    assert_true(interactive.transfer_selected())
    assert_almost_equals(b["shapeRadius"].read(), 5.6, 3)


def test_create_hard_pin():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["translate"] = (1, 2, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    commands.create_rigid(cube1, scene)

    cmds.select(str(cube1))
    assert_true(interactive.create_hard_pin())

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdConstraint")), 0)  # No constraint here
    assert_equals(len(cmds.ls(type="rdControl")), 1)


def test_create_soft_pin():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["translate"] = (1, 2, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    commands.create_rigid(cube1, scene)

    cmds.select(str(cube1))
    assert_true(interactive.create_soft_pin())

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdConstraint")), 1)
    assert_equals(len(cmds.ls(type="rdControl")), 1)


def test_create_force():
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["translate"] = (1, 2, 0)

    # Use commands, in case the interactive function is failing
    scene = commands.create_scene()
    commands.create_rigid(cube1, scene)

    cmds.select(deselect=True)
    assert_true(interactive.create_push_force())
    cmds.select(deselect=True)
    assert_true(interactive.create_pull_force())
    cmds.select(deselect=True)
    assert_true(interactive.create_uniform_force())
    cmds.select(deselect=True)
    assert_true(interactive.create_turbulence_force())
    cmds.select(deselect=True)

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 1)
    assert_equals(len(cmds.ls(type="rdConstraint")), 0)
    assert_equals(len(cmds.ls(type="rdForce")), 4)


def test_create_character():
    _new()

    hierarchy = create_joint_arm()
    root = hierarchy[0]

    cmds.select(root.path())
    assert_true(interactive.create_character())

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 3)

    # Two sockets
    assert_equals(len(cmds.ls(type="rdConstraint")), 2)


def test_active_chain(**opts):
    _new()

    hierarchy = create_joint_arm()
    a, b, c = map(str, hierarchy[:3])
    cmds.select(a, b, c)
    assert_true(interactive.create_active_chain(selection=None, **opts))

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 3)

    # Two local constraints
    assert_equals(len(cmds.ls(type="rdConstraint")), 2)


def test_chain(**opts):
    _new()

    hierarchy = create_joint_arm()
    a, b, c = map(str, hierarchy[:3])
    cmds.select(a, b, c)
    assert_true(interactive.create_active_chain(**opts))

    assert_equals(len(cmds.ls(type="rdScene")), 1)
    assert_equals(len(cmds.ls(type="rdRigid")), 3)

    # Two local constraints
    assert_equals(len(cmds.ls(type="rdConstraint")), 2)


def test_active_chain_opt1_mesh():
    test_active_chain(dynamicControlShapeType=c.CapsuleShape)
    test_active_chain(dynamicControlShapeType=c.MeshShape)


def test_active_chain_opt2_auto_blend():
    test_active_chain(dynamicControlAutoBlend=False)
    test_active_chain(dynamicControlAutoBlend=True)


def test_active_chain_opt4_auto_multiplier_off():
    test_active_chain(dynamicControlAutoMultiplier=False)
    test_active_chain(dynamicControlAutoMultiplier=True)


def test_chain_opt1_mesh():
    test_chain(chainShapeType=c.MeshShape)


def test_chain_opt2_draw_shaded():
    test_chain(chainDrawShaded=False)
    test_chain(chainDrawShaded=True)


def test_chain_opt3_blend_method():
    test_chain(chainBlendMethod=c.SteppedBlendMethod)
    test_chain(chainBlendMethod=c.SmoothBlendMethod)


def test_chain_opt4_auto_multiplier_off():
    test_chain(chainAutoMultiplier=False)
    test_chain(chainAutoMultiplier=True)


def test_chain_opt5_auto_limits():
    test_chain(chainAutoLimits=False)
    test_chain(chainAutoLimits=True)


def test_active_chain_with_delete_all():
    test_active_chain()
    interactive.delete_physics()
    test_active_chain()


def test_animated_rigid():
    """Animated transforms get an animation constraint"""
    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["translate"] = (1, 2, 0)

    interactive.create_active_rigid()

    # Not animated? No constraint
    assert_equals(len(cmds.ls(type="rdConstraint")), 0)

    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["translateY"] = {1: 0, 5: 10, 10: 0}  # Animation

    interactive.create_active_rigid()

    # Animated? Yes please
    assert_equals(len(cmds.ls(type="rdConstraint")), 1)

    # Only translation was keyed
    con = cmdx.ls(type="rdConstraint")[0]
    assert con["linearDriveStiffness"].read() > 0
    assert con["angularDriveStiffness"].read() == 0

    _new()

    cube1, _ = map(cmdx.encode, cmds.polyCube())
    cube1["rotateY"] = {1: 0, 5: 10, 10: 0}  # Animation

    interactive.create_active_rigid()

    # Animated? Yes please
    assert_equals(len(cmds.ls(type="rdConstraint")), 1)

    # Only rotation was keyed
    con = cmdx.ls(type="rdConstraint")[0]
    assert con["angularDriveStiffness"].read() > 0
    assert con["linearDriveStiffness"].read() == 0


def test_save():
    test_active_chain()
    # _save()
    # _load()

    rigid = cmdx.ls(type="rdRigid")[0]
    transform = rigid.parent()

    assert_true(transform["translateY"] != 0)

    _play(rigid)


def test_normalise_shapes():
    _new()

    hierarchy = create_joint_arm()
    cmds.select(hierarchy[0].path())
    interactive.normalise_shapes()


def test_select_shapes():
    """Commands properly finds corresponding transform of selected shape"""

    _new()

    upperarm, lowerarm, hand, tip = create_arm_rig()
    cmds.select(upperarm.shape().path(),
                lowerarm.shape().path(),
                hand.shape().path())
    assert_true(interactive.create_active_chain())

    _play(upperarm)


def test_select_transforms():
    """Commands properly find optional shapes under selected transforms"""
    assert True


def test_select_transforms_and_shapes():
    """Commands properly separate between transforms and shapes"""
    assert True


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
