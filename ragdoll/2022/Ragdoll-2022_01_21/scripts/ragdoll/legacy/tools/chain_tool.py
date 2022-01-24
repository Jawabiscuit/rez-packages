"""Support for chains and trees

Animators can either author rigid bodies and constrain these. Or, they could
select a chain of controls and generate a rigid body chain from that. With a
chain, we're better equipt to generate appropriate collision geometry and
can automatically figure out constraints and limits based on order of
selection, locked channels and leverage the angle between controls to
figure out the constraint frames.

- Single
- Chain
- Tree
- Network

"""

from ...vendor import cmdx
from ... import constants as c, internal as i__
from .. import commands


class Chain(object):
    """Create and manipulate a series of connected rigid bodies

    Arguments:
        links (list): Transforms and/or shapes for which to generate a chain

    """

    def __init__(self, links, scene, opts=None):
        assert isinstance(links, (list, tuple)), "links was not a list"
        assert links, "links was empty"

        opts = opts or {}
        opts = dict({
            "autoKey": False,
            "blendMethod": c.SteppedBlendMethod,
            "computeMass": False,
            "autoMultiplier": True,
            "passiveRoot": True,
            "autoLimits": False,
            "addUserAttributes": True,
        }, **opts)

        opts["defaults"] = dict({
            "shapeType": c.CapsuleShape,
            "drawShaded": False,
        }, **opts.get("defaults", {}))

        self._new_rigids = []
        self._new_constraints = []
        self._new_userattrs = []
        self._new_multipliers = []

        self._scene = scene
        self._cache = {}
        self._opts = opts
        self._pre_flighted = False

        # Separate input into transforms and (optional) shapes
        self._pairs = []

        transforms = []
        for index, link in enumerate(links):
            if isinstance(link, i__.string_types):
                link = cmdx.encode(link)

            assert isinstance(link, cmdx.DagNode), type(link)

            # Only the root is allowed to have a pre-existing rigid
            if index > 0:
                assert not link.shape(type="rdRigid"), (
                    "%s already has a rigid" % link
                )

            if link.isA(cmdx.kShape):
                transform = link.parent()
                shape = link

            else:
                # Supported shapes, in order of preference
                transform = link
                shape = link.shape(type=("mesh",
                                         "nurbsCurve",
                                         "nurbsSurface"))

            transforms.append(transform)
            self._pairs.append((transform, shape))

        # Find the root, which must not be a shape
        self._root = self._pairs[0]
        self._children = transforms[1:]

        # Traverse the tree to find the true root
        self._tree_root = self._find_root()

    def pre_flight(self):
        """Before doing anything, make sure the basics are accounted for"""

        def check_already_chain():
            """In case a user runs the command twice on the same input"""
            all_are_already_rigids = True
            for transform, _ in self._pairs:
                if not transform.shape(type="rdRigid"):
                    all_are_already_rigids = False
                    break

            assert not all_are_already_rigids, (
                "Every transform is already dynamic"
            )

        def check_hierarchy():
            """Ensure incoming chain reflects a physical hierarchy

            For example, this is what a valid selection looks like,
            including a non-selected offset group that is still part
            of the hierarchy.

            o- clavicle
             |-o upperArm
               |-o lowerArm
                 |-o ( offsetGroup )
                   |-o hand

            """

            pairs = self._pairs[:]
            while pairs:
                transform, _ = pairs.pop()
                expected_parent, _ = pairs[-1] if pairs else (None, None)

                if not expected_parent:
                    break

                # Walk up the hierarchy until you find what
                # is supposed to be the parent.
                #
                #                   .
                #  |--o a          /|\
                #     |--o B        |
                #        |--o c     |
                #           |--o d  |
                #                   |
                #
                valid = False
                for parent in transform.lineage():
                    if parent == expected_parent:
                        valid = True
                        break

                problem = (
                    "%s was not a parent of %s" % (
                        expected_parent, transform)
                )

                # Ok, so the prior link isn't a parent, but we
                # also must make it isn't a child of the subsequent
                # link, as that would mean a cycle
                #
                #                   |
                #  |--o a           |
                #     |--o B        |
                #        |--o c     |
                #           |--o d  |
                #                  \ /
                #                   `
                if not valid:
                    is_child = False
                    for child in transform.descendents():
                        if child == expected_parent:
                            is_child = True
                            break

                    # It's valid if the Maya parent isn't a Ragdoll child
                    valid = not is_child

                    # This flips the problem on its head
                    problem = (
                        "%s cannot be a child of %s, that's a cycle" % (
                            expected_parent, transform)
                    )

                assert valid, problem

        def pre_cache():
            """Pre-cache attributes to avoid needless evaluation"""
            for transform, _ in self._pairs:
                world_matrix = transform["worldMatrix"][0].asMatrix()
                parent_matrix = transform["parentMatrix"][0].asMatrix()
                matrix = transform["matrix"].asMatrix()
                translate = transform["translate"].as_vector()
                rotate = transform["rotate"].as_euler()

                if "jointOrient" in transform:
                    joint_orient = transform["jointOrient"].as_quaternion()
                else:
                    # Only joints have these
                    joint_orient = cmdx.Quaternion()

                self._cache[(transform, "worldMatrix")] = world_matrix
                self._cache[(transform, "parentMatrix")] = parent_matrix
                self._cache[(transform, "matrix")] = matrix
                self._cache[(transform, "translate")] = translate
                self._cache[(transform, "rotate")] = rotate
                self._cache[(transform, "jointOrient")] = joint_orient

        def remember_existing_inputs():
            # Remember existing animation
            for transform, _ in self._pairs:
                transform.data["priorConnections"] = {}
                for channel in ("translate", "rotate"):
                    for axis in "XYZ":
                        src = transform[channel + axis]
                        src = src.connection(plug=True, destination=False)

                        if src is not None:
                            anim = transform.data["priorConnections"]
                            dst = "in%s%s1" % (channel.title(), axis)
                            anim[src] = dst

        check_already_chain()
        check_hierarchy()
        remember_existing_inputs()
        pre_cache()

        return True

    def _find_root(self):
        """Traverse the rigid network in search for the true root"""
        transform, shape = self._pairs[0]

        # It'll be the one with a multiplier node, if one exists
        mult = transform.shape("rdConstraintMultiplier")

        if not mult:
            con = transform.shape("rdConstraint")

            if con is not None:
                mult = con["multiplierNode"].connection(
                    type="rdConstraintMultiplier")

        if mult and "simulated" in mult.parent():
            # We're in a tree, use tree root as real root
            transform = mult.parent()
            shape = transform.shape(type=("mesh",
                                          "nurbsCurve",
                                          "nurbsSurface"))

        assert not transform.isA(cmdx.kShape), transform
        assert transform.isA(cmdx.kTransform), transform
        assert not shape or shape.isA(cmdx.kShape), shape

        return transform, shape

    def do_it(self):
        self._new_rigids[:] = []
        self._new_constraints[:] = []
        self._new_multipliers[:] = []
        self._new_userattrs[:] = []

        # May be called ahead of time by the user
        if not self._pre_flighted:
            self.pre_flight()
            self._pre_flighted = True

        self._do_all()

        return (
            self._new_rigids +
            self._new_constraints +
            self._new_multipliers
        )

    def _do_all(self):
        tree_root_transform, tree_root_shape = self._tree_root
        tree_root_rigid = tree_root_transform.shape(type="rdRigid")

        # Root
        if not tree_root_rigid:
            with cmdx.DagModifier() as mod:
                tree_root_rigid = self._make_root(mod,
                                                  tree_root_transform,
                                                  tree_root_shape)

        self._make_simulated_attr(tree_root_rigid, tree_root_transform)

        # Links
        root_transform, root_shape = self._root
        root_rigid = root_transform.shape(type="rdRigid")

        # Always start off with the root
        self._new_rigids.append(root_rigid)

        with cmdx.DagModifier() as mod:
            previous_rigid = root_rigid
            for transform, shape in self._pairs[1:]:
                previous_rigid = self._do_one(mod,
                                              transform,
                                              shape,
                                              previous_rigid)

        with cmdx.DGModifier() as dgmod:
            self._auto_blend(dgmod)

            if self._opts["autoMultiplier"]:
                self._auto_multiplier(dgmod)

        if self._opts["addUserAttributes"]:
            for userattr in self._new_userattrs:
                userattr.do_it()

        # Link rigid enabled to `simulated` attribute
        with cmdx.DagModifier() as mod:
            for rigid in self._new_rigids:
                mod.connect(tree_root_transform["simulated"],
                            rigid["enabled"])

        # Store what the user intended for use as a root (for import)
        with cmdx.DagModifier() as mod:
            mod.set_attr(root_rigid["isRoot"], True)

    def _do_one(self, mod, transform, shape, previous_rigid):
        assert transform and transform.isA(cmdx.kTransform), transform
        assert shape is None or shape.isA(cmdx.kShape), shape
        assert previous_rigid and previous_rigid.type() == "rdRigid"

        rigid = transform.shape(type="rdRigid")

        # Handle branching
        #
        #  o
        #   \          o
        #    \        /
        #     o------o
        #     |       \
        #     |        o---o
        #     o
        #
        if rigid is not None:
            rigid = commands.convert_rigid(rigid, passive=False)

        else:
            rigid = self._make_rigid(mod, transform, shape)

            # Add header to newly created rigid
            transform_attrs = i__.UserAttributes(rigid, transform)
            transform_attrs.add_divider("Ragdoll")
            transform_attrs.add("mass")

            self._new_userattrs += [transform_attrs]

        # Figure out hierarchy
        #
        #               |
        #               v
        #     o---------o---------o
        # previous            subsequent
        #
        #
        index = self._children.index(transform)
        count = len(self._children)
        previous = self._children[index - 1] if index > 0 else self._root[0]
        subsequent = self._children[index + 1] if index < count - 1 else None

        # Joints are special.
        #
        # The user expects it to face in the direction
        # of its immediate joint transform, if any, even
        # if the actual axis is all messed up.
        #
        # o     o<>----o
        #  \   /
        #   \ /
        #    o
        #
        if not subsequent and transform.type() == "joint":
            subsequent = transform.child(type="joint")

        # Transfer geometry into rigid, if any
        #
        #     ______                ______
        #    /\    /|              /     /|
        #   /  \  /.|   ------>   /     / |
        #  /____\/  |            /____ /  |
        #  |\   | . |            |    |   |
        #  | \  |  /             |    |  /
        #  |  \ |./              |    | /
        #  |___\|/               |____|/
        #
        #
        # No need to compute geometry twice
        #
        # TODO(marcus): There is actually a deeper problem here.
        # On computing the child geometry *after* a parent,
        # we're inexplicably evaluating a new position for
        # the child as a result of it now being driven by
        # a dynamic parent. What *should* happen is pre-caching
        # all transforms involved, and computing based solely
        # on this information.
        #

        if not subsequent and previous.has_attr("_rdGeometry"):
            geo = i__.Geometry()
            geo.load(previous["_rdGeometry"].read())

        else:
            geo = commands.infer_geometry(
                transform,
                parent=previous,
                children=[subsequent] if subsequent else False
            )

        # Cache for reuse
        if not transform.has_attr("_rdGeometry"):
            mod.add_attr(transform, cmdx.String("_rdGeometry"))
            mod.do_it()

        mod.set_attr(transform["_rdGeometry"], geo.dump())

        # Clean this up when it's all over
        index = rigid["userAttributes"].next_available_index()
        mod.connect(transform["_rdGeometry"],
                    rigid["userAttributes"][index])

        mod.set_attr(rigid["shapeExtents"], geo.extents)
        mod.set_attr(rigid["shapeLength"], geo.length)
        mod.set_attr(rigid["shapeRadius"], geo.radius)
        mod.set_attr(rigid["shapeRotation"], geo.shape_rotation)
        mod.set_attr(rigid["shapeOffset"], geo.shape_offset)

        for key, value in self._opts["defaults"].items():
            mod.set_attr(rigid[key], value)

        # `shapeLength` is used during constraint creation,
        # to figure out draw scale
        mod.do_it()

        con = commands.socket_constraint(previous_rigid, rigid, opts={
            "name": "rPoseConstraint"
        })

        # Rigids will overlap per default
        mod.set_attr(con["disableCollision"], True)

        if self._opts["autoLimits"]:
            fourtyfive = cmdx.radians(45)
            mod.set_attr(con["angularLimitX"], fourtyfive)
            mod.set_attr(con["angularLimitY"], fourtyfive)
            mod.set_attr(con["angularLimitZ"], fourtyfive)
        else:
            mod.set_attr(con["angularLimitX"], 0)
            mod.set_attr(con["angularLimitY"], 0)
            mod.set_attr(con["angularLimitZ"], 0)

        aim = None
        up = None

        if subsequent:
            aim = subsequent.translation(cmdx.sWorld)

        if previous:
            up = previous.translation(cmdx.sWorld)

        commands.orient(con, aim=aim, up=up)

        # Let the user manually add these, if needed
        mod.set_attr(con["driveStrength"], 0.5)

        # Record hierarchical relationship, for articulations
        mod.connect(previous_rigid["ragdollId"], rigid["parentRigid"])

        # Forward some convenience attributes
        constraint_attrs = i__.UserAttributes(con, transform)
        constraint_attrs.add("driveStrength", nice_name="Pose Strength")
        constraint_attrs.add("angularDriveStiffness", nice_name="Stiffness")
        constraint_attrs.add("angularDriveDamping", nice_name="Damping")

        self._new_rigids += [rigid]
        self._new_constraints += [con]
        self._new_userattrs += [constraint_attrs]

        return rigid

    def _add_pairblend(self, dgmod, rigid, transform):
        """Put a pairBlend between `rigid` and `transform`

         ________________          ___________
        |                |        |           |
        | originalInput  o--------o           |
        |________________|        |           |
                                  |           |
                                  | pairBlend o------>
         ________________         |           |
        |                |        |           |
        | simulation     o--------o           |
        |________________|        |___________|


        """

        assert isinstance(dgmod, cmdx.DGModifier)

        pair_blend = dgmod.create_node("pairBlend")
        dgmod.set_attr(pair_blend["isHistoricallyInteresting"], False)

        # Establish initial values, before keyframes
        # tm = cmdx.Tm(self._cache[(transform, "matrix")])

        # Read from matrix, as opposed to the rotate/translate channels
        # to account for jointOrient, pivots and all manner of things
        # translate = tm.translation()
        # rotate = tm.rotation()

        translate = self._cache[(transform, "translate")]
        rotate = self._cache[(transform, "rotate")]

        dgmod.set_attr(pair_blend["inTranslate1"], translate)
        dgmod.set_attr(pair_blend["inRotate1"], rotate)

        dgmod.connect(rigid["outputTranslateX"], pair_blend["inTranslateX2"])
        dgmod.connect(rigid["outputTranslateY"], pair_blend["inTranslateY2"])
        dgmod.connect(rigid["outputTranslateZ"], pair_blend["inTranslateZ2"])
        dgmod.connect(rigid["outputRotateX"], pair_blend["inRotateX2"])
        dgmod.connect(rigid["outputRotateY"], pair_blend["inRotateY2"])
        dgmod.connect(rigid["outputRotateZ"], pair_blend["inRotateZ2"])

        # Let the animator see the raw animation values, no physics
        dgmod.connect(self._tree_root[0]["simulated"], pair_blend["weight"])

        if self._opts["autoKey"]:
            # Generate default animation curves, it's expected since you can no
            # longer see whether channels are keyed or not, now being green.
            time = cmdx.currentTime()
            mapping = (
                ("animCurveTL", translate.x, "inTranslateX1"),
                ("animCurveTL", translate.y, "inTranslateY1"),
                ("animCurveTL", translate.z, "inTranslateZ1"),
                ("animCurveTA", rotate.x, "inRotateX1"),
                ("animCurveTA", rotate.y, "inRotateY1"),
                ("animCurveTA", rotate.z, "inRotateZ1")
            )

            for curve, value, dst in mapping:
                curve = dgmod.create_node(curve)
                curve.key(time, value)
                dgmod.connect(curve["output"], pair_blend[dst])

        # Transfer existing animation/connections
        for src, dst in transform.data.get("priorConnections", {}).items():
            dst = pair_blend[dst]
            dgmod.connect(src, dst)

        commands._connect_transform(dgmod, pair_blend, transform)

        return pair_blend

    def _auto_blend(self, dgmod):
        """Add a `Simulated` attribute to new links

        """

        assert isinstance(dgmod, cmdx.DGModifier)

        root, _ = self._root
        root_rigid = root.shape(type="rdRigid")

        for rigid in self._new_rigids:

            # Don't bother with the root
            if rigid == root_rigid:
                continue

            transform = rigid.parent()
            blend = self._add_pairblend(dgmod, rigid, transform)
            self._auto_influence(dgmod, rigid, blend)

    def _auto_influence(self, mod, rigid, pair_blend):
        """Treat incoming animation as guide constraint

         ___________
        |           |              ______________
        o           |             |              |
        |           |             |              |
        | pairBlend o-------------o .driveMatrix |
        |           |             |              |
        o           |             |______________|
        |___________|


        """

        constraint = rigid.sibling(type="rdConstraint")

        # This is fine (but what does it mean? :O )
        if not constraint:
            return

        def bake_joint_orient(mat, orient):
            """Bake jointOrient values

            Such that keyframes can be made without
            taking those into account. E.g. a joint with 0 rotate
            but 45 degrees of jointOrient should only require a key
            with 0 degrees.

            """

            assert isinstance(mat, cmdx.om.MMatrix)
            assert isinstance(orient, cmdx.om.MQuaternion)

            mat_tm = cmdx.om.MTransformationMatrix(mat)
            new_quat = mat_tm.rotation(asQuaternion=True) * orient
            mat_tm.setRotation(new_quat)

            return mat_tm.asMatrix()

        transform = rigid.parent()

        joint_orient = self._cache[(transform, "jointOrient")]

        # pairBlend directly feeds into the drive matrix
        compose = mod.create_node("composeMatrix", name="composePairBlend")
        mod.connect(pair_blend["inTranslate1"], compose["inputTranslate"])
        mod.connect(pair_blend["inRotate1"], compose["inputRotate"])
        mod.connect(transform["rotateOrder"], compose["inputRotateOrder"])

        # A drive is relative the parent frame, but the pairblend is relative
        # the parent Maya transform. In case these are not the same, we'll
        # map the pairblend into the space of the parent frame.
        parent_rigid = constraint["parentRigid"].connection()

        # Could be connected to a scene too
        if parent_rigid.type() != "rdRigid":
            return

        relative = mod.create_node("multMatrix", name="makeRelative")

        # From this space..
        parent_transform_matrix = rigid["inputParentInverseMatrix"].asMatrix()
        parent_transform_matrix = parent_transform_matrix.inverse()

        # To this space..
        parent_rigid_matrix = parent_rigid["cachedRestMatrix"].asMatrix()
        parent_rigid_matrix = parent_rigid_matrix.inverse()

        total_matrix = parent_transform_matrix * parent_rigid_matrix
        total_matrix = bake_joint_orient(total_matrix, joint_orient)

        mod.connect(compose["outputMatrix"], relative["matrixIn"][0])
        mod.set_attr(relative["matrixIn"][1], total_matrix)

        mod.connect(relative["matrixSum"], constraint["driveMatrix"])

        # Keep channel box clean
        mod.set_attr(compose["isHistoricallyInteresting"], False)
        mod.set_attr(relative["isHistoricallyInteresting"], False)

    def _auto_multiplier(self, dgmod):
        r"""Multiply provided `constraints`

        o     o     o
         \    |    /
          \   |   /
           o  |  o------o
            \ | /
             \|/
              |
              o  <-- Tree root

        """

        assert self._new_constraints and all(
            con.type() == "rdConstraint" for con in self._new_constraints
        )

        root, _ = self._tree_root

        # Use existing multiplier, if any, to support branching
        mult = root.shape("rdConstraintMultiplier")

        if not mult:
            con = root.shape("rdConstraint")

            if con is not None:
                mult = con["multiplierNode"].connection(
                    type="rdConstraintMultiplier")

        if mult:
            for constraint in self._new_constraints:
                dgmod.connect(mult["ragdollId"], constraint["multiplierNode"])

        else:
            # There isn't any, let's make one
            opts_ = {"name": i__.unique_name("rGlobalStrength")}
            mult = commands.multiply_constraints(self._new_constraints,
                                                 parent=root,
                                                 opts=opts_)

            # Forward some convenience attributes
            multiplier_attrs = i__.UserAttributes(mult, root)
            multiplier_attrs.add("driveStrength",
                                 long_name="globalStrength",
                                 nice_name="Global Strength")

            self._new_multipliers.append(mult)
            self._new_userattrs += [multiplier_attrs]

        return mult

    def _make_simulated_attr(self, rigid, transform):
        if "simulated" not in transform:
            with cmdx.DGModifier() as dgmod:
                if self._opts["blendMethod"] == c.SmoothBlendMethod:
                    dgmod.add_attr(transform, cmdx.Double(
                        "simulated",
                        min=0.0,
                        max=1.0,
                        keyable=True,
                        default=True)
                    )
                else:
                    dgmod.add_attr(transform, cmdx.Boolean(
                        "simulated",
                        keyable=True,
                        default=True)
                    )

                dgmod.doIt()

                index = rigid["userAttributes"].next_available_index()
                dgmod.connect(transform["simulated"],
                              rigid["userAttributes"][index])

        if "notSimulated" not in transform:
            with cmdx.DGModifier() as dgmod:
                dgmod.add_attr(transform, cmdx.Boolean(
                    "notSimulated", keyable=False)
                )

                dgmod.doIt()

                index = rigid["userAttributes"].next_available_index()
                dgmod.connect(transform["notSimulated"],
                              rigid["userAttributes"][index])

                reverse = dgmod.create_node("reverse")

                dgmod.doIt()

                dgmod.set_attr(reverse["isHistoricallyInteresting"], False)
                dgmod.connect(transform["simulated"],
                              reverse["inputX"])
                dgmod.connect(reverse["outputX"],
                              transform["notSimulated"])

    def _make_root(self, mod, transform, shape):
        root_rigid = self._make_rigid(
            mod, transform, shape, passive=self._opts["passiveRoot"]
        )

        if self._opts["passiveRoot"]:
            # Don't collide per default, it's most likely an
            # unsuitable shape for collisions anyway.
            mod.set_attr(root_rigid["collide"], False)

        for key, value in self._opts["defaults"].items():
            mod.set_attr(root_rigid[key], value)

        geo = commands.infer_geometry(
            transform, parent=None, children=[self._children[0]])

        mod.set_attr(root_rigid["shapeLength"], geo.length)
        mod.set_attr(root_rigid["shapeRadius"], geo.radius)
        mod.set_attr(root_rigid["shapeRotation"], geo.shape_rotation)
        mod.set_attr(root_rigid["shapeOffset"], geo.shape_offset)
        mod.set_attr(root_rigid["shapeExtents"], geo.extents)

        transform_attrs = i__.UserAttributes(root_rigid, transform)
        transform_attrs.add_divider("Ragdoll")
        transform_attrs.do_it()

        return root_rigid

    def _make_rigid(self, mod, transform, shape, passive=False):
        rigid = commands._rdrigid(mod, "rRigid", parent=transform)

        # Copy current transformation
        rest = self._cache[(transform, "worldMatrix")]

        mod.set_attr(rigid["cachedRestMatrix"], rest)
        mod.set_attr(rigid["inputMatrix"], rest)
        mod.set_attr(rigid["maxDepenetrationVelocity"], 2000.0)

        commands._add_rigid(mod, rigid, self._scene)

        if shape:
            commands._interpret_shape(mod, rigid, shape)
        else:
            commands._interpret_transform(mod, rigid, transform)

        if passive:
            commands._connect_passive(mod, rigid, transform)
        else:
            commands._connect_active(mod, rigid, transform)

        if self._opts["computeMass"]:
            mod.do_it()  # Ensure shapeExtents is up-to-date
            mass = commands._compute_mass(rigid, self._scene)
            mod.set_attr(rigid["mass"], mass)

        return rigid


@i__.with_undo_chunk
def create(links, scene, opts=None):
    return Chain(links, scene, opts).do_it()
