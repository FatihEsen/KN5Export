# Assetto Corsa KN5 Studio - Cameras & Config INI Import & Export Module
# Handles camera.ini, camera_0.ini, checkpoint positions, and overlay INIs
# Compatible with Blender 3.6 LTS, 4.x, and 5.x

import bpy
import configparser
import os
from mathutils import Vector
from bpy_extras.io_utils import ImportHelper, ExportHelper
from bpy_extras.object_utils import object_data_add
from bpy.props import StringProperty, FloatProperty, BoolProperty


def load_ini(context, filepath, scaling=1.0, as_mesh=False):
    """Loads Assetto Corsa camera or checkpoint INI file into Blender."""
    if not os.path.isfile(filepath):
        return {'CANCELLED'}

    ini = configparser.ConfigParser(
        empty_lines_in_values=False,
        strict=False,
        allow_no_value=True,
        inline_comment_prefixes=(";", "#", "/"),
        comment_prefixes=(";", "#", "/")
    )
    ini.optionxform = str

    try:
        ini.read(filepath, encoding='utf-8')
    except Exception:
        try:
            ini.read(filepath, encoding='latin-1')
        except Exception:
            return {'CANCELLED'}

    sections_with_pos = []
    for sect in ini.sections():
        coords_str = None
        if ini.has_option(sect, 'POSITION'):
            coords_str = ini.get(sect, 'POSITION')
        elif ini.has_option(sect, 'WORLD_POSITION'):
            coords_str = ini.get(sect, 'WORLD_POSITION')

        if coords_str:
            parts = [p.strip() for p in coords_str.split(',')]
            if len(parts) >= 3:
                try:
                    # AC format: X, Z, Y -> Blender format: X, -Y, Z
                    x = float(parts[0]) * scaling
                    z = float(parts[1]) * scaling
                    y = float(parts[2]) * scaling
                    sections_with_pos.append((sect, Vector((x, -y, z))))
                except ValueError:
                    continue

    if not sections_with_pos:
        return {'CANCELLED'}

    base_name = os.path.splitext(os.path.basename(filepath))[0]

    if as_mesh:
        coords = [pos for _, pos in sections_with_pos]
        edges = [[i, i + 1] for i in range(len(coords) - 1)]
        mesh = bpy.data.meshes.new(name=base_name)
        mesh.from_pydata(coords, edges, [])
        mesh.update()
        mesh.validate(verbose=False)
        object_data_add(context, mesh)
    else:
        # Create empty collection for imported cameras/points
        col_name = f"AC_{base_name}"
        col = bpy.data.collections.get(col_name)
        if not col:
            col = bpy.data.collections.new(col_name)
            context.scene.collection.children.link(col)

        for sect_name, pos in sections_with_pos:
            empty = bpy.data.objects.new(sect_name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 1.0 * scaling
            empty.location = pos
            col.objects.link(empty)

    return {'FINISHED'}


def save_ini(context, filepath, scaling=1.0):
    """Exports selected camera empties or mesh points back into an Assetto Corsa INI file."""
    selected_objs = context.selected_objects.copy()
    if not selected_objs:
        return {'CANCELLED'}

    ini = configparser.ConfigParser(
        empty_lines_in_values=False,
        strict=False,
        allow_no_value=True,
        inline_comment_prefixes=(";", "#", "/"),
        comment_prefixes=(";", "#", "/")
    )
    ini.optionxform = str

    if os.path.isfile(filepath):
        try:
            ini.read(filepath, encoding='utf-8')
        except Exception:
            ini.read(filepath, encoding='latin-1')

    scale_factor = 1.0 / scaling if scaling > 0 else 1.0

    # Case 1: Mesh vertices selected
    mesh_obj = next((o for o in selected_objs if o.type == 'MESH'), None)
    if mesh_obj:
        verts = mesh_obj.data.vertices
        for i, v in enumerate(verts):
            sect = f"CAMERA_{i}"
            if not ini.has_section(sect):
                ini.add_section(sect)
            # Blender: (X, Y, Z) -> AC: (X, Z, -Y)
            pos_str = f"{v.co.x * scale_factor:.4f}, {v.co.z * scale_factor:.4f}, {-v.co.y * scale_factor:.4f}"
            ini.set(sect, 'POSITION', pos_str)
    else:
        # Case 2: Empties / Objects selected
        for obj in selected_objs:
            sect = obj.name.split('.')[0]  # Strip Blender duplicate suffix (.001)
            if not ini.has_section(sect):
                ini.add_section(sect)
            loc = obj.matrix_world.to_translation()
            pos_str = f"{loc.x * scale_factor:.4f}, {loc.z * scale_factor:.4f}, {-loc.y * scale_factor:.4f}"
            ini.set(sect, 'POSITION', pos_str)

    with open(filepath, 'w', encoding='utf-8') as f:
        ini.write(f)

    return {'FINISHED'}


# ---------------------------------------------------------
# Blender Operators
# ---------------------------------------------------------

class KN5_OT_ImportINI(bpy.types.Operator, ImportHelper):
    """Import Assetto Corsa camera / checkpoint INI file"""
    bl_idname = "import_scene.ac_ini"
    bl_label = "Import AC Cameras INI"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".ini"

    filter_glob: StringProperty(
        default="*.ini",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scaling factor for camera positions",
    )
    as_mesh: BoolProperty(
        name="Import as Mesh Spline",
        default=False,
        description="Imports coordinates as a connected mesh spline instead of separate empties",
    )

    def execute(self, context):
        res = load_ini(context, self.filepath, self.scaling, self.as_mesh)
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"Cameras/Points loaded from INI: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "No valid camera/checkpoint POSITION entries found in INI.")
        return res


class KN5_OT_ExportINI(bpy.types.Operator, ExportHelper):
    """Export selected cameras or points into Assetto Corsa INI file"""
    bl_idname = "export_scene.ac_ini"
    bl_label = "Export AC Cameras INI"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".ini"

    filter_glob: StringProperty(
        default="*.ini",
        options={'HIDDEN'},
    )
    scaling: FloatProperty(
        name="Scale",
        min=0.001, max=100.0,
        default=1.0,
        description="Scale multiplier for exported coordinates",
    )

    def execute(self, context):
        res = save_ini(context, self.filepath, self.scaling)
        if res == {'FINISHED'}:
            self.report({'INFO'}, f"Saved positions to INI: {os.path.basename(self.filepath)}")
        else:
            self.report({'ERROR'}, "Failed to export INI. Select camera empties or a mesh.")
        return res


def menu_func_import(self, context):
    self.layout.operator(KN5_OT_ImportINI.bl_idname, text="Assetto Corsa Cameras / Points (.ini)")


def menu_func_export(self, context):
    self.layout.operator(KN5_OT_ExportINI.bl_idname, text="Assetto Corsa Cameras / Points (.ini)")


classes = (
    KN5_OT_ImportINI,
    KN5_OT_ExportINI,
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

