"""Recreate Maya scene from Ragdoll dump

# Usage Example
import json
dump = cmds.ragdollDump()
dump = json.loads(dump)
dedump(dump)

"""

import re
import json
import copy
import logging

from maya import cmds
from .vendor import cmdx
from . import commands, internal, constants


log = logging.getLogger("ragdoll")


def load(fname, opts=None):
    """Create a Maya scene from an exported Ragdoll file

    New transforms are generated and then assigned Markers.

    """

    loader = Loader(opts)
    loader.read(fname)
    return loader.load()


def reinterpret(fname, opts=None):
    """Recreate Maya scene from exported Ragdoll file

    User-interface attributes like `density` and display settings
    are restored from a file otherwise mostly contains the raw
    simulation data.

    """

    loader = Loader(opts)
    loader.read(fname)
    return loader.reinterpret()


def export(fname=None, data=None):
    """Export everything Ragdoll-related into `fname`

    Arguments:
        fname (str, optional): Write to this file
        data (dict, optional): Export this dictionary instead

    Returns:
        data (dict): Exported data as a dictionary

    """

    # Pull on solver, both at the start and first frame
    # to ensure everything is initialised.
    initial_time = cmdx.current_time()
    for solver in cmdx.ls(type="rdSolver"):
        start_time = solver["_startTime"].as_time()
        cmdx.current_time(start_time)
        solver["startState"].read()
        cmdx.current_time(start_time + 1)
        solver["currentState"].read()
    cmdx.current_time(initial_time)

    data = data or json.loads(cmds.ragdollDump())

    if "ui" not in data:
        data["ui"] = {}

    # Keep filename in the dump
    data["ui"]["filename"] = fname or "Memory"

    if fname is not None:
        with open(fname, "w") as f:
            json.dump(data, f, indent=4, sort_keys=True)

    return data


class Entity(int):
    pass


def Component(comp):
    """Simplified access to component members"""

    data = {}

    for key, value in comp["members"].items():
        if not isinstance(value, dict):
            pass

        elif value["type"] == "Entity":
            value = Entity(value["value"])

        elif value["type"] == "Vector3":
            value = cmdx.Vector(value["values"])

        elif value["type"] == "Color4":
            value = cmdx.Color(value["values"])

        elif value["type"] == "Matrix44":
            value = cmdx.Matrix4(value["values"])

        elif value["type"] == "Path":
            value = value["value"]

        elif value["type"] == "Quaternion":
            value = cmdx.Quaternion(*value["values"])

        else:
            raise TypeError("Unsupported type: %s" % value)

        data[key] = value

    return data


class Registry(object):
    def __init__(self, dump):
        dump = copy.deepcopy(dump)
        dump["entities"] = {

            # Original JSON stores keys as strings, but the original
            # keys are integers; i.e. entity IDs
            Entity(entity): value
            for entity, value in dump["entities"].items()
        }

        self._dump = dump

    def count(self, *components):
        """Return number of entities with this component(s)"""
        return len(list(self.view(*components)))

    def view(self, *components):
        """Iterate over every entity that has all of `components`"""
        for entity in self._dump["entities"]:
            if all(self.has(entity, comp) for comp in components):
                yield entity

    def has(self, entity, component):
        """Return whether `entity` has `component`"""
        assert isinstance(entity, int), "entity must be int"
        assert isinstance(component, cmdx.string_types), (
            "component must be string")
        return component in self._dump["entities"][entity]["components"]

    def get(self, entity, component):
        """Return `component` for `entity`

        Returns:
            dict: The component

        Raises:
            KeyError: if `entity` does not have `component`

        Example:
            >>> s = {}
            >>> dump = cmds.ragdollDump()
            >>> dump["entities"][1] = {"components": {"SceneComponent": s}}
            >>> loader = Loader(dump)
            >>> assert s == loader.component(1, "SceneComponent")

        """

        try:
            return Component(
                self._dump["entities"][entity]["components"][component]
            )

        except KeyError:
            Name = self.get(entity, "NameComponent")
            name = Name["path"] or Name["value"]
            raise KeyError("%s did not have '%s'" % (name, component))

    def components(self, entity):
        """Return *all* components for `entity`"""
        return self._dump["entities"][entity]["components"]


def _name(Name, level=-1):
    return Name["path"].rsplit("|", 1)[level]


def DefaultDump():
    return {
        "schema": Loader.SupportedSchema,
        "entities": {},
        "info": {}
    }


def DefaultState():
    return {

        # Series of solver entities
        "solvers": [],

        # Series of group entities
        "groups": [],

        # Series of markers entities
        "markers": [],

        # Transforms that are already assigned
        "occupied": [],

        # Constraints of all sorts
        "constraints": [],

        # Map entity -> active Maya transform node
        "entityToTransform": {},

        # Markers without a transform
        "missing": [],

        # Paths used to search for each marker
        "searchTerms": {},
    }


class Loader(object):
    """Reconstruct physics from a Ragdoll dump

    A "dump" is the internal data of the Ragdoll plug-in.

    This loader reconstructs a Maya scene such that the results
    are the same as when the dump was originally created.

    Arguments:
        roots (list): Path(s) that the original path must match
        replace (list): Search/replace pairs of strings to find and replace
            in each original path
        overrideSolver (path): Use this solver instead of the one from the file

    """

    SupportedSchema = "ragdoll-1.0"

    def __init__(self, opts=None):
        opts = opts or {}
        opts = dict(opts, **{
            "roots": [],
            "searchAndReplace": ["", ""],
            "namespace": None,
            "preserveAttributes": True,

            "overrideSolver": "",
            "createMissingTransforms": True,
        })

        self._opts = opts

        # Do we need to re-analyse before use?
        self._dirty = True

        # Is the data valid, e.g. no null-entities?
        self._invalid_reasons = []

        # Transient data, updated on changes to fname and filtering
        self._state = DefaultState()

        self._registry = None

        # Original dump
        self._dump = None

        self._current_fname = ""

    def count(self):
        return len(self._state["entityToTransform"])

    @property
    def registry(self):
        return self._registry

    def dump(self):
        return copy.deepcopy(self._dump)

    def edit(self, options):
        self._opts.update(options)
        self._dirty = True

    def read(self, fname):
        self._invalid_reasons[:] = []

        dump = DefaultDump()

        if isinstance(fname, dict):
            # Developer-mode, bypass everything and use as-is
            dump = fname

        else:
            try:
                with open(fname) as f:
                    dump = json.load(f)
                self._current_fname = fname

            except Exception as e:
                error = (
                    "An exception was thrown when attempting to read %s\n%s"
                    % (fname, str(e))
                )

                self._invalid_reasons += [error]

        assert "schema" in dump and dump["schema"] == self.SupportedSchema, (
            "Dump not compatible with this version of Ragdoll"
        )

        self._registry = Registry(dump)
        self._dump = dump
        self._dirty = True

    def is_valid(self):
        return len(self._invalid_reasons) == 0

    def invalid_reasons(self):
        """Return reasons for failure, useful for reporting"""
        return self._invalid_reasons[:]

    def analyse(self):
        """Fill internal state from dump with something we can use"""

        # No need for needless work
        if not self._dirty:
            return self._state

        # Clear previous results
        self._state = DefaultState()

        self._find_constraints()
        self._find_solvers()
        self._find_groups()
        self._find_markers()

        self.validate()

        self._dirty = False
        return self._state

    def validate(self):
        reasons = []
        self._invalid_reasons[:] = reasons

    def report(self):
        if self._dirty:
            self.analyse()

        def _name(entity):
            Name = self._registry.get(entity, "NameComponent")
            return Name["value"]

        solvers = self._state["solvers"]
        groups = self._state["groups"]
        constraints = self._state["constraints"]
        markers = self._state["entityToTransform"]

        if solvers:
            log.info("Solvers:")
            for entity in solvers:
                log.info("  %s.." % _name(entity))

        if groups:
            log.info("Groups:")
            for entity in groups:
                log.info("  %s.." % _name(entity))

        if markers:
            log.info("Markers:")
            for entity, transform in markers.items():
                log.info("  %s -> %s.." % (_name(entity), transform))

        if constraints:
            log.info("Constraints:")
            for entity in constraints:
                log.info("  %s.." % _name(entity))

        if not any([solvers, groups, constraints, markers]):
            log.warning("Dump was empty")

    @internal.with_undo_chunk
    def reinterpret(self, dry_run=False):
        """Interpret dump back into the UI-commands used to create them.

        For example, if two chains were created using the `Active Chain`
        command, then this function will attempt to figure this out and
        call `Active Chain` on the original controls.

        Unlike `load` this method reproduces what the artist did in order
        to author the rigids and constraints. The advantage is closer
        resemblance to newly authored chains and rigids, at the cost of
        less accurately capturing custom constraints and connections.

        Caveat:
            Imports are made using the current version of Ragdoll and its
            tools. Meaning that if a tool - e.g. create_chain - has been
            updated since the export was made, then the newly imported
            physics will be up-to-date but not necessarily the same as
            when it got exported.

        """

        # In case the user forgot or didn't know
        if self._dirty:
            self.analyse()

        if dry_run:
            return self.report()

        if not self.is_valid():
            return log.error("Dump not valid")

        if self._opts["createMissingTransforms"]:
            self._create_missing_transforms()

        rdsolvers = self._create_solvers()
        rdgroups = self._create_groups(rdsolvers)
        rdmarkers = self._create_markers(rdgroups, rdsolvers)
        rdconstraints = self._create_constraints(rdmarkers)

        self._dirty = True
        log.info("Done")

        return {
            "solvers": rdsolvers.values(),
            "groups": rdgroups.values(),
            "markers": rdmarkers.values(),
            "constraints": rdconstraints.values(),
        }

    def _create_missing_transforms(self):
        missing = self._state["missing"]

        if not missing:
            return

        log.info("Creating missing transforms..")

        with cmdx.DagModifier() as mod:
            for entity in missing:
                MarkerUi = self._registry.get(entity, "MarkerUIComponent")
                Rest = self._registry.get(entity, "RestComponent")
                Scale = self._registry.get(entity, "ScaleComponent")
                path = self._pre_process_path(MarkerUi["sourceTransform"])
                hierarchy, name = path.rsplit("|", 1)

                # Maintain parent, if any
                parent = None
                try:
                    parent = cmdx.encode(hierarchy)
                except cmdx.ExistError:
                    pass

                name = internal.unique_name(name.replace(":", ""))
                transform = mod.create_node("transform",
                                            name=name,
                                            parent=parent)

                matrix = Rest["matrix"]
                scale = Scale["value"]

                if parent:
                    matrix *= parent["worldInverseMatrix"][0].as_matrix()

                tm = cmdx.Tm(matrix)
                transform["translate"] = tm.translation()
                transform["rotate"] = tm.rotation()
                transform["scale"] = scale

                self._state["entityToTransform"][entity] = transform

    def _create_solvers(self):
        log.info("Creating solver(s)..")

        rdsolvers = {}

        unoccupied_markers = list(self._state["markers"])
        for marker in self._state["occupied"]:
            unoccupied_markers.remove(marker)

        for marker in unoccupied_markers:
            if marker not in self._state["entityToTransform"]:
                unoccupied_markers.remove(marker)

        for entity in self._state["solvers"]:
            if self._opts["overrideSolver"]:
                try:
                    rdsolver = cmdx.encode(self._opts["overrideSolver"])
                    rdsolvers[entity] = rdsolver
                    continue

                except cmdx.ExistError:
                    # If the user requested to override it, they likely
                    # intended to stop if it could not be found.
                    raise cmdx.ExistError(
                        "Overridden solver '%s' could not be found"
                        % self._opts["overrideSolver"]
                    )

            # Ensure there is at least 1 marker in it
            is_empty = True
            for marker in unoccupied_markers:
                Scene = self._registry.get(marker, "SceneComponent")
                if Scene["entity"] == entity:
                    is_empty = False
                    break

            if is_empty:
                continue

            Name = self._registry.get(entity, "NameComponent")
            transform_name = Name["path"].rsplit("|", 1)[-1]
            rdsolver = commands.create_solver(transform_name)
            rdsolvers[entity] = rdsolver

        if self._opts["preserveAttributes"]:
            with cmdx.DagModifier() as mod:
                for entity, rdsolver in rdsolvers.items():
                    try:
                        self._apply_solver(mod, entity, rdsolver)
                    except KeyError as e:
                        # Don't let poorly formatted JSON get in the way
                        log.warning("Could not restore attribute: %s.%s"
                                    % (rdsolver, e))

        return rdsolvers

    def _create_groups(self, rdsolvers):
        log.info("Creating group(s)..")

        unoccupied_markers = list(self._state["markers"])
        for marker in self._state["occupied"]:
            unoccupied_markers.remove(marker)

        for marker in unoccupied_markers:
            if marker not in self._state["entityToTransform"]:
                unoccupied_markers.remove(marker)

        rdgroups = {}

        with cmdx.DagModifier() as mod:
            for entity in self._state["groups"]:
                Scene = self._registry.get(entity, "SceneComponent")
                rdsolver = rdsolvers.get(Scene["entity"])

                if not rdsolver:
                    # Exported group wasn't part of an exported solver
                    # This would be exceedingly rare.
                    continue

                # Ensure there is at least 1 marker in it
                is_empty = True
                for marker in unoccupied_markers:
                    Group = self._registry.get(marker, "GroupComponent")
                    if Group["entity"] == entity:
                        is_empty = False
                        break

                if is_empty:
                    continue

                Name = self._registry.get(entity, "NameComponent")

                # E.g. |someCtl_rGroup
                transform_name = Name["path"].rsplit("|", 1)[-1]
                rdgroup = commands._create_group(mod, transform_name, rdsolver)
                rdgroups[entity] = rdgroup

            if self._opts["preserveAttributes"]:
                for entity, rdgroup in rdgroups.items():
                    try:
                        self._apply_group(mod, entity, rdgroup)
                    except KeyError as e:
                        # Don't let poorly formatted JSON get in the way
                        log.warning("Could not restore attribute: %s.%s"
                                    % (rdgroup, e))

        return rdgroups

    def _create_markers(self, rdgroups, rdsolvers):
        log.info("Creating marker(s)..")
        rdmarkers = {}

        ordered_markers = []
        unoccupied_markers = list(self._state["markers"])

        for marker in self._state["occupied"]:
            unoccupied_markers.remove(marker)

        for entity in unoccupied_markers:
            transform = self._state["entityToTransform"].get(entity)

            if not transform:
                continue

            Scene = self._registry.get(entity, "SceneComponent")
            rdsolver = rdsolvers.get(Scene["entity"])

            if not rdsolver:
                # Exported marker wasn't part of an exported solver
                continue

            rdmarker = commands.assign_marker(transform, rdsolver)

            rdmarkers[entity] = rdmarker
            ordered_markers.append((entity, rdmarker))

        if self._opts["preserveAttributes"]:
            with cmdx.DagModifier() as mod:

                # Get this information from the file
                for marker in rdmarkers.values():
                    mod.disconnect(marker["dst"][0])

                mod.do_it()

                for entity, rdmarker in rdmarkers.items():
                    try:
                        self._apply_marker(mod, entity, rdmarker)
                    except KeyError as e:
                        # Don't let poorly formatted JSON get in the way
                        log.warning("Could not restore attribute: %s.%s"
                                    % (rdmarker, e))

        log.info("Adding to group(s)..")
        with cmdx.DagModifier() as mod:
            for entity, rdmarker in ordered_markers:
                Group = self._registry.get(entity, "GroupComponent")
                rdgroup = rdgroups.get(Group["entity"])

                if rdgroup is not None:
                    commands._add_to_group(mod, rdmarker, rdgroup)
                    mod.do_it()  # Commit to group

        log.info("Reconstructing hierarchy..")
        with cmdx.DagModifier() as mod:
            for entity, rdmarker in ordered_markers:
                Subs = self._registry.get(entity, "SubEntitiesComponent")
                Joint = self._registry.get(Subs["relative"], "JointComponent")
                parent_entity = Joint["parent"]

                if parent_entity:
                    # A parent was exported, but hasn't yet been created
                    if parent_entity not in rdmarkers:
                        log.debug(
                            "Missing parent, likely due to partial import"
                        )
                        continue

                    parent_rdmarker = rdmarkers[parent_entity]
                    mod.connect(parent_rdmarker["ragdollId"],
                                rdmarker["parentMarker"])

        if self._opts["createMissingTransforms"]:
            log.info("Taking ownership of newly created missing transforms..")
            with cmdx.DagModifier() as mod:
                for missing in self._state["missing"]:
                    rdmarker = rdmarkers[missing]
                    transform = self._state["entityToTransform"][missing]
                    commands._take_ownership(mod, rdmarker, transform)

        return rdmarkers

    def _create_constraints(self, rdmarkers):
        log.info("Creating constraint(s)..")
        rdconstraints = {}

        for entity in self._state["constraints"]:
            Joint = self._registry.get(entity, "JointComponent")

            parent_entity = Joint["parent"]
            child_entity = Joint["child"]

            if self._registry.has(entity, "DistanceJointComponent"):
                if not parent_entity:
                    log.warning(
                        "Distance constraint without a parent, this is a bug."
                    )

                if not child_entity:
                    log.warning(
                        "Distance constraint without a child, this is a bug."
                    )

                rdparent = rdmarkers.get(parent_entity)
                rdchild = rdmarkers.get(child_entity)

                # Some markers may not have been created, e.g.
                # via user filtering, in which case we can't
                # make this constraint.
                if not (rdparent and rdchild):
                    continue

                rdconstraint = commands.create_distance_constraint(
                    rdparent, rdchild)
                rdconstraints[entity] = rdconstraint

            elif self._registry.has(entity, "FixedJointComponent"):
                if not parent_entity:
                    log.warning(
                        "Weld constraint without a parent, this is a bug."
                    )

                if not child_entity:
                    log.warning(
                        "Weld constraint without a child, this is a bug."
                    )

                rdparent = rdmarkers.get(parent_entity)
                rdchild = rdmarkers.get(child_entity)

                if not (rdparent and rdchild):
                    continue

                rdconstraint = commands.create_fixed_constraint(
                    rdparent, rdchild)
                rdconstraints[entity] = rdconstraint

            elif self._registry.has(entity, "PinJointComponent"):
                if not child_entity:
                    log.warning(
                        "Pin constraint without a child, this is a bug."
                    )

                rdchild = rdmarkers.get(child_entity)

                if not rdchild:
                    continue

                rdconstraint = commands.create_pin_constraint(rdchild)
                rdconstraints[entity] = rdconstraint

        if self._opts["preserveAttributes"]:
            with cmdx.DagModifier() as mod:
                for entity, rdconstraint in rdconstraints.items():
                    try:
                        self._apply_constraint(mod, entity, rdconstraint)
                    except KeyError as e:
                        log.warning("Could not restore attribute: %s.%s"
                                    % (rdconstraint, e))

        return rdconstraints

    def _find_constraints(self):
        constraints = self._state["constraints"]
        constraints[:] = []

        for entity in self._registry.view("DistanceJointUIComponent"):
            constraints.append(entity)

        for entity in self._registry.view("PinJointUIComponent"):
            constraints.append(entity)

        for entity in self._registry.view("FixedJointComponent"):
            constraints.append(entity)

    def _find_solvers(self):
        solvers = self._state["solvers"]
        solvers[:] = []

        for entity in self._registry.view("SolverUIComponent"):
            solvers.append(entity)

    def _find_groups(self):
        groups = self._state["groups"]
        groups[:] = []

        for entity in self._registry.view("GroupUIComponent"):
            groups.append(entity)

        # Re-establish creation order
        def sort(entity):
            order = self._registry.get(entity, "OrderComponent")
            return order["value"]

        groups[:] = sorted(groups, key=sort)

    def _find_markers(self):
        """Find and associate each entity with a Maya transform"""
        markers = self._state["markers"]
        occupied = self._state["occupied"]
        missing = self._state["missing"]
        search_terms = self._state["searchTerms"]
        entity_to_transform = self._state["entityToTransform"]

        for entity in self._registry.view("MarkerUIComponent"):
            # Collected regardless
            markers.append(entity)

            MarkerUi = self._registry.get(entity, "MarkerUIComponent")

            # Find original path, minus the rigid
            # E.g. |rMarker_upperArm_ctl -> |root_grp|upperArm_ctrl
            path = MarkerUi["sourceTransform"]
            path = self._pre_process_path(path)

            search_terms[entity] = path

            # Exclude anything not starting with any of these
            roots = self._opts["roots"]
            if roots and not any(path.startswith(root) for root in roots):
                continue

            try:
                transform = cmdx.encode(path)

            except cmdx.ExistError:
                # Transform wasn't found in this scene, that's OK.
                # It just means it can't actually be loaded onto anything.
                missing.append(entity)
                continue

            # Avoid assigning to already assigned transforms
            if transform in entity_to_transform.values():
                occupied.append(entity)

            elif transform["message"].output(type="rdMarker"):
                occupied.append(entity)

            entity_to_transform[entity] = transform

        # Re-establish creation order
        def sort(entity):
            order = self._registry.get(entity, "OrderComponent")
            return order["value"]

        markers[:] = sorted(markers, key=sort)

    def _pre_process_path(self, path):
        """Apply search-and-replace rules along with namespace changes"""

        search, replace = self._opts["searchAndReplace"]
        search_terms = search.split(" ")
        replace_terms = replace.split(" ")

        if len(search_terms) > len(replace_terms):
            for term in search_terms[len(replace_terms):]:
                replace_terms.append("")

        # Split by space
        for a, b in zip(search_terms, replace_terms):
            path = path.replace(a, b)

        # Remove namespace from `path`
        if self._opts["namespace"] == " ":
            comps = []
            for comp in path.split("|"):
                comp = comp.split(":", 1)[-1]
                comps.append(comp)
            path = "|".join(comps)

        # Replace namespace in `path`
        elif self._opts["namespace"]:
            # Give namespace-less paths an empty namespace
            # such that it can be replaced.
            comps = []
            for comp in path.split("|"):
                if self._opts["namespace"] == " ":
                    comp = comp.split(":", 1)[-1]
                else:
                    if ":" not in comp:
                        comp = ":" + comp
                comps.append(comp)

            path = "|".join(comps)

            namespace = self._opts["namespace"].replace(" ", "")
            path = re.sub(r"\|(.*?)\:", "|%s:" % namespace, path)

        # In case of double || characters
        path = path.replace("||", "|")

        return path

    def _apply_solver(self, mod, entity, solver):
        Solver = self._registry.get(entity, "SolverComponent")
        SolverUi = self._registry.get(entity, "SolverUIComponent")

        frameskip_method = {
            "Pause": 0,
            "Ignore": 1,
        }.get(Solver["frameskipMethod"], 0)

        solver_type = {
            "PGS": 0,
            "TGS": 1,
        }.get(Solver["type"], 1)

        collision_type = {
            "SAT": 0,
            "PCM": 1,
        }.get(Solver["collisionDetectionType"], 1)

        mod.set_attr(solver["solverType"], solver_type)
        mod.set_attr(solver["frameskipMethod"], frameskip_method)
        mod.set_attr(solver["collisionDetectionType"], collision_type)
        mod.set_attr(solver["enabled"], Solver["enabled"])
        mod.set_attr(solver["airDensity"], Solver["airDensity"])
        mod.set_attr(solver["gravity"], Solver["gravity"])
        mod.set_attr(solver["substeps"], Solver["substeps"])
        mod.set_attr(solver["timeMultiplier"], Solver["timeMultiplier"])
        mod.set_attr(solver["spaceMultiplier"], Solver["spaceMultiplier"])
        mod.set_attr(solver["lod"], Solver["lod"])
        mod.set_attr(solver["poit"], Solver["positionIterations"])
        mod.set_attr(solver["veit"], Solver["velocityIterations"])
        mod.set_attr(solver["llst"], SolverUi["linearLimitStiffness"])
        mod.set_attr(solver["lldr"], SolverUi["linearLimitDamping"])
        mod.set_attr(solver["alst"], SolverUi["angularLimitStiffness"])
        mod.set_attr(solver["aldr"], SolverUi["angularLimitDamping"])
        mod.set_attr(solver["lcst"], SolverUi["linearConstraintStiffness"])
        mod.set_attr(solver["lcdr"], SolverUi["linearConstraintDamping"])
        mod.set_attr(solver["acst"], SolverUi["angularConstraintStiffness"])
        mod.set_attr(solver["acdr"], SolverUi["angularConstraintDamping"])
        mod.set_attr(solver["ldst"], SolverUi["linearDriveStiffness"])
        mod.set_attr(solver["lddr"], SolverUi["linearDriveDamping"])
        mod.set_attr(solver["adst"], SolverUi["angularDriveStiffness"])
        mod.set_attr(solver["addr"], SolverUi["angularDriveDamping"])
        mod.set_attr(solver["maxMassRatio"], SolverUi["maxMassRatio"])

    def _apply_group(self, mod, entity, group):
        GroupUi = self._registry.get(entity, "GroupUIComponent")

        input_type = {
            "Inherit": 0,
            "Off": 1,
            "Kinematic": 2,
            "Drive": 3
        }.get(GroupUi["inputType"], 3)

        drive_space = {
            "Relative": 1,
            "Absolute": 2,
            "Custom": 3
        }.get(GroupUi["driveSpace"], 1)

        mod.set_attr(group["inputType"], input_type)
        mod.set_attr(group["driveSpace"], drive_space)
        mod.set_attr(group["enabled"], GroupUi["enabled"])
        mod.set_attr(group["selfCollide"], GroupUi["selfCollide"])
        mod.set_attr(group["driveStiffness"], GroupUi["stiffness"])
        mod.set_attr(group["driveDampingRatio"], GroupUi["dampingRatio"])
        mod.set_attr(group["driveSpaceCustom"], GroupUi["driveSpaceCustom"])

    def _apply_constraint(self, mod, entity, con):
        Joint = self._registry.get(entity, "JointComponent")

        # Common across all constraints
        mod.set_attr(con["enabled"], Joint["enabled"])

        if self._registry.has(entity, "FixedJointComponent"):
            # No attributes for you
            pass

        elif self._registry.has(entity, "DistanceJointComponent"):
            Con = self._registry.get(entity, "DistanceJointComponent")
            Ui = self._registry.get(entity, "DistanceJointUIComponent")

            method = {
                "FromStart": 0,
                "Minimum": 1,
                "Maximum": 2,
                "Custom": 3,
            }.get(Con["method"], 0)

            mod.set_attr(con["stiffness"], Ui["stiffness"])
            mod.set_attr(con["dampingRatio"], Ui["dampingRatio"])
            mod.set_attr(con["maximum"], Con["maximum"])
            mod.set_attr(con["minimum"], Con["minimum"])
            mod.set_attr(con["tolerance"], Con["tolerance"])
            mod.set_attr(con["method"], method)

            parent_offset = cmdx.Tm(Joint["parentFrame"]).translation()
            child_offset = cmdx.Tm(Joint["childFrame"]).translation()
            mod.set_attr(con["parentOffset"], parent_offset)
            mod.set_attr(con["childOffset"], child_offset)

        elif self._registry.has(entity, "PinJointComponent"):
            Ui = self._registry.get(entity, "PinJointUIComponent")

            mod.set_attr(con["linearStiffness"], Ui["linearStiffness"])
            mod.set_attr(con["linearDampingRatio"], Ui["linearDampingRatio"])
            mod.set_attr(con["angularStiffness"], Ui["angularStiffness"])
            mod.set_attr(con["angularDampingRatio"], Ui["angularDampingRatio"])

        else:
            log.warning("Could not apply unsupported constraint: %s" % con)

    def _apply_marker(self, mod, entity, marker):
        Desc = self._registry.get(entity, "GeometryDescriptionComponent")
        Color = self._registry.get(entity, "ColorComponent")
        Rigid = self._registry.get(entity, "RigidComponent")
        Lod = self._registry.get(entity, "LodComponent")
        MarkerUi = self._registry.get(entity, "MarkerUIComponent")
        Drawable = self._registry.get(entity, "DrawableComponent")
        Subs = self._registry.get(entity, "SubEntitiesComponent")
        Joint = self._registry.get(Subs["relative"], "JointComponent")
        Limit = self._registry.get(Subs["relative"], "LimitComponent")

        input_type = {
            "Inherit": 0,
            "Off": 1,
            "Kinematic": 2,
            "Drive": 3
        }.get(MarkerUi["inputType"], 0)

        drive_space = {
            "Inherit": 0,
            "Relative": 1,
            "Absolute": 2,
            "Custom": 3
        }.get(MarkerUi["driveSpace"], 0)

        density_type = {
            "Off": constants.DensityOff,
            "Cotton": constants.DensityCotton,
            "Wood": constants.DensityWood,
            "Flesh": constants.DensityFlesh,
            "Uranium": constants.DensityUranium,
            "BlackHole": constants.DensityBlackHole,
            "Custom": constants.DensityCustom,
        }.get(Rigid["densityType"], 0)

        lod_preset = {
            "Level0": constants.Lod0,
            "Level1": constants.Lod1,
            "Level2": constants.Lod2,
            "Custom": constants.LodCustom,
        }.get(Lod["preset"], 0)

        lod_op = {
            "LessThan": constants.LodLessThan,
            "GreaterThan": constants.GreaterThan,
            "Equal": constants.LodEqual,
            "NotEqual": constants.LodNotEqual,
        }.get(Lod["op"], 0)

        display_type = {
            "Off": -1,
            "Default": 0,
            "Wire": 1,
            "Constant": 2,
            "Shaded": 3,
            "Mass": 4,
            "Friction": 5,
            "Restitution": 6,
            "Velocity": 7,
            "Contacts": 8,
        }.get(Drawable["displayType"], 0)

        mod.set_attr(marker["mass"], MarkerUi["mass"])
        mod.set_attr(marker["densityType"], density_type)
        mod.set_attr(marker["densityCustom"], Rigid["densityCustom"])
        mod.set_attr(marker["inputType"], input_type)
        mod.set_attr(marker["driveSpace"], drive_space)
        mod.set_attr(marker["driveSpaceCustom"], MarkerUi["driveSpaceCustom"])
        mod.set_attr(marker["driveStiffness"], MarkerUi["driveStiffness"])
        mod.set_attr(marker["ddra"], MarkerUi["driveDampingRatio"])
        mod.set_attr(marker["dral"], MarkerUi["driveAbsoluteLinear"])
        mod.set_attr(marker["draa"], MarkerUi["driveAbsoluteAngular"])
        mod.set_attr(marker["list"], MarkerUi["limitStiffness"])
        mod.set_attr(marker["ldra"], MarkerUi["limitDampingRatio"])
        mod.set_attr(marker["collisionGroup"], MarkerUi["collisionGroup"])
        mod.set_attr(marker["friction"], Rigid["friction"])
        mod.set_attr(marker["restitution"], Rigid["restitution"])
        mod.set_attr(marker["collide"], Rigid["collide"])
        mod.set_attr(marker["linearDamping"], Rigid["linearDamping"])
        mod.set_attr(marker["angularDamping"], Rigid["angularDamping"])
        mod.set_attr(marker["positionIterations"], Rigid["positionIterations"])
        mod.set_attr(marker["velocityIterations"], Rigid["velocityIterations"])
        mod.set_attr(marker["maxContactImpulse"], Rigid["maxContactImpulse"])
        mod.set_attr(marker["mxdv"], Rigid["maxDepenetrationVelocity"])
        mod.set_attr(marker["angularMass"], Rigid["angularMass"])
        mod.set_attr(marker["centerOfMass"], Rigid["centerOfMass"])
        mod.set_attr(marker["lodPreset"], lod_preset)
        mod.set_attr(marker["lodOperator"], lod_op)
        mod.set_attr(marker["lod"], Lod["level"])
        mod.set_attr(marker["displayType"], display_type)

        # Limits
        mod.set_attr(marker["parentFrame"], Joint["parentFrame"])
        mod.set_attr(marker["childFrame"], Joint["childFrame"])
        mod.set_attr(marker["limitRangeX"], Limit["twist"])
        mod.set_attr(marker["limitRangeY"], Limit["swing1"])
        mod.set_attr(marker["limitRangeZ"], Limit["swing2"])

        shape_type = {
            "Box": constants.BoxShape,
            "Sphere": constants.SphereShape,
            "Capsule": constants.CapsuleShape,
            "ConvexHull": constants.MeshShape,
        }.get(Desc["type"], constants.CapsuleShape)

        mod.set_attr(marker["shapeType"], shape_type)
        mod.set_attr(marker["shapeExtents"], Desc["extents"])
        mod.set_attr(marker["shapeLength"], Desc["length"])
        mod.set_attr(marker["shapeRadius"], Desc["radius"])
        mod.set_attr(marker["shapeOffset"], Desc["offset"])
        mod.set_attr(marker["color"], Color["value"])

        mod.set_attr(marker["inputGeometryMatrix"],
                     MarkerUi["inputGeometryMatrix"])

        # These are exported as Quaternion
        rotation = Desc["rotation"].asEulerRotation()
        mod.set_attr(marker["shapeRotation"], rotation)

        # Preserve destination transforms, where possible
        # In the case of importing onto a different character,
        # e.g. one without the IK controls, this would not match 1-to-1
        def retarget(path):
            try:
                path = self._pre_process_path(path)
                dest = cmdx.encode(path)

            except cmdx.ExistError:
                log.warning(
                    "Destination path '%s' from %s "
                    "could not be found and was ignored."
                    % (path, self._current_fname)
                )

            else:
                index = marker["dst"].next_available_index()
                dst = marker["dst"][index]
                mod.connect(dest["message"], dst)
                mod.do_it()

        # There will be *no* destinations per default
        for dest in MarkerUi["destinationTransforms"]:
            retarget(dest)

        if MarkerUi["inputGeometryPath"]:
            path = MarkerUi["inputGeometryPath"]
            path = self._pre_process_path(path)

            try:
                shape = cmdx.encode(path)

            except cmdx.ExistError:
                if shape_type == constants.MeshShape:
                    # No mesh? Resort to a plain capsule
                    mod.set_attr(marker["shapeType"], constants.CapsuleShape)
                    log.warning(
                        "%s.%s=%s could not be found, reverting "
                        "to a capsule shape" % (
                            marker, "inputGeometry", path
                        )
                    )

            else:
                commands.replace_mesh(
                    marker, shape, opts={"maintainOffset": False}
                )
