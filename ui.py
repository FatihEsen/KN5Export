# Assetto Corsa KN5 Studio - User Interface Panels & Lists
# Workflow layout: 1 Setup -> 2 Materials -> 3 Export.
# Compatible with Blender 3.6 LTS, 4.x, and 5.x

import bpy

try:
    from .constants import (
        TRACK_SURFACES,
        TRACK_DUMMIES,
    )
except (ImportError, ValueError):
    from constants import (
        TRACK_SURFACES,
        TRACK_DUMMIES,
    )


# ---------------------------------------------------------------------------
# UI Lists (unchanged)
# ---------------------------------------------------------------------------

class KN5_UL_ShaderPropertyList(bpy.types.UIList):
    """UI list for displaying uniform shader parameters."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.name, icon='PROPERTIES')
            row.prop(item, "valueA", text="", slider=True)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name)


class KN5_UL_TextureSlotList(bpy.types.UIList):
    """UI list for displaying texture slot bindings."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.label(text=item.slot_name, icon='IMAGE_DATA')
            if item.image:
                row.label(text=item.image.name, icon='CHECKMARK')
            elif item.override_filename:
                row.label(text=item.override_filename, icon='FILE')
            else:
                row.label(text="(unassigned)", icon='ERROR')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.slot_name)


# ---------------------------------------------------------------------------
# Header: quick Export / Import / health check (always visible)
# ---------------------------------------------------------------------------

class KN5_PT_SidebarMain(bpy.types.Panel):
    """Main Sidebar Panel: Export, Import and Scene Diagnostics."""
    bl_label = "Assetto Corsa KN5 Studio"
    bl_idname = "KN5_PT_SidebarMain"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="KN5 Quick Actions", icon='FILE_REFRESH')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("export_scene.kn5", text="Export KN5", icon='EXPORT')
        row.operator("import_scene.kn5", text="Import KN5", icon='IMPORT')

        box_val = layout.box()
        box_val.label(text="Scene Health", icon='CHECKMARK')
        row = box_val.row(align=True)
        row.operator("kn5.validate_scene", text="Validate", icon='VIEWZOOM')
        row.operator("kn5.auto_fix_scene", text="Auto-Fix", icon='MODIFIER')
        row_tex = box_val.row(align=True)
        audit_op = row_tex.operator("kn5.audit_repair_textures", text="Audit", icon='IMAGE')
        audit_op.repair = False
        repair_op = row_tex.operator("kn5.audit_repair_textures", text="Repair", icon='FILE_REFRESH')
        repair_op.repair = True

        layout.label(text="Follow steps 1 → 2 → 3 below.", icon='INFO')


def _draw_checklist_row(box_check, context, label, is_ok, role_name):
    row = box_check.row(align=True)
    if is_ok:
        row.label(text=f"✔ {label}", icon='CHECKMARK')
    else:
        row.label(text=f"✖ {label}", icon='ERROR')
        if context.active_object:
            op = row.operator("kn5.quick_rename_role", text="Assign", icon='ADD')
            op.role_name = role_name


# ---------------------------------------------------------------------------
# STEP 1 — Setup: structure, rig, dummies, track spawns
# ---------------------------------------------------------------------------

class KN5_PT_Step1Setup(bpy.types.Panel):
    """Step 1: car/track structure, naming, wheel rig and spawns."""
    bl_label = "1 — Setup: Structure & Rig"
    bl_idname = "KN5_PT_Step1Setup"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout
        scene_objs = context.scene.objects
        active_obj = context.active_object

        # 1A. Hierarchy helpers
        box = layout.box()
        box.label(text="Car Hierarchy", icon='OUTLINER_OB_ARMATURE')
        col = box.column(align=True)
        col.operator("kn5.setup_car_hierarchy", text="Create Standard Hierarchy", icon='ADD')
        col.operator("kn5.create_missing_dummies", text="Create Missing Dummies", icon='ADD')
        col.operator("kn5.smart_auto_rename", text="Smart Auto-Rename All", icon='FILE_REFRESH')

        # 1B. Role assignment (only when something selected)
        if active_obj:
            bq = layout.box()
            bq.label(text=f"Selected: '{active_obj.name}'", icon='OBJECT_DATA')
            grid1 = bq.grid_flow(columns=2, align=True)
            for text, role in [
                ("Steering (STEER_HR)", "STEER_HR"),
                ("Cockpit (COCKPIT_HR)", "COCKPIT_HR"),
                ("Body (BODY)", "BODY"),
                ("Glass (EXT_GLASS)", "EXT_GLASS"),
            ]:
                op = grid1.operator("kn5.quick_rename_role", text=text)
                op.role_name = role
            bq.label(text="Wheels / Rims:")
            gw = bq.grid_flow(columns=4, align=True)
            for w in ["LF", "RF", "LR", "RR"]:
                op = gw.operator("kn5.quick_rename_role", text=f"WHEEL_{w}")
                op.role_name = f"WHEEL_{w}"
            gr = bq.grid_flow(columns=4, align=True)
            for r in ["LF", "RF", "LR", "RR"]:
                op = gr.operator("kn5.quick_rename_role", text=f"RIM_{r}")
                op.role_name = f"RIM_{r}"

        # 1C. Live checklist (compact)
        bc = layout.box()
        bc.label(text="Checklist", icon='CHECKBOX_HLT')
        _draw_checklist_row(bc, context, "COCKPIT_HR",
                            any("COCKPIT_HR" in o.name for o in scene_objs), "COCKPIT_HR")
        _draw_checklist_row(bc, context, "STEER_HR",
                            any("STEER_HR" in o.name for o in scene_objs), "STEER_HR")
        _draw_checklist_row(bc, context, "BODY",
                            any(k in o.name for o in scene_objs for k in ["BODY", "GEO_BODY", "EXT_body"]), "BODY")
        wheels_found = [w for w in ["LF", "RF", "LR", "RR"] if any(f"WHEEL_{w}" in o.name for o in scene_objs)]
        row_w = bc.row(align=True)
        if len(wheels_found) == 4:
            row_w.label(text="✔ Wheels: 4/4", icon='CHECKMARK')
        else:
            row_w.label(text=f"✖ Wheels: {len(wheels_found)}/4", icon='ERROR')
            row_w.operator("kn5.auto_rig_wheels", text="Auto-Rig", icon='AUTO')
        susp_found = [w for w in ["LF", "RF", "LR", "RR"] if any(f"SUSP_{w}" in o.name for o in scene_objs)]
        row_s = bc.row(align=True)
        if len(susp_found) == 4:
            row_s.label(text="✔ Suspensions: 4/4", icon='CHECKMARK')
        else:
            row_s.label(text=f"✖ Suspensions: {len(susp_found)}/4", icon='ERROR')
            row_s.operator("kn5.create_missing_dummies", text="Fix", icon='ADD')
        _draw_checklist_row(bc, context, "DRIVER_POS + EYES",
                            any("DRIVER_POS" in o.name for o in scene_objs), "DRIVER_POS")

        # 1D. Wheels, driver, cameras rig
        bw = layout.box()
        bw.label(text="Rig: Wheels / Driver / Cameras", icon='MOD_ARMATURE')
        col = bw.column(align=True)
        col.operator("kn5.auto_rig_wheels", text="Auto-Rig Wheels & Rims", icon='AUTO')
        col.operator("kn5.create_driver_dummies", text="Add Driver Dummies", icon='EMPTY_AXIS')
        col.operator("kn5.setup_car_cameras", text="Setup Camera Rig", icon='CAMERA_DATA')

        # 1E. Track spawns + surfaces
        bt = layout.box()
        bt.label(text="Track: Spawns & Surfaces", icon='EMPTY_AXIS')
        col = bt.column(align=True)
        for prefix, label, _desc in TRACK_DUMMIES[:5]:
            op = col.operator("kn5.create_track_dummy", text=f"+ {label}")
            op.dummy_type = prefix
        bt.label(text="Surface tag:")
        grid = bt.grid_flow(columns=3, align=True)
        for prefix, _label, _desc in TRACK_SURFACES:
            op = grid.operator("kn5.tag_surface", text=prefix)
            op.surface_prefix = prefix + "_"


# ---------------------------------------------------------------------------
# STEP 2 — Materials, paint, lights
# ---------------------------------------------------------------------------

class KN5_PT_Step2Materials(bpy.types.Panel):
    """Step 2: shaders, transparency, paint, AO and lights."""
    bl_label = "2 — Materials, Paint & Light"
    bl_idname = "KN5_PT_Step2Materials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout

        bm = layout.box()
        bm.label(text="Shader Setup", icon='MATERIAL')
        col = bm.column(align=True)
        col.operator("kn5.auto_detect_all_materials", text="Auto-Configure All Materials", icon='AUTO')
        col.operator("kn5.setup_transparent_meshes", text="Auto-Configure Glass", icon='SHADING_RENDERED')
        col.operator("kn5.setup_glossy_paint_chrome", text="Glossy Paint & Chrome", icon='SHADING_RENDERED')
        col.operator("kn5.generate_csp_config", text="Generate CSP Config", icon='SCRIPT')

        ba = layout.box()
        ba.label(text="Paint & Skins", icon='SHADING_RENDERED')
        col = ba.column(align=True)
        col.operator("kn5.bake_car_ao", text="Bake Car Body AO", icon='RENDER_STILL')
        col.operator("kn5.sync_car_skins", text="Sync Textures to Skins", icon='FILE_REFRESH')
        col.operator("kn5.create_clean_paint", text="Create Clean Paint", icon='COLOR')

        bl = layout.box()
        bl.label(text="Lights (lights.ini)", icon='LIGHT_SUN')
        col = bl.column(align=True)
        col.operator("kn5.detect_light_meshes", text="Auto-Detect Light Meshes", icon='AUTO')
        col.operator("kn5.add_light_entry", text="Add Active Mesh as Light", icon='ADD')

        lights_props = getattr(context.scene, "kn5_lights", None)
        if lights_props and len(lights_props.entries) > 0:
            row = bl.row()
            row.template_list(
                "KN5_UL_LightEntryList", "",
                lights_props, "entries",
                lights_props, "active_index",
                rows=3
            )
            side = row.column(align=True)
            side.operator("kn5.add_light_entry", text="", icon='ADD')
            side.operator("kn5.remove_light_entry", text="", icon='REMOVE')
            side.operator("kn5.sort_light_entries", text="", icon='SORTALPHA')
            side.operator("kn5.select_light_mesh", text="", icon='RESTRICT_SELECT_OFF')
            side.separator()
            side.operator("kn5.clear_light_entries", text="", icon='TRASH')

            idx = lights_props.active_index
            if 0 <= idx < len(lights_props.entries):
                entry = lights_props.entries[idx]
                detail = bl.box()
                r = detail.row(align=True)
                r.prop(entry, "mesh_object", text="Mesh")
                r.operator("kn5.select_light_mesh", text="Sel", icon='RESTRICT_SELECT_OFF')
                detail.prop(entry, "mesh_name", text="Name")
                detail.prop(entry, "light_type", text="Type")
                detail.prop(entry, "color", text="Color")
                detail.prop(entry, "off_color", text="Off Color")

        row = bl.row(align=True)
        row.operator("kn5.import_lights_ini", text="Import", icon='IMPORT')
        row.operator("kn5.export_lights_ini", text="Export", icon='EXPORT')


# ---------------------------------------------------------------------------
# STEP 3 — Export & data sync (physics, cameras, AI, animation)
# ---------------------------------------------------------------------------

class KN5_PT_Step3Export(bpy.types.Panel):
    """Step 3: physics sync, cameras, track data and animation helpers."""
    bl_label = "3 — Export & Data Sync"
    bl_idname = "KN5_PT_Step3Export"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout

        bp = layout.box()
        bp.label(text="Physics & Engine Data", icon='MOD_PHYSICS')
        col = bp.column(align=True)
        col.operator("kn5.sync_model_to_physics_ini", text="Sync Model → Physics INIs", icon='FILE_REFRESH')
        col.operator("kn5.align_wheels_physics", text="Check Wheels vs INI", icon='SNAP_VERTEX')
        col.operator("kn5.generate_power_graph", text="Generate Power Graph", icon='IPO_BEZIER')
        col.operator("kn5.export_driver_knh", text="Export driver_base_pos.knh", icon='EXPORT')

        bc = layout.box()
        bc.label(text="Cameras", icon='CAMERA_DATA')
        col = bc.column(align=True)
        col.operator("kn5.sync_cameras_to_ini", text="Sync Cameras → INI", icon='FILE_REFRESH')
        row = col.row(align=True)
        row.operator("kn5.import_car_cameras", text="Import", icon='IMPORT')
        row.operator("kn5.export_car_cameras", text="Export", icon='EXPORT')
        grid = bc.grid_flow(columns=2, align=True)
        for text, ctype in [("Cockpit", "DRIVEREYES"), ("Bonnet", "BONNET"),
                            ("Bumper", "BUMPER"), ("Chase", "CHASE")]:
            op = grid.operator("kn5.switch_active_camera", text=text, icon='VIEW_CAMERA')
            op.camera_type = ctype

        bt = layout.box()
        bt.label(text="Track Data: AI / Spline / INI", icon='CURVE_DATA')
        row = bt.row(align=True)
        row.operator("import_scene.ac_ai", text="Import .AI", icon='IMPORT')
        row.operator("export_scene.ac_ai", text="Export .AI", icon='EXPORT')
        row = bt.row(align=True)
        row.operator("import_scene.ac_csv", text="Import .CSV", icon='IMPORT')
        row.operator("export_scene.ac_csv", text="Export .CSV", icon='EXPORT')
        row = bt.row(align=True)
        row.operator("import_scene.ac_ini", text="Import .INI", icon='IMPORT')
        row.operator("export_scene.ac_ini", text="Export .INI", icon='EXPORT')
        bt.operator("import_scene.ac_fbx_ini", text="Apply .fbx.ini Settings", icon='COLOR')

        ba = layout.box()
        ba.label(text="Animation (via ksEditor)", icon='ANIM')
        ba.label(text="Cursor = hinge, then FBX → .ksanim.")
        ba.operator("kn5.create_part_animation", text="Create Animation Pivot", icon='EMPTY_AXIS')
        ba.operator("kn5.export_animation_fbx", text="Export FBX for ksEditor", icon='EXPORT')


# ---------------------------------------------------------------------------
# Material Properties Panel (unchanged logic, clearer grouping kept)
# ---------------------------------------------------------------------------

class KN5_PT_MaterialProperties(bpy.types.Panel):
    """Assetto Corsa Material Editor Panel."""
    bl_label = "Assetto Corsa Material"
    bl_idname = "KN5_PT_MaterialProperties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def draw(self, context):
        layout = self.layout
        mat = context.material
        ac = getattr(mat, "assettoCorsa", None)
        if not ac:
            layout.label(text="KN5 Material properties not registered.")
            return

        box = layout.box()
        box.label(text="Preset & Auto-Detect", icon='PRESET')
        row = box.row(align=True)
        row.prop(ac, "preset_selector", text="")
        row.operator("kn5.apply_material_preset", text="Apply", icon='CHECKMARK')
        row = box.row(align=True)
        row.operator("kn5.auto_detect_material", text="Auto-Detect", icon='AUTO')
        row.operator("kn5.auto_detect_all_materials", text="Batch All", icon='SHADING_RENDERED')

        box = layout.box()
        box.label(text="Shader", icon='MATERIAL')
        box.prop(ac, "shader_name", text="Shader")
        box.prop(ac, "blend_mode", text="Blend")
        box.prop(ac, "alpha_tested", text="Alpha Tested")
        box.prop(ac, "depth_mode", text="Depth")

        tex_box = layout.box()
        tex_box.label(text="Texture Slots", icon='TEXTURE')
        row = tex_box.row()
        row.template_list(
            "KN5_UL_TextureSlotList", "",
            ac, "texture_slots",
            ac, "texture_slots_active",
            rows=3
        )
        col = row.column(align=True)
        col.operator("kn5.add_texture_slot", text="", icon='ADD')
        col.operator("kn5.remove_texture_slot", text="", icon='REMOVE')

        if 0 <= ac.texture_slots_active < len(ac.texture_slots):
            active_slot = ac.texture_slots[ac.texture_slots_active]
            sub = tex_box.box()
            sub.prop(active_slot, "slot_name", text="Slot")
            sub.prop(active_slot, "image", text="Image")
            sub.prop(active_slot, "override_filename", text="File")

        row = tex_box.row(align=True)
        audit_op = row.operator("kn5.audit_repair_textures", text="Audit", icon='VIEWZOOM')
        audit_op.current_material = True
        repair_op = row.operator("kn5.audit_repair_textures", text="Repair", icon='FILE_REFRESH')
        repair_op.current_material = True
        repair_op.repair = True

        prop_box = layout.box()
        prop_box.label(text="Shader Properties", icon='SCRIPTPLUGINS')
        row = prop_box.row()
        row.template_list(
            "KN5_UL_ShaderPropertyList", "",
            ac, "shader_properties",
            ac, "shader_properties_active",
            rows=3
        )
        col = row.column(align=True)
        col.operator("kn5.add_shader_property", text="", icon='ADD')
        col.operator("kn5.remove_shader_property", text="", icon='REMOVE')

        if 0 <= ac.shader_properties_active < len(ac.shader_properties):
            active_prop = ac.shader_properties[ac.shader_properties_active]
            sub = prop_box.box()
            sub.prop(active_prop, "name", text="Name")
            sub.prop(active_prop, "valueA", text="A", slider=True)
            sub.prop(active_prop, "valueB", text="B")
            sub.prop(active_prop, "valueC", text="C")
            sub.prop(active_prop, "valueD", text="D")


# ---------------------------------------------------------------------------
# Object Properties Panel
# ---------------------------------------------------------------------------

class KN5_PT_ObjectProperties(bpy.types.Panel):
    """Assetto Corsa Object Flags and LOD Panel."""
    bl_label = "Assetto Corsa Object Flags"
    bl_idname = "KN5_PT_ObjectProperties"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"

    def draw(self, context):
        layout = self.layout
        obj = context.object
        if not obj:
            return

        ac = getattr(obj, "assettoCorsa", None)
        if not ac:
            layout.label(text="Assetto Corsa object properties not registered.")
            return

        box = layout.box()
        box.label(text="Render Flags", icon='RESTRICT_RENDER_OFF')
        col = box.column(align=True)
        col.prop(ac, "renderable", text="Renderable")
        col.prop(ac, "cast_shadows", text="Cast Shadows")
        col.prop(ac, "transparent", text="Transparent")
        col.prop(ac, "visible", text="Visible")

        box = layout.box()
        box.label(text="LOD & Layer", icon='ARROW_LEFTRIGHT')
        col = box.column(align=True)
        col.prop(ac, "lod_in", text="LOD In")
        col.prop(ac, "lod_out", text="LOD Out")
        col.prop(ac, "layer", text="Layer")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTER_CLASSES = (
    KN5_UL_ShaderPropertyList,
    KN5_UL_TextureSlotList,
    KN5_PT_SidebarMain,
    KN5_PT_Step1Setup,
    KN5_PT_Step2Materials,
    KN5_PT_Step3Export,
    KN5_PT_MaterialProperties,
    KN5_PT_ObjectProperties,
)


def register():
    for cls in REGISTER_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(REGISTER_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
