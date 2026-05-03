import os
import io
import re
import sys
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om


class OrientAimUp_UI:
    COLOR_GRAY = [0.4, 0.4, 0.4]
    COLOR_GREEN = [0.3, 0.9, 0.3]
    COLOR_RED = [0.9, 0.3, 0.3]
    COLOR_BLUE = [0.3, 0.3, 0.9]

    def __init__(self, *args):
        self.window_name = "OrientAimUPWindow"
        self.window_title = "3_OrientAimUP"
        self.av_axisX = None
        self.av_axisY = None
        self.av_axisZ = None
        self.wu_axisX = None
        self.wu_axisY = None
        self.wu_axisZ = None
        self.av_preview_btn = None
        self.wu_preview_btn = None
        self.IndivPyOrient()

    # =========================
    # Utility
    # =========================
    def _warning(self, msg):
        cmds.warning(msg)
        return []

    def normalize(self, vector):
        if vector.length() < 1e-8:
            return om.MVector(0.0, 0.0, 0.0)
        return vector.normal()

    def average_vectors(self, vectors):
        if not vectors:
            return om.MVector(0.0, 0.0, 0.0)

        total = om.MVector(0.0, 0.0, 0.0)
        for vector in vectors:
            total += vector
        return total / float(len(vectors))

    def build_matrix_from_axes(self, pos, x_axis, y_axis, z_axis):
        return [
            x_axis.x,
            x_axis.y,
            x_axis.z,
            0.0,
            y_axis.x,
            y_axis.y,
            y_axis.z,
            0.0,
            z_axis.x,
            z_axis.y,
            z_axis.z,
            0.0,
            pos.x,
            pos.y,
            pos.z,
            1.0,
        ]

    def clean_name(self, name):
        return re.sub("_+", "_", name).strip("_")

    def clean_name_keep_namespace(self, obj_name):
        if ":" in obj_name:
            namespace, base = obj_name.rsplit(":", 1)
            return "{}:{}".format(namespace, self.clean_name(base))
        return self.clean_name(obj_name)

    def unique_name(self, base):
        if not cmds.objExists(base):
            return base

        index = 1
        while cmds.objExists("{}{}".format(base, index)):
            index += 1
        return "{}{}".format(base, index)

    def build_locator_name(self, base_name, suffix, allow_multiple=False):
        """
        Build locator name based on suffix.

        allow_multiple=True:
            If name exists, create pSphere1_orient1, pSphere1_orient2...

        allow_multiple=False:
            If name exists, warning and block creation.
        """
        loc_name = self.clean_name_keep_namespace("{}_{}".format(base_name, suffix))

        if allow_multiple:
            return self.unique_name(loc_name)

        if cmds.objExists(loc_name):
            cmds.warning("<{}> already exists. Please delete it before creating again.".format(loc_name))
            return None

        return loc_name

    def get_transform_from_anything(self, obj):
        if not obj:
            return None

        if "." in obj:
            obj = obj.split(".", 1)[0]

        if not cmds.objExists(obj):
            return None

        obj_type = cmds.objectType(obj)
        if obj_type in ("transform", "joint"):
            return obj

        parent = cmds.listRelatives(obj, p=True, pa=True)
        if parent:
            return parent[0]

        return None

    def get_shape_from_transform(self, transform):
        if not transform or not cmds.objExists(transform):
            return None

        shapes = cmds.listRelatives(transform, s=True, ni=True, f=True) or []
        if shapes:
            return shapes[0]
        return None

    def get_mesh_dag_path_from_obj(self, obj):
        transform = self.get_transform_from_anything(obj)
        if not transform:
            return None

        shape = self.get_shape_from_transform(transform)
        if not shape or cmds.objectType(shape) != "mesh":
            return None

        selection = om.MSelectionList()
        selection.add(shape)
        return selection.getDagPath(0)

    def get_mesh_fn_from_obj(self, obj):
        dag_path = self.get_mesh_dag_path_from_obj(obj)
        if not dag_path:
            return None
        return om.MFnMesh(dag_path)

    def average_object_pivots(self, objects):
        pivots = []
        for obj in objects:
            transform = self.get_transform_from_anything(obj)
            if not transform:
                continue
            pivot = cmds.xform(transform, q=True, ws=True, rp=True)
            pivots.append(om.MVector(pivot[0], pivot[1], pivot[2]))

        if not pivots:
            return None
        return self.average_vectors(pivots)

    def build_axes_from_normal_and_tangent(self, normal, tangent):
        z_axis = self.normalize(normal)
        x_axis = self.normalize(tangent)

        if z_axis.length() < 1e-8:
            return None, None, None

        if x_axis.length() < 1e-8 or abs(z_axis * x_axis) > 0.999:
            fallback = om.MVector(1, 0, 0)
            if abs(z_axis * fallback) > 0.999:
                fallback = om.MVector(0, 1, 0)
            x_axis = self.normalize(fallback ^ z_axis)

        y_axis = self.normalize(z_axis ^ x_axis)
        x_axis = self.normalize(y_axis ^ z_axis)

        if x_axis.length() < 1e-8 or y_axis.length() < 1e-8 or z_axis.length() < 1e-8:
            return None, None, None

        return x_axis, y_axis, z_axis

    # =========================
    # Selection detection
    # =========================
    def detect_selection_mode(self, selection):
        if not selection:
            return None

        has_face = any(".f[" in item for item in selection)
        has_vertex = any(".vtx[" in item for item in selection)
        has_edge = any(".e[" in item for item in selection)
        has_component = has_face or has_vertex or has_edge

        if has_face and not (has_vertex or has_edge):
            return "face"
        if has_vertex and not (has_face or has_edge):
            return "vertex"
        if has_edge and not (has_face or has_vertex):
            return "edge"
        if not has_component:
            return "transform"

        return "mixed"

    # =========================
    # Transform mode
    # =========================
    def create_locator_from_transform_selection(self, selection, suffix="orient", allow_multiple=False):
        center = self.average_object_pivots(selection)
        if center is None:
            return self._warning("FAILED TO CALCULATE TRANSFORM CENTER")

        src_obj = self.get_transform_from_anything(selection[0])
        base_name = self.clean_name_keep_namespace(src_obj) if src_obj else "transform"
        loc_name = self.build_locator_name(base_name, suffix, allow_multiple)
        if not loc_name:
            return []

        locator = cmds.spaceLocator(name=loc_name)[0]
        cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])

        if src_obj:
            try:
                cmds.matchTransform(locator, src_obj, rot=True)
            except Exception:
                pass

        mel.eval('print("RESULT: <{}> transform locator CREATED\\n")'.format(locator))
        return [locator]

    # =========================
    # Vertex mode
    # =========================
    def get_vertex_positions(self, verts):
        positions = []
        for vtx in verts:
            try:
                pos = cmds.pointPosition(vtx, world=True)
                positions.append(om.MVector(pos[0], pos[1], pos[2]))
            except Exception:
                pass
        return positions

    def get_vertex_normal(self, vtx):
        mesh_fn = self.get_mesh_fn_from_obj(vtx)
        if not mesh_fn:
            return om.MVector(0, 0, 1)

        try:
            vertex_id = int(vtx.split(".vtx[")[-1][:-1])
            normal = mesh_fn.getVertexNormal(vertex_id, True, om.MSpace.kWorld)
            return self.normalize(om.MVector(normal.x, normal.y, normal.z))
        except Exception:
            return om.MVector(0, 0, 1)

    def create_locator_from_vertex_selection(self, selection, suffix="orient", allow_multiple=False):
        verts = cmds.filterExpand(selection, sm=31, ex=True) or []
        if not verts:
            return self._warning("PLEASE SELECT VERTEX COMPONENTS")

        pos_list = self.get_vertex_positions(verts)
        if not pos_list:
            return self._warning("FAILED TO GET VERTEX POSITIONS")

        src_obj = self.get_transform_from_anything(verts[0])
        base_name = self.clean_name_keep_namespace(src_obj) if src_obj else "vertex"
        loc_name = self.build_locator_name(base_name, suffix, allow_multiple)
        if not loc_name:
            return []

        locator = cmds.spaceLocator(name=loc_name)[0]
        count = len(pos_list)

        if count == 1:
            point = pos_list[0]
            cmds.xform(locator, ws=True, t=[point.x, point.y, point.z])
            mel.eval('print("RESULT: <{}> single vertex locator CREATED\\n")'.format(locator))
            return [locator]

        if count == 2:
            point_a = pos_list[0]
            point_b = pos_list[1]
            center = (point_a + point_b) * 0.5

            x_axis = self.normalize(point_b - point_a)
            if x_axis.length() < 1e-8:
                cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])
                mel.eval('print("RESULT: <{}> 2-vertex center locator CREATED (fallback)\\n")'.format(locator))
                return [locator]

            up_ref = om.MVector(0, 1, 0)
            if abs(x_axis * up_ref) > 0.999:
                up_ref = om.MVector(1, 0, 0)

            z_axis = self.normalize(x_axis ^ up_ref)
            y_axis = self.normalize(z_axis ^ x_axis)

            if x_axis.length() < 1e-8 or y_axis.length() < 1e-8 or z_axis.length() < 1e-8:
                cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])
                mel.eval('print("RESULT: <{}> 2-vertex center locator CREATED (fallback)\\n")'.format(locator))
                return [locator]

            matrix = self.build_matrix_from_axes(center, x_axis, y_axis, z_axis)
            cmds.xform(locator, ws=True, matrix=matrix)
            mel.eval('print("RESULT: <{}> 2-vertex oriented locator CREATED\\n")'.format(locator))
            return [locator]

        if count == 3:
            point_a = pos_list[0]
            point_b = pos_list[1]
            point_c = pos_list[2]
            center = self.average_vectors(pos_list)

            x_axis = self.normalize(point_b - point_a)
            temp = self.normalize(point_c - point_a)
            z_axis = self.normalize(x_axis ^ temp)
            y_axis = self.normalize(z_axis ^ x_axis)

            if x_axis.length() < 1e-8 or y_axis.length() < 1e-8 or z_axis.length() < 1e-8:
                cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])
                mel.eval('print("RESULT: <{}> 3-vertex center locator CREATED (fallback)\\n")'.format(locator))
                return [locator]

            matrix = self.build_matrix_from_axes(center, x_axis, y_axis, z_axis)
            cmds.xform(locator, ws=True, matrix=matrix)
            mel.eval('print("RESULT: <{}> 3-vertex oriented locator CREATED\\n")'.format(locator))
            return [locator]

        center = self.average_vectors(pos_list)
        cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])
        mel.eval('print("RESULT: <{}> multi-vertex center locator CREATED\\n")'.format(locator))
        return [locator]

    # =========================
    # Face mode
    # =========================
    def create_locator_from_face_selection(self, selection, suffix="orient", allow_multiple=False):
        faces = cmds.filterExpand(selection, sm=34, ex=True) or []
        if not faces:
            return self._warning("PLEASE SELECT FACE COMPONENTS")

        src_obj = self.get_transform_from_anything(faces[0])
        base_name = self.clean_name_keep_namespace(src_obj) if src_obj else "face"
        loc_name = self.build_locator_name(base_name, suffix, allow_multiple)
        if not loc_name:
            return []

        locator = cmds.spaceLocator(name=loc_name)[0]

        if len(faces) > 1:
            face_centers = []

            for face_name in faces:
                try:
                    selection_list = om.MSelectionList()
                    selection_list.add(face_name)
                    dag_path, _ = selection_list.getComponent(0)
                    mesh_fn = om.MFnMesh(dag_path)

                    face_id = int(face_name.split(".f[")[-1][:-1])
                    vert_ids = mesh_fn.getPolygonVertices(face_id)
                    if len(vert_ids) < 3:
                        continue

                    points = mesh_fn.getPoints(om.MSpace.kWorld)
                    face_points = [om.MVector(points[vid].x, points[vid].y, points[vid].z) for vid in vert_ids]
                    face_centers.append(self.average_vectors(face_points))
                except Exception:
                    pass

            if not face_centers:
                cmds.delete(locator)
                return self._warning("FAILED TO GET FACE DATA")

            center = self.average_vectors(face_centers)
            cmds.xform(locator, ws=True, t=[center.x, center.y, center.z])
            mel.eval('print("RESULT: <{}> multi-face center locator CREATED\\n")'.format(locator))
            return [locator]

        face_name = faces[0]

        try:
            selection_list = om.MSelectionList()
            selection_list.add(face_name)
            dag_path, _ = selection_list.getComponent(0)
            mesh_fn = om.MFnMesh(dag_path)

            face_id = int(face_name.split(".f[")[-1][:-1])
            vert_ids = mesh_fn.getPolygonVertices(face_id)
            if len(vert_ids) < 3:
                cmds.delete(locator)
                return self._warning("FACE NEEDS AT LEAST 3 VERTICES")

            points = mesh_fn.getPoints(om.MSpace.kWorld)
            face_points = [om.MVector(points[vid].x, points[vid].y, points[vid].z) for vid in vert_ids]

            center = self.average_vectors(face_points)
            normal = self.normalize(mesh_fn.getPolygonNormal(face_id, om.MSpace.kWorld))
            edge_dir = self.normalize(face_points[1] - face_points[0])

            x_axis, y_axis, z_axis = self.build_axes_from_normal_and_tangent(normal, edge_dir)
            if not x_axis:
                cmds.delete(locator)
                return self._warning("FAILED TO BUILD FACE ORIENTATION")

            matrix = self.build_matrix_from_axes(center, x_axis, y_axis, z_axis)
            cmds.xform(locator, ws=True, matrix=matrix)
            mel.eval('print("RESULT: <{}> face locator CREATED\\n")'.format(locator))
            return [locator]
        except Exception:
            cmds.delete(locator)
            return self._warning("FAILED TO GET FACE DATA")

    # =========================
    # Edge mode
    # =========================
    def get_edge_vertices(self, edge_name):
        verts = cmds.polyListComponentConversion(edge_name, tv=True) or []
        return cmds.ls(verts, fl=True) or []

    def create_locator_from_edge_selection(self, selection, suffix="orient", allow_multiple=False):
        edges = cmds.filterExpand(selection, sm=32, ex=True) or []
        if not edges:
            return self._warning("PLEASE SELECT EDGE COMPONENTS")

        all_points = []
        edge_dirs = []
        avg_normals = []

        for edge in edges:
            verts = self.get_edge_vertices(edge)
            if len(verts) < 2:
                continue

            try:
                point_a = cmds.pointPosition(verts[0], world=True)
                point_b = cmds.pointPosition(verts[1], world=True)
                vector_a = om.MVector(point_a[0], point_a[1], point_a[2])
                vector_b = om.MVector(point_b[0], point_b[1], point_b[2])

                all_points.append(vector_a)
                all_points.append(vector_b)
                edge_dirs.append(self.normalize(vector_b - vector_a))

                mesh_fn = self.get_mesh_fn_from_obj(edge)
                if mesh_fn:
                    for vtx in verts[:2]:
                        vertex_id = int(vtx.split(".vtx[")[-1][:-1])
                        normal = mesh_fn.getVertexNormal(vertex_id, True, om.MSpace.kWorld)
                        avg_normals.append(self.normalize(om.MVector(normal.x, normal.y, normal.z)))
            except Exception:
                pass

        if not all_points:
            return self._warning("FAILED TO GET EDGE DATA")

        center = self.average_vectors(all_points)
        tangent = self.normalize(self.average_vectors(edge_dirs)) if edge_dirs else om.MVector(1, 0, 0)
        normal = self.normalize(self.average_vectors(avg_normals)) if avg_normals else om.MVector(0, 0, 1)

        x_axis, y_axis, z_axis = self.build_axes_from_normal_and_tangent(normal, tangent)
        if not x_axis:
            return self._warning("FAILED TO BUILD EDGE ORIENTATION")

        src_obj = self.get_transform_from_anything(edges[0])
        base_name = self.clean_name_keep_namespace(src_obj) if src_obj else "edge"
        loc_name = self.build_locator_name(base_name, suffix, allow_multiple)
        if not loc_name:
            return []

        locator = cmds.spaceLocator(name=loc_name)[0]
        matrix = self.build_matrix_from_axes(center, x_axis, y_axis, z_axis)
        cmds.xform(locator, ws=True, matrix=matrix)

        mel.eval('print("RESULT: <{}> edge locator CREATED\\n")'.format(locator))
        return [locator]

    # =========================
    # Main auto dispatcher
    # =========================
    def createLocatorAuto(self, suffix="orient", allow_multiple=False):
        selection = cmds.ls(sl=True, fl=True) or []
        if not selection:
            return self._warning("SELECT SOMETHING TO FUNCTION")

        mode = self.detect_selection_mode(selection)
        if mode == "mixed":
            return self._warning("PLEASE SELECT ONLY ONE TYPE: TRANSFORM, VERTEX, EDGE, OR FACE")

        cmds.undoInfo(openChunk=True)
        try:
            if mode == "transform":
                return self.create_locator_from_transform_selection(selection, suffix, allow_multiple)
            if mode == "vertex":
                return self.create_locator_from_vertex_selection(selection, suffix, allow_multiple)
            if mode == "edge":
                return self.create_locator_from_edge_selection(selection, suffix, allow_multiple)
            if mode == "face":
                return self.create_locator_from_face_selection(selection, suffix, allow_multiple)
            return self._warning("UNSUPPORTED SELECTION MODE")
        finally:
            cmds.undoInfo(closeChunk=True)

    def get_selected_aim_vector(self):
        revValue = cmds.checkBox(self.av_rev, q=True, v=True)
        if cmds.radioButton(self.av_axisX, q=True, sl=True):
            return (-1, 0, 0) if revValue else (1, 0, 0)
        if cmds.radioButton(self.av_axisY, q=True, sl=True):
            return (0, -1, 0) if revValue else (0, 1, 0)
        if cmds.radioButton(self.av_axisZ, q=True, sl=True):
            return (0, 0, -1) if revValue else (0, 0, 1)
        return (-1, 0, 0) if revValue else (1, 0, 0)

    def get_selected_world_up(self):
        revValue = cmds.checkBox(self.wu_rev, q=True, v=True)
        if cmds.radioButton(self.wu_axisX, q=True, sl=True):
            return (-1, 0, 0) if revValue else (1, 0, 0)
        if cmds.radioButton(self.wu_axisY, q=True, sl=True):
            return (0, -1, 0) if revValue else (0, 1, 0)
        if cmds.radioButton(self.wu_axisZ, q=True, sl=True):
            return (0, 0, -1) if revValue else (0, 0, 1)
        return (0, -1, 0) if revValue else (0, 1, 0)
    
    def textGuideCC(self,checkbox,txt):
        autoCB = cmds.checkBox(checkbox, q=True, v=True)
        TrueTxt = ' [ ON ] - Selection only orient locator to AIM '
        FalseTxt = ' [ OFF ] - Three selection to AIM '
        if autoCB:
            cmds.text(txt, e=True, l=TrueTxt, bgc=self.COLOR_GREEN)
        else:
            cmds.text(txt, e=True, l=FalseTxt, bgc=self.COLOR_RED)
    
    def orientSelFunc(self):
        aimVector = self.get_selected_aim_vector()
        upVector = self.get_selected_world_up()
        autoCB = cmds.checkBox(self.autoOrientCB, q=True, v=True)
        removeConst = cmds.checkBox(self.removeConstCB, q=True, v=True)
        
        def has_orient_constraint(obj):
            if not obj or not cmds.objExists(obj):
                return []
            found = []
            attrs = [
                "{}.rotate".format(obj),
                "{}.rotateX".format(obj),
                "{}.rotateY".format(obj),
                "{}.rotateZ".format(obj)
            ]
            for attr in attrs:
                if not cmds.objExists(attr):
                    continue
                cons = cmds.listConnections(
                    attr,
                    s=True,
                    d=False,
                    type="aimConstraint"
                ) or []
                for con in cons:
                    if con not in found:
                        found.append(con)
            child_cons = cmds.listRelatives(obj, c=True, type="aimConstraint", f=True) or []
            for con in child_cons:
                if con not in found:
                    found.append(con)
            return found
        
        if not autoCB:
            selection = cmds.ls(sl=True, l=True) or []
            if not selection:
                return []
            if len(selection) != 3: # Specific only 3 selection
                cmds.warning("Please select EXACTLY 3 objects in ASCENDING ORDER : AIM, UP, ORIENT")
                return []
            aimItem = selection[0]
            upItem = selection[1]
            orientItem = selection[2]

            if aimItem == upItem or aimItem == orientItem or upItem == orientItem:
                cmds.warning("AIM, UP, and ORIENT must be 3 different objects.")
                return []
            
            cmds.undoInfo(openChunk=True)
            try:
                hasConst = has_orient_constraint(orientItem)
                if hasConst:
                    cmds.delete(hasConst)
                aimConst = cmds.aimConstraint(aimItem,orientItem,
	            							  mo=False,
	            							  wut='object',
	            							  wuo=upItem,
	            							  aim=aimVector,
	            							  u=upVector)
                if removeConst:
                    cmds.delete(aimConst)
                    aimConst = []
                cmds.select(orientItem,r=True)
                mel.eval( 'print ("REMINDER : {} < Orient Complete >\\n")'.format(orientItem))
                return aimConst
            except Exception as e:
                cmds.warning("Orient failed: {}".format(e))
                cmds.undoInfo(closeChunk=True)
                return []
            
            finally:
                cmds.undoInfo(closeChunk=True)
        else:
            cmds.warning("Automation orient is disabled / not implemented yet.")
            return []
       	
			
        	
    # =========================
    # UI
    # =========================
    def tXcolor(self, radio_button, axis_button):
        if cmds.radioButton(radio_button, q=True, sl=True):
            cmds.button(axis_button, e=True, l="X", bgc=self.COLOR_RED)

    def tYcolor(self, radio_button, axis_button):
        if cmds.radioButton(radio_button, q=True, sl=True):
            cmds.button(axis_button, e=True, l="Y", bgc=self.COLOR_GREEN)

    def tZcolor(self, radio_button, axis_button):
        if cmds.radioButton(radio_button, q=True, sl=True):
            cmds.button(axis_button, e=True, l="Z", bgc=self.COLOR_BLUE)

    def JAMMSoftScriptLauncher(self):
        def exec_code_compatible(code_obj, global_dict, local_dict=None):
            if local_dict is None:
                local_dict = global_dict

            if sys.version_info[0] >= 3:
                exec(code_obj, global_dict, local_dict)
            else:
                exec("exec code_obj in global_dict, local_dict")

        def read_script_file(path):
            try:
                with io.open(path, "r", encoding="utf-8") as script_file:
                    return script_file.read()
            except UnicodeDecodeError:
                if sys.version_info[0] < 3:
                    with open(path, "r") as script_file:
                        return script_file.read()
                with io.open(path, "r", encoding="mbcs") as script_file:
                    return script_file.read()

        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            cmds.warning("__file__ is not available. Please run this tool from a saved .py file.")
            return

        root_dir = os.path.dirname(script_dir)
        script_path = os.path.normpath(os.path.join(root_dir, "01_Script", "jammOrientJoint.py"))

        if not os.path.exists(script_path):
            cmds.warning("JAMMSoft script not found: {}".format(script_path))
            return

        try:
            script_globals = {
                "__file__": script_path,
                "__name__": "jammOrientJoint_runtime",
                "__builtins__": __builtins__,
            }

            script_source = read_script_file(script_path)
            code_obj = compile(script_source, script_path, "exec")
            exec_code_compatible(code_obj, script_globals, script_globals)

            launch_func = script_globals.get("orientJointsWindow")
            if not callable(launch_func):
                cmds.warning("orientJointsWindow() not found in {}".format(script_path))
                return

            launch_func()
        except Exception as e:
            cmds.warning("Error running JAMMSoft script: {}".format(e))

    def reload_UI(self, *args):
        self.IndivPyOrient()

    def IndivPyOrient(self):
        if cmds.window(self.window_name, q=True, ex=True):
            cmds.deleteUI(self.window_name, window=True)

        window = cmds.window(self.window_name, t=self.window_title, mb=True, s=True, tlb=False, rtf=True, mnb=False, mxb=False, wh=(250, 120))
        existing_menus = cmds.window(window, q=True, menuArray=True) or []
        for menu in existing_menus:
            if cmds.menu(menu, q=True, ex=True):
                cmds.deleteUI(menu)

        cmds.setParent(window)
        cmds.menu(l='File', parent=window)
        cmds.menuItem(l='Script', divider=True)
        cmds.menuItem(l='JAMMSoft JointOrient', i='SP_FileIcon.png', c=lambda *_: self.JAMMSoftScriptLauncher())
        cmds.menuItem(divider=True)
        cmds.menu(l='Reload', parent=window)
        cmds.menuItem(l='ReloadUI', divider=True)
        cmds.menuItem(l='Reload', i='QR_refresh.png', en=True, c=lambda *_: self.reload_UI())
        cmds.menuItem(divider=True)

        main_form = cmds.formLayout(parent=window)
        btn_form = cmds.formLayout(p=main_form, bgc=(0.2, 0.2, 0.2))

        cmds.formLayout(main_form, e=True, attachForm=[(btn_form, 'top', 0), (btn_form, 'left', 5), (btn_form, 'right', 5)])

        instText = cmds.text(l='[ Create Locator based on selection ]')
        aimup_btn = cmds.button(l='AIMUP', p=btn_form, bgc=(0.4, 0.4, 0.4), c=lambda *_: self.createLocatorAuto('aimUp', allow_multiple=False))
        orient_btn = cmds.button(l='ORIENT', p=btn_form, bgc=(0.4, 0.4, 0.4), c=lambda *_: self.createLocatorAuto('orient', allow_multiple=True))
        worldup_btn = cmds.button(l='WORLDUP', p=btn_form, bgc=(0.4, 0.4, 0.4), c=lambda *_: self.createLocatorAuto('worldUp', allow_multiple=False))
        spacer = cmds.separator(style='none', p=btn_form)

        cmds.formLayout(btn_form, e=True, attachControl=[(aimup_btn, 'top', 3, instText),
                                                         (orient_btn, 'top', 5, aimup_btn),
                                                         (worldup_btn, 'top', 5, aimup_btn),
                                                         (spacer, 'top', 5, orient_btn)],
	                                        attachForm=[(instText, 'top', 3), (instText, 'left', 3),
	                                                    (aimup_btn, 'left', 3),
	                                                    (orient_btn, 'left', 3),
	                                                    (worldup_btn, 'right', 3)],
	                                    attachPosition=[(aimup_btn, 'right', 0, 50),
	                                                    (orient_btn, 'right', 0, 50),
	                                                    (worldup_btn, 'left', 0, 52)])

        aimLayout2 = cmds.formLayout(p=main_form, bgc=(0.5, 0.5, 0.5))
        cmds.formLayout(main_form, e=True, attachControl=[(aimLayout2, 'top', 5, btn_form)],
                                        attachForm=[(aimLayout2, 'left', 7), (aimLayout2, 'right', 7)])

        av_aimLayout = cmds.formLayout(p=aimLayout2, bgc=(0.3, 0.3, 0.3))
        cmds.formLayout(aimLayout2, e=True, attachForm=[(av_aimLayout, 'left', 3), (av_aimLayout, 'right', 3)])

        av_lb = cmds.text(l='Aim :', en=1, fn='boldLabelFont')
        self.av_preview_btn = cmds.button(l='X', w=25, h=22, en=False, bgc=self.COLOR_RED)
        av_radioCol = cmds.radioCollection()
        self.av_axisX = cmds.radioButton(l='X', ann='Xaxis', sl=True, cl=av_radioCol, onc=lambda *_: self.tXcolor(self.av_axisX, self.av_preview_btn))
        self.av_axisY = cmds.radioButton(l='Y', ann='Yaxis', cl=av_radioCol, onc=lambda *_: self.tYcolor(self.av_axisY, self.av_preview_btn))
        self.av_axisZ = cmds.radioButton(l='Z', ann='Zaxis', cl=av_radioCol, onc=lambda *_: self.tZcolor(self.av_axisZ, self.av_preview_btn))
        self.av_rev = cmds.checkBox(l='Reverse ')
        cmds.formLayout(av_aimLayout, e=True, attachControl=[(self.av_preview_btn, 'left', 10, av_lb),
                                                             (self.av_axisX, 'left', 10, self.av_preview_btn),
                                                             (self.av_axisY, 'left', 5, self.av_axisX),
                                                             (self.av_axisZ, 'left', 5, self.av_axisY),
                                                             (self.av_rev, 'left', 10, self.av_axisZ)],
		                                         attachForm=[(av_lb, 'top', 4), (av_lb, 'left', 10),
		                                                     (self.av_axisX, 'top', 2),
		                                                     (self.av_axisY, 'top', 2),
		                                                     (self.av_axisZ, 'top', 2),
		                                                     (self.av_rev, 'top', 3)])

        aimLayout = cmds.formLayout(p=main_form, bgc=(0.5, 0.5, 0.5))
        cmds.formLayout(main_form, e=True, attachControl=[(aimLayout, 'top', 5, aimLayout2)],
                                        attachForm=[(aimLayout, 'left', 7), (aimLayout, 'right', 7)])

        wu_aimLayout = cmds.formLayout(p=aimLayout, bgc=(0.3, 0.3, 0.3))
        cmds.formLayout(aimLayout, e=True, attachForm=[(wu_aimLayout, 'left', 3), (wu_aimLayout, 'right', 3)])

        wu_lb = cmds.text(l='Up :', en=1, fn='boldLabelFont')
        self.wu_preview_btn = cmds.button(l='Y', w=25, h=22, en=False, bgc=self.COLOR_GREEN)
        wu_radioCol = cmds.radioCollection()
        self.wu_axisX = cmds.radioButton(l='X', ann='Xaxis', cl=wu_radioCol, onc=lambda *_: self.tXcolor(self.wu_axisX, self.wu_preview_btn))
        self.wu_axisY = cmds.radioButton(l='Y', ann='Yaxis', sl=True, cl=wu_radioCol, onc=lambda *_: self.tYcolor(self.wu_axisY, self.wu_preview_btn))
        self.wu_axisZ = cmds.radioButton(l='Z', ann='Zaxis', cl=wu_radioCol, onc=lambda *_: self.tZcolor(self.wu_axisZ, self.wu_preview_btn))
        self.wu_rev = cmds.checkBox(l='Reverse ')
        cmds.formLayout(wu_aimLayout, e=True, attachControl=[(self.wu_preview_btn, 'left', 16, wu_lb),
                                                             (self.wu_axisX, 'left', 10, self.wu_preview_btn),
                                                             (self.wu_axisY, 'left', 5, self.wu_axisX),
                                                             (self.wu_axisZ, 'left', 5, self.wu_axisY),
                                                             (self.wu_rev, 'left', 10, self.wu_axisZ)],
		                                         attachForm=[(wu_lb, 'top', 4), (wu_lb, 'left', 10),
		                                                     (self.wu_axisX, 'top', 2),
		                                                     (self.wu_axisY, 'top', 2),
		                                                     (self.wu_axisZ, 'top', 2),
		                                                     (self.wu_rev, 'top', 3)])

        func_spacer = cmds.separator(style='in', p=main_form)
        self.autoOrientCB = cmds.checkBox(l='AUTOMATION', p=main_form, en=False, cc=lambda *_: self.textGuideCC(self.autoOrientCB,self.autoGuideTxt))
        self.removeConstCB = cmds.checkBox(l='REMOVE_CONSTRAINT', v=True, p=main_form)
        self.autoGuideTxt = cmds.text(l=' [ OFF ] - THREE selection to AIM : AIM, UP, ORIENT ', bgc=self.COLOR_RED, p=main_form)
        orientSelBtn = cmds.button(l='- Orient Selection -', h=25, p=main_form,c=lambda *_: self.orientSelFunc())
        cmds.formLayout(main_form, e=True, attachControl=[(func_spacer, 'top', 5, aimLayout),
                                                          (self.autoOrientCB, 'top', 1, func_spacer),
                                                          (self.removeConstCB, 'top', 1, func_spacer),
                                                          (self.removeConstCB, 'left', 10, self.autoOrientCB),
                                                          #
                                                          (self.autoGuideTxt, 'top', 2, self.autoOrientCB),
                                                          (orientSelBtn, 'top', 5, self.autoGuideTxt)],
	                                        attachForm=[(func_spacer, 'left', 0), (func_spacer, 'right', 0),
	                                                    (self.autoOrientCB, 'left', 5),
	                                                    (self.autoGuideTxt, 'left', 5),
	                                                    (orientSelBtn, 'left', 5), (orientSelBtn, 'right', 5)])

        end_spacer = cmds.separator(style='none', p=main_form)
        cmds.formLayout(main_form, e=True, attachControl=[(end_spacer, 'top', 10, orientSelBtn)])
        cmds.showWindow(window)


if __name__ == "__main__":
    try:
        OrientAimUp_UI()
    except Exception:
        import traceback
        print(traceback.format_exc())
        raise
