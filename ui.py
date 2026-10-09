# Assetto Corsa KN5 Studio - User Interface Panels & Lists
# Beautiful, responsive, workflow-oriented UI panels for 3D Viewport Sidebar, Material Properties, and Object Properties.

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
# UI Lists
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
# 1. 3D Viewport Sidebar - Main Quick Actions & Pre-Flight
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

        # Quick Export / Import actions
        box = layout.box()
        box.label(text="KN5 Quick Actions", icon='FILE_REFRESH')
        row = box.row(align=True)
        row.scale_y = 1.3
        row.operator("export_scene.kn5", text="Export KN5", icon='EXPORT')
        row.operator("import_scene.kn5", text="Import KN5", icon='IMPORT')

        # Pre-flight Scene Validator
        box_val = layout.box()
        box_val.label(text="Scene Diagnostics & Auto-Fix", icon='CHECKMARK')
        row = box_val.row(align=True)
        row.operator("kn5.validate_scene", text="Validate Scene", icon='VIEWZOOM')
        row.operator("kn5.auto_fix_scene", text="Auto-Fix Scale & UV", icon='MODIFIER')

        row_tex = box_val.row(align=True)
        audit_op = row_tex.operator("kn5.audit_repair_textures", text="Audit Textures", icon='IMAGE')
        audit_op.repair = False
        repair_op = row_tex.operator("kn5.audit_repair_textures", text="Repair Links", icon='FILE_REFRESH')
        repair_op.repair = True


# ---------------------------------------------------------------------------
# 2. Car Hierarchy & Smart Object Naming (Top Priority)
# ---------------------------------------------------------------------------

class KN5_PT_SidebarCarChecklist(bpy.types.Panel):
    """Car Object Naming, Role Tagging & Live Checklist."""
    bl_label = "🏎️ Car Structure & Naming Guide"
    bl_idname = "KN5_PT_SidebarCarChecklist"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout
        scene_objs = context.scene.objects
        active_obj = context.active_object

        # 1. Smart Auto-Rename & Dummies Header
        box = layout.box()
        box.label(text="⚡ Smart Auto-Renamer", icon='AUTO')
        col = box.column(align=True)
        col.operator("kn5.smart_auto_rename", text="⚡ Smart Auto-Rename All", icon='FILE_REFRESH')
        col.operator("kn5.create_missing_dummies", text="+ Create All Missing Dummies", icon='ADD')
        col.operator("kn5.setup_car_hierarchy", text="Create Standard Empty Hierarchy", icon='OUTLINER_OB_ARMATURE')

        # 2. Quick Role Assignment for Active Selected Object
        box_quick = layout.box()
        if active_obj:
            box_quick.label(text=f"Selected: '{active_obj.name}'", icon='OBJECT_DATA')
            box_quick.label(text="Assign Standard AC Role:", icon='HAND')

            # Row 1: Interior & Body
            grid1 = box_quick.grid_flow(columns=2, align=True)
            op = grid1.operator("kn5.quick_rename_role", text="Steering Wheel (STEER_HR)")
            op.role_name = "STEER_HR"
            op = grid1.operator("kn5.quick_rename_role", text="Interior (COCKPIT_HR)")
            op.role_name = "COCKPIT_HR"
            op = grid1.operator("kn5.quick_rename_role", text="Body (BODY)")
            op.role_name = "BODY"
            op = grid1.operator("kn5.quick_rename_role", text="Glass (EXT_GLASS)")
            op.role_name = "EXT_GLASS"

            # Row 2: Wheels & Rims
            box_quick.label(text="Wheels (WHEEL_*) & Rims (RIM_*):")
            grid_w = box_quick.grid_flow(columns=4, align=True)
            for w in ["LF", "RF", "LR", "RR"]:
                op = grid_w.operator("kn5.quick_rename_role", text=f"WHEEL_{w}")
                op.role_name = f"WHEEL_{w}"
            grid_r = box_quick.grid_flow(columns=4, align=True)
            for r in ["LF", "RF", "LR", "RR"]:
                op = grid_r.operator("kn5.quick_rename_role", text=f"RIM_{r}")
                op.role_name = f"RIM_{r}"

            # Row 3: Mirrors & Brakes
            box_quick.label(text="Mirrors (MIRROR_*) & Brakes (DISC_*):")
            grid_m = box_quick.grid_flow(columns=3, align=True)
            for m in ["L", "R", "C"]:
                op = grid_m.operator("kn5.quick_rename_role", text=f"MIRROR_{m}")
                op.role_name = f"MIRROR_{m}"
            grid_d = box_quick.grid_flow(columns=4, align=True)
            for d in ["LF", "RF", "LR", "RR"]:
                op = grid_d.operator("kn5.quick_rename_role", text=f"DISC_{d}")
                op.role_name = f"DISC_{d}"
        else:
            box_quick.label(text="Select an object to quick-assign its role.", icon='INFO')

        # 3. Interactive Naming Checklist
        box_check = layout.box()
        box_check.label(text="📋 AC Model Hierarchy Checklist", icon='CHECKBOX_HLT')

        def draw_status_row(label, is_ok, role_name):
            row = box_check.row(align=True)
            if is_ok:
                row.label(text=f"✔ {label}", icon='CHECKMARK')
            else:
                row.label(text=f"✖ {label}", icon='ERROR')
                if active_obj:
                    op = row.operator("kn5.quick_rename_role", text="Assign Active", icon='ADD')
                    op.role_name = role_name

        # Cockpit & Steering
        has_cockpit = any("COCKPIT_HR" in o.name for o in scene_objs)
        draw_status_row("COCKPIT_HR (Interior Root)", has_cockpit, "COCKPIT_HR")

        has_steer = any("STEER_HR" in o.name for o in scene_objs)
        draw_status_row("STEER_HR (Steering Wheel)", has_steer, "STEER_HR")

        # Body
        has_body = any(k in o.name for o in scene_objs for k in ["BODY", "GEO_BODY", "EXT_body"])
        draw_status_row("BODY / GEO_BODY (Exterior Body)", has_body, "BODY")

        # Wheels
        wheels_found = [w for w in ["LF", "RF", "LR", "RR"] if any(f"WHEEL_{w}" in o.name for o in scene_objs)]
        wheels_ok = len(wheels_found) == 4
        row_w = box_check.row(align=True)
        if wheels_ok:
            row_w.label(text=f"✔ Wheels: 4/4 ({', '.join(wheels_found)})", icon='CHECKMARK')
        else:
            row_w.label(text=f"✖ Wheels: {len(wheels_found)}/4 ({', '.join(wheels_found)})", icon='ERROR')
            row_w.operator("kn5.auto_rig_wheels", text="Auto-Rig", icon='AUTO')

        # Suspensions
        susp_found = [w for w in ["LF", "RF", "LR", "RR"] if any(f"SUSP_{w}" in o.name for o in scene_objs)]
        susp_ok = len(susp_found) == 4
        row_s = box_check.row(align=True)
        if susp_ok:
            row_s.label(text=f"✔ Suspensions: 4/4 ({', '.join(susp_found)})", icon='CHECKMARK')
        else:
            row_s.label(text=f"✖ Suspensions: {len(susp_found)}/4 ({', '.join(susp_found)})", icon='ERROR')
            row_s.operator("kn5.create_missing_dummies", text="Fix", icon='ADD')

        # Driver Anchors
        has_driver_pos = any("DRIVER_POS" in o.name for o in scene_objs)
        draw_status_row("DRIVER_POS (Driver Seating)", has_driver_pos, "DRIVER_POS")

        has_driver_eyes = any("DRIVER_EYES" in o.name for o in scene_objs)
        draw_status_row("DRIVER_EYES (Cockpit Camera)", has_driver_eyes, "DRIVER_EYES")

        # Mirrors
        mirrors_found = [m for m in ["MIRROR_L", "MIRROR_R", "MIRROR_C"] if any(m in o.name for o in scene_objs)]
        row_m = box_check.row(align=True)
        if len(mirrors_found) >= 2:
            row_m.label(text=f"✔ Mirrors ({', '.join(mirrors_found)})", icon='CHECKMARK')
        else:
            row_m.label(text=f"ℹ Mirrors: {len(mirrors_found)} found ({', '.join(mirrors_found)})", icon='INFO')

        # Glass
        has_glass = any(k in o.name for o in scene_objs for k in ["GLASS", "CRISTAL", "CRISTALCLARO"])
        draw_status_row("EXT_GLASS / INT_GLASS (Windows)", has_glass, "EXT_GLASS")


# ---------------------------------------------------------------------------
# 3. Wheels, Suspension & Driver Alignment
# ---------------------------------------------------------------------------

class KN5_PT_SidebarCarPhysics(bpy.types.Panel):
    """Wheel Rigging, Physics Sync and Driver Alignment."""
    bl_label = "🛞 Wheels, Physics & Driver Sync"
    bl_idname = "KN5_PT_SidebarCarPhysics"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout

        # Wheel & Physics Tools
        box = layout.box()
        box.label(text="Wheel Rigging & INI Sync", icon='AUTO')
        col = box.column(align=True)
        col.operator("kn5.auto_rig_wheels", text="⚡ Auto-Rig Wheels & Rims", icon='MOD_ARMATURE')
        col.operator("kn5.sync_model_to_physics_ini", text="🔄 Auto-Sync 3D Model to Physics INIs", icon='FILE_REFRESH')
        col.operator("kn5.align_wheels_physics", text="📐 Check Wheels vs INI", icon='SNAP_VERTEX')

        # Driver & Cockpit Seating Position
        box_drv = layout.box()
        box_drv.label(text="Driver & Cockpit Seating Position", icon='USER')
        col_drv = box_drv.column(align=True)
        col_drv.operator("kn5.create_driver_dummies", text="+ Add Driver Dummies (DRIVER_POS, EYES)", icon='EMPTY_AXIS')
        col_drv.operator("kn5.export_driver_knh", text="Export driver_base_pos.knh", icon='EXPORT')

        # Power Graph & UI Specs
        box_pwr = layout.box()
        box_pwr.label(text="Engine Specs & Power Graph", icon='LINENUMBERS_ON')
        col_pwr = box_pwr.column(align=True)
        col_pwr.operator("kn5.generate_power_graph", text="⚡ Auto-Generate Power Graph (ui_car.json)", icon='IPO_BEZIER')


# ---------------------------------------------------------------------------
# 4. Vehicle Cameras, Viewpoints & INI Sync
# ---------------------------------------------------------------------------

class KN5_PT_SidebarCarCameras(bpy.types.Panel):
    """Vehicle Cameras Rig, Viewpoints and INI Synchronization."""
    bl_label = "🎥 Cameras & Viewpoints"
    bl_idname = "KN5_PT_SidebarCarCameras"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout

        # 1. Main INI Sync Button
        box_sync = layout.box()
        box_sync.label(text="INI Synchronization", icon='FILE_REFRESH')
        col_sync = box_sync.column(align=True)
        col_sync.operator("kn5.sync_cameras_to_ini", text="🔄 Sync Cameras to car.ini / cameras.ini", icon='FILE_REFRESH')

        # 2. Camera Rig & Dummies Setup
        box_rig = layout.box()
        box_rig.label(text="Camera Rig & Empties", icon='CAMERA_DATA')
        col_rig = box_rig.column(align=True)
        col_rig.operator("kn5.setup_car_cameras", text="⚡ Auto-Setup Camera Rig & Empties", icon='AUTO')
        row_io = col_rig.row(align=True)
        row_io.operator("kn5.import_car_cameras", text="Import INI", icon='IMPORT')
        row_io.operator("kn5.export_car_cameras", text="Export INI...", icon='EXPORT')

        # 3. View Switcher
        box_view = layout.box()
        box_view.label(text="Quick Viewpoint Switcher", icon='HIDE_OFF')
        grid = box_view.grid_flow(columns=2, align=True)
        
        op = grid.operator("kn5.switch_active_camera", text="Cockpit", icon='VIEW_CAMERA')
        op.camera_type = "DRIVEREYES"
        
        op = grid.operator("kn5.switch_active_camera", text="Bonnet", icon='VIEW_CAMERA')
        op.camera_type = "BONNET"
        
        op = grid.operator("kn5.switch_active_camera", text="Bumper", icon='VIEW_CAMERA')
        op.camera_type = "BUMPER"
        
        op = grid.operator("kn5.switch_active_camera", text="Chase", icon='VIEW_CAMERA')
        op.camera_type = "CHASE"


# ---------------------------------------------------------------------------
# 5. Materials, Paint & Lighting
# ---------------------------------------------------------------------------

class KN5_PT_SidebarCarMaterials(bpy.types.Panel):
    """Car Paint, Ambient Occlusion and Lights."""
    bl_label = "🎨 Materials, Paint & Lighting"
    bl_idname = "KN5_PT_SidebarCarMaterials"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"

    def draw(self, context):
        layout = self.layout

        # Material Setup
        box_mat = layout.box()
        box_mat.label(text="Material & Transparency Tools", icon='MATERIAL')
        col_mat = box_mat.column(align=True)
        col_mat.operator("kn5.setup_transparent_meshes", text="🪟 Auto-Configure Glass & Windows", icon='SHADING_RENDERED')
        col_mat.operator("kn5.auto_detect_all_materials", text="⚡ Auto-Configure All Materials", icon='AUTO')
        col_mat.operator("kn5.setup_glossy_paint_chrome", text="✨ Apply High-Gloss Paint & Chrome", icon='SHADING_RENDERED')
        col_mat.operator("kn5.generate_csp_config", text="⚡ Generate CSP Config (ext_config.ini)", icon='SCRIPT')

        # Car Paint & AO Baking
        box_ao = layout.box()
        box_ao.label(text="Car Paint & AO Baking", icon='SHADING_RENDERED')
        col_ao = box_ao.column(align=True)
        col_ao.operator("kn5.bake_car_ao", text="⚡ Auto-Bake Car Body AO", icon='SHADING_RENDERED')
        col_ao.operator("kn5.sync_car_skins", text="🔄 Sync Textures to Skins", icon='FILE_REFRESH')
        col_ao.operator("kn5.create_clean_paint", text="🎨 Create Clean Solid Paint", icon='COLOR')

        # Lights & Emissions (lights.ini)
        box_lgt = layout.box()
        box_lgt.label(text="Lights & Emissions (lights.ini)", icon='LIGHT_SUN')
        col_lgt = box_lgt.column(align=True)
        col_lgt.operator("kn5.detect_light_meshes", text="⚡ Auto-Detect Light Meshes", icon='AUTO')
        col_lgt.operator("kn5.add_light_entry", text="Add Active Mesh as Light", icon='ADD')

        lights_props = getattr(context.scene, "kn5_lights", None)
        if lights_props and len(lights_props.entries) > 0:
            row = box_lgt.row()
            row.template_list(
                "KN5_UL_LightEntryList", "",
                lights_props, "entries",
                lights_props, "active_index",
                rows=3
            )
            side_col = row.column(align=True)
            side_col.operator("kn5.add_light_entry", text="", icon='ADD')
            side_col.operator("kn5.remove_light_entry", text="", icon='REMOVE')
            side_col.operator("kn5.sort_light_entries", text="", icon='SORTALPHA')
            side_col.operator("kn5.select_light_mesh", text="", icon='RESTRICT_SELECT_OFF')
            side_col.separator()
            side_col.operator("kn5.clear_light_entries", text="", icon='TRASH')

            # Detail editor for selected entry
            idx = lights_props.active_index
            if 0 <= idx < len(lights_props.entries):
                entry = lights_props.entries[idx]
                detail = box_lgt.box()
                row_mesh = detail.row(align=True)
                row_mesh.prop(entry, "mesh_object", text="Pick Mesh")
                row_mesh.operator("kn5.select_light_mesh", text="Select", icon='RESTRICT_SELECT_OFF')
                detail.prop(entry, "mesh_name", text="KN5 Mesh Name")
                detail.prop(entry, "light_type", text="Type")
                detail.prop(entry, "color", text="Color")
                detail.prop(entry, "off_color", text="Off Color")

        row_imp_exp = box_lgt.row(align=True)
        row_imp_exp.operator("kn5.import_lights_ini", text="Import lights.ini", icon='IMPORT')
        row_imp_exp.operator("kn5.export_lights_ini", text="Export lights.ini", icon='EXPORT')


# ---------------------------------------------------------------------------
# 5. Door & Wiper Animations (Collapsed by default)
# ---------------------------------------------------------------------------

class KN5_PT_SidebarCarAnimation(bpy.types.Panel):
    """Door & Wiper Animation Tools."""
    bl_label = "🎬 Door & Wiper Animations"
    bl_idname = "KN5_PT_SidebarCarAnimation"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Door & Wiper Animation", icon='ANIM')
        box.label(text="Select mesh parts; place the 3D Cursor at the hinge/axle.")
        box.operator("kn5.create_part_animation", text="Create Animation Pivot", icon='EMPTY_AXIS')
        box.operator("kn5.export_animation_fbx", text="Export FBX for ksEditor", icon='EXPORT')
        box.label(text="Open the FBX in ksEditor to create the .ksanim game clip.")


# ---------------------------------------------------------------------------
# 6. Track Tools & Spawns (Bottom Priority / Collapsed by default)
# ---------------------------------------------------------------------------

class KN5_PT_SidebarTrackTools(bpy.types.Panel):
    """Track creation, spawns, and physical surface tagger."""
    bl_label = "🏁 Track Tools & Spawns"
    bl_idname = "KN5_PT_SidebarTrackTools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # Spawns & Timing Gates
        box = layout.box()
        box.label(text="Add Track Dummy", icon='EMPTY_AXIS')
        col = box.column(align=True)
        for prefix, label, desc in TRACK_DUMMIES[:5]:
            op = col.operator("kn5.create_track_dummy", text=f"+ {label} ({prefix})")
            op.dummy_type = prefix

        # Surface Physical Tagger
        box = layout.box()
        box.label(text="Tag Active Object as Track Surface", icon='MOD_PHYSICS')
        grid = box.grid_flow(columns=2, align=True)
        for prefix, label, desc in TRACK_SURFACES:
            op = grid.operator("kn5.tag_surface", text=prefix)
            op.surface_prefix = prefix + "_"


# ---------------------------------------------------------------------------
# 7. Track AI, Splines & Cameras (Bottom Priority / Collapsed by default)
# ---------------------------------------------------------------------------

class KN5_PT_SidebarTrackAITools(bpy.types.Panel):
    """Track AI line, CSV splines, camera INI, and material persistence tools."""
    bl_label = "🏁 Track AI, Splines & Cameras"
    bl_idname = "KN5_PT_SidebarTrackAITools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "KN5 Studio"
    bl_parent_id = "KN5_PT_SidebarMain"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # AI Lines (fast_lane.ai, ideal_line.ai, pit_lane.ai)
        box = layout.box()
        box.label(text="AI Racing Line (.ai)", icon='ANIM')
        row = box.row(align=True)
        row.operator("import_scene.ac_ai", text="Import .AI", icon='IMPORT')
        row.operator("export_scene.ac_ai", text="Export .AI", icon='EXPORT')

        # Track Splines & Borders (side_l.csv, side_r.csv, groove.csv)
        box = layout.box()
        box.label(text="Track Spline & Borders (.csv)", icon='CURVE_DATA')
        row = box.row(align=True)
        row.operator("import_scene.ac_csv", text="Import .CSV", icon='IMPORT')
        row.operator("export_scene.ac_csv", text="Export .CSV", icon='EXPORT')

        # Cameras & Checkpoints (camera.ini, overlay.ini)
        box = layout.box()
        box.label(text="Cameras & Checkpoints (.ini)", icon='CAMERA_DATA')
        row = box.row(align=True)
        row.operator("import_scene.ac_ini", text="Import .INI", icon='IMPORT')
        row.operator("export_scene.ac_ini", text="Export .INI", icon='EXPORT')

        # FBX Persistence & Transparency (.fbx.ini)
        box = layout.box()
        box.label(text="Material Persistence (.fbx.ini)", icon='SHADING_TEXTURE')
        box.operator("import_scene.ac_fbx_ini", text="Apply .fbx.ini Settings", icon='COLOR')


# ---------------------------------------------------------------------------
# Material Properties Panel
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

        # Preset loader & Auto-detect
        box = layout.box()
        box.label(text="Material Presets & Auto-Detect", icon='PRESET')
        row = box.row(align=True)
        row.prop(ac, "preset_selector", text="")
        row.operator("kn5.apply_material_preset", text="Apply", icon='CHECKMARK')
        row = box.row(align=True)
        row.operator("kn5.auto_detect_material", text="⚡ Auto-Detect This Material", icon='AUTO')
        row.operator("kn5.auto_detect_all_materials", text="Batch All", icon='SHADING_RENDERED')

        # Shader and Blend settings
        box = layout.box()
        box.label(text="Shader Configuration", icon='MATERIAL')
        box.prop(ac, "shader_name", text="Shader")
        box.prop(ac, "blend_mode", text="Blend Mode")
        box.prop(ac, "alpha_tested", text="Alpha Tested")
        box.prop(ac, "depth_mode", text="Depth Mode")

        # Texture Mappings Box
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
            sub.prop(active_slot, "slot_name", text="Slot Name")
            sub.prop(active_slot, "image", text="Blender Image")
            sub.prop(active_slot, "override_filename", text="Custom File")

        row = tex_box.row(align=True)
        audit_op = row.operator("kn5.audit_repair_textures", text="Audit This Material", icon='VIEWZOOM')
        audit_op.current_material = True
        repair_op = row.operator("kn5.audit_repair_textures", text="Repair Links", icon='FILE_REFRESH')
        repair_op.current_material = True
        repair_op.repair = True

        # Shader Properties Box
        prop_box = layout.box()
        prop_box.label(text="Shader Uniform Properties", icon='SCRIPTPLUGINS')
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
            sub.prop(active_prop, "valueA", text="Value A (Float)", slider=True)
            sub.prop(active_prop, "valueB", text="Value B (Vector2)")
            sub.prop(active_prop, "valueC", text="Value C (Vector3)")
            sub.prop(active_prop, "valueD", text="Value D (Vector4)")


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
        col.prop(ac, "lod_in", text="LOD In Distance")
        col.prop(ac, "lod_out", text="LOD Out Distance")
        col.prop(ac, "layer", text="Layer Index")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

REGISTER_CLASSES = (
    KN5_UL_ShaderPropertyList,
    KN5_UL_TextureSlotList,
    KN5_PT_SidebarMain,
    KN5_PT_SidebarCarChecklist,
    KN5_PT_SidebarCarPhysics,
    KN5_PT_SidebarCarCameras,
    KN5_PT_SidebarCarMaterials,
    KN5_PT_SidebarCarAnimation,
    KN5_PT_SidebarTrackTools,
    KN5_PT_SidebarTrackAITools,
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
