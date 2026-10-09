# Assetto Corsa KN5 Studio - AI Line Import & Export Module
# Handles fast_lane.ai, ideal_line.ai, pit_lane.ai binary files
# Compatible with Blender 3.6 LTS, 4.x, and 5.x

import bpy
import os
import struct
import math
from mathutils import Vector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.object_utils import object_data_add
from bpy.props import StringProperty, FloatProperty, IntProperty, BoolProperty, EnumProperty


def calculate_distance_3d(p1, p2) -> float:
    """Calculate Euclidean distance between two 3D points."""
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2 + (p2[2] - p1[2]) ** 2)


def create_mesh_from_ai_data(mesh_name, idx, data_ideal, data_detail, scaling, ignore_last_edge):
    """Generates a Blender mesh from AC AI line datasets."""
    coords = []
    edges = []
    edge_idx = 0
    max_range = len(data_ideal)
    if max_range == 0:
        return None

    xl, z, yl, dist, _id = data_ideal[max_range - 1]

    for i in range(max_range):
        x, z, y, dist, _id = data_ideal[i]
        if idx != -1:
            if idx in (6, 7):
                direction = -math.degrees(math.atan2(yl - y, x - xl))
                yl = y
                xl = x
                if idx == 6 and len(data_detail) > 0:
                    wall_left = data_detail[i][6]
                    x += math.cos((-direction + 90) * math.pi / 180.0) * wall_left
                    y -= math.sin((-direction + 90) * math.pi / 180.0) * wall_left
                elif idx == 7 and len(data_detail) > 0:
                    wall_right = data_detail[i][7]
                    x += math.cos((-direction - 90) * math.pi / 180.0) * wall_right
                    y -= math.sin((-direction - 90) * math.pi / 180.0) * wall_right
            elif idx == 5:
                if len(data_detail) > 0:
                    z = data_detail[i][idx] / 100.0
            elif idx == 1:
                if len(data_detail) > 0:
                    z = data_detail[i][idx]
            else:
                if len(data_detail) > 0:
                    z = data_detail[i][idx] * 100.0

        # AC coordinate to Blender: (X, -Y, Z)
        coords.append(Vector((float(x) * scaling, -float(y) * scaling, float(z) * scaling)))
        if 0 <= i < max_range - 1:
            edges.append([edge_idx, edge_idx + 1])
        edge_idx += 1

    if not ignore_last_edge and edge_idx > 1:
        edges.append([edge_idx - 1, 0])

    mesh = bpy.data.meshes.new(name=mesh_name)
    mesh.from_pydata(coords, edges, [])
    mesh.update()
    mesh.validate(verbose=False)
    mesh.update(calc_edges=True)

    obj = object_data_add(bpy.context, mesh)
    return obj


def load_ai(context, filepath, scaling=1.0, import_extra_data=False, ignore_last_edge=False):
    """Loads Assetto Corsa .ai file into Blender."""
    if not os.path.isfile(filepath):
        return {'CANCELLED'}

    filesize = os.stat(filepath).st_size
    if filesize < 16:
        return {'CANCELLED'}

    mesh_base_name = os.path.splitext(os.path.basename(filepath))[0]

    with open(filepath, "rb") as buf:
        header, detail_count, u1, u2 = struct.unpack("4i", buf.read(16))
        data_ideal = []
        data_detail = []

        bytes_read = 16
        c = 0
        while bytes_read + 20 <= filesize and c < detail_count:
            data_ideal.append(struct.unpack("4f i", buf.read(20)))
            bytes_read += 20
            c += 1

        c = 0
        while bytes_read + 72 <= filesize and c < detail_count:
            data_detail.append(struct.unpack("18f", buf.read(72)))
            bytes_read += 72
            c += 1

        if len(data_ideal) > 1 and not ignore_last_edge:
            px = (data_ideal[-1][0], data_ideal[-1][1], data_ideal[-1][2])
            p0 = (data_ideal[0][0], data_ideal[0][1], data_ideal[0][2])
            p1 = (data_ideal[1][0], data_ideal[1][1], data_ideal[1][2])
            d_last_0 = calculate_distance_3d(px, p0)
            d_0_1 = calculate_distance_3d(p0, p1)
            if d_last_0 > d_0_1 * 3.0:
                ignore_last_edge = True

        if data_ideal and data_detail:
            if import_extra_data:
                extra_channels = [
                    (0, "0_unknown"), (1, "1_speed"), (2, "2_gas"), (3, "3_brake"),
                    (4, "4_latG"), (5, "5_radius"), (8, "8_camber"), (9, "9_direction"),
                    (10, "10_normalX"), (11, "11_normalY"), (12, "12_normalZ"),
                    (13, "13_length"), (14, "14_forwardX"), (15, "15_forwardY"),
                    (16, "16_forwardZ"), (17, "17_tag")
                ]
                for ch_idx, ch_name in extra_channels:
                    create_mesh_from_ai_data(f"{mesh_base_name}__{ch_name}", ch_idx, data_ideal, data_detail, scaling, ignore_last_edge)

            create_mesh_from_ai_data(f"{mesh_base_name}_border_left", 6, data_ideal, data_detail, scaling, ignore_last_edge)
            create_mesh_from_ai_data(f"{mesh_base_name}_border_right", 7, data_ideal, data_detail, scaling, ignore_last_edge)
            create_mesh_from_ai_data(f"{mesh_base_name}_ideal_line", -1, data_ideal, data_detail, scaling, ignore_last_edge)

    return {'FINISHED'}


def save_ai(context, filepath, shift_count=0, line_idx="-1", scaling=1.0, reverse=False,
            fixed_borders=False, fixed_left=2.0, fixed_right=2.0):
    """Exports or updates an Assetto Corsa .ai file from selected mesh object(s)."""
    selected_objs = context.selected_objects.copy()
    if not selected_objs:
        return {'CANCELLED'}

    bm_ideal = None
    bm_left = None
    bm_right = None

    if len(selected_objs) == 1:
        bm_ideal = selected_objs[0].data
    else:
        # Multi-select: identify ideal line and borders by object names
        file_part = os.path.splitext(os.path.basename(filepath))[0].lower()
        for ob in selected_objs:
            name_lower = ob.name.lower()
            if 'left' in name_lower:
                bm_left = ob.data
            elif 'right' in name_lower:
                bm_right = ob.data
            elif 'ideal' in name_lower or file_part in name_lower or ob == context.active_object:
                bm_ideal = ob.data

        if bm_ideal is None and context.active_object and context.active_object.type == 'MESH':
            bm_ideal = context.active_object.data

    if bm_ideal is None or len(bm_ideal.vertices) < 2:
        return {'CANCELLED'}

    vert_count = len(bm_ideal.vertices)

    data_ideal = []
    data_detail = []
    data_rest = b""
    header = 7
    u1, u2 = 0, 0
    existing_detail_count = 0

    if os.path.isfile(filepath) and os.stat(filepath).st_size > 24:
        with open(filepath, "rb") as buf:
            header, existing_detail_count, u1, u2 = struct.unpack("4i", buf.read(16))
            for _ in range(existing_detail_count):
                data_ideal.append(struct.unpack("4f i", buf.read(20)))
            for _ in range(existing_detail_count):
                data_detail.append(struct.unpack("18f", buf.read(72)))
            data_rest = buf.read()

    scale_factor = 1.0 / scaling if scaling > 0 else 1.0

    valid_borders = (
        not fixed_borders
        and bm_left is not None
        and bm_right is not None
        and len(bm_left.vertices) == vert_count
        and len(bm_right.vertices) == vert_count
    )
    if (bm_left is not None or bm_right is not None) and not valid_borders and not fixed_borders:
        left_len = len(bm_left.vertices) if bm_left else 0
        right_len = len(bm_right.vertices) if bm_right else 0
        print(f"Warning: Border vertices (L:{left_len}, R:{right_len}) do not match ideal line ({vert_count}). Using fixed border widths ({fixed_left}m / {fixed_right}m).")

    # If count matches existing AI line, preserve detail telemetry; otherwise generate clean AI line
    if existing_detail_count == vert_count and len(data_detail) == vert_count:
        with open(filepath, "wb") as buf:
            buf.write(struct.pack("4i", header, vert_count, u1, u2))

            run_index = (vert_count + shift_count) % vert_count
            dist = 0.0
            last_co = None

            for i in range(vert_count):
                idx = (vert_count - 1 - run_index) if reverse else run_index
                v = bm_ideal.vertices[idx].co
                x = v.x * scale_factor
                y = v.y * scale_factor
                z = v.z * scale_factor

                if int(line_idx) != -1:
                    orig_x, orig_y, orig_z, orig_dist, _ = data_ideal[i]
                    buf.write(struct.pack("4f i", orig_x, orig_y, orig_z, orig_dist, data_ideal[idx][4]))
                else:
                    # AC coordinates: X, Z, -Y
                    buf.write(struct.pack("4f i", x, z, -y, dist, data_ideal[idx][4]))
                    if last_co is not None:
                        dist += calculate_distance_3d(v, last_co) * scale_factor
                    last_co = v

                run_index = (run_index + 1) % vert_count

            run_index = (vert_count + shift_count) % vert_count
            for i in range(vert_count):
                idx = (vert_count - 1 - run_index) if reverse else run_index
                det = list(data_detail[idx])

                if valid_borders:
                    v_center = bm_ideal.vertices[idx].co
                    dist_l = calculate_distance_3d(v_center, bm_left.vertices[idx].co) * scale_factor
                    dist_r = calculate_distance_3d(v_center, bm_right.vertices[idx].co) * scale_factor
                else:
                    dist_l = fixed_left
                    dist_r = fixed_right

                det[6] = dist_l
                det[7] = dist_r

                if int(line_idx) != -1:
                    ch = int(line_idx)
                    v_z = bm_ideal.vertices[idx].co.z
                    if ch == 5:
                        det[ch] = v_z * 100.0
                    elif ch != 1:
                        det[ch] = v_z / 100.0
                    else:
                        det[ch] = v_z

                buf.write(struct.pack("18f", *det))
                run_index = (run_index + 1) % vert_count

            buf.write(data_rest)
    else:
        # Create brand new clean AI line
        with open(filepath, "wb") as buf:
            buf.write(struct.pack("4i", 7, vert_count, 0, 0))

            run_index = (vert_count + shift_count) % vert_count
            dist = 0.0
            last_co = bm_ideal.vertices[run_index].co

            for i in range(vert_count):
                idx = (vert_count - 1 - run_index) if reverse else run_index
                v = bm_ideal.vertices[idx].co
                x = v.x * scale_factor
                y = v.y * scale_factor
                z = v.z * scale_factor

                if i > 0:
                    dist += calculate_distance_3d(v, last_co) * scale_factor
                last_co = v

                # AC coords: X, Z, -Y
                buf.write(struct.pack("4f i", x, z, -y, dist, i))
                run_index = (run_index + 1) % vert_count

            run_index = (vert_count + shift_count) % vert_count
            for i in range(vert_count):
                idx = (vert_count - 1 - run_index) if reverse else run_index
                if valid_borders:
                    v_center = bm_ideal.vertices[idx].co
                    dist_l = calculate_distance_3d(v_center, bm_left.vertices[idx].co) * scale_factor
                    dist_r = calculate_distance_3d(v_center, bm_right.vertices[idx].co) * scale_factor
                else:
                    dist_l = fixed_left
                    dist_r = fixed_right

                ext = [0.0] * 18
                if i == 0:
                    ext[0] = 1.40129846432481e-45 * vert_count
                ext[6] = dist_l
                ext[7] = dist_r

                buf.write(struct.pack("18f", *ext))
                run_index = (run_index + 1) % vert_count

    return {'FINISHED'}


# ---------------------------------------------------------
# Blender Operators
# ---------------------------------------------------------

class KN5_OT_ImportAI(bpy.types.Operator, ImportHelper):
    """Import Assetto Corsa AI Line (.ai) file"""
    bl_idname = "import_scene.ac_ai"
    bl_label = "Import AC AI Line"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".ai"

    filter_glob: StringProperty(
        default="*.ai",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scaling factor for imported AI coordinates",
    )
    import_extra_data: BoolProperty(
        name="Import 18 Telemetry Channels",
        default=False,
        description="Imports all speed, throttle, brake, camber, and normal layers as separate meshes",
    )
    ignore_last_edge: BoolProperty(
        name="Do Not Connect Start/End",
        default=False,
        description="Useful for point-to-point (A2B) hillclimb tracks",
    )

    def execute(self, context):
        res = load_ai(context, self.filepath, self.scaling, self.import_extra_data, self.ignore_last_edge)
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"AI Line loaded successfully: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "Failed to read AI line file.")
        return res


class KN5_OT_ExportAI(bpy.types.Operator, ExportHelper):
    """Export or Update Assetto Corsa AI Line (.ai) file"""
    bl_idname = "export_scene.ac_ai"
    bl_label = "Export AC AI Line"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".ai"

    filter_glob: StringProperty(
        default="*.ai",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scale multiplier for exported coordinates",
    )
    shift_count: IntProperty(
        name="Shift Vertex Start Index",
        min=-999999, max=999999,
        default=0,
        description="Shift starting vertex position along the track",
    )
    reverse: BoolProperty(
        name="Reverse Direction",
        default=False,
        description="Export track points in reverse order",
    )
    line_idx: EnumProperty(
        name="Data Channel",
        description="Specific channel to update in existing AI line",
        items=[
            ('-1', "Ideal Line (All)", "Full ideal line coordinates"),
            ('0', "0 - Unknown", "Data 0"),
            ('1', "1 - Speed", "Speed profile"),
            ('2', "2 - Gas", "Gas throttle application"),
            ('3', "3 - Brake", "Braking zone profile"),
            ('4', "4 - LatG", "Lateral G force"),
            ('5', "5 - Radius", "Turn radius"),
            ('6', "6 - Left Border", "Left track boundary"),
            ('7', "7 - Right Border", "Right track boundary"),
            ('8', "8 - Camber", "Road camber"),
            ('9', "9 - Direction", "Direction vector"),
        ],
        default='-1'
    )
    fixed_borders: BoolProperty(
        name="Use Fixed Width Borders",
        default=False,
        description="Override mesh borders with fixed track width distances",
    )
    fixed_left: FloatProperty(
        name="Fixed Left Border (m)",
        min=0.2, max=50.0,
        default=4.0,
    )
    fixed_right: FloatProperty(
        name="Fixed Right Border (m)",
        min=0.2, max=50.0,
        default=4.0,
    )

    def execute(self, context):
        res = save_ai(
            context, self.filepath, self.shift_count, self.line_idx,
            self.scaling, self.reverse, self.fixed_borders,
            self.fixed_left, self.fixed_right
        )
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"AI Line exported successfully: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "Failed to export AI line. Make sure an ideal line mesh is selected.")
        return res


def menu_func_import(self, context):
    self.layout.operator(KN5_OT_ImportAI.bl_idname, text="Assetto Corsa AI Line (.ai)")


def menu_func_export(self, context):
    self.layout.operator(KN5_OT_ExportAI.bl_idname, text="Assetto Corsa AI Line (.ai)")


classes = (
    KN5_OT_ImportAI,
    KN5_OT_ExportAI,
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
