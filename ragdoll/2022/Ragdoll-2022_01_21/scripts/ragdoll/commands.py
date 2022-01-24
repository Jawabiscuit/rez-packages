"""Functionality for scripting

These provide low-level access to node creation and scenegraph
manipulation and are meant for use in automation, pipeline and rigging.

These do not depend on scene selection, user preferences or Maya state.

NOTE: Every function in here MUST be undoable as-one.

"""

import logging

from maya import cmds
from .vendor import cmdx
from . import (
    internal,
    constants,
    nodes,
)

log = logging.getLogger("ragdoll")

# Exceptions thrown in this module
AlreadyAssigned = type("AlreadyAssigned", (RuntimeError,), {})
LockedTransformLimits = type("LockedTransformLimits", (RuntimeError,), {})


def create_solver(name=None, opts=None):
    r"""Create a new rdSolver node
               ____
              /    \
          /  |      |
      ---/----\____/
        /       /
    ---/-------/---
      /       /

    The solver is where the magic happens. Markers are connected to it
    and solved within; populating its .outputMatrix attribute with the
    final result.

    Arguments:
        name (str, optional): Override the default name of this solver
        opts (dict, optional): Configure the solver with these options

    Options:
        frameskipMethod (int): Method to use whenever a frame is skipped,
            can be either api.FrameskipPause or api.FrameskipIgnore

    """

    opts = dict({
        "frameskipMethod": constants.FrameskipPause,
    }, **(opts or {}))

    name = name or "rSolver"
    name = internal.unique_name(name)
    shape_name = internal.shape_name(name)

    with cmdx.DagModifier() as mod:
        solver_parent = mod.create_node("transform", name=name)
        solver = nodes.create("rdSolver", mod,
                              name=shape_name,
                              parent=solver_parent)

        mod.set_attr(solver["frameskipMethod"], opts["frameskipMethod"])

        # Scale isn't relevant for the solver, what would it mean?
        mod.set_keyable(solver_parent["scaleX"], False)
        mod.set_keyable(solver_parent["scaleY"], False)
        mod.set_keyable(solver_parent["scaleZ"], False)
        mod.lock_attr(solver_parent["scaleX"])
        mod.lock_attr(solver_parent["scaleY"])
        mod.lock_attr(solver_parent["scaleZ"])

        _take_ownership(mod, solver, solver_parent)

    return solver


def assign_markers(transforms, solver, opts=None):
    """Assign markers to `transforms` belonging to `solver`

    Each marker transfers the translation and rotation of each transform
    and generates its physical equivalent, ready for recording.

    Options:
        autoLimit (bool): Transfer locked channels into physics limits
        density (enum): Auto-compute mass based on volume and a density,
            such as Flesh or Wood
        materialInChannelBox (bool): Show material attributes in Channel Box
        shapeInChannelBox (bool): Show shape attributes in Channel Box
        limitInChannelBox (bool): Show limit attributes in Channel Box

    """

    assert len(transforms) > 0, "Nothing to assign_markers to"
    assert all(isinstance(t, cmdx.Node) for t in transforms), (
        "%s was not a tuple of cmdx transforms" % str(transforms)
    )

    opts = dict({
        "autoLimit": False,
        "density": constants.DensityFlesh,
        "materialInChannelBox": True,
        "shapeInChannelBox": True,
        "limitInChannelBox": False,
    }, **(opts or {}))

    if len(transforms) == 1:
        other = transforms[0]["message"].output(type="rdMarker")

        if other is not None:
            raise AlreadyAssigned(
                "%s was already assigned a marker" % transforms[0]
            )

    else:
        existing = []
        for t in transforms[1:]:
            other = t["message"].output(type="rdMarker")
            if other is not None:
                existing += [other]

        if existing:
            raise AlreadyAssigned(
                "At least %d transform(s) were already assigned"
                % len(existing)
            )

    parent_marker = transforms[0]["worldMatrix"][0].output(type="rdMarker")

    group = None
    root_transform = transforms[0]

    if len(transforms) > 1:
        if parent_marker:
            group = parent_marker["startState"].output(type="rdGroup")

            # Already got a marker
            transforms.pop(0)

        if not group:
            with cmdx.DagModifier() as mod:
                name = root_transform.name(namespace=False)
                group = _create_group(
                    mod, name="%s_rGroup" % name, solver=solver
                )

    markers = list()
    with cmdx.DGModifier() as dgmod:
        for index, transform in enumerate(transforms):
            name = "rMarker_%s" % transform.name()
            marker = nodes.create("rdMarker", dgmod, name=name)

            try:
                children = [transforms[index + 1]]
            except IndexError:
                children = None

            if parent_marker:
                parent_transform = parent_marker["inputMatrix"].input()
                dgmod.set_attr(marker["recordTranslation"], False)
            else:
                parent_transform = None

            shape = transform.shape(type=("mesh",
                                          "nurbsCurve",
                                          "nurbsSurface"))

            if shape and shape.type() == "mesh":
                dgmod.connect(shape["outMesh"],
                              marker["inputGeometry"])

            if shape and shape.type() in ("nurbsCurve", "nurbsSurface"):
                dgmod.connect(shape["local"],
                              marker["inputGeometry"])

            # It's a limb
            if parent_marker or len(transforms) > 1:
                geo = _infer_geometry(transform,
                                      parent_transform,
                                      children)

                geo.shape_type = constants.CapsuleShape

            # It's a lone object
            else:
                dgmod.set_attr(marker["inputType"], constants.InputOff)

                if shape:
                    geo = _interpret_shape(shape)

                else:
                    geo = _infer_geometry(transform)
                    geo.shape_type = constants.CapsuleShape

            # Make the root passive
            if len(transforms) > 1 and not parent_marker:
                dgmod.set_attr(marker["inputType"], constants.InputKinematic)

            dgmod.set_attr(marker["shapeType"], geo.shape_type)
            dgmod.set_attr(marker["shapeExtents"], geo.extents)
            dgmod.set_attr(marker["shapeLength"], geo.length)
            dgmod.set_attr(marker["shapeRadius"], geo.radius)
            dgmod.set_attr(marker["shapeRotation"], geo.shape_rotation)
            dgmod.set_attr(marker["shapeOffset"], geo.shape_offset)
            dgmod.set_attr(marker["densityType"], opts["density"])

            # Assign some random color, within some nice range
            dgmod.set_attr(marker["color"], internal.random_color())
            dgmod.set_attr(marker["version"], internal.version())

            dgmod.set_attr(marker["originMatrix"],
                           transform["worldMatrix"][0].as_matrix())

            dgmod.connect(transform["worldMatrix"][0], marker["inputMatrix"])
            dgmod.connect(transform["rotatePivot"], marker["rotatePivot"])
            dgmod.connect(transform["rotatePivotTranslate"],
                          marker["rotatePivotTranslate"])

            # Source and destination
            dgmod.connect(transform["message"], marker["src"])
            dgmod.connect(transform["message"], marker["dst"][0])

            # For the offset, we need to store the difference between
            # the source and destination transforms. At the time of
            # creation, these are the same.
            dgmod.set_attr(marker["offsetMatrix"][0], cmdx.Matrix4())

            if transform.type() == "joint":
                draw_scale = geo.length * 0.25
            else:
                draw_scale = sum(geo.extents) / 3.0

            dgmod.set_attr(marker["drawScale"], draw_scale)

            # Currently not implemented
            dgmod.lock_attr(marker["recordToExistingKeys"])
            dgmod.lock_attr(marker["recordToExistingTangents"])

            if group:
                _add_to_group(dgmod, marker, group)

                if parent_marker is not None:
                    dgmod.connect(parent_marker["ragdollId"],
                                  marker["parentMarker"])

                parent_marker = marker

            else:
                _add_to_solver(dgmod, marker, solver)

            # Keep next_available_index() up-to-date
            dgmod.do_it()

            # Used as a basis for angular limits
            reset_constraint_frames(dgmod, marker)

            # No limits on per default
            dgmod.set_attr(marker["limitRange"], (0, 0, 0))

            if opts["autoLimit"]:
                auto_limit(dgmod, marker)

            markers.append(marker)

    toggle_channel_box_attributes(markers, opts={
        "materialAttributes": opts["materialInChannelBox"],
        "shapeAttributes": opts["shapeInChannelBox"],
        "limitAttributes": opts["limitInChannelBox"],
    })

    return markers


def assign_marker(transform, solver, opts=None):
    """Convenience function for passing and recieving a single `transform`"""
    return assign_markers([transform], solver, opts)[0]


def create_lollipop(markers):
    r"""Create a NURBS control for `marker` for convenience

       ____
      \    |
       \___|
       /
      /
     /
    /

    The NURBS control will carry its own Channel Box contents, making
    it easier to spot and manipulate in a complex rig scenario.

    """

    with cmdx.DagModifier() as mod:
        for marker in markers:
            transform = marker["src"].input()
            name = transform.name(namespace=False)

            # R_armBlend2_JNT --> R_armBlend2
            name = name.rsplit("_", 1)[0]

            # R_armBlend2 -> R_armBlend2_MRK
            name = name + "_MRK"

            lol = mod.create_node("transform", name=name, parent=transform)
            mod.set_keyable(lol["translateX"], False)
            mod.set_keyable(lol["translateY"], False)
            mod.set_keyable(lol["translateZ"], False)
            mod.set_keyable(lol["rotateX"], False)
            mod.set_keyable(lol["rotateY"], False)
            mod.set_keyable(lol["rotateZ"], False)
            mod.set_keyable(lol["scaleX"], False)
            mod.set_keyable(lol["scaleY"], False)
            mod.set_keyable(lol["scaleZ"], False)

            mod.set_attr(lol["overrideEnabled"], True)
            mod.set_attr(lol["overrideShading"], False)
            mod.set_attr(lol["overrideColor"], constants.YellowIndex)

            # Find a suitable scale
            scale = list(sorted(marker["shapeExtents"].read()))[1]
            mod.set_attr(lol["scale"], scale * 0.25)

            # Make shape
            mod.do_it()
            curve = cmdx.curve(
                lol, points=(
                    (-0, +0, +0),
                    (-0, +4, +0),
                    (-1, +5, +0),
                    (-0, +6, +0),
                    (+1, +5, +0),
                    (-0, +4, +0),
                ), mod=mod
            )

            # Delete this alongside physics
            _take_ownership(mod, marker, lol)

            # Hide from channelbox
            mod.set_attr(curve["isHistoricallyInteresting"], False)


def auto_limit(mod, marker):
    """Automatically derive physical limits based on locked rotate channels"""

    try:
        dst = marker["dst"][0].input()

    except IndexError:
        # It's possible there is no target
        raise RuntimeError("No destination transform for %s" % marker)

    # Everything is unlocked
    if not any(dst["r" + axis].locked for axis in "xyz"):
        return

    locked = set()

    if dst["rx"].locked:
        mod.set_attr(marker["limitRangeX"], cmdx.radians(-1))
        locked.add("rx")

    if dst["ry"].locked:
        mod.set_attr(marker["limitRangeY"], cmdx.radians(-1))
        locked.add("ry")

    if dst["rz"].locked:
        mod.set_attr(marker["limitRangeZ"], cmdx.radians(-1))
        locked.add("rz")

    # In case of common locked combinations, give the remaining
    # axis a visible limit.
    if locked == {"ry", "rz"}:
        mod.set_attr(marker["limitRangeX"], cmdx.radians(45))

    if locked == {"rx", "rz"}:
        mod.set_attr(marker["limitRangeY"], cmdx.radians(45))

    if locked == {"rx", "ry"}:
        mod.set_attr(marker["limitRangeZ"], cmdx.radians(45))


def cache(solvers):
    """Persistently store the simulated result of the `solvers`

    Use this to scrub the timeline both backwards and forwards without
    resimulating anything.

    """

    # Remember where we came from
    initial_time = cmdx.current_time()

    for solver in solvers:
        start_time = solver["_startTime"].asTime()

        # Clear existing cache
        with cmdx.DagModifier() as mod:
            mod.set_attr(solver["cache"], 0)

        # Special case of caching whilst standing on the start time.
        if initial_time == start_time:
            next_time = start_time + cmdx.om.MTime(1, cmdx.TimeUiUnit())
            # Ensure start frame is visited from a frame other than
            # the start frame, as that's when non-keyed plugs are dirtied
            #
            # |   |   |   |   |   |
            # |===|---------------|
            # <---
            # --->--->--->--->--->
            #
            cmdx.current_time(next_time)
            solver["currentState"].read()

        cmdx.current_time(start_time)
        solver["startState"].read()

        # Prime for updated cache
        with cmdx.DagModifier() as mod:
            mod.set_attr(solver["cache"], 1)

    start_frames = {
        s: int(s["_startTime"].asTime().value)
        for s in solvers
    }

    start_frame = min(start_frames.values())
    end_frame = int(cmdx.max_time().value)
    total = end_frame - start_frame

    for frame in range(start_frame, end_frame + 1):
        time = cmdx.om.MTime(frame, cmdx.TimeUiUnit())
        cmdx.current_time(time)

        for solver in solvers:
            if frame == start_frames[solver]:
                solver["startState"].read()

            elif frame > start_frames[solver]:
                solver["currentState"].read()

        percentage = 100 * float(frame - start_frame) / total
        yield percentage

    # Restore where we came from
    cmdx.current_time(initial_time)


def link_solver(a, b, opts=None):
    """Link solver `a` with `b`

    This will make `a` part of `b`, allowing markers to interact.

    Arguments:
        a (rdSolver): The "child" solver
        b (rdSolver): The "parent" solver

    Returns:
        Nothing

    """

    assert a and a.isA("rdSolver"), "%s was not a solver" % a
    assert b and b.isA("rdSolver"), "%s was not a solver" % b

    with cmdx.DagModifier() as mod:
        index = b["inputStart"].next_available_index()
        mod.connect(a["startState"], b["inputStart"][index])
        mod.connect(a["currentState"], b["inputCurrent"][index])

        # Make it obvious which is main
        mod.try_set_attr(a.parent()["visibility"], False)


def unlink_solver(solver, opts=None):
    """Unlink `solver`

    From any other solver it may be connected to.

    Arguments:
        a (rdSolver): The solver to unlink from any other solver

    Returns:
        Nothing

    """

    assert solver and solver.isA("rdSolver"), "%s was not a solver" % solver
    linked_to = solver["startState"].output(type="rdSolver", plug="inputStart")

    assert linked_to, "%s was not linked" % solver

    with cmdx.DagModifier() as mod:
        mod.disconnect(solver["startState"], linked_to)
        mod.disconnect(solver["currentState"], linked_to)

        mod.try_set_attr(solver.parent()["visibility"], True)


def retarget_marker(marker, transform, opts=None):
    """Retarget `marker` to `transform`

    When recording, write simulation from `marker` onto `transform`,
    regardless of where it is assigned.

    """

    opts = dict({
        "append": False,
    }, **(opts or {}))

    with cmdx.DGModifier() as mod:
        if not opts["append"]:
            for el in marker["dst"]:
                mod.disconnect(el, destination=False)

            for el in marker["offsetMatrix"]:
                mod.set_attr(el, cmdx.Mat4())

            mod.do_it()

        index = marker["dst"].next_available_index()
        src = marker["src"].input()
        dst = marker["dst"][index]

        mod.connect(transform["message"], dst)

        # Should we record translation?
        if all(transform["t%s" % axis].editable for axis in "xyz"):
            mod.try_set_attr(marker["recordTranslation"], True)

        # Should we record translation?
        if all(transform["r%s" % axis].editable for axis in "xyz"):
            mod.try_set_attr(marker["recordRotation"], True)

        # Store offset for recording later
        offset = src["worldMatrix"][0].as_matrix()
        offset *= transform["worldInverseMatrix"][0].as_matrix()
        mod.set_attr(marker["offsetMatrix"][index], offset)


def untarget_marker(marker, opts=None):
    """Remove all recording targets from `marker`"""

    with cmdx.DGModifier() as mod:
        for dst in marker["dst"]:
            other = dst.input(plug=True)
            mod.disconnect(dst, other)


def reparent_marker(child, new_parent, opts=None):
    """Make `new_parent` the new parent of `child`

    Arguments:
        child (rdMarker): The marker whose about to have its parent changed
        new_parent (rdMarker): The new parent of `child`

    """

    with cmdx.DGModifier() as mod:
        mod.connect(new_parent["ragdollId"], child["parentMarker"])


def unparent_marker(child, opts=None):
    """Remove parent from `child`

    Meaning `child` will be a free marker, without a parent.

    """

    old_parent = child["parentMarker"].input(type="rdMarker", plug=True)

    if not old_parent:
        log.warning("%s had no parent to remove" % child)
        return False

    with cmdx.DGModifier() as mod:
        mod.disconnect(child["parentMarker"], old_parent)

    return True


def create_ground(solver, options=None):
    """Create a ground plane, connected to `solver`

    It'll have the size of the viewport grid.

    Arguments:
        solver (rdSolver): Assign ground to this solver

    Returns:
        rdMarker: Newly created marker of the newly created polyPlane

    """

    grid_size = cmds.optionVar(query="gridSize")

    # In headless, or a fresh Maya, there is no grid size
    if not grid_size or grid_size < 0.001:
        grid_size = 10

    plane, gen = map(cmdx.encode, cmds.polyPlane(
        name="rGround",
        width=grid_size * 2,
        height=grid_size * 2,
        subdivisionsHeight=1,
        subdivisionsWidth=1,
        axis=cmdx.up_axis()
    ))

    marker = assign_markers([plane], solver)[0]

    with cmdx.DagModifier() as mod:
        mod.set_attr(marker["inputType"], constants.InputKinematic)
        mod.set_attr(marker["displayType"], constants.DisplayWire)
        mod.set_attr(marker["densityType"], constants.DensityWood)

        mod.set_attr(plane["overrideEnabled"], True)
        mod.set_attr(plane["overrideShading"], False)
        mod.set_attr(plane["overrideColor"], constants.WhiteIndex)

        _take_ownership(mod, marker, plane)
        _take_ownership(mod, marker, gen)

    return marker


@internal.with_undo_chunk
def create_distance_constraint(parent, child, opts=None):
    """Create a new distance constraint between `parent` and `child`"""
    assert parent.isA("rdMarker"), "%s was not a marker" % parent.type()
    assert child.isA("rdMarker"), "%s was not a marker" % child.type()
    assert parent["_scene"] == child["_scene"], (
        "%s and %s not part of the same solver"
    )

    solver = _find_solver(parent)
    assert solver and solver.isA("rdSolver"), (
        "%s was not part of a solver" % parent
    )

    parent_transform = parent["src"].input(type=cmdx.kDagNode)
    child_transform = child["src"].input(type=cmdx.kDagNode)
    parent_name = parent_transform.name(namespace=False)
    child_name = child_transform.name(namespace=False)

    parent_position = cmdx.Point(parent_transform.translation(cmdx.sWorld))
    child_position = cmdx.Point(child_transform.translation(cmdx.sWorld))
    distance = parent_position.distanceTo(child_position)

    name = internal.unique_name("%s_to_%s" % (parent_name, child_name))
    shape_name = internal.shape_name(name)

    with cmdx.DagModifier() as mod:
        transform = mod.create_node("transform", name=name)
        con = nodes.create("rdDistanceConstraint",
                           mod, shape_name, parent=transform)

        mod.set_attr(con["minimum"], distance)
        mod.set_attr(con["maximum"], distance)

        # Inherit the rotate pivot
        mod.set_attr(con["parentOffset"],
                     parent_transform["rotatePivot"].as_vector())
        mod.set_attr(con["childOffset"],
                     child_transform["rotatePivot"].as_vector())

        mod.connect(parent["ragdollId"], con["parentMarker"])
        mod.connect(child["ragdollId"], con["childMarker"])

        _take_ownership(mod, con, transform)
        _add_constraint(mod, con, solver)

    return con


@internal.with_undo_chunk
def create_fixed_constraint(parent, child, opts=None):
    """Create a new fixed constraint between `parent` and `child`"""
    assert parent.isA("rdMarker"), "%s was not a marker" % parent.type()
    assert child.isA("rdMarker"), "%s was not a marker" % child.type()
    assert parent["_scene"] == child["_scene"], (
        "%s and %s not part of the same solver"
    )

    solver = _find_solver(parent)
    assert solver and solver.isA("rdSolver"), (
        "%s was not part of a solver" % parent
    )

    parent_transform = parent["src"].input(type=cmdx.kDagNode)
    child_transform = child["src"].input(type=cmdx.kDagNode)
    parent_name = parent_transform.name(namespace=False)
    child_name = child_transform.name(namespace=False)

    name = internal.unique_name("%s_to_%s" % (parent_name, child_name))
    shape_name = internal.shape_name(name)

    with cmdx.DagModifier() as mod:
        transform = mod.create_node("transform", name=name)
        con = nodes.create("rdFixedConstraint",
                           mod, shape_name, parent=transform)

        mod.connect(parent["ragdollId"], con["parentMarker"])
        mod.connect(child["ragdollId"], con["childMarker"])

        _take_ownership(mod, con, transform)
        _add_constraint(mod, con, solver)

    return con


@internal.with_undo_chunk
def create_pose_constraint(parent, child, opts=None):
    assert parent.isA("rdMarker"), "%s was not a marker" % parent.type()
    assert child.isA("rdMarker"), "%s was not a marker" % child.type()
    assert parent["_scene"] == child["_scene"], (
        "%s and %s not part of the same solver"
    )

    solver = _find_solver(parent)
    assert solver and solver.isA("rdSolver"), (
        "%s was not part of a solver" % parent
    )

    parent_transform = parent["src"].input(type=cmdx.kDagNode)
    child_transform = child["src"].input(type=cmdx.kDagNode)
    parent_name = parent_transform.name(namespace=False)
    child_name = child_transform.name(namespace=False)

    name = internal.unique_name("%s_to_%s" % (parent_name, child_name))
    shape_name = internal.shape_name(name)

    with cmdx.DagModifier() as mod:
        transform = mod.create_node("transform", name=name)
        con = nodes.create("rdPinConstraint",
                           mod, shape_name, parent=transform)

        mod.set_attr(transform["translate"], child_transform.translation())
        mod.set_attr(transform["rotate"], child_transform.rotation())

        # Temporary means of viewport selection
        mod.set_attr(transform["displayHandle"], True)

        mod.connect(parent["ragdollId"], con["parentMarker"])
        mod.connect(child["ragdollId"], con["childMarker"])
        mod.connect(transform["worldMatrix"][0], con["targetMatrix"])

        _take_ownership(mod, con, transform)
        _add_constraint(mod, con, solver)

    return con


@internal.with_undo_chunk
def create_pin_constraint(child, opts=None):
    """Create a new pin constraint for `child`"""
    assert child.isA("rdMarker"), "%s was not a marker" % child.type()

    solver = _find_solver(child)
    assert solver and solver.isA("rdSolver"), (
        "%s was not part of a solver" % child
    )

    source_transform = child["src"].input(type=cmdx.kDagNode)
    source_name = source_transform.name(namespace=False)
    source_tm = source_transform.transform(cmdx.sWorld)

    name = internal.unique_name("%s_rPin" % source_name)
    shape_name = internal.shape_name(name)

    with cmdx.DagModifier() as mod:
        transform = mod.create_node("transform", name=name)
        con = nodes.create("rdPinConstraint",
                           mod, shape_name, parent=transform)

        mod.set_attr(transform["translate"], source_tm.translation())
        mod.set_attr(transform["rotate"], source_tm.rotation())

        # More suitable default values
        mod.set_attr(con["linearStiffness"], 0.01)
        mod.set_attr(con["angularStiffness"], 0.01)

        # Temporary means of viewport selection
        mod.set_attr(transform["displayHandle"], True)

        mod.connect(child["ragdollId"], con["childMarker"])
        mod.connect(transform["worldMatrix"][0], con["targetMatrix"])

        _take_ownership(mod, con, transform)
        _add_constraint(mod, con, solver)

    return con


def reset_constraint_frames(mod, marker, **opts):
    """Reset constraint frames

    Options:
        symmetrical (bool): Keep limits visually consistent when inverted

    """

    opts = dict(opts, **{
        "symmetrical": True,
    })

    assert marker and isinstance(marker, cmdx.Node), (
        "%s was not a cmdx instance" % marker
    )

    if marker.isA("rdMarker"):
        parent = marker["parentMarker"].input(type="rdMarker")
        child = marker

    if parent is not None:
        parent_matrix = parent["inputMatrix"].as_matrix()
    else:
        # It's connected to the world
        parent_matrix = cmdx.Matrix4()

    rotate_pivot = child["rotatePivot"].as_vector()
    child_matrix = child["inputMatrix"].as_matrix()

    child_frame = cmdx.Tm()
    child_frame.translateBy(rotate_pivot)
    child_frame = child_frame.as_matrix()

    # Reuse the shape offset to determine
    # the direction in which each axis is facing.
    main_axis = child["shapeOffset"].as_vector()

    # The offset isn't necessarily only in one axis, it may have
    # small values in each axis. The largest axis is the one that
    # we are most likely interested in.
    main_axis_abs = cmdx.Vector(
        abs(main_axis.x),
        abs(main_axis.y),
        abs(main_axis.z),
    )

    largest_index = list(main_axis_abs).index(max(main_axis_abs))
    largest_axis = cmdx.Vector()
    largest_axis[largest_index] = main_axis[largest_index]

    x_axis = cmdx.Vector(1, 0, 0)
    y_axis = cmdx.Vector(0, 1, 0)

    if any(axis < 0 for axis in largest_axis):
        if largest_axis.x < 0:
            flip = cmdx.Quaternion(cmdx.pi, y_axis)

        elif largest_axis.y < 0:
            flip = cmdx.Quaternion(cmdx.pi, x_axis)

        else:
            flip = cmdx.Quaternion(cmdx.pi, x_axis)

        if opts["symmetrical"] and largest_axis.x < 0:
            flip *= cmdx.Quaternion(cmdx.pi, x_axis)

        if opts["symmetrical"] and largest_axis.y < 0:
            flip *= cmdx.Quaternion(cmdx.pi, y_axis)

        if opts["symmetrical"] and largest_axis.z < 0:
            flip *= cmdx.Quaternion(cmdx.pi, y_axis)

        child_frame = cmdx.Tm(child_frame)
        child_frame.rotateBy(flip)
        child_frame = child_frame.as_matrix()

    # Align parent matrix to wherever the child matrix is
    parent_frame = child_frame * child_matrix * parent_matrix.inverse()

    mod.set_attr(marker["limitRange"], (cmdx.pi / 4, cmdx.pi / 4, cmdx.pi / 4))
    mod.set_attr(marker["parentFrame"], parent_frame)
    mod.set_attr(marker["childFrame"], child_frame)
    mod.set_attr(marker["limitType"], 999)  # Custom


@internal.with_undo_chunk
def edit_constraint_frames(marker, opts=None):
    assert marker and marker.isA("rdMarker"), "%s was not a marker" % marker
    opts = dict({
        "addUserAttributes": False,
    }, **(opts or {}))

    parent_marker = marker["parentMarker"].connection()
    child_marker = marker

    assert parent_marker and child_marker, (
        "Unconnected constraint: %s" % marker
    )

    parent = parent_marker["src"].input(type=cmdx.kDagNode)
    child = child_marker["src"].input(type=cmdx.kDagNode)

    assert parent and child, (
        "Could not find source transform for %s and/or %s" % (
            parent_marker, child_marker)
    )

    with cmdx.DagModifier() as mod:
        parent_frame = mod.create_node("transform",
                                       name="parentFrame",
                                       parent=parent)
        child_frame = mod.create_node("transform",
                                      name="childFrame",
                                      parent=child)

        for frame in (parent_frame, child_frame):
            mod.set_attr(frame["displayHandle"], True)
            mod.set_attr(frame["displayLocalAxis"], True)

        parent_frame_tm = cmdx.Tm(marker["parentFrame"].asMatrix())
        child_frame_tm = cmdx.Tm(marker["childFrame"].asMatrix())

        parent_translate = parent_frame_tm.translation()
        child_translate = child_frame_tm.translation()

        mod.set_attr(parent_frame["translate"], parent_translate)
        mod.set_attr(parent_frame["rotate"], parent_frame_tm.rotation())
        mod.set_attr(child_frame["translate"], child_translate)
        mod.set_attr(child_frame["rotate"], child_frame_tm.rotation())

        mod.connect(parent_frame["matrix"], marker["parentFrame"])
        mod.connect(child_frame["matrix"], marker["childFrame"])

        _take_ownership(mod, marker, parent_frame)
        _take_ownership(mod, marker, child_frame)

    return parent_frame, child_frame


def replace_mesh(marker, mesh, opts=None):
    """Replace the 'Mesh' shape type in `marker` with `mesh`.

    Arguments:
        marker (cmdx.Node): Rigid whose mesh to replace
        mesh (cmdx.Node): Mesh to replace with
        clean (bool, optional): Remove other inputs, such as curve
            or surface node. Multiple inputs are supported, so this
            is optional. Defaults to True.

    Returns:
        Nothing

    """

    assert isinstance(marker, cmdx.Node), "%s was not a cmdx.Node" % marker
    assert isinstance(mesh, cmdx.Node), "%s was not a cmdx.Node" % mesh
    assert marker.isA("rdMarker"), "%s was not a 'rdMarker' node" % marker
    assert mesh.isA(("mesh", "nurbsCurve", "nurbsSurface")), (
        "%s must be either 'mesh', 'nurbsSurface' or 'nurbsSurface'" % mesh
    )

    # Setup default values
    opts = dict({
        "maintainOffset": True,
        "maintainHistory": True,
    }, **(opts or {}))

    # Clone input mesh. We aren't able to simply connect to the
    # transformGeometry and disconnect it, because it appears
    # to flush its data on disconnect. So we need a dedicated
    # mesh for this.
    if not opts["maintainHistory"]:
        with cmdx.DagModifier(interesting=False) as mod:
            copy = mod.create_node(mesh.type(),
                                   name=mesh.name() + "Orig",
                                   parent=mesh.parent())

            if mesh.type() == "mesh":
                a, b = "outMesh", "inMesh"

            elif mesh.type() == "nurbsCurve":
                a, b = "local", "create"

            elif mesh.type() == "nurbsSurface":
                a, b = "local", "create"

            mod.connect(mesh[a], copy[b])
            mod.do_it()
            cmds.refresh(force=True)
            mod.disconnect(copy["inMesh"])
            mod.set_attr(copy["intermediateObject"], True)

            mesh = copy

    with cmdx.DGModifier(interesting=False) as mod:
        if mesh.isA("mesh"):
            mod.connect(mesh["outMesh"], marker["inputGeometry"])

        elif mesh.isA("nurbsCurve"):
            mod.connect(mesh["local"], marker["inputGeometry"])

        elif mesh.isA("nurbsSurface"):
            mod.connect(mesh["local"], marker["inputGeometry"])

        if opts["maintainOffset"]:
            mesh_matrix = mesh["worldMatrix"][0].as_matrix()
            mesh_matrix *= marker["inputMatrix"].as_matrix().inverse()
            mod.set_attr(marker["inputGeometryMatrix"], mesh_matrix)


def toggle_channel_box_attributes(markers, opts=None):
    assert markers, "No markers were passed"

    opts = dict({
        "materialAttributes": True,
        "shapeAttributes": True,
        "limitAttributes": True,
    }, **(opts or {}))

    # Attributes to be toggled
    material_attrs = (
        ".collide",
        ".densityType",
        # ".mass",  # Auto-hidden when density is enabled
        ".friction",
        ".restitution",
        ".displayType",
        ".collisionGroup",
        ".maxDepenetrationVelocity",  # A.k.a. Hardness
    )

    shape_attrs = (
        ".shapeType",
        ".shapeExtentsX",
        ".shapeExtentsY",
        ".shapeExtentsZ",
        ".shapeLength",
        ".shapeRadius",
        ".shapeOffsetX",
        ".shapeOffsetY",
        ".shapeOffsetZ",
        ".shapeRotationX",
        ".shapeRotationY",
        ".shapeRotationZ",
    )

    limit_attrs = (
        ".limitStiffness",
        ".limitDampingRatio",
        ".limitRangeX",
        ".limitRangeY",
        ".limitRangeZ",
    )

    attrs = []

    if opts["materialAttributes"]:
        attrs += material_attrs

    if opts["shapeAttributes"]:
        attrs += shape_attrs

    if opts["limitAttributes"]:
        attrs += limit_attrs

    if not attrs:
        log.warning("Nothing to toggle")
        return False

    # Determine whether to show or hide attributes
    visible = markers[0][attrs[0][1:]].channel_box

    for marker in markers:
        for attr in attrs:
            cmds.setAttr(str(marker) + attr, channelBox=not visible)

    return not visible


@internal.with_timing
@internal.with_undo_chunk
def delete_physics(nodes, dry_run=False):
    """Delete Ragdoll from anything related to `nodes`

    This will delete anything related to Ragdoll from your scenes, including
    any attributes added (polluted) onto your animation controls.

    Arguments:
        nodes (list): Delete physics from these nodes
        dry_run (bool, optional): Do not actually delete anything,
            but still run through the process and throw exceptions
            if any, and still return the results of what *would*
            have been deleted if it wasn't dry.

    """

    assert isinstance(nodes, (list, tuple)), "First input must be a list"

    result = {
        "deletedRagdollNodeCount": 0,
        "deletedOwnedNodeCount": 0,
    }

    # Include shapes in supplied nodes
    shapes = []
    for node in nodes:

        # Don't bother with underworld shapes
        if node.isA(cmdx.kShape):
            continue

        if node.isA(cmdx.kDagNode):
            shapes += node.shapes()

    # Include DG nodes too
    dgnodes = []
    for node in nodes:
        dgnodes += list(
            node["message"].outputs(
                type=("rdGroup",
                      "rdMarker",
                      "rdDistanceConstraint",
                      "rdFixedConstraint")))

    shapes = filter(None, shapes)
    shapes = list(shapes) + nodes
    nodes = shapes + dgnodes

    # Filter by our types
    all_nodetypes = cmds.pluginInfo("ragdoll", query=True, dependNode=True)
    ragdoll_nodes = list(
        node for node in nodes
        if node.type() in all_nodetypes
    )

    # Nothing to do!
    if not ragdoll_nodes:
        return result

    # See whether any of the nodes are referenced, in which
    # case we don't have permission to delete those.
    for node in ragdoll_nodes[:]:
        if node.is_referenced():
            ragdoll_nodes.remove(node)
            raise internal.UserWarning(
                "Cannot Delete Referenced Nodes",
                "I can't do that.\n\n%s is referenced "
                "and **cannot** be deleted." % node.shortest_path()
            )

    # Delete nodes owned by Ragdoll nodes.
    #  _____________________       ___________________
    # |                     |     |                   |
    # | Marker              |     | Transform         |
    # |                     |     |                   |
    # |           owned [0] o<----o message           |
    # |_____________________|     |___________________|
    #
    #
    owned = list()
    for node in ragdoll_nodes:
        if not node.has_attr("owner"):
            continue

        for element in node["owner"]:
            for other in element.connections(source=True, destination=False):
                owned.append(other)

    result["deletedRagdollNodeCount"] = len(ragdoll_nodes)
    result["deletedOwnedNodeCount"] = len(owned)

    # It was just a joke, relax
    if dry_run:
        return result

    # Delete attributes first, as they may otherwise
    # disappear along with their node.
    with cmdx.DagModifier() as mod:
        for node in ragdoll_nodes + owned:
            try:
                mod.delete(node)
                mod.do_it()

            except cmdx.ExistError:
                # Deleting a shape whose parent transform has no other shape
                # automatically deletes the transform. This is shit behavior
                # that can be corrected in Maya 2022 onwards,
                # via includeParents=False
                pass

    return result


def delete_all_physics(dry_run=False):
    """Nuke it from orbit

    Return to simpler days, days before physics, with this one command.

    """

    all_nodetypes = cmds.pluginInfo("ragdoll", query=True, dependNode=True)
    all_nodes = cmdx.ls(type=all_nodetypes)
    return delete_physics(all_nodes, dry_run=dry_run)


"""

Internal helper functions

These things just help readability for the above functions,
and aren't meant for use outside of this module.

"""


def _find_solver(leaf):
    """Return solver for `leaf`

    `leaf` may be a marker or a group, and it will walk the physics
    hierarchy in reverse until it finds the first solver.

    Note that a solver may be connected to another solver, in which case
    this returns the *first* solver found.

    """

    while leaf and not leaf.isA("rdSolver"):
        leaf = leaf["startState"].output(("rdGroup", "rdSolver"))
    return leaf


def _infer_geometry(root, parent=None, children=None, geometry=None):
    """Find length and orientation from `root`

    This function looks at the child and parent of any given root for clues as
    to how to orient it. Length is simply the distance between `root` and its
    first child.

    Arguments:
        root (root): The root from which to derive length and orientation

    """

    geometry = geometry or internal.Geometry()

    # Better this than nothing
    if not children:
        children = []

        # Consider cases where children have no distance from their parent,
        # common in offset groups without an actual offset in them. Such as
        # for organisational purposes
        #
        # | hip_grp
        # .-o offset_grp      <-- Some translation
        #   .-o hip_ctl
        #     .-o hip_loc   <-- Identity matrix
        #
        root_pos = root.translation(cmdx.sWorld)
        for child in root.children(type=root.type()):
            child_pos = child.translation(cmdx.sWorld)

            if not root_pos.is_equivalent(child_pos):
                children += [child]

    # Special case of a tip without children
    #
    # o        How long are you?
    #  \              |
    #   \             v
    #    o------------o
    #
    # In this case, reuse however long the parent is
    if not children and parent:
        children = [root]
        root = parent
        parent = None

    def position_incl_pivot(node, debug=False):
        """Return the final position of the translate and rotate handles

        That includes the rotate pivot, which isn't part
        of the worldspace matrix.

        """

        if node.type() == "joint":
            return node.translation(cmdx.sWorld)

        rotate_pivot = node.transformation().rotatePivot()

        world_tm = node.transform(cmdx.sWorld)
        world_tm.translateBy(rotate_pivot, cmdx.sPreTransform)

        pos = world_tm.translation()

        if debug:
            loc = cmdx.encode(cmds.spaceLocator(name=node.name())[0])
            loc["translate"] = pos

        return pos

    orient = cmdx.Quaternion()
    root_tm = root.transform(cmdx.sWorld)
    root_pos = position_incl_pivot(root)
    root_scale = root_tm.scale()

    # There is a lot we can gather from the childhood
    if children:

        # Support multi-child scenarios
        #
        #         o
        #        /
        #  o----o--o
        #        \
        #         o
        #
        positions = []
        for child in children:
            positions += [position_incl_pivot(child)]

        pos2 = cmdx.Vector()
        for pos in positions:
            pos2 += pos
        pos2 /= len(positions)

        # Find center joint if multiple children
        #
        # o o o  <-- Which is in the middle?
        #  \|/
        #   o
        #   |
        #
        distances = []
        for pos in positions + [root_pos]:
            distances += [(pos - pos2).length()]
        center_index = distances.index(min(distances))
        center_node = (children + [root])[center_index]

        # Roots typically get this, where e.g.
        #
        #      o
        #      |
        #      o  <-- Root
        #     / \
        #    o   o
        #
        if center_node != root:
            parent = parent or root.parent(type=root.type())

            if not parent:
                # Try using grand-child instead
                parent = center_node.child(type=root.type())

            if parent:
                up = position_incl_pivot(parent)
                up = (up - root_pos).normal()
            else:
                up = cmdx.up_axis()

            aim = (pos2 - root_pos).normal()
            cross = aim ^ up  # Make axes perpendicular
            up = cross ^ aim

            orient *= cmdx.Quaternion(cmdx.Vector(0, 1, 0), up)
            orient *= cmdx.Quaternion(orient * cmdx.Vector(1, 0, 0), aim)

            center_node_pos = position_incl_pivot(center_node)
            length = (center_node_pos - root_pos).length()

            geometry.orient = orient
            geometry.length = length

    if geometry.length > 0.0:

        if geometry.radius:
            # Pre-populated somewhere above
            radius = geometry.radius

        # Joints for example ship with this attribute built-in, very convenient
        elif "radius" in root:
            joint_scale = cmds.jointDisplayScale(query=True)
            radius = root["radius"].read() * joint_scale

        # If we don't have that, try and establish one from the bounding box
        else:
            shape = root.shape(type=("mesh", "nurbsCurve", "nurbsSurface"))

            if shape:
                bbox = shape.bounding_box
                bbox = cmdx.Vector(bbox.width, bbox.height, bbox.depth)

                radius = sorted([bbox.x, bbox.y, bbox.z])

                # A bounding box will be either flat or long
                # That means 2/3 axes will be similar, and one
                # either 0 or large.
                #  ___________________
                # /__________________/|
                # |__________________|/
                #
                radius = radius[1]  # Pick middle one
                radius *= 0.5  # Width to radius
                radius *= 0.5  # Controls are typically larger than the model

            else:
                # If there's no visible geometry what so ever, we have
                # very little to go on in terms of establishing a radius.
                radius = geometry.length * 0.1

        size = cmdx.Vector(geometry.length, radius, radius)
        offset = orient * cmdx.Vector(geometry.length / 2.0, 0, 0)

        geometry.extents = cmdx.Vector(geometry.length, radius * 2, radius * 2)
        geometry.radius = radius

    else:
        size, center = _hierarchy_bounding_size(root)
        tm = cmdx.Tm(root_tm)

        if all(axis == 0 for axis in size):
            geometry.length = 0
            geometry.radius = 1
            geometry.extents = cmdx.Vector(1, 1, 1)

        else:
            geometry.length = size.x
            geometry.radius = min([size.y, size.z])
            geometry.extents = size

            # Embed length
            tm.translateBy(cmdx.Vector(0, size.x * -0.5, 0))

        offset = center - tm.translation()

    # Compute final shape matrix with these ingredients
    shape_tm = cmdx.Tm(translate=root_pos,
                       rotate=geometry.orient)
    shape_tm.translateBy(offset, cmdx.sPostTransform)
    shape_tm = cmdx.Tm(shape_tm.asMatrix() * root_tm.asMatrix().inverse())

    geometry.shape_offset = shape_tm.translation()
    geometry.shape_rotation = shape_tm.rotation()

    # Take root_scale into account
    if abs(root_scale.x) <= 0:
        geometry.radius = 0
        geometry.extents.x = 0

    if abs(root_scale.y) > 0:
        geometry.extents.x /= root_scale.x
        geometry.length /= root_scale.y
    else:
        geometry.length = 0
        geometry.extents.y = 0

    if abs(root_scale.z) <= 0:
        geometry.extents.z = 0

    # Keep radius at minimum 10% of its length to avoid stick-figures
    geometry.radius = max(geometry.length * 0.1, geometry.radius)

    return geometry


def _add_constraint(mod, con, solver):
    assert con["startState"].output() != solver, (
        "%s already a member of %s" % (con, solver)
    )

    index = solver["inputStart"].next_available_index()

    mod.set_attr(con["version"], internal.version())
    mod.connect(con["startState"], solver["inputStart"][index])
    mod.connect(con["currentState"], solver["inputCurrent"][index])

    # Ensure `next_available_index` is up-to-date
    mod.do_it()


def _take_ownership(mod, rdnode, node):
    """Make `rdnode` the owner of `node`"""

    try:
        plug = rdnode["owner"]
    except cmdx.ExistError:
        try:
            plug = rdnode["exclusiveNodes"]
        except cmdx.ExistError:
            raise TypeError("%s not a Ragdoll node" % rdnode)

    # Is the node already owned?
    existing_connection = node["message"].output(plug=True)
    if existing_connection and existing_connection.name() == "owner":
        print("%s / %s" % (rdnode, node))
        mod.disconnect(node["message"], existing_connection)

    # Ensure next_available_index is up-to-date
    mod.do_it()

    index = plug.next_available_index()
    mod.connect(node["message"], plug[index])


def _create_group(mod, name, solver):
    name = internal.unique_name(name)
    shape_name = internal.shape_name(name)
    group_parent = mod.create_node("transform", name=name)
    group = nodes.create("rdGroup", mod,
                         name=shape_name,
                         parent=group_parent)

    index = solver["inputStart"].next_available_index()
    mod.connect(group["startState"], solver["inputStart"][index])
    mod.connect(group["currentState"],
                solver["inputCurrent"][index])

    if constants.RAGDOLL_DEVELOPER:
        mod.set_keyable(group["articulated"], True)
        mod.set_keyable(group["articulationType"], True)

    _take_ownership(mod, group, group_parent)

    return group


def _remove_membership(mod, marker):
    existing = marker["ragdollId"].outputs(
        type=("rdGroup", "rdSolver"),
        plugs=True
    )

    for other in existing:
        mod.disconnect(marker["ragdollId"], other)

    mod.do_it()


def _add_to_group(mod, marker, group):
    _remove_membership(mod, marker)

    index = group["inputStart"].next_available_index()
    mod.connect(marker["startState"], group["inputStart"][index])
    mod.connect(marker["currentState"], group["inputCurrent"][index])
    return True


def _add_to_solver(mod, marker, solver):
    _remove_membership(mod, marker)

    index = solver["inputStart"].next_available_index()
    mod.connect(marker["startState"], solver["inputStart"][index])
    mod.connect(marker["currentState"], solver["inputCurrent"][index])
    return True


def _shapeattributes_from_generator(mod, shape, rigid):
    """Look at `shape` history for a e.g. polyCube or polySphere

    This function interprets a simple shape, like a box, as a box
    rather than treat it like an arbitrary convex hull. That enables
    us to leverage the simpler shape types for improved
    performance, editability and visibility.

    """

    gen = None

    if "inMesh" in shape and shape["inMesh"].connected:
        gen = shape["inMesh"].connection()

    elif "create" in shape and shape["create"].connected:
        gen = shape["create"].connection()

    else:
        return

    if gen.type() == "polyCube":
        mod.set_attr(rigid["shapeType"], constants.BoxShape)
        mod.set_attr(rigid["shapeExtentsX"], gen["width"])
        mod.set_attr(rigid["shapeExtentsY"], gen["height"])
        mod.set_attr(rigid["shapeExtentsZ"], gen["depth"])

    elif gen.type() == "polySphere":
        mod.set_attr(rigid["shapeType"], constants.SphereShape)
        mod.set_attr(rigid["shapeRadius"], gen["radius"])

    elif gen.type() == "polyCylinder" and gen["roundCap"]:
        mod.set_attr(rigid["shapeType"], constants.CylinderShape)
        mod.set_attr(rigid["shapeRadius"], gen["radius"])
        mod.set_attr(rigid["shapeLength"], gen["height"])

        # Align with Maya's cylinder/capsule axis
        # TODO: This doesn't account for partial values, like 0.5, 0.1, 1.0
        mod.set_attr(rigid["shapeRotation"], list(map(cmdx.radians, (
            (0, 0, 90) if gen["axisY"] else
            (0, 90, 0) if gen["axisZ"] else
            (0, 0, 0)
        ))))

    elif gen.type() == "makeNurbCircle":
        mod.set_attr(rigid["shapeRadius"], gen["radius"])

    elif gen.type() == "makeNurbSphere":
        mod.set_attr(rigid["shapeType"], constants.SphereShape)
        mod.set_attr(rigid["shapeRadius"], gen["radius"])

    elif gen.type() == "makeNurbCone":
        mod.set_attr(rigid["shapeRadius"], gen["radius"])
        mod.set_attr(rigid["shapeLength"], gen["heightRatio"])

    elif gen.type() == "makeNurbCylinder":
        mod.set_attr(rigid["shapeType"], constants.CylinderShape)
        mod.set_attr(rigid["shapeRadius"], gen["radius"])
        mod.set_attr(rigid["shapeLength"], gen["heightRatio"])
        mod.set_attr(rigid["shapeRotation"], list(map(cmdx.radians, (
            (0, 0, 90) if gen["axisY"] else
            (0, 90, 0) if gen["axisZ"] else
            (0, 0, 0)
        ))))


def _interpret_shape(mod, rigid, shape):
    """Translate `shape` into rigid shape attributes

    For example, if the shape is a `mesh`, we'll plug that in as
    a mesh for convex hull generation.

    """

    assert isinstance(rigid, cmdx.DagNode), "%s was not a cmdx.DagNode" % rigid
    assert isinstance(shape, cmdx.DagNode), "%s was not a cmdx.DagNode" % shape
    assert shape.isA(cmdx.kShape), "%s was not a shape" % shape
    assert rigid.type() == "rdRigid", "%s was not a rdRigid" % rigid

    bbox = shape.bounding_box
    extents = cmdx.Vector(bbox.width, bbox.height, bbox.depth)
    center = cmdx.Vector(bbox.center)

    # Account for flat shapes, like a circle
    radius = extents.x
    length = max(extents.y, extents.x)

    # Account for X not necessarily being
    # represented by the width of the bounding box.
    if radius < internal.tolerance:
        radius = length * 0.5

    mod.set_attr(rigid["shapeOffset"], center)
    mod.set_attr(rigid["shapeExtents"], extents)
    mod.set_attr(rigid["shapeRadius"], radius * 0.5)
    mod.set_attr(rigid["shapeLength"], length)

    if shape.type() == "mesh":
        mod.connect(shape["outMesh"], rigid["inputMesh"])
        mod.set_attr(rigid["shapeType"], constants.MeshShape)

    elif shape.type() == "nurbsCurve":
        mod.connect(shape["local"], rigid["inputCurve"])
        mod.set_attr(rigid["shapeType"], constants.MeshShape)

    elif shape.type() == "nurbsSurface":
        mod.connect(shape["local"], rigid["inputSurface"])
        mod.set_attr(rigid["shapeType"], constants.MeshShape)

    # In case the shape is connected to a common
    # generator, like polyCube or polyCylinder
    _shapeattributes_from_generator(mod, shape, rigid)


def _interpret_transform(mod, rigid, transform):
    """Translate `transform` into rigid shape attributes

    Primarily joints, that have a radius and length.

    """

    if transform.isA(cmdx.kJoint):
        mod.set_attr(rigid["shapeType"], constants.CapsuleShape)

        # Orient inner shape to wherever the joint is pointing
        # as opposed to whatever its jointOrient is facing
        geometry = _infer_geometry(transform)

        mod.set_attr(rigid["shapeOffset"], geometry.shape_offset)
        mod.set_attr(rigid["shapeRotation"], geometry.shape_rotation)
        mod.set_attr(rigid["shapeLength"], geometry.length)
        mod.set_attr(rigid["shapeRadius"], geometry.radius)
        mod.set_attr(rigid["shapeExtents"], geometry.extents)


def _interpret_shape(shape):
    """Translate `shape` into rigid shape attributes

    For example, if the shape is a `mesh`, we'll plug that in as
    a mesh for convex hull generation.

    """

    assert isinstance(shape, cmdx.DagNode), "%s was not a cmdx.DagNode" % shape
    assert shape.isA(cmdx.kShape), "%s was not a shape" % shape

    bbox = shape.bounding_box
    extents = cmdx.Vector(bbox.width, bbox.height, bbox.depth)
    center = cmdx.Vector(bbox.center)

    # Account for flat shapes, like a circle
    radius = extents.x
    length = max(extents.y, extents.x)

    # Account for X not necessarily being
    # represented by the width of the bounding box.
    if radius < internal.tolerance:
        radius = length * 0.5

    geo = internal.Geometry()
    geo.shape_offset = center
    geo.extents = extents
    geo.radius = radius * 0.5
    geo.length = length

    gen = None

    # Guilty until proven innocent
    geo.shape_type = constants.MeshShape

    if "inMesh" in shape and shape["inMesh"].connected:
        gen = shape["inMesh"].connection()

    elif "create" in shape and shape["create"].connected:
        gen = shape["create"].connection()

    if gen:
        # In case the shape is connected to a common
        # generator, like polyCube or polyCylinder

        if gen.type() == "polyCube":
            geo.shape_type = constants.BoxShape
            geo.extents.x = gen["width"].read()
            geo.extents.y = gen["height"].read()
            geo.extents.z = gen["depth"].read()

        elif gen.type() == "polySphere":
            geo.shape_type = constants.SphereShape
            geo.radius = gen["radius"].read()

        elif gen.type() == "polyPlane":
            geo.shape_type = constants.BoxShape
            geo.extents.x = gen["width"].read()
            geo.extents.z = gen["height"].read()

            # Align top of box with plane
            if gen["axisY"]:
                average_size = (geo.extents.x + geo.extents.y) / 2.0
                geo.extents.y = average_size / 40.0
                geo.shape_offset.y = -geo.extents.y / 2.0
            else:
                average_size = (geo.extents.x + geo.extents.y) / 2.0
                geo.extents.z = average_size / 40.0
                geo.shape_offset.z = -geo.extents.z / 2.0

        elif gen.type() == "polyCylinder" and gen["roundCap"]:
            geo.shape_type = constants.CylinderShape
            geo.radius = gen["radius"].read()
            geo.length = gen["height"].read()

            # Align with Maya's cylinder/capsule axis
            # TODO: This doesn't account for partial values, like 0.5, 0.1, 1.0
            geo.shape_rotation = list(map(cmdx.radians, (
                (0, 0, 90) if gen["axisY"] else
                (0, 90, 0) if gen["axisZ"] else
                (0, 0, 0)
            )))

        elif gen.type() == "makeNurbCircle":
            geo.radius = gen["radius"]

        elif gen.type() == "makeNurbSphere":
            geo.shape_type = constants.SphereShape
            geo.radius = gen["radius"]

        elif gen.type() == "makeNurbCone":
            geo.radius = gen["radius"]
            geo.length = gen["heightRatio"]

        elif gen.type() == "makeNurbCylinder":
            geo.shape_type = constants.CylinderShape
            geo.radius = gen["radius"]
            geo.length = gen["heightRatio"]
            geo.shape_rotation = list(map(cmdx.radians, (
                (0, 0, 90) if gen["axisY"] else
                (0, 90, 0) if gen["axisZ"] else
                (0, 0, 0)
            )))

    return geo


def _hierarchy_bounding_size(root):
    """Bounding size taking immediate children into account

            _________
         o |    a    |
    ---o-|-o----o----o--
         | |_________|
         |      |
        o-o    bbox of a
        | |
        | |
        o o
        | |
        | |
       -o o-

    DagNode.boundingBox on the other hand takes an entire
    hierarchy into account.

    """

    pos1 = root.translation(cmdx.sWorld)
    positions = [pos1]

    # Start by figuring out a center point
    for child in root.children(type=root.type()):
        positions += [child.translation(cmdx.sWorld)]

    # There were no children, consider the parent instead
    if len(positions) < 2:

        # It's possible the immediate parent is an empty
        # group without translation. We can't use that, so
        # instead walk the hierarchy until you find the first
        # parent with some usable translation to it.
        for parent in root.lineage():
            pos2 = parent.translation(cmdx.sWorld)

            if pos2.is_equivalent(pos1, internal.tolerance):
                continue

            # The parent will be facing in the opposite direction
            # of what we want, so let's invert that.
            pos2 -= pos1
            pos2 *= -1
            pos2 += pos1

            positions += [pos2]

            break

    # There were neither parent nor children,
    # we don't have a lot of options here.
    if len(positions) < 2:
        return (
            # No size
            cmdx.Vector(0, 0, 0),

            # Original center
            pos1
        )

    center = cmdx.Vector()
    for pos in positions:
        center += pos
    center /= len(positions)

    # Then figure out a bounding box, relative this center
    min_ = cmdx.Vector()
    max_ = cmdx.Vector()

    for pos2 in positions:
        dist = pos2 - center

        min_.x = min(min_.x, dist.x)
        min_.y = min(min_.y, dist.y)
        min_.z = min(min_.z, dist.z)

        max_.x = max(max_.x, dist.x)
        max_.y = max(max_.y, dist.y)
        max_.z = max(max_.z, dist.z)

    size = cmdx.Vector(
        max_.x - min_.x,
        max_.y - min_.y,
        max_.z - min_.z,
    )

    # Keep smallest value within some sensible range
    minimum = list(size).index(min(size))
    size[minimum] = max(size) * 0.5

    return size, center
