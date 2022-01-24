import os
import copy
import json
import logging
import traceback
import functools
import contextlib

from maya import cmds, mel
from ..vendor import cmdx, qargparse
from . import (
    commands,
    ui,
    dump,
    tools,
)

from .. import (
    options,
    constants as c,
    internal as i__,
    __,
)

log = logging.getLogger("ragdoll")

Warning = ValueError
DoNothing = None
Cancelled = False

kSuccess = True
kFailure = False

MessageBox = ui.MessageBox


def _print_exception():
    log.debug(traceback.format_exc())


def _resource(*fname):
    dirname = os.path.dirname(__file__)
    resdir = os.path.join(dirname, "resources")
    return os.path.normpath(os.path.join(resdir, *fname))


def _is_standalone():
    """Is Maya running without a GUI?"""
    return not hasattr(cmds, "about") or cmds.about(batch=True)


def _is_interactive():
    """Is Maya running with a GUI?"""
    return not _is_standalone()


if _is_standalone():
    def MessageBox(*args, **kwargs):
        return kSuccess


def requires_ui(func):
    """Wrapper for functions that rely on being displayed

    Mostly for CI. These are simply ignored.

    """

    @functools.wraps(func)
    def requires_ui_wrapper(*args, **kwargs):
        if _is_standalone():
            return kSuccess
        return func(*args, **kwargs)
    return requires_ui_wrapper


def with_exception_handling(func):
    """Turn exceptions into user-facing messages"""

    @functools.wraps(func)
    def format_exception_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except i__.UserWarning as e:
            log.warning(traceback.format_exc())

            MessageBox(
                e.title,
                e.message,
                buttons=ui.OkButton,
                icon=ui.InformationIcon
            )

            return kFailure

        except Exception:
            # Turn this into a friendly warning
            log.warning(traceback.format_exc())
            return kFailure

    return format_exception_wrapper


def _selected_channels():
    """Get currently selected attributes from the channelbox

    Reference: http://forums.cgsociety.org/showthread.php
                      ?f=89&t=892246&highlight=main+channelbox

    """

    channel_box = mel.eval(
        "global string $gChannelBoxName; $temp=$gChannelBoxName;"
    )

    attrs = cmds.channelBox(channel_box,
                            selectedMainAttributes=True,
                            query=True) or []

    attrs += cmds.channelBox(channel_box,
                             selectedShapeAttributes=True,
                             query=True) or []

    attrs += cmds.channelBox(channel_box,
                             selectedHistoryAttributes=True,
                             query=True) or []

    attrs += cmds.channelBox(channel_box,
                             selectedOutputAttributes=True,
                             query=True) or []

    # Returned attributes are shortest possible,
    # e.g. 'tx' instead of 'translateX'
    return attrs


@requires_ui
def validate_evaluation_mode():
    if not options.read("validateEvaluationMode"):
        return kSuccess

    mode = cmds.evaluationManager(query=True, mode=True)

    if mode[0] != "off":  # Both Serial and Parallel are OK
        return kSuccess

    def enable_parallel():
        cmds.evaluationManager(mode="parallel")
        log.info("Enabled Parallel Evaluation")
        return kSuccess

    return ui.warn(
        option="validateEvaluationMode",
        title="DG Evaluation Mode Detected",
        message=(
            "Maya is currently evaluating in the old DG mode, "
            "Ragdoll is most optimal with with Parallel Evaluation or "
            "at the very least Serial. If you experience issues with "
            "performance or drawing in the viewport, switch to Parallel."
        ),
        call_to_action="What would you like to do?",
        actions=[
            ("Ignore", lambda: True),
            ("Enable Parallel Evaluation", enable_parallel),
            ("Cancel", lambda: False)
        ]
    )


@requires_ui
def validate_cached_playback():
    if not cmds.optionVar(query="cachedPlaybackEnable"):
        return kSuccess

    if not options.read("validateCachingMode"):
        return kSuccess

    def disable_cached_playback():
        cmds.optionVar(intValue=("cachedPlaybackEnable", 0))
        log.info("Cached Playback Disabled")
        return kSuccess

    return ui.warn(
        option="validateCachingMode",
        title="Cached Playback Warning",
        message=(
            "Ragdoll does not work well with Cached Playback."
        ),
        call_to_action="What would you like to do?",
        actions=[
            ("Ignore", lambda: True),
            ("Disable Cached Playback", disable_cached_playback),
            ("Cancel", lambda: False)
        ]
    )


@requires_ui
def validate_playbackspeed():
    if not options.read("validatePlaybackSpeed"):
        return kSuccess

    playback_speed = cmds.playbackOptions(playbackSpeed=True, query=True)

    if playback_speed == 0.0:
        return kSuccess

    def fix_it():
        cmds.playbackOptions(playbackSpeed=0.0, maxPlaybackSpeed=1)

        log.info("Playing every frame")
        return kSuccess

    return ui.warn(
        option="validatePlaybackSpeed",
        title="Play every frame",
        message=(
            "Ensure your playback speed is set to 'Play every frame' "
            "to avoid frame drops, these can break a simulation and "
            "generally causes odd things to happen."
        ),
        call_to_action="What would you like to do?",
        actions=[
            ("Ignore", lambda: True),
            ("Play Every Frame", fix_it),
            ("Cancel", lambda: False)
        ]
    )


@requires_ui
def validate_layer_override():
    if not options.read("validateLayerOverride"):
        return kSuccess

    layer = cmds.treeView("AnimLayerTabanimLayerEditor",
                          query=True, selectItem=True)

    if not layer or layer == ["BaseAnimation"]:
        return kSuccess

    if cmds.animLayer(layer[0], query=True, override=True):
        return kSuccess

    def fix_it():
        cmds.animLayer(layer[0], edit=True, override=True)
        log.info("%s was set to Override" % layer[0])
        return kSuccess

    return ui.warn(
        option="validateLayerOverride",
        title="Selected Layer",
        message=(
            "The selected layer is set to 'Additive' mode, which is "
            "incompatible with Record Simulation. It must be set to "
            "'Override'"
        ),
        call_to_action="What would you like to do?",
        actions=[
            ("Ignore", lambda: True),
            ("Set to Override", fix_it),
            ("Cancel", lambda: False)
        ]
    )


@requires_ui
def validate_legacy_opengl():
    if not options.read("validateLegacyOpenGL2"):
        return kSuccess

    opengl_legacy = cmds.optionVar(query="vp2RenderingEngine") == "OpenGL"
    direct_x = cmds.optionVar(query="vp2RenderingEngine") == "DirectX11"

    if not (opengl_legacy or direct_x):
        return kSuccess

    def fix_it():
        cmds.optionVar(stringValue=("vp2RenderingEngine",
                                    "OpenGLCoreProfileCompat"))
        log.warning(
            "OpenGL Core Compatibility Profile "
            "enabled, restart required."
        )
        return False

    return ui.warn(
        option="validateLegacyOpenGL2",
        title="Unsupported Rendering Engine Detected",
        message=(
            "Your viewport is set to render in either DirectX or "
            "Legacy OpenGL, which is incompatible with the Ragdoll "
            "renderer.\n\nNOTE: Changing renderer requires a restart of Maya."
        ),
        call_to_action="Go to Maya Preferences to change this.",
        actions=[
            ("Ignore", lambda: True),
            ("Fix it", fix_it),
            ("Cancel", lambda: False)
        ]
    )


def _filtered_selection(node_type, selection=None):
    """Interpret user selection

    They should be able to..

    1. Select transforms, even though they meant the shape
    2. Select a transform with *multiple* shapes of a given type
    2. Select the shape
    3. Select multiple shapes
    4. Select multiple shapes *and* transforms

    """

    selection = list(selection or cmdx.selection())

    if not selection:
        return []

    shapes = []
    for node in selection:
        if node.isA(cmdx.kDagNode):
            for shape in node.shapes(node_type):
                if "intermediateObject" in shape and shape["io"]:
                    log.info("Skipped intermediate shape %s" % shape)
                    continue
                shapes += [shape]

    shapes = filter(None, shapes)
    shapes = list(shapes) + selection
    shapes = filter(lambda shape: shape.isA(node_type), shapes)

    return list(shapes)


@i__.with_undo_chunk
def create_scene(selection=None):
    if not validate_evaluation_mode():
        return

    if not validate_cached_playback():
        return

    if not validate_playbackspeed():
        return

    if not validate_legacy_opengl():
        return

    # Update known solvers
    __.solvers = [n.shortestPath() for n in cmdx.ls(type="rdScene")]

    scene = commands.create_scene()

    # Use last-created scene per default
    __.solvers.insert(0, scene.shortestPath())

    return scene


@requires_ui
def is_valid_transform(transform):
    """Ragdoll currently does not support any custom pivot or axis"""

    if options.read("validateScalePivot"):
        nonzero = []
        tolerance = 0.01
        for attr in ("scalePivot",
                     "scalePivotTranslate"):
            for axis in "XYZ":
                plug = transform[attr + axis]
                if abs(plug.read()) > tolerance:
                    nonzero.append(plug)

        if nonzero:
            for plug in nonzero:
                log.warning("%s was not zero" % plug.path())

            return ui.warn(
                option="validateScalePivot",
                title="Custom Scale Pivot Not Supported",
                message=(
                    "Non-zero scale pivot was found. These are currently "
                    "unsupported and need to be zeroed out, "
                    "see Script Editor for details."
                ),
                call_to_action="What would you like to do?",
                actions=[

                    # Happens automatically by commands.py
                    # Take it or leave it, doesn't work otherwise
                    ("Zero out scalePivot", lambda: True),

                    ("Cancel", lambda: False)
                ]
            )

    return kSuccess


def _opt(key, override=None):
    override = override or {}
    return override.get(key, options.read(key))


def _rewind(scene):
    start_time = scene["startTime"].asTime()
    cmdx.currentTime(start_time)


@i__.with_undo_chunk
def create_active_rigid(selection=None, **opts):
    """Create a new rigid from selection"""

    created = []
    selection = selection or cmdx.selection(type="dagNode")

    if not selection:

        # Make a new rigid from scratch
        with cmdx.DagModifier() as mod:
            name = i__.unique_name("rigid")
            transform = mod.create_node("transform", name=name)

        selection = [transform]

    # Based on the first selection, determine
    # whether to convert or create something new.
    if selection[0].isA(cmdx.kShape):
        if selection[0].type() == "rdRigid":
            return convert_rigid(selection, **opts)

    elif selection[0].isA(cmdx.kTransform):
        if selection[0].shape("rdRigid"):
            return convert_rigid(selection, **opts)

    if not _validate_transforms(selection):
        return

    # Pre-flight check
    for node in selection:
        transform = node.parent() if node.isA(cmdx.kShape) else node
        if not is_valid_transform(transform):
            return

        # Rigid bodies must have translate and rotate channels
        if not transform.isA(cmdx.kTransform):
            log.warning("%s is not a transform node", transform.path())
            return

    select = _opt("rigidSelect", opts)
    passive = _opt("createRigidType", opts) == c.CreatePassive
    scene = _find_current_scene()

    # Cancelled by user
    if not scene:
        return

    if passive and _opt("cycleProtection", opts):
        def will_cycle(root):
            rigid = root.shape(type="rdRigid")

            # Passive or active, this is fine
            if rigid:
                return False

            # This is not fine
            return i__.is_dynamic(root, scene)

        for node in selection:
            transform = node.parent() if node.isA(cmdx.kShape) else node

            if not will_cycle(transform):
                continue

            log.warning("%s cannot be made passive" % transform)
            MessageBox("Cycle Warning", (
                "**Passive Child, Active Parent**\n\n"
                "Cannot make *passive* rigid the "
                "child of an *active* hierarchy. "
                "This would have caused a cycle.\n\n"
                "Ensure no parent is already being simulated."
            ), buttons=ui.OkButton, icon=ui.InformationIcon)

            return kFailure

    if _opt("autoReturnToStart", opts):
        _rewind(scene)

    for index, node in enumerate(selection):
        transform = node.parent() if node.isA(cmdx.kShape) else node

        # Check *before* it becomes rigid
        translate_animated = any(
            transform[attr].connected for attr in ("tx", "ty", "tz")
        )
        rotate_animated = any(
            transform[attr].connected for attr in ("rx", "ry", "rz")
        )

        opts_ = {
            "computeMass": _opt("computeMass2", opts),
            "passive": passive,
            "defaults": {},
            "addUserAttributes": _opt("addUserAttributes", opts),
        }

        # Translate UI options into attribute defaults
        initial_shape = _opt("initialShape", opts)
        if initial_shape != c.InitialShapeAuto:
            opts_["defaults"]["shapeType"] = {
                # UI -> API
                c.InitialShapeBox: c.BoxShape,
                c.InitialShapeSphere: c.SphereShape,
                c.InitialShapeCapsule: c.CapsuleShape,
                c.InitialShapeMesh: c.MeshShape,
            }[initial_shape]

        try:
            rigid = commands.create_rigid(node, scene, opts=opts_)

        except Exception as e:
            _print_exception()
            log.error(str(e))
            continue

        # There may have been an error
        if not rigid:
            continue

        created += [rigid]

        # Preserve animation, if any, as soft constraints
        follow = _opt("existingAnimation", opts) == c.ExistingFollow
        if not passive and follow and (translate_animated or rotate_animated):
            subopts = {"defaults": {"driveStrength": 1.0}}

            if not translate_animated:
                subopts["defaults"]["linearDriveStiffness"] = 0
                subopts["defaults"]["linearDriveDamping"] = 0

            if not rotate_animated:
                subopts["defaults"]["angularDriveStiffness"] = 0
                subopts["defaults"]["angularDriveDamping"] = 0

            con = commands.animation_constraint(rigid, opts=subopts)
            created += [con]

    if created:
        new_rigids = [n for n in created if n.type() == "rdRigid"]

        if select:
            all_rigids = [r.parent() for r in new_rigids]
            cmds.select(list(map(str, all_rigids)))

        log.info("Created %d rigid bodies", len(new_rigids))
        return kSuccess

    else:
        return log.warning("Nothing happened, that was unexpected")


@i__.with_undo_chunk
def create_passive_rigid(selection=None, **opts):
    # Special case of nothing selected, just make a default sphere
    if not selection and not cmdx.selection():
        with cmdx.DagModifier() as mod:
            name = i__.unique_name("rPassive")
            transform = mod.create_node("transform", name=name)

        cmds.select(transform.path())

    opts["createRigidType"] = c.CreatePassive
    opts["convertRigidType"] = c.ConvertPassive
    return create_active_rigid(selection, **opts)


@i__.with_undo_chunk
@with_exception_handling
def create_active_chain(selection=None, **opts):
    links = selection or cmdx.selection(type="dagNode")

    # This is no chain
    if len(links) < 2:
        raise i__.UserWarning(
            "Selection Problem",
            "Select one root, followed by one or more children "
            "to form a chain of physics objects."
        )

    if not links:
        raise i__.UserWarning(
            "Selection Problem",
            "Select two or more transforms "
            "in the order they should be connected. "
            "The first selection will be passive (i.e. animated)."
        )

    for link in links:
        if not is_valid_transform(link):
            return

    # Protect against accidental duplicates
    for link in links[1:]:
        if link.shape("rdRigid") is not None:
            return log.warning("Already dynamic: '%s'" % link)

    opts_ = {
        "autoMultiplier": _opt("chainAutoMultiplier", opts),
        "autoLimits": _opt("chainAutoLimits", opts),
        "passiveRoot": _opt("chainPassiveRoot", opts),
        "computeMass": _opt("computeMass2", opts),
        "drawShaded": False,
        "defaults": {}
    }

    shape_type = _opt("chainShapeType", opts)
    if shape_type != c.InitialShapeAuto:
        opts_["defaults"]["shapeType"] = {
            # UI -> API
            c.InitialShapeBox: c.BoxShape,
            c.InitialShapeSphere: c.SphereShape,
            c.InitialShapeCapsule: c.CapsuleShape,
            c.InitialShapeMesh: c.MeshShape,
        }[shape_type]

    scene = _find_current_scene()

    # Cancelled by user
    if not scene:
        return

    def cycle_protection():
        root = links[0]
        rigid = root.shape(type="rdRigid")

        # Passive or active, this is fine
        if rigid:
            return kSuccess

        # This is not fine
        return not i__.is_dynamic(root, scene)

    if _opt("cycleProtection", opts) and not cycle_protection():
        if opts_["passiveRoot"]:
            log.warning("%s cannot be made passive" % links[0])
            MessageBox("Passive Child, Active Parent", (
                "Cannot make *passive* rigid the "
                "child of an *active* hierarchy."
            ), buttons=ui.OkButton, icon=ui.InformationIcon)

            return kFailure

    tools.create_chain(links, scene, opts=opts_)

    root = links[0]
    cmds.select(str(root))

    return kSuccess


def _axis_to_vector(axis="x"):
    return {
        "x": cmdx.Vector(1, 0, 0),
        "y": cmdx.Vector(0, 1, 0),
        "z": cmdx.Vector(0, 0, 1),
        0: cmdx.Vector(1, 0, 0),
        1: cmdx.Vector(0, 1, 0),
        2: cmdx.Vector(0, 0, 1),
    }[axis]


@i__.with_undo_chunk
def create_muscle(selection=None, **opts):
    try:
        a, b = selection or cmdx.selection()
    except ValueError:
        return log.warning("Select root and tip anchors of new muscle")

    if not all(node.isA(cmdx.kTransform) for node in (a, b)):
        return log.error(
            "Select two transforms for root and tip anchors of muscle"
        )

    if not all(node.parent() for node in (a, b)):
        return log.error(
            "Anchors must have a parent, see muscle documentation for details"
        )

    new_scene = not cmdx.ls(type="rdScene")
    scene = _find_current_scene()

    # Cancelled by user
    if not scene:
        return

    if _opt("autoReturnToStart", opts):
        _rewind(scene)

    if new_scene:
        # Muscles work best with the PGS solver, fow now
        log.info("Swapping TGS for PGS for better muscle simulation results")
        with cmdx.DagModifier() as mod:
            mod.set_attr(scene["solverType"], c.PGSSolverType)
            mod.set_attr(scene["gravity"], 0)

    kwargs = {
        "up_axis": _axis_to_vector(_opt("muscleUpAxis", opts)),
        "aim_axis": _axis_to_vector(_opt("muscleAimAxis", opts)),
        "flex": _opt("muscleFlex", opts),
        "radius": _opt("muscleRadius", opts),
    }

    muscle, root, tip = tools.create_muscle(a, b, scene, **kwargs)

    cmds.select(muscle.parent().path())
    return kSuccess


def _validate_transforms(nodes, tolerance=0.01):
    """Check for unsupported features in nodes of `root`"""
    negative_scaled = []
    positive_scaled = []
    issues = []

    for node in nodes:
        if not node.isA(cmdx.kTransform):
            continue

        tm = node.transform(cmdx.sWorld)
        if any(value < 0 - tolerance for value in tm.scale()):
            negative_scaled += [node]

        if any(value > 1 + tolerance for value in tm.scale()):
            positive_scaled += [node]

    if negative_scaled and options.read("validateScale"):
        issues += [
            "%d node(s) has negative scale\n%s" % (
                len(negative_scaled),
                "\n".join(" - %s" % node for node in negative_scaled),
            )
        ]

    if issues:
        for issue in issues:
            log.warning(issue)

        log.warning("%d %s" % (
            len(issues),
            "issue was found" if len(issues) == 1 else
            "issues were found"
        ))

    return False if issues else True


@i__.with_undo_chunk
def create_character(selection=None, **opts):
    scene = _find_current_scene()

    # Cancelled by user
    if not scene:
        return

    root = selection or cmdx.selection(type="joint")

    if not root or root[0].type() != "joint":
        return log.warning("Select root joint from which to create character")

    if len(root) > 1:
        return log.warning(
            "Multiple roots selected, select the root of 1 hierarchy"
        )

    # Operate only on first selected joint, to avoid
    # the tragic fate of accidentally making 100 ragdolls
    # (Could still be done via scripting)
    root = root[0]

    hierarchy = [root]
    hierarchy += [
        joint for joint in root.descendents(type="joint")
        if joint.child(type="joint")
    ]

    if not _validate_transforms(hierarchy):
        return

    if _opt("autoReturnToStart", opts):
        _rewind(scene)

    kwargs = {
        "copy": _opt("characterCopy", opts),
        "control": _opt("characterControl", opts),
        "normalise_shapes": _opt("characterNormalise", opts),
    }

    print(options.read("characterCopy"))

    tools.create_character(root, scene, **kwargs)

    cmds.select(str(root))
    log.info("Successfully created character from %s", root)
    return kSuccess


def _find_rigid(node, autocreate=False):
    if node.type() == "rdRigid":
        pass

    elif node.type() in ("transform", "joint"):
        shape = node.shape(type="rdRigid")

        # Automatically convert selection to rigid for the constraints
        if not shape and not node.shape(type="rdLink"):
            if autocreate:
                scene = _find_current_scene(autocreate=autocreate)

                # Cancelled by user
                if not scene:
                    return

                shape = commands.create_active_rigid(node, scene)
            else:
                return log.warning(
                    "%s did not have a rdRigid shape" % node.path()
                )

        node = shape

    return node


@i__.with_undo_chunk
def create_constraint(selection=None, **opts):
    select = _opt("constraintSelect", opts)
    constraint_type = _opt("constraintType", opts)
    selection = selection or cmdx.selection()

    if selection and selection[0].type() == "rdConstraint":
        # The user meant to convert/restore a constraint
        return convert_constraint(selection, **opts)

    try:
        parent, child = selection
    except ValueError:
        return log.warning(
            "Select parent and child rigids, "
            "these will become constrained to each other"
        )

    scene = _find_current_scene(autocreate=True)

    # Cancelled by user
    if not scene:
        return

    parent = _find_rigid(parent) or scene
    child = _find_rigid(child)

    if any(node is None for node in (parent, child)):
        return log.warning("Must select two rigids")

    opts = {
        "maintainOffset": _opt("maintainOffset", opts),
        "outlinerStyle": _opt("constraintOutlinerStyle", opts),
    }

    if constraint_type == c.PointConstraint:
        con = commands.point_constraint(parent, child, opts=opts)

    elif constraint_type == c.OrientConstraint:
        con = commands.orient_constraint(parent, child, opts=opts)

    elif constraint_type == c.HingeConstraint:
        con = commands.hinge_constraint(parent, child, opts=opts)

    elif constraint_type == c.SocketConstraint:
        con = commands.socket_constraint(parent, child, opts=opts)

    elif constraint_type == c.ParentConstraint:
        con = commands.parent_constraint(parent, child, opts=opts)

    elif constraint_type == c.IgnoreContactsConstraint:
        con = commands.ignore_contacts_constraint(parent, child, opts=opts)

    else:
        return log.warning(
            "Unrecognised constraint type '%s'" % constraint_type
        )

    guide_strength = _opt("constraintGuideStrength", opts)
    if guide_strength > 0:
        with cmdx.DagModifier() as mod:
            mod.set_attr(con["driveStrength"], guide_strength)

    if select:
        cmds.select(con.path(), replace=True)

    log.info("Constrained %s to %s" % (child, parent))
    return kSuccess


@i__.with_undo_chunk
def convert_constraint(selection=None, **opts):
    converted = []

    select = _opt("constraintSelect", opts)
    constraint_type = _opt("constraintType", opts)

    if constraint_type is None:
        constraint_type = options.read("convertConstraintType")

    for node in selection or cmdx.selection():
        con = node

        if not node.type() == "rdConstraint":
            con = node.shape(type="rdConstraint")

        if not con:
            log.warning("No constraint found for %s", node)
            continue

        if constraint_type == c.PointConstraint:
            converted += [commands.convert_to_point(con)]

        elif constraint_type == c.OrientConstraint:
            converted += [commands.convert_to_orient(con)]

        elif constraint_type == c.ParentConstraint:
            converted += [commands.convert_to_parent(con)]

        elif constraint_type == c.HingeConstraint:
            converted += [commands.convert_to_hinge(con)]

        elif constraint_type == c.SocketConstraint:
            converted += [commands.convert_to_socket(con)]

        else:
            # Raise errors, instead of logging directly, such that the
            # error message references the calling function instead of this,
            # helper-level function
            log.warning("Unrecognised constraint type '%s'", constraint_type)
            break

    if not converted:
        return log.warning("Nothing converted")

    elif select:
        cmds.select(list(map(str, converted)), replace=True)

    log.info("Converted %d constraints" % len(converted))
    return kSuccess


@i__.with_undo_chunk
def convert_rigid(selection=None, **opts):
    selection = selection or cmdx.selection()
    converted = []
    typ = _opt("convertRigidType", opts)

    rigids = []
    for node in selection:
        rigid = node

        if node.isA(cmdx.kTransform):
            rigid = node.shape(type="rdRigid")

        if not rigid or rigid.type() != "rdRigid":
            log.warning("Couldn't convert %s" % node)
            continue

        # Toggle between kinematic and dynamic
        passive = typ == c.ConvertPassive

        if _opt("cycleProtection", opts) and passive:
            scene = rigid["nextState"].connection(type="rdScene")

            if scene is None:
                # This rigid isn't even part of a scene
                pass

            transform = rigid.parent()
            parent = transform.parent()

            if parent and i__.is_dynamic(parent, scene):
                log.warning("%s cannot be made passive" % transform)
                MessageBox("Cycle Warning", (
                    "**Passive Child, Active Parent**\n\n"
                    "Cannot make *passive* rigid the "
                    "child of an *active* hierarchy. "
                    "This would have caused a cycle.\n\n"
                    "Ensure the parent of the selected node is "
                    "not already being affected by the simulation."
                ), buttons=ui.OkButton, icon=ui.InformationIcon)

                return kFailure

        rigids += [(rigid, passive)]

    for rigid, passive in rigids:
        commands.convert_rigid(rigid, opts={"passive": passive})
        converted.append(rigid)

    if not converted:
        return log.debug("Nothing converted")

    log.info("%d rigids converted", len(converted))
    return kSuccess


@i__.with_undo_chunk
def convert_to_socket(node):
    con = node.shape(type="rdConstraint")

    if con is None:
        return log.warning(
            "Couldn't find an existing constraint to convert, "
            "did you mean to select parent and child?"
        )

    commands.convert_to_socket(con)
    log.info("Converted %s -> Socket", con.path())
    return kSuccess


@i__.with_undo_chunk
def create_point_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.PointConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def create_orient_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.OrientConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def create_parent_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.ParentConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def create_hinge_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.HingeConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def create_socket_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.SocketConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def ignore_contacts_constraint(selection=None, **opts):
    opts = dict(opts, **{"constraintType": c.IgnoreContactsConstraint})
    return create_constraint(selection, **opts)


@i__.with_undo_chunk
def create_animation_constraint(selection=None, **opts):
    selection = selection or cmdx.selection()

    created = []
    for node in selection:
        rigid = _find_rigid(node)

        if not rigid:
            continue

        opts = {
            "strength": _opt("constraintGuideStrength", opts),
        }

        con = commands.animation_constraint(rigid, opts=opts)
        created += [con]

    log.info("Successfully created %s" % ", ".join(str(c) for c in created))
    return kSuccess


@i__.with_undo_chunk
def set_initial_state(selection=None, **opts):
    selection = selection or cmdx.selection()
    use_selection = _opt("initialStateUseSelection", opts)

    if not use_selection:
        selection = cmdx.ls(type="rdRigid")

    rigids = []
    for rigid in selection:
        if rigid.isA(cmdx.kTransform):
            rigid = rigid.shape(type="rdRigid")

        if rigid and rigid.type() == "rdRigid":
            rigids += [rigid]

    if not rigids:
        return log.warning("No rigids found to set initial state for")

    commands.set_initial_state(rigids)

    log.info(
        "Successfully set initial state for %d rigid bodies.", len(rigids)
    )
    return kSuccess


@i__.with_undo_chunk
def clear_initial_state(selection=None, **opts):
    selection = selection or cmdx.selection()
    use_selection = _opt("initialStateUseSelection", opts)

    if not use_selection:
        selection = cmdx.ls(type="rdRigid")

    rigids = []
    for rigid in selection:
        if rigid.isA(cmdx.kTransform):
            rigid = rigid.shape(type="rdRigid")

        if rigid and rigid.type() == "rdRigid":
            rigids += [rigid]

    if not rigids:
        return log.warning("No rigids found to clear initial state for")

    commands.clear_initial_state(rigids)

    log.info(
        "Successfully cleared initial state for %d rigid bodies.", len(rigids)
    )
    return kSuccess


@i__.with_undo_chunk
def create_soft_pin(selection=None, **opts):
    controls = []
    selection = selection or cmdx.selection()

    if len(selection) == 1:
        actor = selection[0]

        if actor.isA(cmdx.kTransform):
            actor = selection[0].shape(type="rdRigid")

        if not actor:
            return log.warning("%s was not a Ragdoll Rigid" % selection[0])

        _, ctrl, _ = commands.create_soft_pin(actor)
        controls += [ctrl.parent().path()]

    elif len(selection) == 2:
        reference, actor = selection

        if actor.isA(cmdx.kTransform):
            actor = selection[1].shape(type="rdRigid")

        if not actor or actor.type() != "rdRigid":
            return log.warning("%s was not a Ragdoll Rigid" % selection[1])

        if actor.sibling(type="rdConstraint"):
            ctrl = commands.create_active_control(
                actor, reference=reference)
        else:
            _, ctrl, _ = commands.create_soft_pin(
                actor, reference=reference
            )

        controls += [reference.path()]

    else:
        return log.warning(
            "Select one rigid, or one rigid and a reference transform"
        )

    cmds.select(controls)
    return kSuccess


@i__.with_undo_chunk
def create_hard_pin(selection=None, **opts):
    controls = []

    for node in selection or cmdx.selection():
        actor = node

        if actor.isA(cmdx.kTransform):
            actor = node.shape(type="rdRigid")

        if not actor or actor.type() != "rdRigid":
            log.warning("%s was not an Ragdoll Rigid", node)
            continue

        con = commands.create_hard_pin(actor)
        controls += [con.path()]

    if not controls:
        return log.warning("Nothing happened, did you select a rigid?")
    else:
        cmds.select(controls)
        return kSuccess


@i__.with_undo_chunk
def create_mimic(selection=None, **opts):
    node = selection or cmdx.selection(type=("rdRigid", "transform"))

    # This is no chain
    if not node or len(node) > 1:
        raise i__.UserWarning(
            "Selection Problem",
            "Select the root of one chain."
        )

    root = node[0]
    if root.isA(cmdx.kTransform):
        root = root.shape("rdRigid")

    if not root or root.type() != "rdRigid":
        raise i__.UserWarning(
            "Selection Problem",
            "%s was not a rigid." % node[0]
        )

    opts = {
        "nodeType": c.Joint if _opt("mimicNodeType", opts) else c.Transform,
        "exclusive": _opt("mimicExclusive", opts),
        "addSoftPin": _opt("mimicAddSoftPin", opts),
        "addHardPin": _opt("mimicAddHardPin", opts),
        "addUserAttributes": _opt("mimicAddUserAttributes", opts),
        "addMultiplier": _opt("mimicAddMultiplier", opts),
        "freezeTransform": _opt("mimicFreezeTransform", opts),
        "cleanChannelBox": _opt("mimicCleanChannelBox", opts),
    }

    # Uses offsetParentMatrix
    if cmdx.__maya_version__ < 2020:
        opts["freezeTransform"] = False

    mimic = commands.create_mimic(root, opts=opts)

    cmds.select(str(mimic))

    return kSuccess


@contextlib.contextmanager
def refresh_suspended():
    cmds.refresh(suspend=True)

    try:
        yield
    finally:
        cmds.refresh(suspend=False)


@contextlib.contextmanager
def isolate_select(nodes):
    isolated_panel = cmds.paneLayout("viewPanes", query=True, pane1=True)

    previous_selection = cmds.ls(selection=True)
    cmds.select(nodes)
    cmds.editor(isolated_panel,
                edit=True,
                lockMainConnection=True,
                mainListConnection="activeList")
    cmds.isolateSelect(isolated_panel, state=True)

    try:
        yield
    finally:
        cmds.isolateSelect(isolated_panel, state=False)
        cmds.select(previous_selection)


@i__.with_undo_chunk
@with_exception_handling
def bake_simulation(selection=None, **opts):
    opts_ = {
        "deletePhysics": _opt("bakeDeletePhysics", opts),
        "bakeToLayer": _opt("bakeToLayer", opts),
        "includeStatic": _opt("bakeIncludeStatic", opts),
        "unrollRotation": _opt("bakeUnrollRotation", opts),
        "scene": _opt("bakeScene", opts),
    }

    rigids = []

    if opts_["scene"] == c.BakeAll:
        rigids.extend(cmdx.ls(type="rdRigid"))

    elif opts_["scene"] == c.BakeSelected:
        for scene in _filtered_selection("rdScene"):
            for element in scene["outputObjects"]:
                rigid = element.connection(source=False, type="rdRigid")
                rigids.append(rigid) if rigid else DoNothing

    if not rigids:
        return log.warning("No rigids found!")

    with i__.Timer("bake") as duration:
        if _opt("bakePerformance", opts) == 1:
            with isolate_select(rigids):
                commands.bake_simulation(rigids, opts=opts_)

        elif _opt("bakePerformance", opts) == 2:
            with refresh_suspended():
                commands.bake_simulation(rigids, opts=opts_)

        else:
            commands.bake_simulation(rigids, opts=opts_)

    cmds.inViewMessage(
        amg="Baked simulation in <hl>%.2fs</hl>" % duration.s,
        pos="topCenter",
        fade=True
    )

    return kSuccess


@i__.with_undo_chunk
def transfer_selected(selection=None):
    try:
        a, b = selection or cmdx.selection()
    except ValueError:
        return log.warning(
            "Select source and destination rigids, in that order"
        )

    commands.transfer_attributes(a, b, opts={"mirror": True})

    log.info("Transferred attributes from %s -> %s", a, b)
    return kSuccess


@with_exception_handling
def replace_mesh(selection=None, **opts):
    opts = {
        "exclusive": _opt("replaceMeshExclusive", opts),
        "maintainOffset": _opt("replaceMeshMaintainOffset", opts),
    }

    meshes = (
        _filtered_selection("mesh", selection) +
        _filtered_selection("nurbsCurve", selection) +
        _filtered_selection("nurbsSurface", selection)
    )

    rigids = _filtered_selection("rdRigid", selection)

    if len(rigids) < 1:
        raise i__.UserWarning(
            "Selection Problem",
            "No rigid selected. Select 1 mesh and 1 rigid, in any order."
        )

    if len(rigids) > 1:
        raise i__.UserWarning(
            "Selection Problem",
            "2 or more rigids selected. Pick one."
        )

    if len(meshes) < 1:
        raise i__.UserWarning(
            "Selection Problem",
            "No meshes selected. Select 1 mesh and 1 rigid."
        )

    if len(meshes) > 1:
        existing_msh = rigids[0]["inputMesh"].input()
        existing_crv = rigids[0]["inputCurve"].input()
        existing_srf = rigids[0]["inputSurface"].input()

        for mesh in meshes[:]:
            if mesh in (existing_msh, existing_crv, existing_srf):
                meshes.remove(mesh)

        # Still got more?
        if len(meshes) > 1:
            raise i__.UserWarning(
                "Selection Problem",
                "2 or more meshes selected, pick one."
            )

    commands.replace_mesh(rigids[0], meshes[0], opts=opts)

    return kSuccess


def edit_constraint_frames(selection=None):
    frames = []

    for node in selection or cmdx.selection():
        con = node

        if con.isA(cmdx.kTransform):
            cons = list(node.shapes(type="rdConstraint"))

            if cons:
                # Last created constraint
                con = cons[-1]

        if not con.type() == "rdConstraint":
            log.warning("%s is not a constraint" % con)
            continue

        if not con:
            log.warning("%s had no constraint" % node)
            continue

        frames.extend(commands.edit_constraint_frames(con))

    log.info("Created %d frames" % len(frames))
    cmds.select(list(map(str, frames)))
    return kSuccess


def _rotate_constraint_frames(degrees, axis, selection=None):
    rotated = []

    for node in selection or cmdx.selection():
        con = node

        if con.isA(cmdx.kTransform):
            cons = list(node.shapes(type="rdConstraint"))

            if cons:
                # Last created constraint
                con = cons[-1]

        if not con.type() == "rdConstraint":
            log.warning("%s is not a constraint" % con)
            continue

        if not con:
            log.warning("%s had no constraint" % node)
            continue

        rotated += [con]
        commands.rotate_constraint(con, degrees=degrees, axis=axis)

    log.info("Rotated %d constraints" % len(rotated))
    return kSuccess


def rotate_constraint_frames_x(selection=None):
    return _rotate_constraint_frames(90, (1, 0, 0), selection)


def rotate_constraint_frames_y(selection=None):
    return _rotate_constraint_frames(90, (0, 1, 0), selection)


def rotate_constraint_frames_z(selection=None):
    return _rotate_constraint_frames(90, (0, 0, 1), selection)


def tune_constraint_frames_x_add(selection=None):
    return _rotate_constraint_frames(5, (1, 0, 0), selection)


def tune_constraint_frames_y_add(selection=None):
    return _rotate_constraint_frames(5, (0, 1, 0), selection)


def tune_constraint_frames_z_add(selection=None):
    return _rotate_constraint_frames(5, (0, 0, 1), selection)


def tune_constraint_frames_x_sub(selection=None):
    return _rotate_constraint_frames(-5, (1, 0, 0), selection)


def tune_constraint_frames_y_sub(selection=None):
    return _rotate_constraint_frames(-5, (0, 1, 0), selection)


def tune_constraint_frames_z_sub(selection=None):
    return _rotate_constraint_frames(-5, (0, 0, 1), selection)


def reset_constraint_frames(selection=None):
    resetted = []

    for node in selection or cmdx.selection():
        con = node

        if con.isA(cmdx.kTransform):
            cons = list(node.shapes(type="rdConstraint"))

            if cons:
                # Last created constraint
                con = cons[-1]

        if not con.type() == "rdConstraint":
            log.warning("%s is not a constraint" % con)
            continue

        if not con:
            log.warning("%s had no constraint" % node)
            continue

        resetted += [con]
        commands.reset_constraint_frames(con)

    log.info("Resetted %d constraints" % len(resetted))
    return kSuccess


def edit_shape(selection=None):
    editors = []

    for node in selection or cmdx.selection():
        rigid = node

        if rigid.isA(cmdx.kTransform):
            rigid = node.shape(type=("rdMaker", "rdRigid"))

        if rigid is None:
            log.warning("No rigid found for %s" % node)
            continue

        if rigid.type() not in ("rdRigid", "rdMarker"):
            log.warning("%s was not a rigid" % rigid)
            continue

        if not rigid:
            log.warning("%s had no rigid" % node)
            continue

        editors.append(commands.edit_shape(rigid))

    log.info("Created %d shape editors" % len(editors))
    cmds.select(list(map(str, editors)))
    return kSuccess


def _find_current_scene(autocreate=True):
    current_scene = None
    scene_enum = options.read("solver")

    try:
        # Enum -> String
        scene_name = __.solvers[scene_enum]

    except IndexError:
        # No questions asked, just make a new one
        current_scene = create_scene()

    else:
        # The one stored persistently may not actually exist,
        # it may come from another scene or at a time when it
        # did exist but got deleted
        try:
            node = cmdx.encode(scene_name)

            if node.shortestPath() == scene_name:
                current_scene = node

            else:
                # E.g. rSceneShape may exist, but _:rSceneShape is
                # what exists because it's coming from a reference.
                # We're only interested in the exact name.
                raise cmdx.ExistError

        except cmdx.ExistError:
            # Ok, no persistent clue or request for a new scene
            try:
                current_scene = cmdx.ls(type="rdScene")[0]

            # Nothing in sight, now it's up to the caller
            except IndexError:
                if autocreate:
                    current_scene = create_scene()
                else:
                    raise cmdx.ExistError("No Ragdoll scene was found")

    if current_scene is not None:
        # Use this from now on
        current = __.solvers.index(current_scene.shortestPath())
        options.write("solver", current)

    return current_scene


def _create_force(selection=None, force_type=None):
    # To specific rigids, or all of them
    selection = cmdx.selection() or cmdx.ls(type="rdRigid")

    rigids = []
    for node in selection:
        rigid = node

        if rigid.isA(cmdx.kTransform):
            rigid = node.shape(type="rdRigid")

        if not rigid:
            log.warning("%s was not an Ragdoll Rigid" % node)
            continue

        rigids += [rigid]

    if not rigids:
        return log.warning("No rigids found")

    scene = _find_current_scene(autocreate=False)

    # Cancelled by user
    if not scene:
        return

    force = commands.create_force(force_type, scene)

    for rigid in rigids:
        commands.assign_force(rigid, force)

    cmds.select(force.parent().path())
    return kSuccess


@i__.with_undo_chunk
def create_push_force(selection=None):
    return _create_force(selection, c.PushForce)


@i__.with_undo_chunk
def create_pull_force(selection=None):
    return _create_force(selection, c.PullForce)


@i__.with_undo_chunk
def create_uniform_force(selection=None):
    return _create_force(selection, c.UniformForce)


@i__.with_undo_chunk
def create_turbulence_force(selection=None):
    return _create_force(selection, c.TurbulenceForce)


@i__.with_undo_chunk
def create_slice(selection=None):
    scene = _find_current_scene(autocreate=False)

    # Cancelled by user
    if not scene:
        return

    slice = commands.create_slice(scene)
    cmds.select(slice.parent().path())
    log.info("Created %s" % slice)
    return kSuccess


@i__.with_undo_chunk
def assign_force(selection=None):
    sel = selection or cmdx.selection()

    if len(sel) < 2:
        return log.warning(
            "Select rigid body followed by one or more forces to assign"
        )

    force, targets = sel[0], sel[1:]

    if force.isA(cmdx.kTransform):
        force = force.shape(type="rdForce")

    if not force or force.type() != "rdForce":
        return log.warning("%s was not a force" % sel[0])

    assignments = []
    for node in targets:
        target = node

        if target.isA(cmdx.kTransform):
            target = node.shape(type="rdRigid")

        if not target or target.type() != "rdRigid":
            log.warning("%s was not a rigid body" % node)
            continue

        if commands.assign_force(target, force):
            assignments += [force]

    if assignments:
        return log.info("Assigned %s to %d rigids" % (force, len(assignments)))
    else:
        log.warning("No forces assigned")
        return kSuccess


@i__.with_undo_chunk
def duplicate_selected(selection=None, **opts):
    selection = cmdx.selection()
    cmds.select(deselect=True)

    duplicates = []
    for node in selection:
        rigid = node

        if rigid.isA(cmdx.kTransform):
            rigid = node.shape(type="rdRigid")

        if not rigid:
            log.warning("%s skipped, not a rigid" % node)
            continue

        log.info("Duplicating %s" % rigid)

        dup = commands.duplicate(rigid)
        duplicates += [dup]

        cmds.select(dup.parent().path(), add=True)

    if duplicates:
        log.info("Duplicated %d rigids" % len(duplicates))
        return kSuccess
    else:
        return log.warning("Nothing duplicated")


@i__.with_undo_chunk
@with_exception_handling
def delete_physics(selection=None, **opts):
    if cmds.about(apiVersion=True) == 20220000:
        MessageBox(
            "Warning",
            "Maya 2022.0 has a critical bug leading to a crash "
            "when running this command. You will need the "
            "service pack 2022.1 or greater."
        )

        return kFailure

    delete = commands.delete_all_physics

    if _opt("deleteFromSelection", opts):
        selection = selection or cmdx.selection()

        if selection:
            def delete():
                return commands.delete_physics(selection)

    result = delete()

    any_node = cmds.ls()[0]
    cmds.select(any_node)  # Trigger a change to selection
    cmds.select(deselect=True)

    if any(result.values()):
        log.info(
            "Deleted {deletedRagdollNodeCount} Ragdoll nodes, "
            "{deletedExclusiveNodeCount} exclusive nodes and "
            "{deletedUserAttributeCount} user attributes".format(**result)
        )
        return kSuccess

    else:
        return log.warning("Nothing deleted")


@requires_ui
def create_dynamic_control(selection=None, **opts):
    message = """\
"Dynamic Control" is now "Active Chain".

It was renamed a few versions ago, so whenever you see
"Dynamic Control", think "Active Chain". It's at the top
of the Ragdoll menu.
"""

    MessageBox(
        "Heads up!",
        message,
        buttons=ui.OkButton,
        icon=ui.InformationIcon
    )

    return kSuccess


@i__.with_undo_chunk
def convert_to_polygons(selection=None):
    meshes = []

    for node in cmdx.selection(type=("transform", "rdRigid", "rdControl")):
        actor = node

        if actor.isA(cmdx.kTransform):
            actor = node.shape(type=("rdRigid", "rdControl"))

        if not actor:
            log.warning("%s was not a rdRigid or rdControl" % node)
            continue

        mesh = commands.convert_to_polygons(actor)
        meshes += [mesh.parent().path()]

    if meshes:
        cmds.select(meshes)
        log.info("Converted %d rigids to polygons" % len(meshes))
        return kSuccess
    else:
        return log.warning("Nothing converted")


def normalise_shapes(selection=None):
    selection = selection or cmdx.selection()

    if not selection:
        return log.warning("Select root of hierarchy to normalise it")

    root = selection[0]

    if root.isA(cmdx.kShape):
        root = root.parent()

    commands.normalise_shapes(root)

    return kSuccess


@with_exception_handling
def combine_scenes(selection=None):
    scenes = _filtered_selection("rdScene")

    if not scenes or len(scenes) < 2:
        raise i__.UserWarning(
            "Invalid selection",
            "Select two or more scene to combine them into one."
        )

    old_scenes = ", ".join(s.name() for s in scenes[1:])
    master = commands.combine_scenes(scenes)
    log.info("Successfully combined %s into %s" % (old_scenes, master))

    return kSuccess


@with_exception_handling
def extract_from_scene(selection=None):
    rigids = _filtered_selection("rdRigid")

    if not rigids:
        raise i__.UserWarning(
            "Invalid selection",
            "Select one or more rigids to extract from its scene."
        )

    count = len(rigids)
    scene = commands.extract_from_scene(rigids)
    cmds.select(str(scene.parent()))
    log.info("Successfully extracted %d rigids into %s" % (count, scene))
    return kSuccess


@with_exception_handling
def move_to_scene(selection=None):
    rigids = _filtered_selection("rdRigid")
    scenes = _filtered_selection("rdScene")

    if not rigids:
        raise i__.UserWarning(
            "Invalid selection",
            "Select one or more rigids to move into scene."
        )

    if not scenes or len(scenes) != 1:
        raise i__.UserWarning(
            "Invalid selection",
            "Select one scene to move rigids into."
        )

    count = len(rigids)
    scene = commands.move_to_scene(rigids, scenes[0])
    log.info("Successfully moved %d rigids into %s" % (count, scene))
    return kSuccess


def multiply_selected(selection=None):
    rigids = _filtered_selection("rdRigid")
    constraints = _filtered_selection("rdConstraint")

    if not rigids and not constraints:
        return False

    selected_channels = _selected_channels()
    multipliers = []
    if rigids:
        multipliers += [commands.multiply_rigids(
            rigids, channels=selected_channels
        )]
    if constraints:
        multipliers += [commands.multiply_constraints(
            constraints, channels=selected_channels
        )]

    cmds.select(list(map(str, multipliers)))

    return kSuccess


def multiply_rigids(selection=None):
    rigids = _filtered_selection("rdRigid")

    if not rigids:
        return False

    selected_channels = _selected_channels()
    mult = commands.multiply_rigids(
        rigids, channels=selected_channels
    )

    cmds.select(str(mult))

    return kSuccess


def multiply_constraints(selection=None):
    constraints = _filtered_selection("rdConstraint")

    if not constraints:
        return False

    selected_channels = _selected_channels()

    mult = commands.multiply_constraints(
        constraints, channels=selected_channels
    )

    cmds.select(str(mult))

    return kSuccess


def freeze_evaluation(selection=None, **opts):
    opts = dict({
        "freeze": _opt("freezeEvaluation", opts),
        "includeHierarchy": _opt("freezeEvaluationHierarchy", opts),
        "shapesOnly": _opt("freezeEvaluationShapesOnly", opts),
    }, **(opts or {}))

    selection = cmdx.selection()

    if opts["includeHierarchy"]:
        for transform in cmdx.selection(type="dagNode"):
            selection.extend(transform.descendents())

    with cmdx.DGModifier() as mod:
        for node in set(selection):

            if node.isA(cmdx.kShape) or not opts["shapesOnly"]:
                mod.set_attr(node["frozen"], opts["freeze"])

            if node.type() == "rdRigid":
                other = node["enabled"].input(plug=True)
                mod.disconnect(node["enabled"], other)
                mod.do_it()
                mod.set_attr(node["enabled"], not opts["freeze"])

    return kSuccess


def unfreeze_evaluation(selection=None, **opts):
    opts["freezeEvaluation"] = False
    return freeze_evaluation(selection, **opts)


def select_invalid_constraints(selection=None, **opts):
    """Select constraints without a valid rigid body

    Sometimes constraints get disconnected from their rigid bodies.
    These should ideally be automatically deleted, but sometimes are not.

    """

    invalid = []

    for con in cmdx.ls(type="rdConstraint"):
        if not con["childRigid"].input():
            invalid.append(str(con))

        if not con["parentRigid"].input():
            invalid.append(str(con))

    cmds.select(deselect=True)

    if invalid:
        cmds.select(invalid)
    else:
        log.warning("No invalid constraints found")

    return kSuccess


#
# User Interface
#


def show_explorer(selection=None):
    if not json.loads(cmds.ragdollDump()):
        return

    def get_fresh_dump(*args, **kwargs):
        return json.loads(cmds.ragdollDump(*args, **kwargs))

    if ui.Explorer.instance and ui.isValid(ui.Explorer.instance):
        return ui.Explorer.instance.show()

    win = ui.Explorer(parent=ui.MayaWindow())
    win.load(get_fresh_dump)
    win.show(dockable=True)


def _last_command():
    """Store repeatable command at module-level

    This assumes no threading happens.

    """

    _last_command._func()


def repeatable(func):
    """Make `func` repeatable in Maya

    See https://groups.google.com/g/python_inside_maya
               /c/2GO5PGD6Q6w/m/U-97zyB_DAAJ

    """

    @functools.wraps(func)
    def repeatable_wrapper(*args, **kwargs):
        _last_command._func = func

        command = 'python("import {0};{0}._last_command()")'.format(__name__)
        result = func()

        try:
            cmds.repeatLast(
                addCommand=command,
                addCommandLabel=func.__name__
            )
        except Exception:
            pass

        return result
    return repeatable_wrapper


def welcome_user(*args):
    if ui.SplashScreen.instance and ui.isValid(ui.SplashScreen.instance):
        return ui.SplashScreen.instance.show()

    parent = ui.MayaWindow()
    win = ui.SplashScreen(parent)
    win.show()
    win.activateWindow()

    # Maya automatically centers new windows,
    # sometimes. On some platforms. Trust no one.
    ui.center_window(win)

    return win


def open_physics(selection=None):
    pass


def open_physics_options(selection=None):
    pass


@with_exception_handling
def export_physics(selection=None, **opts):

    # Initialise start and next frames of each scene
    current_time = cmds.currentTime(query=True)
    for scene in cmdx.ls(type="rdScene"):
        start_time = scene["startTime"].asTime().value
        cmds.currentTime(start_time)
        cmds.currentTime(start_time + 1)
    cmds.currentTime(current_time)

    data = cmds.ragdollDump()
    data = json.loads(data)

    if not data["entities"]:
        return log.error("Nothing to export")

    from PySide2 import QtWidgets
    fname, suffix = QtWidgets.QFileDialog.getSaveFileName(
        ui.MayaWindow(),
        "Export Ragdoll Scene",
        os.path.dirname(options.read("exportPath")),
        "Ragdoll scene files (*.rag)"
    )

    if not fname:
        return cmds.warning("Cancelled")

    fname = os.path.normpath(fname)

    # Include optional thumbnail
    data["ui"] = {

        # Guarantee forward-slash for paths, on all OSes
        "filename": fname.replace("\\", "/"),

        "description": "",
    }

    if _opt("exportIncludeThumbnail", opts):
        thumbnail = ui.view_to_pixmap()
        b64 = ui.pixmap_to_base64(thumbnail)
        data["ui"]["thumbnail"] = b64.decode("ascii")

    try:
        dump.export(fname, data=data)
    except Exception:
        _print_exception()
        return log.warning("Could not export %s" % fname)

    # Update any currently opened Import UI
    for title, widget in __.widgets.items():
        if not isinstance(widget, ui.ImportOptions):
            continue

        if not ui.isValid(widget):
            continue

        log.warning("Updating currently opened Import UI")
        widget.on_path_changed(force=True)

    options.write("exportPath", fname)
    log.info(
        "Successfully exported to %s in %.2f ms"
        % (fname, data["info"]["serialisationTimeMs"])
    )

    return True


@with_exception_handling
def import_physics_from_file(selection=None, **opts):
    from PySide2 import QtWidgets
    fname, suffix = QtWidgets.QFileDialog.getOpenFileName(
        ui.MayaWindow(),
        "Import Ragdoll Scene",
        os.path.dirname(options.read("importPath")),
        "Ragdoll scene files (*.rag)"
    )

    if not fname:
        return cmds.warning("Cancelled")

    fname = os.path.normpath(fname)
    loader = dump.Loader()

    try:
        loader.read(fname)
    except Exception:
        _print_exception()
        return log.error("Could not read from %s" % fname)

    method = _opt("importMethod", opts)

    try:
        if method == "Load":
            merge = _opt("importMergePhysics", opts)
            loader.load(merge=merge)
        else:
            loader.reinterpret()

    except Exception:
        _print_exception()
        return log.error("Could not load %s" % fname)

    options.write("importPath", fname)
    log.info("Successfully imported %s" % fname)

    return True


def _Arg(var, label=None, callback=None):
    var = __.optionvars[var]
    var = copy.deepcopy(var)  # Allow edits to internal lists etc.

    # Special case
    if var["name"] == "solver":
        scenes = [n.shortestPath() for n in cmdx.ls(type="rdScene")]
        var["items"] = scenes + ["Create new solver"]
        var["default"] = 0
        var["initial"] = None  # Always prefer the latest created scene

        __.solvers = scenes

        options.write(var)  # Update this whenever the window is shown

    if label is not None:
        var["label"] = label

    # Restore persistent values, from Maya preferences
    optionvar = options.read(var)
    if optionvar is not None:
        var["initial"] = optionvar

    # Used elsewhere
    _ = var.pop("arg", var["name"])

    depends = var.pop("depends", [])
    for dependency in depends:
        pass

    cls = getattr(qargparse, var.pop("type"))
    arg = cls(**var)

    if callback is not None:
        arg.changed.connect(callback)

    return arg


def _Window(key, command=None, cls=None):
    parent = ui.MayaWindow()
    menuitem = __.menuitems[key]
    args = map(_Arg, menuitem.get("options", []))

    win = (cls or ui.Options)(
        key,
        args,
        command=repeatable(command) if command else None,
        icon=_resource("icons", menuitem["icon"]),
        description=menuitem["summary"],
        media=menuitem.get("media", []),
        parent=parent
    )

    # On Windows, windows typically spawn in the
    # center of the screen. On Linux? Flip a coin.
    ui.center_window(win)

    win.show()

    return win


def global_preferences(*args):
    def callback():
        from maya import cmds
        ctime = cmds.currentTime(query=True)
        cmds.evalDeferred(lambda: cmds.currentTime(ctime, update=True))

    def global_preferences():
        pass

    window = _Window("globalPreferences", global_preferences)

    # Update viewport immediately whenever this changes
    scale = window.parser.find("scale")
    scale.changed.connect(callback)

    return window


def save_preferences(*args):
    options.save()
    log.info("Successfully saved Ragdoll preferences")


def reset_preferences(*args):
    options.reset()
    log.info("Successfully reset Ragdoll preferences")


def create_rigid_options(*args):
    window = _Window("activeRigid", create_active_rigid)
    return window


def create_chain_options(*args):
    window = _Window("activeChain", create_active_chain)
    return window


def create_passive_options(selection=None):
    window = _Window("passiveRigid", create_passive_rigid)
    return window


def convert_constraint_options(*args):
    window = _Window("convertConstraint", convert_constraint)
    return window


def convert_rigid_options(*args):
    window = _Window("convertRigid", convert_rigid)
    return window


def bake_simulation_options(*args):
    window = _Window("bakeSimulation", bake_simulation)
    return window


def _constraint_options(typ):
    def _create_constraint_options(*args):
        # Preselect whatever the user picked
        options.write("constraintType", typ)
        window = _Window("constraint", create_constraint)
        return window

    return _create_constraint_options


def freeze_evaluation_options(*args):
    options.write("freezeEvaluation", True)
    return _Window("freezeEvaluation", freeze_evaluation)


def unfreeze_evaluation_options(*args):
    options.write("freezeEvaluation", False)
    return _Window("freezeEvaluation", freeze_evaluation)


def create_hard_pin_options(*args):
    return _Window("hardPin", create_hard_pin)


def replace_mesh_options(*args):
    return _Window("replaceMesh", replace_mesh)


def create_soft_pin_options(*args):
    return _Window("softPin", create_soft_pin)


def create_push_force_options(*args):
    return _Window("push", create_push_force)


def create_pull_force_options(*args):
    return _Window("pull", create_pull_force)


def create_uniform_force_options(*args):
    return _Window("directional", create_uniform_force)


def create_turbulence_force_options(*args):
    return _Window("wind", create_turbulence_force)


def create_mimic_options(*args):
    return _Window("mimic", create_mimic)


def multiply_rigids_options(*args):
    return _Window("multiplyRigids", multiply_rigids)


def multiply_selected_options(*args):
    return _Window("multiplySelected", multiply_selected)


def edit_shape_options(*args):
    return _Window("editShape", edit_shape)


def multiply_constraints_options(*args):
    return _Window("multiplyConstraints", create_turbulence_force)


def create_animation_constraint_options(selection=None, **opts):
    return _Window("animationConstraint", create_animation_constraint)


def create_character_options(*args):
    window = _Window("character", create_character)

    # Create dependencies between arguments
    control = window.parser.find("characterControl")
    copy = window.parser.find("characterCopy")
    control["condition"] = copy.read

    return window


def create_muscle_options(*args):
    return _Window("muscle", create_muscle)


def create_dynamic_control_options(*args):
    return create_chain_options()


def set_initial_state_options(*args):
    return _Window("setInitialState", set_initial_state)


def clear_initial_state_options(*args):
    return _Window("clearInitialState", clear_initial_state)


def delete_physics_options(*args):
    return _Window("deleteAllPhysics", delete_physics)


def import_physics_options(*args):
    win = None

    def import_physics():
        return win.do_import()

    win = _Window("importPhysics", import_physics, cls=ui.ImportOptions)
    ui.center_window(win)
    win.resize(ui.px(1100), ui.px(560))

    return win


def export_physics_options(*args):
    return _Window("exportPhysics", export_physics)


def show_constraint_editor(selection=None):
    window = ui.PivotEditor(parent=ui.MayaWindow())
    tools.show_pivot_editor(window)


# Backwards compatibility
create_rigid = create_active_rigid
create_collider = create_passive_rigid
