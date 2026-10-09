# Assetto Corsa KN5 Studio - Track Splines & CSV Import & Export Module
# Handles side_l.csv, side_r.csv, groove.csv, and track centerline splines
# Compatible with Blender 3.6 LTS, 4.x, and 5.x

import bpy
import os
import csv
import math
from mathutils import Vector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.object_utils import object_data_add
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty


def calculate_distance_3d(p1, p2) -> float:
    """Calculate Euclidean distance between two points in 3D."""
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)


def convert_object_to_mesh(obj):
    """Converts a curve or surface object to mesh with selection isolation."""
    view_layer = bpy.context.view_layer
    orig_selected = list(bpy.context.selected_objects)
    orig_active = view_layer.objects.active

    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj

    bpy.ops.object.convert(target="MESH")

    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in orig_selected:
        if o.name in bpy.data.objects:
            o.select_set(True)
    if orig_active and orig_active.name in bpy.data.objects:
        view_layer.objects.active = orig_active


def convert_object_to_curve(obj):
    """Converts a mesh to curve with selection isolation."""
    view_layer = bpy.context.view_layer
    orig_selected = list(bpy.context.selected_objects)
    orig_active = view_layer.objects.active

    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj

    bpy.ops.object.convert(target="CURVE")

    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in orig_selected:
        if o.name in bpy.data.objects:
            o.select_set(True)
    if orig_active and orig_active.name in bpy.data.objects:
        view_layer.objects.active = orig_active


def load_csv(context, filepath, scaling=1.0, ignore_last_edge=False):
    """Loads Assetto Corsa track CSV spline into Blender."""
    if not os.path.isfile(filepath):
        return {'CANCELLED'}

    points = []
    edges = []
    edge_idx = 0

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter=',', quotechar='"')
        for row in reader:
            if not row or len(row) < 3:
                continue
            try:
                # AC CSV format: X, Z, Y -> Blender: X, -Y, Z
                x = float(row[0]) * scaling
                z = float(row[1]) * scaling
                y = float(row[2]) * scaling
                points.append(Vector((x, -y, z)))

                if edge_idx >= 1:
                    edges.append([edge_idx - 1, edge_idx])
                edge_idx += 1
            except (ValueError, IndexError):
                continue

    if not points:
        return {'CANCELLED'}

    if not ignore_last_edge and edge_idx > 2:
        edges.append([edge_idx - 1, 0])

    mesh_name = os.path.splitext(os.path.basename(filepath))[0]
    mesh = bpy.data.meshes.new(name=mesh_name)
    mesh.from_pydata(points, edges, [])
    mesh.update()
    mesh.validate(verbose=False)
    mesh.update(calc_edges=True)

    obj = object_data_add(bpy.context, mesh)
    return {'FINISHED'}


def save_csv(context, filepath, scaling=1.0, shift_count=0, reverse=False,
             sort_with_curve=False, skip_pot=False, is_closed_loop=True):
    """Exports active Blender mesh vertices to an Assetto Corsa track CSV file."""
    selected_objs = [o for o in context.selected_objects if o.type in ('MESH', 'CURVE')]
    if not selected_objs:
        return {'CANCELLED'}

    obj = context.active_object if context.active_object in selected_objs else selected_objs[0]

    if sort_with_curve:
        convert_object_to_curve(obj)
        convert_object_to_mesh(obj)

    if obj.type != 'MESH':
        return {'CANCELLED'}

    verts = obj.data.vertices
    num_verts = len(verts)
    if num_verts < 2:
        return {'CANCELLED'}

    scale_factor = 1.0 / scaling if scaling > 0 else 1.0

    # Calculate total length
    dist_total = 0.0
    limit = num_verts if is_closed_loop else (num_verts - 1)
    for i in range(limit):
        next_i = (i + 1) % num_verts
        dist_total += calculate_distance_3d(verts[i].co, verts[next_i].co) * scale_factor

    if dist_total <= 0.0:
        dist_total = 1.0

    run_idx = (num_verts + shift_count) % num_verts if is_closed_loop else 0
    accum_dist = 0.0
    actual_start_idx = (num_verts - 1 - run_idx) if reverse else run_idx
    last_co = verts[actual_start_idx].co

    with open(filepath, 'w', encoding='utf-8') as f:
        for i in range(num_verts):
            actual_idx = (num_verts - 1 - run_idx) if reverse else run_idx
            co = verts[actual_idx].co

            if i > 0:
                accum_dist += calculate_distance_3d(co, last_co) * scale_factor
            last_co = co

            pot = min(1.0, max(0.0, accum_dist / dist_total))

            # Blender -> AC format: X, Z, -Y
            x = co.x * scale_factor
            y = co.y * scale_factor
            z = co.z * scale_factor

            if skip_pot:
                f.write(f"{x:.4f},{z:.4f},{-y:.4f}\n")
            else:
                f.write(f"{x:.4f},{z:.4f},{-y:.4f},{pot:.6f}\n")

            if is_closed_loop:
                run_idx = (run_idx + 1) % num_verts
            else:
                run_idx += 1

    return {'FINISHED'}


# ---------------------------------------------------------
# Blender Operators
# ---------------------------------------------------------

class KN5_OT_ImportCSV(bpy.types.Operator, ImportHelper):
    """Import Assetto Corsa track CSV spline (side_l, side_r, groove)"""
    bl_idname = "import_scene.ac_csv"
    bl_label = "Import AC CSV Spline"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv;*.txt",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scaling factor for coordinates",
    )
    ignore_last_edge: BoolProperty(
        name="Do Not Connect Start/End",
        default=False,
        description="Check this for point-to-point / A2B tracks",
    )

    def execute(self, context):
        res = load_csv(context, self.filepath, self.scaling, self.ignore_last_edge)
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"Track CSV spline loaded: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "Failed to parse CSV file.")
        return res


class KN5_OT_ExportCSV(bpy.types.Operator, ExportHelper):
    """Export Assetto Corsa track CSV spline (side_l, side_r, groove)"""
    bl_idname = "export_scene.ac_csv"
    bl_label = "Export AC CSV Spline"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".csv"

    filter_glob: StringProperty(
        default="*.csv;*.txt",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scale multiplier for exported coordinates",
    )
    shift_count: IntProperty(
        name="Shift Start Vertex",
        min=-999999, max=999999,
        default=0,
        description="Shift starting vertex along the loop",
    )
    reverse: BoolProperty(
        name="Reverse Direction",
        default=False,
        description="Export points in reverse order",
    )
    sort_with_curve: BoolProperty(
        name="Sort by Converting to Curve",
        default=False,
        description="Reorder vertices by temporarily converting mesh to curve",
    )
    skip_pot: BoolProperty(
        name="Skip Point of Track (X,Y,Z only)",
        default=False,
        description="Export only X,Z,Y without the 4th PointOfTrack distance parameter",
    )
    is_closed_loop: BoolProperty(
        name="Closed Circuit",
        default=True,
        description="Uncheck for Point-to-Point / A2B / Hillclimb tracks to prevent connecting end to start",
    )

    def execute(self, context):
        res = save_csv(
            context, self.filepath, self.scaling, self.shift_count,
            self.reverse, self.sort_with_curve, self.skip_pot,
            self.is_closed_loop
        )
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"Track CSV exported: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "Failed to export CSV. Make sure a curve or mesh spline is selected.")
        return res


def menu_func_import(self, context):
    self.layout.operator(KN5_OT_ImportCSV.bl_idname, text="Assetto Corsa Track Spline (.csv)")


def menu_func_export(self, context):
    self.layout.operator(KN5_OT_ExportCSV.bl_idname, text="Assetto Corsa Track Spline (.csv)")


classes = (
    KN5_OT_ImportCSV,
    KN5_OT_ExportCSV,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    except Exception:
        pass
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

