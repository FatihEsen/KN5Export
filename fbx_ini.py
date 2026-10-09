# Assetto Corsa KN5 Studio - FBX.INI Material Persistence Settings Module
# Reads Assetto Corsa .fbx.ini material persistence configs and applies blend modes & textures
# Compatible with Blender 3.6 LTS, 4.x, and 5.x

import bpy
import configparser
import os
from typing import Optional
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty


def find_fbx_texture_file(base_dir: str, tex_file: str) -> Optional[str]:
    """Resolves texture path from .fbx.ini across base and common texture subfolders."""
    if not tex_file or not base_dir:
        return None

    clean_name = os.path.basename(tex_file.replace("\\", "/"))
    base_name_no_ext, _ = os.path.splitext(clean_name)

    search_dirs = [
        base_dir,
        os.path.join(base_dir, "texture"),
        os.path.join(base_dir, "textures"),
        os.path.join(os.path.dirname(base_dir), "texture"),
        os.path.join(os.path.dirname(base_dir), "textures"),
    ]

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        direct = os.path.join(d, clean_name)
        if os.path.isfile(direct):
            return direct
        try:
            for entry in os.listdir(d):
                e_no_ext, _ = os.path.splitext(entry)
                if entry.casefold() == clean_name.casefold() or e_no_ext.casefold() == base_name_no_ext.casefold():
                    full = os.path.join(d, entry)
                    if os.path.isfile(full):
                        return full
        except (OSError, PermissionError):
            continue
    return None


def get_diffuse_image_node(mat):
    """Finds the Image Texture node plugged into Base Color of the Principled BSDF."""
    if not mat or not mat.use_nodes or not mat.node_tree:
        return None
    principled = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if principled and 'Base Color' in principled.inputs:
        base_color = principled.inputs['Base Color']
        if base_color.is_linked:
            from_node = base_color.links[0].from_node
            if from_node.type == 'TEX_IMAGE':
                return from_node
    return None


def apply_alpha_channel(mat, enable=True):
    """Configures Alpha connection and material blend mode."""
    if not mat or not mat.use_nodes or not mat.node_tree:
        return

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    principled = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not principled:
        return

    # In Blender 4.2+ / 5.x, blend_method is on material or render settings
    if hasattr(mat, "blend_method"):
        mat.blend_method = 'BLEND' if enable else 'OPAQUE'

    alpha_input = principled.inputs.get('Alpha')
    if not alpha_input:
        return

    if enable:
        diffuse_node = get_diffuse_image_node(mat)
        if diffuse_node and diffuse_node.image:
            diffuse_node.image.alpha_mode = 'STRAIGHT'
            if not alpha_input.is_linked:
                links.new(diffuse_node.outputs['Alpha'], alpha_input)
    else:
        # Disconnect alpha input
        if alpha_input.is_linked:
            for l in list(links):
                if l.to_socket == alpha_input:
                    links.remove(l)
        alpha_input.default_value = 1.0


def scan_and_apply_fbx_ini(context, filepath, apply_to_all_materials=True):
    """Parses an Assetto Corsa .fbx.ini file and applies transparency and texture settings."""
    if not os.path.isfile(filepath):
        return {'CANCELLED'}, "File not found"

    ini = configparser.ConfigParser(
        empty_lines_in_values=False,
        strict=False,
        allow_no_value=True,
        inline_comment_prefixes=(";", "#", "/", "|"),
        comment_prefixes=(";", "#", "/", "|")
    )
    ini.optionxform = str

    try:
        ini.read(filepath, encoding='utf-8')
    except Exception:
        try:
            ini.read(filepath, encoding='latin-1')
        except Exception as e:
            return {'CANCELLED'}, f"Parse error: {e}"

    fbx_mat_count = 0
    if ini.has_section('MATERIAL_LIST'):
        try:
            fbx_mat_count = int(ini.get('MATERIAL_LIST', 'COUNT'))
        except ValueError:
            fbx_mat_count = 0

    # Build dictionary of INI materials
    ini_materials = {}
    for j in range(fbx_mat_count):
        sect = f"MATERIAL_{j}"
        if ini.has_section(sect) and ini.has_option(sect, 'NAME'):
            m_name = ini.get(sect, 'NAME')
            blend_val = ini.get(sect, 'ALPHABLEND') if ini.has_option(sect, 'ALPHABLEND') else '0'
            test_val = ini.get(sect, 'ALPHATEST') if ini.has_option(sect, 'ALPHATEST') else '0'
            tex_0 = ini.get(sect, 'RES_0_TEXTURE').lower() if ini.has_option(sect, 'RES_0_TEXTURE') else ''
            ini_materials[m_name] = {
                'blend': blend_val == '1',
                'test': test_val == '1',
                'texture': tex_0
            }

    if not ini_materials:
        # Fallback: scan all sections matching MATERIAL_*
        for sect in ini.sections():
            if sect.startswith('MATERIAL_') and ini.has_option(sect, 'NAME'):
                m_name = ini.get(sect, 'NAME')
                blend_val = ini.get(sect, 'ALPHABLEND') if ini.has_option(sect, 'ALPHABLEND') else '0'
                test_val = ini.get(sect, 'ALPHATEST') if ini.has_option(sect, 'ALPHATEST') else '0'
                tex_0 = ini.get(sect, 'RES_0_TEXTURE').lower() if ini.has_option(sect, 'RES_0_TEXTURE') else ''
                ini_materials[m_name] = {
                    'blend': blend_val == '1',
                    'test': test_val == '1',
                    'texture': tex_0
                }

    target_materials = set()
    if apply_to_all_materials:
        for m in bpy.data.materials:
            target_materials.add(m)
    else:
        for obj in context.selected_objects:
            for slot in obj.material_slots:
                if slot.material:
                    target_materials.add(slot.material)

    applied_count = 0
    base_dir = os.path.dirname(filepath)

    for mat in target_materials:
        if mat.name in ini_materials:
            cfg = ini_materials[mat.name]
            is_transparent = cfg['blend'] or cfg['test']
            apply_alpha_channel(mat, enable=is_transparent)

            # Update texture if present on disk
            tex_file = cfg['texture']
            if tex_file:
                found_path = find_fbx_texture_file(base_dir, tex_file)
                if found_path:
                    diffuse_node = get_diffuse_image_node(mat)
                    if diffuse_node:
                        try:
                            new_img = bpy.data.images.load(found_path, check_existing=True)
                            diffuse_node.image = new_img
                        except Exception:
                            pass
            applied_count += 1

    return {'FINISHED'}, f"Updated {applied_count} materials from .fbx.ini"


# ---------------------------------------------------------
# Blender Operator
# ---------------------------------------------------------

class KN5_OT_ImportFBXINI(bpy.types.Operator, ImportHelper):
    """Import and apply Assetto Corsa .fbx.ini material persistence settings"""
    bl_idname = "import_scene.ac_fbx_ini"
    bl_label = "Apply AC .fbx.ini Settings"
    bl_options = {'PRESET', 'UNDO'}
    filename_ext = ".ini"

    filter_glob: StringProperty(
        default="*.fbx.ini;*.ini",
        options={'HIDDEN'},
    )
    apply_all: BoolProperty(
        name="Apply to Entire Scene",
        default=True,
        description="Apply settings to all matching scene materials (if false, applies only to selected objects)",
    )

    def execute(self, context):
        res, msg = scan_and_apply_fbx_ini(context, self.filepath, self.apply_all)
        if res == {'FINISHED'}:
            self.report({'INFO'}, msg)
        else:
            self.report({'ERROR'}, msg)
        return res


def menu_func_import(self, context):
    self.layout.operator(KN5_OT_ImportFBXINI.bl_idname, text="Assetto Corsa .fbx.ini Settings (.fbx.ini)")


classes = (
    KN5_OT_ImportFBXINI,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

