# Assetto Corsa KN5 Studio - Scene Tools, Helpers, and Pre-flight Validator
# Provides track spawn generator, car hierarchy setup, surface tagging, and validation.

import bpy
import re
import os
import struct
import math
import mathutils
import configparser
from typing import Optional, List, Dict, Set, Tuple
from bpy_extras.io_utils import ExportHelper, ImportHelper
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

try:
    from .dds import rgba_pixels_to_bgra_dds, is_dds_bytes
except (ImportError, ValueError):
    from dds import rgba_pixels_to_bgra_dds, is_dds_bytes




class KN5_NodeProperties(bpy.types.PropertyGroup):
    """Assetto Corsa specific properties attached to bpy.types.Object."""
    cast_shadows: BoolProperty(
        name="Cast Shadows",
        default=True,
        description="Whether this mesh casts real-time sun/light shadows"
    )
    visible: BoolProperty(
        name="Visible",
        default=True,
        description="Controls in-game visibility"
    )
    transparent: BoolProperty(
        name="Transparent",
        default=False,
        description="Marks mesh as transparent for rendering order"
    )
    renderable: BoolProperty(
        name="Renderable",
        default=True,
        description="Toggles if the object should be rendered by the graphics engine"
    )
    layer: IntProperty(
        name="Layer",
        default=0,
        min=0,
        max=3,
        description="Render layer index (0 is standard)"
    )
    lod_in: FloatProperty(
        name="LOD In Distance",
        default=0.0,
        min=0.0,
        unit='LENGTH',
        description="Nearest distance at which this LOD becomes visible (0 = always visible)"
    )
    lod_out: FloatProperty(
        name="LOD Out Distance",
        default=0.0,
        min=0.0,
        unit='LENGTH',
        description="Farthest distance at which this LOD remains visible (0 = infinite)"
    )


class KN5_OT_CreateTrackDummy(bpy.types.Operator):
    """Adds a standard Assetto Corsa track dummy / spawn point."""
    bl_idname = "kn5.create_track_dummy"
    bl_label = "Add Track Dummy"
    bl_description = "Creates a properly named Empty for start grids, pit boxes, or timing gates"
    bl_options = {'REGISTER', 'UNDO'}

    dummy_type: StringProperty(name="Dummy Type", default="AC_START_")

    def execute(self, context):
        prefix = self.dummy_type

        # Calculate next available index for numbered spawns
        existing_names = [o.name for o in context.scene.objects]
        idx = 0
        if prefix.endswith("_"):
            while f"{prefix}{idx}" in existing_names:
                idx += 1
            target_name = f"{prefix}{idx}"
        else:
            target_name = prefix

        empty = bpy.data.objects.new(target_name, None)
        context.collection.objects.link(empty)

        # Visual style
        if "START" in prefix or "PIT" in prefix or "HOTLAP" in prefix:
            empty.empty_display_type = 'SINGLE_ARROW'
            empty.empty_display_size = 2.0
        elif "TIME" in prefix:
            empty.empty_display_type = 'CUBE'
            empty.empty_display_size = 1.0
        else:
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 1.0

        # Position at 3D cursor
        empty.location = context.scene.cursor.location

        # Select the new object
        bpy.ops.object.select_all(action='DESELECT')
        empty.select_set(True)
        context.view_layer.objects.active = empty

        self.report({'INFO'}, f"Created track dummy '{target_name}' at cursor.")
        return {'FINISHED'}


class KN5_OT_SetupCarHierarchy(bpy.types.Operator):
    """Sets up standard Assetto Corsa vehicle wheel and cockpit empty hierarchy."""
    bl_idname = "kn5.setup_car_hierarchy"
    bl_label = "Setup Car Hierarchy"
    bl_description = "Generates standard empties for car wheels (LF, RF, LR, RR), suspension, steer, and cockpit"
    bl_options = {'REGISTER', 'UNDO'}

    car_name: StringProperty(name="Car Root Name", default="CAR_ROOT")

    def execute(self, context):
        existing_root = context.scene.objects.get(self.car_name)
        if existing_root:
            self.report({'INFO'}, f"'{self.car_name}' already exists; hierarchy was not duplicated.")
            return {'FINISHED'}

        col = context.collection

        # Root empty
        root = bpy.data.objects.new(self.car_name, None)
        root.empty_display_type = 'PLAIN_AXES'
        root.empty_display_size = 1.5
        col.objects.link(root)

        wheel_positions = {
            "LF": (0.69, -1.336, 0.322),
            "RF": (-0.69, -1.336, 0.322),
            "LR": (0.69, 1.161, 0.322),
            "RR": (-0.69, 1.161, 0.322),
        }

        for side, pos in wheel_positions.items():
            # Suspension dummy
            susp = bpy.data.objects.new(f"SUSP_{side}", None)
            susp.parent = root
            susp.location = pos
            susp.rotation_euler = (0.0, 0.0, 0.0)
            susp.empty_display_type = 'SINGLE_ARROW'
            susp.empty_display_size = 0.4
            col.objects.link(susp)

            # Wheel dummy
            wheel = bpy.data.objects.new(f"WHEEL_{side}", None)
            wheel.parent = susp
            wheel.location = (0.0, 0.0, 0.0)
            wheel.rotation_euler = (0.0, 0.0, 0.0)
            wheel.empty_display_type = 'CIRCLE'
            wheel.empty_display_size = 0.35
            col.objects.link(wheel)

        # Cockpit and steering (-Y is front, +Y is rear, +X is left)
        cockpit = bpy.data.objects.new("COCKPIT_HR", None)
        cockpit.parent = root
        cockpit.location = (0.36, -0.20, 0.80)
        cockpit.empty_display_type = 'CUBE'
        cockpit.empty_display_size = 0.5
        col.objects.link(cockpit)

        steer = bpy.data.objects.new("STEER_HR", None)
        steer.parent = cockpit
        steer.location = (0.0, -0.18, -0.15)
        steer.empty_display_type = 'CIRCLE'
        steer.empty_display_size = 0.18
        col.objects.link(steer)

        # Driver position and eye dummy
        driver_pos = bpy.data.objects.new("DRIVER_POS", None)
        driver_pos.parent = cockpit
        driver_pos.location = (0.0, 0.24, -0.37)
        driver_pos.rotation_euler = (0.0, 0.0, math.radians(-90))
        driver_pos.empty_display_type = 'SINGLE_ARROW'
        driver_pos.empty_display_size = 0.35
        col.objects.link(driver_pos)

        driver_eyes = bpy.data.objects.new("DRIVER_EYES", None)
        driver_eyes.parent = driver_pos
        driver_eyes.location = (0.0, -0.08, 0.58)
        driver_eyes.empty_display_type = 'SPHERE'
        driver_eyes.empty_display_size = 0.12
        col.objects.link(driver_eyes)

        self.report({'INFO'}, f"Created complete vehicle dummy hierarchy under '{self.car_name}'.")
        return {'FINISHED'}


class KN5_OT_CreatePartAnimation(bpy.types.Operator):
    """Create an Assetto Corsa animation pivot and preview keyframes."""
    bl_idname = "kn5.create_part_animation"
    bl_label = "Create Door / Wiper Animation"
    bl_description = "Parent selected meshes to a pivot at the 3D cursor and create preview keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    animation_type: EnumProperty(
        name="Animation",
        items=[
            ('DOOR', "Door", "Create a one-way open animation"),
            ('WIPER', "Wiper", "Create repeated back-and-forth wiper motion"),
        ],
        default='DOOR',
    )
    door_side: EnumProperty(
        name="Door Side",
        items=[('L', "Left", "Export as the left-door animation clip"),
               ('R', "Right", "Export as the right-door animation clip")],
        default='L',
    )
    axis: EnumProperty(
        name="Rotation Axis",
        items=[('X', "X", "Rotate around Blender X"),
               ('Y', "Y", "Rotate around Blender Y"),
               ('Z', "Z", "Rotate around Blender Z")],
        default='Z',
    )
    angle_degrees: FloatProperty(
        name="Angle (degrees)",
        description="Door opening angle or wiper sweep amplitude",
        default=65.0,
        min=1.0,
        max=180.0,
    )
    frames_per_motion: IntProperty(
        name="Frames per Motion",
        description="Door opening time or duration of one complete wiper sweep cycle",
        default=20,
        min=2,
        max=1000,
    )
    wiper_cycles: IntProperty(
        name="Preview Cycles",
        description="Number of wiper cycles to create on the timeline",
        default=6,
        min=1,
        max=50,
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "animation_type")
        if self.animation_type == 'DOOR':
            layout.prop(self, "door_side")
        layout.prop(self, "axis")
        layout.prop(self, "angle_degrees")
        layout.prop(self, "frames_per_motion")
        if self.animation_type == 'WIPER':
            layout.prop(self, "wiper_cycles")
        layout.label(text="Place the 3D Cursor at the hinge or wiper axle.", icon='CURSOR')

    def execute(self, context):
        parts = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not parts:
            self.report({'ERROR'}, "Select one or more mesh parts first.")
            return {'CANCELLED'}

        active_part = context.active_object if context.active_object in parts else parts[0]
        selected_parts = set(parts)
        active_root = active_part
        while active_root.parent in selected_parts:
            active_root = active_root.parent
        if self.animation_type == 'DOOR':
            pivot_name = f"ANIM_DOOR_{self.door_side}_{re.sub(r'[^A-Za-z0-9_]+', '_', active_part.name)}"
            clip_name = f"car_door_{self.door_side}"
        else:
            pivot_name = f"ANIM_WIPER_{re.sub(r'[^A-Za-z0-9_]+', '_', active_part.name)}"
            clip_name = "car_wiper"
        pivot = bpy.data.objects.new(pivot_name, None)
        pivot.empty_display_type = 'ARROWS'
        pivot.empty_display_size = 0.25
        pivot.rotation_mode = 'XYZ'
        pivot["kn5_animation_clip"] = clip_name
        context.collection.objects.link(pivot)
        pivot.parent = active_root.parent
        pivot.matrix_world = mathutils.Matrix.Translation(context.scene.cursor.location)

        part_roots = [obj for obj in parts if obj.parent not in selected_parts]
        world_matrices = {obj: obj.matrix_world.copy() for obj in part_roots}
        for obj in part_roots:
            obj.parent = pivot
            obj.matrix_world = world_matrices[obj]

        axis_index = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        amplitude = math.radians(self.angle_degrees)
        start_frame = 1
        if self.animation_type == 'DOOR':
            pivot.rotation_euler[axis_index] = 0.0
            pivot.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=start_frame)
            pivot.rotation_euler[axis_index] = amplitude
            end_frame = start_frame + self.frames_per_motion
            pivot.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=end_frame)
            description = "door open animation"
        else:
            duration = self.frames_per_motion
            for cycle in range(self.wiper_cycles):
                cycle_start = start_frame + cycle * duration
                cycle_mid = cycle_start + max(1, duration // 2)
                cycle_end = cycle_start + duration
                pivot.rotation_euler[axis_index] = -amplitude
                pivot.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=cycle_start)
                pivot.rotation_euler[axis_index] = amplitude
                pivot.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=cycle_mid)
                pivot.rotation_euler[axis_index] = -amplitude
                pivot.keyframe_insert(data_path="rotation_euler", index=axis_index, frame=cycle_end)
            end_frame = start_frame + duration * self.wiper_cycles
            description = f"{self.wiper_cycles} wiper preview cycles"

        pivot["kn5_animation_end_frame"] = end_frame

        action = pivot.animation_data.action if pivot.animation_data else None
        if action:
            for fcurve in getattr(action, "fcurves", ()):
                if fcurve.data_path == "rotation_euler" and fcurve.array_index == axis_index:
                    for key in fcurve.keyframe_points:
                        key.interpolation = 'LINEAR'

        context.scene.frame_end = max(context.scene.frame_end, end_frame)
        context.scene.frame_set(start_frame)
        pivot.select_set(True)
        context.view_layer.objects.active = pivot
        self.report({'INFO'}, f"Created {description} on '{pivot.name}'. Adjust the pivot at the 3D Cursor if needed.")
        return {'FINISHED'}


class KN5_OT_ExportAnimationFBX(bpy.types.Operator, ExportHelper):
    """Export the active animation pivot and hierarchy for conversion in ksEditor."""
    bl_idname = "kn5.export_animation_fbx"
    bl_label = "Export Animation FBX for ksEditor"
    bl_description = "Export this animated hierarchy as FBX; ksEditor converts it to the game's .ksanim clip"
    bl_options = {'REGISTER'}

    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={'HIDDEN'})
    filepath: StringProperty(subtype='FILE_PATH')
    # Operator properties cannot hold Blender datablock pointers; store the name.
    animation_pivot_name: StringProperty(name="Animation Pivot", options={'HIDDEN'})

    def invoke(self, context, event):
        pivot = context.active_object
        clip_name = pivot.get("kn5_animation_clip", "") if pivot else ""
        if not clip_name:
            self.report({'ERROR'}, "Select the animation pivot created by KN5 Studio first.")
            return {'CANCELLED'}
        self.animation_pivot_name = pivot.name
        if not self.filepath:
            if bpy.data.filepath:
                self.filepath = os.path.join(os.path.dirname(bpy.data.filepath), clip_name + ".fbx")
            else:
                self.filepath = clip_name + ".fbx"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        pivot = bpy.data.objects.get(self.animation_pivot_name) or context.active_object
        clip_name = pivot.get("kn5_animation_clip", "") if pivot else ""
        if not clip_name:
            self.report({'ERROR'}, "Select the animation pivot created by KN5 Studio first.")
            return {'CANCELLED'}

        export_objects = {pivot, *pivot.children_recursive}
        parent = pivot.parent
        while parent:
            export_objects.add(parent)
            parent = parent.parent

        old_selected = list(context.selected_objects)
        old_active = context.view_layer.objects.active
        old_frame_start = context.scene.frame_start
        old_frame_end = context.scene.frame_end
        old_frame_current = context.scene.frame_current
        try:
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in export_objects:
                obj.select_set(True)
            context.view_layer.objects.active = pivot
            context.scene.frame_start = 1
            context.scene.frame_end = max(2, int(pivot.get("kn5_animation_end_frame", old_frame_end)))
            context.scene.frame_set(1)

            bpy.ops.export_scene.fbx(
                filepath=self.filepath,
                use_selection=True,
                object_types={'EMPTY', 'MESH'},
                add_leaf_bones=False,
                bake_anim=True,
                bake_anim_use_nla_strips=False,
                bake_anim_use_all_actions=False,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=0.0,
                axis_forward='-Z',
                axis_up='Y',
            )
        except Exception as exc:
            self.report({'ERROR'}, f"Animation FBX export failed: {exc}")
            return {'CANCELLED'}
        finally:
            context.scene.frame_start = old_frame_start
            context.scene.frame_end = old_frame_end
            context.scene.frame_set(old_frame_current)
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in old_selected:
                if obj.name in context.view_layer.objects:
                    obj.select_set(True)
            if old_active and old_active.name in context.view_layer.objects:
                context.view_layer.objects.active = old_active

        self.report({'INFO'}, f"Exported {self.filepath}. Open it in ksEditor to create {clip_name}.ksanim.")
        return {'FINISHED'}


def compute_smart_cockpit_anchors(context) -> dict:
    """
    Intelligently computes world-space positions for COCKPIT_HR, STEER_HR, DRIVER_POS, and DRIVER_EYES.
    Vehicle orientation: -Y is Front, +Y is Rear, +Z is Up, +X is Left (LHD driver side), -X is Right (RHD).
    """
    import mathutils
    from mathutils import Vector

    steer_mesh = None
    steer_center = None
    steer_radius = 0.18

    # 1. Look for steering wheel mesh
    steer_keywords = ['volante', 'steer', 'steering', 'int_volante', 'volant', 'lenkrad', 'direksiyon']
    for o in context.scene.objects:
        if o.type == 'MESH':
            n = o.name.lower()
            if any(k in n for k in steer_keywords) and 'column' not in n and 'shaft' not in n:
                steer_mesh = o
                break

    if steer_mesh:
        if steer_mesh.bound_box:
            bb_w = [steer_mesh.matrix_world @ Vector(v) for v in steer_mesh.bound_box]
            steer_center = sum(bb_w, Vector()) / 8.0
            dim_x = max(v.x for v in bb_w) - min(v.x for v in bb_w)
            dim_z = max(v.z for v in bb_w) - min(v.z for v in bb_w)
            steer_radius = max(min(dim_x, dim_z), 0.25) / 2.0
        else:
            steer_center = steer_mesh.matrix_world.translation.copy()
    else:
        # Check if STEER_HR empty already exists
        steer_empty = context.scene.objects.get("STEER_HR")
        if steer_empty and steer_empty.type == 'EMPTY':
            steer_center = steer_empty.matrix_world.translation.copy()

    # 2. Look for driver seat mesh (to refine seating height/depth)
    seat_keywords = ['seat', 'asiento', 'koltuk', 'chair', 'sedile', 'driver_seat', 'int_seat']
    seat_center = None
    seat_candidates = []
    for o in context.scene.objects:
        if o.type == 'MESH':
            n = o.name.lower()
            if any(k in n for k in seat_keywords) and 'rail' not in n and 'bracket' not in n and 'belt' not in n:
                seat_candidates.append(o)

    # Determine driver side: if steer_center known, match its sign of X, otherwise assume LHD (X > 0)
    driver_side_sign = (1 if steer_center.x >= 0 else -1) if steer_center else 1
    best_seat = None
    for s in seat_candidates:
        s_pos = s.matrix_world.translation
        if (s_pos.x * driver_side_sign) > 0.05:
            best_seat = s
            break
    if not best_seat and seat_candidates:
        best_seat = seat_candidates[0]

    if best_seat and best_seat.bound_box:
        bb_s = [best_seat.matrix_world @ Vector(v) for v in best_seat.bound_box]
        min_z = min(v.z for v in bb_s)
        max_z = max(v.z for v in bb_s)
        mid_y = (min(v.y for v in bb_s) + max(v.y for v in bb_s)) / 2.0
        cushion_z = min_z + (max_z - min_z) * 0.25
        seat_center = Vector(((min(v.x for v in bb_s) + max(v.x for v in bb_s)) / 2.0, mid_y, cushion_z))

    # 3. Compute final coordinates
    if not steer_center:
        if seat_center:
            steer_pos = Vector((seat_center.x, seat_center.y - 0.42, seat_center.z + 0.25))
        else:
            # Default LHD: X=0.36, Y=-0.38, Z=0.65
            steer_pos = Vector((0.36, -0.38, 0.65))
    else:
        steer_pos = steer_center

    drv_x = steer_pos.x

    if seat_center:
        drv_y = seat_center.y
        drv_z = seat_center.z + 0.05
    else:
        drv_y = steer_pos.y + 0.42
        drv_z = steer_pos.z - 0.22

    eyes_x = drv_x
    eyes_y = drv_y - 0.08
    eyes_z = drv_z + 0.58

    cockpit_pos = Vector((0.0, steer_pos.y + 0.20, steer_pos.z))

    return {
        "steer_mesh": steer_mesh,
        "steer_pos": steer_pos,
        "steer_radius": steer_radius,
        "driver_pos": Vector((drv_x, drv_y, drv_z)),
        "driver_eyes": Vector((eyes_x, eyes_y, eyes_z)),
        "cockpit_pos": cockpit_pos,
    }


class KN5_OT_CreateDriverDummies(bpy.types.Operator):
    """Creates standard Assetto Corsa driver seating and eye position empties."""
    bl_idname = "kn5.create_driver_dummies"
    bl_label = "Add Driver Dummies"
    bl_description = "Creates DRIVER_POS (seating anchor) and DRIVER_EYES (cockpit view camera) empties"
    bl_options = {'REGISTER', 'UNDO'}

    auto_detect: BoolProperty(
        name="Auto-Detect from Cockpit / Steering",
        description="Automatically compute realistic driver position from steering wheel or seat mesh",
        default=True,
    )
    seat_height: FloatProperty(
        name="Driver Seat Height (Z)",
        description="Height (Z in Blender) of the driver pelvis / seat cushion",
        default=0.45,
        unit='LENGTH',
    )
    lateral_offset: FloatProperty(
        name="Driver Lateral Position (X)",
        description="Lateral position (X in Blender, positive = left drive, negative = right drive)",
        default=0.36,
        unit='LENGTH',
    )

    def invoke(self, context, event):
        anchors = compute_smart_cockpit_anchors(context)
        self.lateral_offset = round(anchors["driver_pos"].x, 3)
        self.seat_height = round(anchors["driver_pos"].z, 3)
        return self.execute(context)

    def execute(self, context):
        col = context.collection or context.scene.collection
        anchors = compute_smart_cockpit_anchors(context)

        root = context.scene.objects.get("CAR_ROOT") or context.scene.objects.get("SCENE_ROOT") or context.scene.objects.get("RootNode")

        cockpit_hr = context.scene.objects.get("COCKPIT_HR")
        if not cockpit_hr:
            cockpit_hr = bpy.data.objects.new("COCKPIT_HR", None)
            cockpit_hr.empty_display_type = 'CUBE'
            cockpit_hr.empty_display_size = 0.5
            cockpit_hr.location = anchors["cockpit_pos"]
            if root:
                cockpit_hr.parent = root
            col.objects.link(cockpit_hr)

        # Steering wheel dummy
        steer_hr = context.scene.objects.get("STEER_HR")
        if not steer_hr:
            steer_hr = bpy.data.objects.new("STEER_HR", None)
            steer_hr.empty_display_type = 'CIRCLE'
            steer_hr.empty_display_size = anchors["steer_radius"]
            steer_hr.location = anchors["steer_pos"]
            steer_hr.parent = cockpit_hr
            steer_hr.matrix_parent_inverse = cockpit_hr.matrix_world.inverted()
            col.objects.link(steer_hr)
            
            # If steering wheel mesh exists and unparented, parent it
            s_mesh = anchors["steer_mesh"]
            if s_mesh and s_mesh.parent != steer_hr:
                orig_m = s_mesh.matrix_world.copy()
                s_mesh.parent = steer_hr
                s_mesh.matrix_parent_inverse = steer_hr.matrix_world.inverted()
                s_mesh.matrix_world = orig_m

        if self.auto_detect:
            pos_x = anchors["driver_pos"].x
            pos_y = anchors["driver_pos"].y
            pos_z = anchors["driver_pos"].z
            eyes_x = anchors["driver_eyes"].x
            eyes_y = anchors["driver_eyes"].y
            eyes_z = anchors["driver_eyes"].z
        else:
            pos_x = self.lateral_offset
            pos_y = anchors["driver_pos"].y
            pos_z = self.seat_height
            eyes_x = self.lateral_offset
            eyes_y = pos_y - 0.08
            eyes_z = pos_z + 0.58

        # Driver seat / pelvis anchor
        driver_pos = context.scene.objects.get("DRIVER_POS")
        if not driver_pos:
            driver_pos = bpy.data.objects.new("DRIVER_POS", None)
            driver_pos.empty_display_type = 'SINGLE_ARROW'
            driver_pos.empty_display_size = 0.35
            col.objects.link(driver_pos)

        driver_pos.location = (pos_x, pos_y, pos_z)
        driver_pos.rotation_euler = (0.0, 0.0, math.radians(-90))
        if cockpit_hr:
            driver_pos.parent = cockpit_hr
            driver_pos.matrix_parent_inverse = cockpit_hr.matrix_world.inverted()

        # Driver eyes / cockpit camera
        driver_eyes = context.scene.objects.get("DRIVER_EYES")
        if not driver_eyes:
            driver_eyes = bpy.data.objects.new("DRIVER_EYES", None)
            driver_eyes.empty_display_type = 'SPHERE'
            driver_eyes.empty_display_size = 0.12
            col.objects.link(driver_eyes)

        driver_eyes.location = (eyes_x, eyes_y, eyes_z)
        driver_eyes.parent = driver_pos
        driver_eyes.matrix_parent_inverse = driver_pos.matrix_world.inverted()

        # Select DRIVER_POS
        for o in context.selected_objects:
            o.select_set(False)
        driver_pos.select_set(True)
        context.view_layer.objects.active = driver_pos

        self.report({'INFO'}, f"Created/Updated DRIVER_POS ({pos_x:.3f}, {pos_y:.3f}, {pos_z:.3f}) and DRIVER_EYES ({eyes_x:.3f}, {eyes_y:.3f}, {eyes_z:.3f}).")
        return {'FINISHED'}


class KN5_OT_AutoRigWheels(bpy.types.Operator):
    """Automatically detects, repairs, and parents rims, tires, and brake discs to proper WHEEL_XX empties."""
    bl_idname = "kn5.auto_rig_wheels"
    bl_label = "Auto-Rig Wheels & Rims"
    bl_description = "Detects rims, tires, and brake discs, repairs naming typos (e.g. WHELL_RR), removes empty duplicates, and parents parts to WHEEL_LF, RF, LR, RR"
    bl_options = {'REGISTER', 'UNDO'}

    center_dummies: BoolProperty(
        name="Center Dummies to Wheels",
        description="Recenter WHEEL_XX dummy origins to the geometric bounding box center of their tires/rims",
        default=True,
    )
    clean_orphans: BoolProperty(
        name="Clean Orphan / Duplicate Empties",
        description="Removes unused duplicate empties (.001, .002) and FBX import leftovers",
        default=True,
    )
    wheel_rotation: EnumProperty(
        name="Wheel Rotation",
        items=[
            ('NONE', "0° (Kunos Standard)", "Do not rotate - Assetto Corsa requires 0,0,0 identity rotation"),
            ('Z_NEG90', "Z: -90° (Align -Y)", "Rotate -90 degrees on Z axis"),
            ('Y_90', "Y: 90°", "Rotate 90 degrees on Y axis"),
            ('X_90', "X: 90°", "Rotate 90 degrees on X axis"),
        ],
        default='NONE',
        description="Rotation applied to WHEEL_XX empties (Keep 0° for Assetto Corsa)",
    )

    def execute(self, context):
        import mathutils

        # 1. Repair common dummy naming typos & rename conflicting MESH objects
        typo_map = {
            "WHELL_LF": "WHEEL_LF",
            "WHELL_RF": "WHEEL_RF",
            "WHELL_LR": "WHEEL_LR",
            "WHELL_RR": "WHEEL_RR",
            "WHEEL_FL": "WHEEL_LF",
            "WHEEL_FR": "WHEEL_RF",
            "WHEEL_RL": "WHEEL_LR",
        }
        for o in list(context.scene.objects):
            up = o.name.upper()
            if up in typo_map:
                o.name = typo_map[up]

        # Critical: If any MESH object is named WHEEL_LF/RF/LR/RR, rename it to RIM_XX
        # so that the actual empty dummy can own the required Assetto Corsa WHEEL_XX name.
        corners = ["LF", "RF", "LR", "RR"]
        for o in list(context.scene.objects):
            if o.type == 'MESH':
                for c in corners:
                    if o.name.upper() == f"WHEEL_{c}":
                        candidate_name = f"RIM_{c}"
                        if candidate_name in context.scene.objects:
                            candidate_name = f"WHEEL_MESH_{c}"
                        print(f"Auto-Rig: Renamed conflicting MESH '{o.name}' -> '{candidate_name}'")
                        o.name = candidate_name

        # 2. Clean orphan/leftover FBX duplicates if enabled
        if self.clean_orphans:
            for o in list(context.scene.objects):
                if "FBX:_childa" in o.name:
                    bpy.data.objects.remove(o, do_unlink=True)
                elif o.type == 'EMPTY' and (o.name.endswith(".001") or o.name.endswith(".002")):
                    if "WHEEL_" in o.name.upper() or "SUSP_" in o.name.upper():
                        if not o.children:
                            bpy.data.objects.remove(o, do_unlink=True)

        # 3. Locate or create standard WHEEL_XX dummies (guaranteed clean name)
        wheel_dummies = {}

        for c in corners:
            # Check exact match
            dummy = context.scene.objects.get(f"WHEEL_{c}")
            if dummy and dummy.type == 'EMPTY':
                wheel_dummies[c] = dummy
            else:
                # Search for case-insensitive or .001 empty
                for o in context.scene.objects:
                    if o.type == 'EMPTY' and (o.name.upper() == f"WHEEL_{c}" or o.name.upper().startswith(f"WHEEL_{c}.")):
                        o.name = f"WHEEL_{c}"
                        dummy = o
                        break
                if dummy and dummy.type == 'EMPTY':
                    wheel_dummies[c] = dummy

        corner_parts = {c: [] for c in corners}
        corner_calipers = {c: [] for c in corners}
        ignored_keywords = [
            'LIGHT', 'LAMP', 'LAMB', 'LAMBA', 'FAR', 'STOP', 'FREN', 'SIGNAL', 'SINYAL',
            'EMISSIVE', 'REFL', 'REFLECTOR', 'GL', 'ANTIFOG', 'FOG', 'HEADLIGHT', 'TAILLIGHT',
            'BRAKELIGHT', 'INDICATOR', 'GLASS', 'WINDOW', 'WINDSHIELD', 'MIRROR', 'DOOR',
            'BODY', 'BUMPER', 'HOOD', 'BONNET', 'TRUNK', 'BOOT', 'ROOF', 'WING', 'SPOILER',
            'CHASSIS', 'COCKPIT', 'INTERIOR', 'STEER', 'SEAT', 'CHAIR', 'PEDAL', 'HANDBRAKE',
            'SHIFTER', 'GEAR', 'LEVER', 'DASH', 'CLUSTER', 'CONSOLE', 'EXHAUST', 'ENGINE',
            'WIPER', 'BASE', 'RAIL', 'COLUMN',
        ]

        scene_light_names = set()
        scene_lights = getattr(context.scene, "kn5_lights", None)
        if scene_lights:
            for entry in scene_lights.entries:
                if entry.mesh_name:
                    scene_light_names.add(entry.mesh_name.upper())
                if entry.mesh_object:
                    scene_light_names.add(entry.mesh_object.name.upper())

        def _get_wheel_corner(name: str) -> Optional[str]:
            import re
            up = name.upper()
            patterns = [
                (r"(?:^|[_\.\s])(LF|FL|FRONT_LEFT|FRONT_L|F_L)(?:[_\.\s]|\.\d+|$)", "LF"),
                (r"(?:^|[_\.\s])(RF|FR|FRONT_RIGHT|FRONT_R|F_R)(?:[_\.\s]|\.\d+|$)", "RF"),
                (r"(?:^|[_\.\s])(LR|RL|REAR_LEFT|BACK_LEFT|REAR_L|BACK_L|R_L|B_L|BL)(?:[_\.\s]|\.\d+|$)", "LR"),
                (r"(?:^|[_\.\s])(RR|REAR_RIGHT|BACK_RIGHT|REAR_R|BACK_R|R_R|B_R|BR)(?:[_\.\s]|\.\d+|$)", "RR"),
            ]
            for pattern, corner in patterns:
                if re.search(pattern, up):
                    return corner
            return None

        wheel_keywords = ['RIM', 'TYRE', 'TIRE', 'WHEEL', 'DISC', 'DISK', 'ROTOR']
        caliper_keywords = ['CALIPER', 'KALIPER', 'PINZA']

        for o in context.scene.objects:
            if o.type != 'MESH':
                continue
            name_upper = o.name.upper()

            # Skip registered lights or light/body/interior objects
            if name_upper in scene_light_names:
                continue
            if any(k in name_upper for k in ignored_keywords):
                continue

            is_caliper = (
                any(k in name_upper for k in caliper_keywords)
                or name_upper.startswith(("CALIPER_", "KALIPER_", "PINZA_"))
            )

            # Must be a legitimate wheel component
            is_component = (
                is_caliper
                or any(k in name_upper for k in wheel_keywords)
                or name_upper.startswith(("RIM_", "TYRE_", "TIRE_", "WHEEL_MESH_", "DISC_", "DISK_", "ROTOR_"))
            )
            if not is_component:
                for slot in getattr(o, "material_slots", []):
                    if slot.material:
                        ac = getattr(slot.material, "assettoCorsa", None)
                        if ac and getattr(ac, "shader_name", "").lower() == "ksbrakedisc":
                            is_component = True
                            break

            if not is_component:
                continue

            # Match corner tag with boundary protection
            matched = _get_wheel_corner(name_upper)
            if matched:
                if is_caliper:
                    corner_calipers[matched].append(o)
                else:
                    corner_parts[matched].append(o)

        # 5. Create missing dummies, accurately center without transform drift, and parent parts
        parented_count = 0
        car_root = context.scene.objects.get("CAR_ROOT") or context.scene.objects.get("thalia") or context.scene.objects.get("clio_symbol")

        def get_target_wheel_rot(corner: str):
            if self.wheel_rotation == 'Z_NEG90':
                return (0.0, 0.0, math.radians(-90))
            elif self.wheel_rotation == 'Y_90':
                return (0.0, math.radians(90 if corner in ('LF', 'LR') else -90), 0.0)
            elif self.wheel_rotation == 'X_90':
                return (math.radians(90), 0.0, 0.0)
            return (0.0, 0.0, 0.0)

        for c in corners:
            parts = corner_parts[c]
            calipers = corner_calipers[c]
            if not parts and not calipers and c not in wheel_dummies:
                continue

            # Compute bounding box center across rotating parts in world coordinates (ignoring off-center caliper)
            centers = []
            for p in parts:
                if p.bound_box:
                    bb_w = [p.matrix_world @ mathutils.Vector(v) for v in p.bound_box]
                    centers.append(sum(bb_w, mathutils.Vector()) / 8.0)
                else:
                    centers.append(p.matrix_world.translation.copy())

            dummy = wheel_dummies.get(c)
            target_center = (sum(centers, mathutils.Vector()) / len(centers)) if centers else (dummy.matrix_world.translation.copy() if dummy else None)
            target_rot = get_target_wheel_rot(c)

            if not dummy:
                dummy = bpy.data.objects.new(f"WHEEL_{c}", None)
                dummy.empty_display_type = 'CIRCLE'
                dummy.empty_display_size = 0.35
                context.collection.objects.link(dummy)
                # Wheel dummies in AC must be direct children of the car root (top-level)
                dummy.parent = None
                if target_center is not None:
                    dummy.matrix_world.translation = target_center
                dummy.rotation_euler = target_rot
                context.view_layer.update()
                wheel_dummies[c] = dummy
            elif target_center is not None and (self.center_dummies or dummy.location.length_squared < 0.001 or abs(dummy.location.x) < 0.1):
                # Recenter existing dummy to geometric center and apply orientation without causing child drift
                diff = (dummy.matrix_world.translation - target_center).length
                rot_diff = sum(abs(a - b) for a, b in zip(dummy.rotation_euler, target_rot))
                if diff > 0.0001 or (self.wheel_rotation != 'NONE' and rot_diff > 0.001):
                    child_transforms = [(child, child.matrix_world.copy()) for child in dummy.children]
                    
                    # If parent is a SUSP_ empty, move SUSP_ dummy and zero out WHEEL_ location
                    if dummy.parent and "SUSP_" in dummy.parent.name.upper():
                        susp = dummy.parent
                        susp.matrix_world.translation = target_center
                        if self.wheel_rotation != 'NONE':
                            susp.rotation_euler = target_rot
                        dummy.location = (0.0, 0.0, 0.0)
                        dummy.rotation_euler = (0.0, 0.0, 0.0)
                    else:
                        dummy.matrix_world.translation = target_center
                        if self.wheel_rotation != 'NONE':
                            dummy.rotation_euler = target_rot

                    context.view_layer.update()
                    for child, orig_wmat in child_transforms:
                        child.matrix_world = orig_wmat
                        child.matrix_parent_inverse = dummy.matrix_world.inverted()
                    context.view_layer.update()

            # Parent rotating parts (rim, tyre, disc) to the wheel dummy preserving world matrix
            for p in parts:
                if p.parent != dummy:
                    orig_mat = p.matrix_world.copy()
                    p.parent = dummy
                    p.matrix_parent_inverse = dummy.matrix_world.inverted()
                    p.matrix_world = orig_mat
                    parented_count += 1

            # Parent brake calipers under SUSP_XX dummy so they steer/travel with suspension but NEVER spin
            if calipers:
                susp_empty = context.scene.objects.get(f"SUSP_{c}")
                if not susp_empty or susp_empty.type != 'EMPTY':
                    for o in context.scene.objects:
                        if o.type == 'EMPTY' and (o.name.upper() == f"SUSP_{c}" or o.name.upper().startswith(f"SUSP_{c}.")):
                            o.name = f"SUSP_{c}"
                            susp_empty = o
                            break
                if not susp_empty:
                    susp_empty = bpy.data.objects.new(f"SUSP_{c}", None)
                    susp_empty.empty_display_type = 'SINGLE_ARROW'
                    susp_empty.empty_display_size = 0.4
                    context.collection.objects.link(susp_empty)
                    susp_empty.matrix_world.translation = dummy.matrix_world.translation
                    if car_root:
                        susp_empty.parent = car_root
                        susp_empty.matrix_parent_inverse = car_root.matrix_world.inverted()
                    context.view_layer.update()

                for cal in calipers:
                    if cal.parent != susp_empty:
                        orig_mat = cal.matrix_world.copy()
                        cal.parent = susp_empty
                        cal.matrix_parent_inverse = susp_empty.matrix_world.inverted()
                        cal.matrix_world = orig_mat
                        parented_count += 1

        context.view_layer.update()
        msg = f"Auto-Rig Wheels: Configured 4 wheel hubs, parented {parented_count} meshes (rims, tires, discs, non-spinning calipers under SUSP)."
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def update_ini_file_values(filepath, updates):
    """Updates key=value pairs within sections in an INI file while preserving formatting."""
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        written_keys = {sec: set() for sec in updates}
        processed_sections = set()

        current_section = None
        new_lines = []

        def flush_unwritten_keys(sec):
            if sec and sec in updates:
                for k, v in updates[sec].items():
                    if k not in written_keys[sec]:
                        new_lines.append(f"{k}={v}\n")
                        written_keys[sec].add(k)

        for line in lines:
            stripped = line.strip()
            sec_match = re.match(r'^\[([^\]]+)\]', stripped)
            if sec_match:
                flush_unwritten_keys(current_section)
                current_section = sec_match.group(1).strip()
                processed_sections.add(current_section)
                new_lines.append(line)
                continue

            if current_section and current_section in updates:
                sec_updates = updates[current_section]
                key_match = re.match(r'^([A-Za-z0-9_]+)\s*=', stripped)
                if key_match:
                    key = key_match.group(1).strip()
                    if key in sec_updates:
                        comment = ""
                        if ";" in line:
                            comment = " ;" + line.split(";", 1)[1].rstrip()
                        new_val = sec_updates[key]
                        new_lines.append(f"{key}={new_val}{comment}\n")
                        written_keys[current_section].add(key)
                        continue
            new_lines.append(line)

        flush_unwritten_keys(current_section)

        # If any section in updates was entirely missing from file, append it
        for sec, kv in updates.items():
            if sec not in processed_sections:
                new_lines.append(f"\n[{sec}]\n")
                for k, v in kv.items():
                    new_lines.append(f"{k}={v}\n")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False


class KN5_OT_SyncModelToPhysicsINI(bpy.types.Operator):
    """Measures 3D car model dimensions, wheelbase, track, tyres, and colliders, and automatically updates data/*.ini files."""
    bl_idname = "kn5.sync_model_to_physics_ini"
    bl_label = "Auto-Sync 3D Model to Physics INI"
    bl_description = "Calculates exact 3D wheelbase, track width, tyre radius, inertia box, colliders, and aero positions and writes them to suspensions.ini, car.ini, tyres.ini, colliders.ini, aero.ini"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        car_dir = find_car_directory(context)
        if not car_dir:
            self.report({'WARNING'}, "Could not locate car folder (data/ folder not found).")
            return {'CANCELLED'}
        data_dir = os.path.join(car_dir, "data")
        if not os.path.exists(data_dir):
            self.report({'WARNING'}, f"data/ directory does not exist in {car_dir}.")
            return {'CANCELLED'}

        # Extract 3D metrics from Blender scene
        all_verts = []
        for o in context.scene.objects:
            if o.type == 'MESH' and not o.name.startswith("__"):
                for v in o.data.vertices:
                    w_co = o.matrix_world @ v.co
                    all_verts.append(w_co)

        if not all_verts:
            self.report({'WARNING'}, "No mesh objects found in scene to measure.")
            return {'CANCELLED'}

        min_x, max_x = min(v.x for v in all_verts), max(v.x for v in all_verts)
        min_y, max_y = min(v.y for v in all_verts), max(v.y for v in all_verts)
        min_z, max_z = min(v.z for v in all_verts), max(v.z for v in all_verts)

        total_width = max_x - min_x
        total_length = max_y - min_y
        total_height = max_z - min_z
        front_bumper_z = -min_y
        rear_bumper_z = -max_y

        w_lf = context.scene.objects.get("WHEEL_LF")
        w_rf = context.scene.objects.get("WHEEL_RF")
        w_lr = context.scene.objects.get("WHEEL_LR")
        w_rr = context.scene.objects.get("WHEEL_RR")

        front_track = abs(w_lf.matrix_world.translation.x - w_rf.matrix_world.translation.x) if (w_lf and w_rf) else 1.38
        rear_track = abs(w_lr.matrix_world.translation.x - w_rr.matrix_world.translation.x) if (w_lr and w_rr) else 1.38
        front_axle_z = -(w_lf.matrix_world.translation.y + w_rf.matrix_world.translation.y) / 2.0 if (w_lf and w_rf) else 1.336
        rear_axle_z = -(w_lr.matrix_world.translation.y + w_rr.matrix_world.translation.y) / 2.0 if (w_lr and w_rr) else -1.161
        wheelbase = abs(front_axle_z - rear_axle_z)
        cg_loc = abs(rear_axle_z) / wheelbase if wheelbase > 0.001 else 0.50

        # Collect all wheel mesh parts to accurately measure tyre radius (tyre is always outer-most / largest)
        wheel_candidates = []
        if w_lf:
            wheel_candidates.extend([c for c in w_lf.children if c.type == 'MESH'])
        for name in ["TYRE_LF", "WHEEL_MESH_LF", "TIRE_LF", "WHEEL_LF", "RIM_LF"]:
            obj = context.scene.objects.get(name)
            if obj and obj not in wheel_candidates and obj.type == 'MESH':
                wheel_candidates.append(obj)

        mesh_radii = [max(c.dimensions.y, c.dimensions.z) / 2.0 for c in wheel_candidates]
        mesh_widths = [c.dimensions.x for c in wheel_candidates]
        # Tyre radius must be the maximum radius (tire is larger than rim; rim is ~0.20-0.22m, tyre is ~0.28-0.34m)
        tyre_radius = max(mesh_radii) if mesh_radii else 0.320
        if tyre_radius < 0.26:
            tyre_radius = 0.320
        tyre_width = max(mesh_widths) if mesh_widths else 0.185

        # Read existing suspensions.ini values to preserve custom camber/basey/cg if present
        susp_file = os.path.join(data_dir, "suspensions.ini")
        existing_basey_f = -0.260
        existing_basey_r = -0.270
        existing_cg = cg_loc
        if os.path.exists(susp_file):
            try:
                import configparser
                sp = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), strict=False)
                with open(susp_file, 'r', encoding='utf-8', errors='ignore') as sf:
                    sp.read_file(sf)
                existing_basey_f = float(sp.get('FRONT', 'BASEY', fallback='-0.260'))
                existing_basey_r = float(sp.get('REAR', 'BASEY', fallback='-0.270'))
                existing_cg = float(sp.get('BASIC', 'CG_LOCATION', fallback=str(cg_loc)))
            except Exception:
                pass

        # Calculate exact GRAPHICS_OFFSET for car.ini [BASIC] section:
        model_wheel_y = (w_lf.matrix_world.translation.z + w_rf.matrix_world.translation.z) / 2.0 if (w_lf and w_rf) else tyre_radius
        calc_offset_y = round(-(model_wheel_y - existing_basey_f), 3)
        phys_front_z = wheelbase * (1.0 - existing_cg)
        calc_offset_z = round(phys_front_z - front_axle_z, 3)

        # 1. suspensions.ini
        update_ini_file_values(susp_file, {
            "BASIC": {
                "WHEELBASE": f"{wheelbase:.3f}",
                "CG_LOCATION": f"{existing_cg:.3f}",
            },
            "FRONT": {
                "TRACK": f"{front_track:.3f}",
                "BASEY": f"{existing_basey_f:.3f}",
            },
            "REAR": {
                "TRACK": f"{rear_track:.3f}",
                "BASEY": f"{existing_basey_r:.3f}",
            },
            "GRAPHICS_OFFSETS": {
                "WHEEL_LF": "0.0",
                "SUSP_LF": "0.0",
                "WHEEL_RF": "0.0",
                "SUSP_RF": "0.0",
                "WHEEL_LR": "0.0",
                "SUSP_LR": "0.0",
                "WHEEL_RR": "0.0",
                "SUSP_RR": "0.0",
            }
        })

        # 2. car.ini - Critical: GRAPHICS_OFFSET belongs in [BASIC], NOT [GRAPHICS]!
        car_ini_file = os.path.join(data_dir, "car.ini")
        if os.path.exists(car_ini_file):
            with open(car_ini_file, 'r', encoding='utf-8', errors='ignore') as cf:
                clines = cf.readlines()
            # Clean stray GRAPHICS_OFFSET
            clines = [l for l in clines if not l.strip().startswith("GRAPHICS_OFFSET")]
            with open(car_ini_file, 'w', encoding='utf-8') as cf:
                cf.writelines(clines)

        update_ini_file_values(car_ini_file, {
            "BASIC": {
                "GRAPHICS_OFFSET": f"0,{calc_offset_y},{calc_offset_z}",
                "INERTIA": f"{min(total_width, 1.75):.2f}, {min(total_height, 1.50):.2f}, {total_length:.2f}",
            }
        })

        # 3. tyres.ini
        tyre_updates = {}
        for sec in ["FRONT", "REAR", "FRONT_1", "REAR_1", "FRONT_2", "REAR_2", "FRONT_3", "REAR_3"]:
            tyre_updates[sec] = {
                "RADIUS": f"{tyre_radius:.3f}",
                "WIDTH": f"{tyre_width:.3f}",
            }
        update_ini_file_values(os.path.join(data_dir, "tyres.ini"), tyre_updates)

        # 4. colliders.ini
        floor_center_z = (front_bumper_z + rear_bumper_z) / 2.0
        floor_len = total_length * 0.94
        update_ini_file_values(os.path.join(data_dir, "colliders.ini"), {
            "COLLIDER_0": {
                "CENTRE": f"0, 0.25, {floor_center_z:.2f}",
                "SIZE": f"{min(total_width*0.85, 1.65):.2f}, 0.20, {floor_len:.2f}",
            }
        })

        # 5. aero.ini
        update_ini_file_values(os.path.join(data_dir, "aero.ini"), {
            "WING_0": {
                "POSITION": f"0, {total_height*0.45:.2f}, {floor_center_z:.2f}",
            },
            "WING_1": {
                "POSITION": f"0, 0.35, {front_bumper_z - 0.25:.2f}",
            },
            "WING_2": {
                "POSITION": f"0, 0.85, {rear_bumper_z + 0.20:.2f}",
            }
        })

        # 6. ambient_shadows.ini
        update_ini_file_values(os.path.join(data_dir, "ambient_shadows.ini"), {
            "SETTINGS": {
                "WIDTH": f"{total_width:.2f}",
                "LENGTH": f"{total_length:.2f}",
            }
        })

        msg = f"Synced 3D Model to INI! WB={wheelbase:.3f}m, CG={cg_loc:.3f}, Track={front_track:.3f}m, Length={total_length:.2f}m"
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class KN5_OT_AlignWheelsToPhysics(bpy.types.Operator):
    """Calculates and aligns wheel positions or GRAPHICS_OFFSET from suspensions.ini and car.ini."""
    bl_idname = "kn5.align_wheels_physics"
    bl_label = "Align Wheels from INI Data"
    bl_description = "Reads suspensions.ini and car.ini to inspect and align wheel geometry or calculate car.ini GRAPHICS_OFFSET"
    bl_options = {'REGISTER', 'UNDO'}

    apply_to_car_ini: BoolProperty(
        name="Write GRAPHICS_OFFSET to car.ini",
        description="Explicitly write the calculated visual offset; disabled by default so alignment is read-only",
        default=False,
    )

    def execute(self, context):
        import configparser

        car_dir = find_car_directory(context)
        found_data = os.path.join(car_dir, "data") if car_dir else None
        if not found_data or not os.path.exists(os.path.join(found_data, "suspensions.ini")):
            blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""
            for cand in [os.path.join(blend_dir, "data"), os.path.join(blend_dir, "..", "data")]:
                if os.path.exists(os.path.join(cand, "suspensions.ini")):
                    found_data = cand
                    break

        if not found_data:
            self.report({'WARNING'}, "Could not find suspensions.ini in standard car folders.")
            return {'CANCELLED'}

        susp_path = os.path.join(found_data, "suspensions.ini")
        car_path = os.path.join(found_data, "car.ini")

        try:
            susp_parser = configparser.ConfigParser(inline_comment_prefixes=(';', '#'), strict=False)
            with open(susp_path, 'r', encoding='utf-8', errors='ignore') as susp_file:
                susp_parser.read_file(susp_file, source=susp_path)

            wb = float(susp_parser.get('BASIC', 'WHEELBASE', fallback='2.473'))
            cg = float(susp_parser.get('BASIC', 'CG_LOCATION', fallback='0.60'))
            track_f = float(susp_parser.get('FRONT', 'TRACK', fallback='1.38'))
            basey_f = float(susp_parser.get('FRONT', 'BASEY', fallback='-0.26'))

            # Front and rear physics wheel Z coordinates (AC DirectX: +Z = forward, -Z = backward)
            phys_front_z = wb * (1.0 - cg)
            phys_rear_z = -wb * cg

            # Check Blender wheel dummies
            wheel_lf = context.scene.objects.get("WHEEL_LF")
            wheel_lr = context.scene.objects.get("WHEEL_LR")

            if wheel_lf and wheel_lr:
                # Blender (X, Y, Z) -> AC (X, Z, -Y)
                model_front_z = -wheel_lf.matrix_world.translation.y
                model_rear_z = -wheel_lr.matrix_world.translation.y
                model_wheel_y = wheel_lf.matrix_world.translation.z

                front_offset_z = phys_front_z - model_front_z
                rear_offset_z = phys_rear_z - model_rear_z
                calc_offset_z = round((front_offset_z + rear_offset_z) / 2.0, 3)
                calc_offset_y = round(basey_f - model_wheel_y, 3)
                axle_delta = round(front_offset_z - rear_offset_z, 3)

                msg = (f"Physics WB={wb:.3f}m, CG={cg:.3f}. "
                       f"Front/rear Z offsets={front_offset_z:.3f}/{rear_offset_z:.3f}m "
                       f"(axle mismatch {axle_delta:+.3f}m). "
                       f"Mean GRAPHICS_OFFSET=0,{calc_offset_y},{calc_offset_z}")
                print(msg)

                if self.apply_to_car_ini and os.path.exists(car_path):
                    with open(car_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    # Clean stray GRAPHICS_OFFSET from anywhere
                    lines = [l for l in lines if not l.strip().startswith("GRAPHICS_OFFSET")]
                    new_lines = []
                    inserted = False
                    for l in lines:
                        new_lines.append(l)
                        if l.strip().startswith("[BASIC]") and not inserted:
                            new_lines.append(f"GRAPHICS_OFFSET=0,{calc_offset_y},{calc_offset_z}\t\t; 3 axis correction (x,y,z), applies to 3D model (meters)\n")
                            inserted = True
                    with open(car_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    self.report({'INFO'}, f"Updated car.ini [BASIC] GRAPHICS_OFFSET=0,{calc_offset_y},{calc_offset_z}.")
                else:
                    self.report({'INFO'}, msg)
            else:
                self.report({'INFO'}, f"Read physics data: Wheelbase={wb:.3f}m, CG={cg:.2f}, Track={track_f:.3f}m")

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to parse suspension data: {e}")
            return {'CANCELLED'}


class KN5_OT_ExportDriverKNH(bpy.types.Operator, ExportHelper):
    """Exports Assetto Corsa driver_base_pos.knh to set driver model position in game."""
    bl_idname = "kn5.export_driver_knh"
    bl_label = "Export driver_base_pos.knh"
    bl_description = "Exports the driver_base_pos.knh file to set driver model seating position and height in Assetto Corsa"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".knh"
    filter_glob: StringProperty(default="*.knh", options={'HIDDEN'})

    offset_x: FloatProperty(
        name="Lateral (X)",
        description="Left/Right position in meters (AC coordinates: + = right, - = left)",
        default=0.0,
    )
    offset_y: FloatProperty(
        name="Height (Y)",
        description="Vertical height in meters (higher raises driver, lower sinks driver)",
        default=0.28,
    )
    offset_z: FloatProperty(
        name="Longitudinal (Z)",
        description="Forward/Backward position in meters (AC coordinates: + = forward, - = backward)",
        default=0.0,
    )
    use_selected: BoolProperty(
        name="Read from Selected Object",
        description="Read coordinates from selected DRIVER_POS or Empty in Blender",
        default=True,
    )

    def invoke(self, context, event):
        if not self.filepath:
            self.filepath = "driver_base_pos.knh"

        sel = context.active_object
        if sel and self.use_selected:
            # Blender (X, Y, Z) -> AC DirectX (X, Z, -Y)
            loc = sel.matrix_world.translation if sel.parent else sel.location
            self.offset_x = round(loc.x, 3)
            self.offset_y = round(loc.z, 3)
            self.offset_z = round(-loc.y, 3)

        return super().invoke(context, event)

    def execute(self, context):
        x = self.offset_x
        y = self.offset_y
        z = self.offset_z

        name = b"SCENE_ROOT"
        matrix_floats = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            float(x), float(y), float(z), 1.0,
            0.0
        ]
        raw = struct.pack("<I", len(name)) + name + struct.pack(f"<{len(matrix_floats)}f", *matrix_floats)

        try:
            with open(self.filepath, "wb") as f:
                f.write(raw)
            msg = f"Saved driver_base_pos.knh (X={x:.3f}m, Height Y={y:.3f}m, Z={z:.3f}m) to {os.path.basename(self.filepath)}"
            print(msg)
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Failed to write driver_base_pos.knh: {e}")
            return {'CANCELLED'}


class KN5_OT_ImportDriverKNH(bpy.types.Operator, ImportHelper):
    """Imports Assetto Corsa driver_base_pos.knh to read and apply driver model seating position."""
    bl_idname = "kn5.import_driver_knh"
    bl_label = "Import driver_base_pos.knh"
    bl_description = "Reads driver_base_pos.knh and sets driver seating position (DRIVER_POS) in Blender"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".knh"
    filter_glob: StringProperty(default="*.knh", options={'HIDDEN'})

    def execute(self, context):
        if not os.path.exists(self.filepath):
            self.report({'ERROR'}, f"File not found: {self.filepath}")
            return {'CANCELLED'}

        try:
            with open(self.filepath, "rb") as f:
                data = f.read()

            if len(data) < 72:
                self.report({'ERROR'}, f"Invalid KNH file size: {len(data)} bytes")
                return {'CANCELLED'}

            name_len = struct.unpack("<I", data[:4])[0]
            name = data[4:4+name_len].decode("utf-8", errors="ignore")
            floats = struct.unpack("<17f", data[4+name_len:4+name_len+68])

            ac_x = floats[12]
            ac_y = floats[13]
            ac_z = floats[14]

            # In AC driver_base_pos.knh:
            # X = lateral offset, Y = height offset (up), Z = longitudinal offset
            # Convert to Blender coords: X = X, Y = -Z, Z = Y
            # Or if applying to DRIVER_POS
            driver_pos = context.scene.objects.get("DRIVER_POS")
            if not driver_pos:
                driver_pos = bpy.data.objects.new("DRIVER_POS", None)
                driver_pos.empty_display_type = 'SINGLE_ARROW'
                driver_pos.empty_display_size = 0.35
                context.collection.objects.link(driver_pos)
                cockpit_hr = context.scene.objects.get("COCKPIT_HR")
                if cockpit_hr:
                    driver_pos.parent = cockpit_hr
                    driver_pos.matrix_parent_inverse = cockpit_hr.matrix_world.inverted()

            # Base seated position: lateral default -0.38m (driver side), seat height 0.45m + ac_y
            driver_pos.location.z = max(0.20, 0.45 + ac_y if ac_y < 0.20 else ac_y)
            if abs(ac_x) > 0.05:
                driver_pos.location.x = ac_x
            if abs(ac_z) > 0.05:
                driver_pos.location.y = -ac_z

            # Sync DRIVER_EYES if exists
            driver_eyes = context.scene.objects.get("DRIVER_EYES")
            if driver_eyes and driver_eyes.parent == driver_pos:
                driver_eyes.location = (0.0, 0.05, 0.60)

            bpy.context.view_layer.update()
            msg = f"Imported driver position: X={ac_x:.3f}m, Height Y={ac_y:.3f}m, Z={ac_z:.3f}m (DRIVER_POS Z={driver_pos.location.z:.3f}m)"
            print(msg)
            self.report({'INFO'}, msg)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed to import KNH: {e}")
            return {'CANCELLED'}


# ---------------------------------------------------------------------------
# Vehicle Cameras System (Cockpit, Bonnet, Bumper, Chase & cameras.ini)
# ---------------------------------------------------------------------------

def ac_to_blender_pos(ac_vec: mathutils.Vector) -> mathutils.Vector:
    """AC DirectX (X right, Y up, Z forward) -> Blender (X right, Y forward, Z up)"""
    return mathutils.Vector((float(ac_vec.x), float(-ac_vec.z), float(ac_vec.y)))


def blender_to_ac_pos(b_vec: mathutils.Vector) -> mathutils.Vector:
    """Blender (X right, Y forward, Z up) -> AC DirectX (X right, Y up, Z forward)"""
    return mathutils.Vector((float(b_vec.x), float(b_vec.z), float(-b_vec.y)))


def ac_to_blender_camera_matrix(pos: mathutils.Vector, fwd: mathutils.Vector, up: mathutils.Vector) -> mathutils.Matrix:
    """Reconstructs Blender camera 4x4 matrix from AC position, forward and up vectors."""
    b_pos = ac_to_blender_pos(pos)
    b_fwd = mathutils.Vector((float(fwd.x), float(-fwd.z), float(fwd.y))).normalized()
    b_up = mathutils.Vector((float(up.x), float(-up.z), float(up.y))).normalized()
    b_right = b_fwd.cross(b_up).normalized()
    b_up_clean = b_right.cross(b_fwd).normalized()

    # Blender camera looks down -Z, +Y is up, +X is right
    rot_3x3 = mathutils.Matrix((
        (b_right.x, b_up_clean.x, -b_fwd.x),
        (b_right.y, b_up_clean.y, -b_fwd.y),
        (b_right.z, b_up_clean.z, -b_fwd.z),
    ))
    mat = rot_3x3.to_4x4()
    mat.translation = b_pos
    return mat


def blender_to_ac_camera_data(cam_obj: bpy.types.Object):
    """Extracts AC position, forward vector, up vector, and pitch angle (deg) from a Blender camera."""
    mw = cam_obj.matrix_world
    b_pos = mw.translation
    ac_pos = blender_to_ac_pos(b_pos)

    # Blender camera looks down -Z, +Y is up
    b_fwd = mw.to_3x3() @ mathutils.Vector((0, 0, -1))
    b_up = mw.to_3x3() @ mathutils.Vector((0, 1, 0))

    ac_fwd = mathutils.Vector((float(b_fwd.x), float(b_fwd.z), float(-b_fwd.y))).normalized()
    ac_up = mathutils.Vector((float(b_up.x), float(b_up.z), float(-b_up.y))).normalized()

    # Pitch angle in degrees
    pitch_deg = math.degrees(math.asin(max(-1.0, min(1.0, ac_fwd.y))))
    return ac_pos, ac_fwd, ac_up, pitch_deg


def find_car_data_dir(context) -> str:
    """Locates the nearest car data/ directory from blend filepath or active workspace."""
    candidates = []
    if bpy.data.filepath:
        b_dir = os.path.dirname(bpy.data.filepath)
        candidates.append(os.path.join(b_dir, "data"))
        candidates.append(b_dir)
        candidates.append(os.path.join(os.path.dirname(b_dir), "data"))

    # Common workspace and game installation paths
    candidates.append(r"D:\Saved Games\SteamLibrary\steamapps\common\assettocorsa\content\cars\my_custom_car\data")
    candidates.append(r"C:\Users\Fatih\Desktop\thalia\data")
    candidates.append(r"D:\Saved Games\SteamLibrary\steamapps\common\assettocorsa\content\cars\thalia\data")

    for c in candidates:
        if os.path.isdir(c) and (os.path.exists(os.path.join(c, "car.ini")) or os.path.exists(os.path.join(c, "cameras.ini"))):
            return c
    return ""


def update_ini_text_file(filepath: str, section: str, key_values: dict):
    """Updates key=value pairs in an INI file while preserving comments and layout."""
    if not os.path.exists(filepath):
        # Create fresh INI if not present
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"[{section}]\n")
            for k, v in key_values.items():
                f.write(f"{k}={v}\n")
        return

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    out_lines = []
    in_target_section = False
    updated_keys = set()
    section_found = False

    sec_header = f"[{section.upper()}]"

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_target_section:
                # Add any missing keys before leaving the target section
                for k, v in key_values.items():
                    if k not in updated_keys:
                        out_lines.append(f"{k}={v}\n")
                        updated_keys.add(k)
                in_target_section = False

            if stripped.upper() == sec_header:
                in_target_section = True
                section_found = True
            out_lines.append(line)
            continue

        if in_target_section and "=" in line and not stripped.startswith((";", "#")):
            parts = line.split("=", 1)
            key = parts[0].strip()
            if key in key_values:
                # Preserve inline comment if present
                comment = ""
                if ";" in parts[1]:
                    comment = " ;" + parts[1].split(";", 1)[1]
                elif "#" in parts[1]:
                    comment = " #" + parts[1].split("#", 1)[1]
                out_lines.append(f"{key}={key_values[key]}{comment}\n")
                updated_keys.add(key)
                continue

        out_lines.append(line)

    if in_target_section:
        for k, v in key_values.items():
            if k not in updated_keys:
                out_lines.append(f"{k}={v}\n")
                updated_keys.add(k)

    if not section_found:
        out_lines.append(f"\n[{section}]\n")
        for k, v in key_values.items():
            out_lines.append(f"{k}={v}\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(out_lines)


class KN5_OT_SetupCarCameras(bpy.types.Operator):
    """Creates a standard Assetto Corsa vehicle camera rig in Blender with interactive views."""
    bl_idname = "kn5.setup_car_cameras"
    bl_label = "Setup Car Cameras Rig"
    bl_description = "Creates standard car cameras (Cockpit, Bonnet, Bumper, Chase) with real-time viewport preview"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # 1. Collection for cameras
        col_name = "AC_CAMERAS"
        cam_col = bpy.data.collections.get(col_name)
        if not cam_col:
            cam_col = bpy.data.collections.new(col_name)
            context.scene.collection.children.link(cam_col)

        # Look for existing car.ini to auto-read current values
        data_dir = find_car_data_dir(context)
        car_ini_data = {}
        if data_dir:
            c_path = os.path.join(data_dir, "car.ini")
            if os.path.exists(c_path):
                cp = configparser.ConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
                cp.optionxform = str
                cp.read(c_path)
                if 'GRAPHICS' in cp:
                    car_ini_data = dict(cp['GRAPHICS'])

        # Camera specs definition
        # (name, default_ac_pos, default_pitch_deg, fov, display_size)
        driver_pos_ac = [float(x) for x in car_ini_data.get('DRIVEREYES', '0.375, 1.050, 0.120').split(',')[:3]]
        bonnet_pos_ac = [float(x) for x in car_ini_data.get('BONNET_CAMERA_POS', '0.0, 0.800, 0.300').split(',')[:3]]
        bonnet_pitch = float(car_ini_data.get('BONNET_CAMERA_PITCH', '-6.0'))
        bumper_pos_ac = [float(x) for x in car_ini_data.get('BUMPER_CAMERA_POS', '0.0, 0.300, 2.150').split(',')[:3]]
        bumper_pitch = float(car_ini_data.get('BUMPER_CAMERA_PITCH', '0.0'))

        cam_definitions = [
            {
                "name": "AC_CAM_DRIVEREYES",
                "label": "Cockpit / Driver Eyes",
                "pos_ac": mathutils.Vector((driver_pos_ac[0], driver_pos_ac[1], driver_pos_ac[2])),
                "pitch": float(car_ini_data.get('ON_BOARD_PITCH_ANGLE', '-1.0')),
                "fov": 56.0,
                "clip_start": 0.05,
            },
            {
                "name": "AC_CAM_BONNET",
                "label": "Bonnet / Hood Camera",
                "pos_ac": mathutils.Vector((bonnet_pos_ac[0], bonnet_pos_ac[1], bonnet_pos_ac[2])),
                "pitch": bonnet_pitch,
                "fov": 60.0,
                "clip_start": 0.10,
            },
            {
                "name": "AC_CAM_BUMPER",
                "label": "Front Bumper Camera",
                "pos_ac": mathutils.Vector((bumper_pos_ac[0], bumper_pos_ac[1], bumper_pos_ac[2])),
                "pitch": bumper_pitch,
                "fov": 62.0,
                "clip_start": 0.10,
            },
            {
                "name": "AC_CAM_CHASE",
                "label": "Chase / 3rd Person Camera",
                "pos_ac": mathutils.Vector((0.0, 1.650, -4.500)),
                "pitch": float(car_ini_data.get('CHASE_CAMERA_PITCH', '0.0')),
                "fov": 50.0,
                "clip_start": 0.20,
            },
        ]

        created_count = 0
        for spec in cam_definitions:
            cam_name = spec["name"]
            cam_obj = bpy.data.objects.get(cam_name)
            if not cam_obj:
                cam_data = bpy.data.cameras.new(cam_name)
                cam_obj = bpy.data.objects.new(cam_name, cam_data)
                cam_col.objects.link(cam_obj)
                created_count += 1
            else:
                cam_data = cam_obj.data

            # Lens setup
            cam_data.angle = math.radians(spec["fov"])
            cam_data.clip_start = spec["clip_start"]
            cam_data.clip_end = 2000.0

            # Compute orientation from position & pitch
            # AC forward vector with pitch: Y is up, Z is forward
            pitch_rad = math.radians(spec["pitch"])
            fwd_ac = mathutils.Vector((0.0, math.sin(pitch_rad), math.cos(pitch_rad))).normalized()
            up_ac = mathutils.Vector((0.0, 1.0, 0.0))

            mat = ac_to_blender_camera_matrix(spec["pos_ac"], fwd_ac, up_ac)
            cam_obj.matrix_world = mat

        # Set driver cockpit as default active camera
        cockpit_cam = bpy.data.objects.get("AC_CAM_DRIVEREYES")
        if cockpit_cam:
            context.scene.camera = cockpit_cam

        bpy.context.view_layer.update()
        msg = f"Setup complete: Configured {len(cam_definitions)} car cameras under 'AC_CAMERAS' collection."
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class KN5_OT_SwitchActiveCamera(bpy.types.Operator):
    """Switches Blender active camera to the chosen car viewpoint and enters camera view."""
    bl_idname = "kn5.switch_active_camera"
    bl_label = "Switch Viewpoint"
    bl_description = "Activates the specified vehicle camera and switches 3D viewport to camera perspective"
    bl_options = {'REGISTER', 'UNDO'}

    camera_type: EnumProperty(
        name="Camera View",
        items=[
            ("DRIVEREYES", "Cockpit View", "Driver eye viewpoint inside cockpit"),
            ("BONNET", "Bonnet View", "Mounted on hood looking forward"),
            ("BUMPER", "Bumper View", "Low-mounted on front bumper"),
            ("CHASE", "Chase View", "3rd person trailing view behind car"),
        ],
        default="DRIVEREYES"
    )

    def execute(self, context):
        target_name = f"AC_CAM_{self.camera_type}"
        cam_obj = context.scene.objects.get(target_name)

        if not cam_obj or cam_obj.type != 'CAMERA':
            # Create camera rig if missing
            bpy.ops.kn5.setup_car_cameras()
            cam_obj = context.scene.objects.get(target_name)

        if cam_obj:
            context.scene.camera = cam_obj
            # Switch active 3D view to camera perspective
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.region_3d.view_perspective = 'CAMERA'
            self.report({'INFO'}, f"Switched active view to {cam_obj.name}")
            return {'FINISHED'}

        self.report({'WARNING'}, f"Camera '{target_name}' not found.")
        return {'CANCELLED'}


class KN5_OT_ImportCarCameras(bpy.types.Operator, ImportHelper):
    """Imports camera positions and parameters from car.ini and cameras.ini into Blender."""
    bl_idname = "kn5.import_car_cameras"
    bl_label = "Import Cameras from INI"
    bl_description = "Reads car.ini [GRAPHICS] cameras and cameras.ini [CAMERA_X] into Blender camera objects"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ini"
    filter_glob: StringProperty(default="*.ini", options={'HIDDEN'})

    def execute(self, context):
        filepath = self.filepath
        if not os.path.exists(filepath):
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        data_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath).lower()

        # Find car.ini and cameras.ini
        car_ini_path = filepath if filename == "car.ini" else os.path.join(data_dir, "car.ini")
        cameras_ini_path = filepath if filename == "cameras.ini" else os.path.join(data_dir, "cameras.ini")

        # 1. Collection
        col_name = "AC_CAMERAS"
        cam_col = bpy.data.collections.get(col_name)
        if not cam_col:
            cam_col = bpy.data.collections.new(col_name)
            context.scene.collection.children.link(cam_col)

        imported_count = 0

        # 2. Parse car.ini [GRAPHICS]
        if os.path.exists(car_ini_path):
            cp = configparser.ConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
            cp.optionxform = str
            cp.read(car_ini_path)
            if 'GRAPHICS' in cp:
                g = cp['GRAPHICS']
                car_cam_map = {
                    "AC_CAM_DRIVEREYES": {
                        "pos_key": "DRIVEREYES",
                        "pitch_key": "ON_BOARD_PITCH_ANGLE",
                        "default_pos": "0.375, 1.050, 0.120",
                        "default_pitch": "-1.0",
                        "fov": 56.0,
                    },
                    "AC_CAM_BONNET": {
                        "pos_key": "BONNET_CAMERA_POS",
                        "pitch_key": "BONNET_CAMERA_PITCH",
                        "default_pos": "0.0, 0.800, 0.300",
                        "default_pitch": "-6.0",
                        "fov": 60.0,
                    },
                    "AC_CAM_BUMPER": {
                        "pos_key": "BUMPER_CAMERA_POS",
                        "pitch_key": "BUMPER_CAMERA_PITCH",
                        "default_pos": "0.0, 0.300, 2.150",
                        "default_pitch": "0.0",
                        "fov": 62.0,
                    },
                }

                for cam_name, info in car_cam_map.items():
                    raw_pos = g.get(info["pos_key"], info["default_pos"]).split(",")
                    pos_ac = mathutils.Vector((float(raw_pos[0]), float(raw_pos[1]), float(raw_pos[2])))
                    pitch_val = float(g.get(info["pitch_key"], info["default_pitch"]))

                    pitch_rad = math.radians(pitch_val)
                    fwd_ac = mathutils.Vector((0.0, math.sin(pitch_rad), math.cos(pitch_rad))).normalized()
                    up_ac = mathutils.Vector((0.0, 1.0, 0.0))

                    cam_obj = bpy.data.objects.get(cam_name)
                    if not cam_obj:
                        cam_data = bpy.data.cameras.new(cam_name)
                        cam_obj = bpy.data.objects.new(cam_name, cam_data)
                        cam_col.objects.link(cam_obj)
                    cam_obj.data.angle = math.radians(info["fov"])
                    cam_obj.matrix_world = ac_to_blender_camera_matrix(pos_ac, fwd_ac, up_ac)
                    imported_count += 1

        # 3. Parse cameras.ini [CAMERA_X]
        if os.path.exists(cameras_ini_path):
            cp_cam = configparser.ConfigParser(strict=False, inline_comment_prefixes=(';', '#'))
            cp_cam.optionxform = str
            cp_cam.read(cameras_ini_path)

            for sec in cp_cam.sections():
                if sec.upper().startswith("CAMERA_"):
                    c_sec = cp_cam[sec]
                    if 'POSITION' in c_sec and 'FORWARD' in c_sec:
                        pos_floats = [float(v) for v in c_sec['POSITION'].split(",")[:3]]
                        fwd_floats = [float(v) for v in c_sec['FORWARD'].split(",")[:3]]
                        up_floats = [float(v) for v in c_sec.get('UP', '0,1,0').split(",")[:3]]
                        fov_val = float(c_sec.get('FOV', '60'))

                        pos_ac = mathutils.Vector(pos_floats)
                        fwd_ac = mathutils.Vector(fwd_floats).normalized()
                        up_ac = mathutils.Vector(up_floats).normalized()

                        cam_name = f"AC_{sec.upper()}"
                        cam_obj = bpy.data.objects.get(cam_name)
                        if not cam_obj:
                            cam_data = bpy.data.cameras.new(cam_name)
                            cam_obj = bpy.data.objects.new(cam_name, cam_data)
                            cam_col.objects.link(cam_obj)
                        cam_obj.data.angle = math.radians(fov_val)
                        cam_obj.matrix_world = ac_to_blender_camera_matrix(pos_ac, fwd_ac, up_ac)
                        imported_count += 1

        bpy.context.view_layer.update()
        msg = f"Imported {imported_count} cameras from INI data into Blender."
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class KN5_OT_ExportCarCameras(bpy.types.Operator, ExportHelper):
    """Exports updated camera positions and pitch angles from Blender into car.ini and cameras.ini."""
    bl_idname = "kn5.export_car_cameras"
    bl_label = "Export Cameras to INI"
    bl_description = "Writes Blender camera coordinates and angles to car.ini [GRAPHICS] and cameras.ini [CAMERA_X]"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ini"
    filter_glob: StringProperty(default="*.ini", options={'HIDDEN'})

    def execute(self, context):
        filepath = self.filepath
        data_dir = os.path.dirname(filepath) if os.path.isdir(os.path.dirname(filepath)) else ""
        if not data_dir:
            data_dir = find_car_data_dir(context)

        car_ini_path = filepath if os.path.basename(filepath).lower() == "car.ini" else (os.path.join(data_dir, "car.ini") if data_dir else filepath)
        cameras_ini_path = filepath if os.path.basename(filepath).lower() == "cameras.ini" else (os.path.join(data_dir, "cameras.ini") if data_dir else "")

        updated_items = 0

        # 1. Update car.ini [GRAPHICS]
        car_updates = {}
        cam_cockpit = context.scene.objects.get("AC_CAM_DRIVEREYES")
        if cam_cockpit:
            pos_ac, fwd_ac, up_ac, pitch_deg = blender_to_ac_camera_data(cam_cockpit)
            car_updates["DRIVEREYES"] = f"{pos_ac.x:.4f},{pos_ac.y:.4f},{pos_ac.z:.4f}"
            car_updates["ON_BOARD_PITCH_ANGLE"] = f"{pitch_deg:.1f}"

        cam_bonnet = context.scene.objects.get("AC_CAM_BONNET")
        if cam_bonnet:
            pos_ac, fwd_ac, up_ac, pitch_deg = blender_to_ac_camera_data(cam_bonnet)
            car_updates["BONNET_CAMERA_POS"] = f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}"
            car_updates["BONNET_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        cam_bumper = context.scene.objects.get("AC_CAM_BUMPER")
        if cam_bumper:
            pos_ac, fwd_ac, up_ac, pitch_deg = blender_to_ac_camera_data(cam_bumper)
            car_updates["BUMPER_CAMERA_POS"] = f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}"
            car_updates["BUMPER_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        cam_chase = context.scene.objects.get("AC_CAM_CHASE")
        if cam_chase:
            pos_ac, fwd_ac, up_ac, pitch_deg = blender_to_ac_camera_data(cam_chase)
            car_updates["CHASE_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        if car_updates:
            update_ini_text_file(car_ini_path, "GRAPHICS", car_updates)
            updated_items += len(car_updates)
            print(f"Updated car.ini at {car_ini_path}: {car_updates}")

        # 2. Update cameras.ini if present or if cameras like AC_CAMERA_0 exist
        cam_objects = [o for o in context.scene.objects if o.type == 'CAMERA' and o.name.upper().startswith("AC_CAMERA_")]
        if cam_objects and cameras_ini_path:
            for c_obj in cam_objects:
                sec_name = c_obj.name.replace("AC_", "")
                pos_ac, fwd_ac, up_ac, pitch_deg = blender_to_ac_camera_data(c_obj)
                fov_deg = math.degrees(c_obj.data.angle)
                cam_dict = {
                    "POSITION": f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}",
                    "FORWARD": f"{fwd_ac.x:.6f},{fwd_ac.y:.6f},{fwd_ac.z:.6f}",
                    "UP": f"{up_ac.x:.6f},{up_ac.y:.6f},{up_ac.z:.6f}",
                    "FOV": f"{fov_deg:.1f}",
                }
                update_ini_text_file(cameras_ini_path, sec_name, cam_dict)
                updated_items += 1

        msg = f"Exported camera configuration to INI files ({updated_items} parameters updated)."
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def get_ac_pitch_from_obj(obj: bpy.types.Object) -> float:
    """Calculates AC camera pitch angle (degrees) from object world orientation."""
    rot = obj.matrix_world.to_euler()
    deg_x = math.degrees(rot.x)
    if 45.0 <= deg_x <= 135.0:
        return round(deg_x - 90.0, 1)
    elif -135.0 <= deg_x <= -45.0:
        return round(deg_x + 90.0, 1)
    return round(deg_x, 1)


class KN5_OT_SyncCamerasToIni(bpy.types.Operator):
    """Automatically synchronizes all camera empties and rigs from 3D Viewport into car.ini and cameras.ini."""
    bl_idname = "kn5.sync_cameras_to_ini"
    bl_label = "Sync Cameras to car.ini"
    bl_description = "Reads current positions and angles of camera empties/rigs and writes directly to car.ini [GRAPHICS] and cameras.ini"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        data_dir = find_car_data_dir(context)
        if not data_dir:
            self.report({'ERROR'}, "Could not locate the car 'data/' directory. Please save the blend file inside the car folder or use Export Cameras.")
            return {'CANCELLED'}

        car_ini_path = os.path.join(data_dir, "car.ini")
        cameras_ini_path = os.path.join(data_dir, "cameras.ini")

        updated_items = 0
        car_updates = {}

        # 1. Cockpit / Driver Eyes (Prioritize the camera object the user directly moves in viewport)
        cam_driver = context.scene.objects.get("AC_CAM_DRIVEREYES")
        obj_driver = cam_driver or context.scene.objects.get("CAM_DRIVER_EYES") or context.scene.objects.get("DRIVER_EYES")
        if obj_driver:
            mw = obj_driver.matrix_world
            pos_ac = blender_to_ac_pos(mw.translation)
            pitch_deg = get_ac_pitch_from_obj(obj_driver)
            car_updates["DRIVEREYES"] = f"{pos_ac.x:.4f},{pos_ac.y:.4f},{pos_ac.z:.4f}"
            car_updates["ON_BOARD_PITCH_ANGLE"] = f"{pitch_deg:.1f}"

            # Synchronize root DRIVER_EYES dummy in model tree
            driver_eyes_dummy = context.scene.objects.get("DRIVER_EYES")
            if driver_eyes_dummy and driver_eyes_dummy != obj_driver:
                driver_eyes_dummy.matrix_world.translation = mw.translation.copy()

        # 2. Bonnet / Hood Camera
        obj_bonnet = context.scene.objects.get("AC_CAM_BONNET") or context.scene.objects.get("CAM_BONNET")
        if obj_bonnet:
            mw = obj_bonnet.matrix_world
            pos_ac = blender_to_ac_pos(mw.translation)
            pitch_deg = get_ac_pitch_from_obj(obj_bonnet)
            car_updates["BONNET_CAMERA_POS"] = f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}"
            car_updates["BONNET_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        # 3. Front Bumper Camera
        obj_bumper = context.scene.objects.get("AC_CAM_BUMPER") or context.scene.objects.get("CAM_BUMPER")
        if obj_bumper:
            mw = obj_bumper.matrix_world
            pos_ac = blender_to_ac_pos(mw.translation)
            pitch_deg = get_ac_pitch_from_obj(obj_bumper)
            car_updates["BUMPER_CAMERA_POS"] = f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}"
            car_updates["BUMPER_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        # 4. Chase Camera Pitch
        obj_chase = context.scene.objects.get("AC_CAM_CHASE") or context.scene.objects.get("CAM_CHASE")
        if obj_chase:
            pitch_deg = get_ac_pitch_from_obj(obj_chase)
            car_updates["CHASE_CAMERA_PITCH"] = f"{pitch_deg:.1f}"

        # 5. Mirror Anchor
        obj_mirror = context.scene.objects.get("MIRROR_C") or context.scene.objects.get("MIRROR_L")
        if obj_mirror:
            mw = obj_mirror.matrix_world
            pos_ac = blender_to_ac_pos(mw.translation)
            car_updates["MIRROR_POSITION"] = f"{pos_ac.x:.4f},{pos_ac.y:.4f},{pos_ac.z:.4f}"

        if car_updates and os.path.exists(car_ini_path):
            update_ini_text_file(car_ini_path, "GRAPHICS", car_updates)
            updated_items += len(car_updates)
            print(f"Updated car.ini at {car_ini_path}: {car_updates}")

        # 6. Update dash_cam.ini
        dash_cam_obj = context.scene.objects.get("AC_CAM_DASH") or context.scene.objects.get("CAM_DASH")
        dash_ini_path = os.path.join(data_dir, "dash_cam.ini")
        if dash_cam_obj and os.path.exists(dash_ini_path):
            dash_pos_ac = blender_to_ac_pos(dash_cam_obj.matrix_world.translation)
            with open(dash_ini_path, "w", encoding="utf-8") as f:
                f.write("[DASH_CAM]\n")
                f.write(f"POS={dash_pos_ac.x:.6f},{dash_pos_ac.y:.6f},{dash_pos_ac.z:.6f}\n")
                f.write("EXP=28\n")
            updated_items += 1

        # 7. Update cameras.ini if custom cameras or onboard empties exist
        if os.path.exists(cameras_ini_path):
            onboard_cams = [
                ("AC_CAM_ROOF", "CAM_ROOF", "CAMERA_0", 65.0),
                ("AC_CAM_DASH", "CAM_DASH", "CAMERA_3", 60.0),
            ]
            for cam_n, emp_n, sec_n, def_fov in onboard_cams:
                c_obj = context.scene.objects.get(cam_n) or context.scene.objects.get(emp_n)
                if c_obj:
                    mw = c_obj.matrix_world
                    pos_ac = blender_to_ac_pos(mw.translation)
                    pitch_deg = get_ac_pitch_from_obj(c_obj)
                    pitch_rad = math.radians(pitch_deg)
                    fwd_ac = mathutils.Vector((0.0, math.sin(pitch_rad), math.cos(pitch_rad))).normalized()
                    up_ac = mathutils.Vector((0.0, 1.0, 0.0))
                    fov_deg = math.degrees(c_obj.data.angle) if c_obj.type == 'CAMERA' else def_fov

                    cam_dict = {
                        "POSITION": f"{pos_ac.x:.6f},{pos_ac.y:.6f},{pos_ac.z:.6f}",
                        "FORWARD": f"{fwd_ac.x:.6f},{fwd_ac.y:.6f},{fwd_ac.z:.6f}",
                        "UP": f"{up_ac.x:.6f},{up_ac.y:.6f},{up_ac.z:.6f}",
                        "FOV": f"{fov_deg:.1f}",
                    }
                    update_ini_text_file(cameras_ini_path, sec_n, cam_dict)
                    updated_items += 1

        msg = f"Synced {updated_items} camera & dummy parameters into car.ini / cameras.ini!"
        print(msg)
        self.report({'INFO'}, msg)
        return {'FINISHED'}



class KN5_OT_TagSurface(bpy.types.Operator):

    """Prefixes selected mesh object with Assetto Corsa physical surface name."""
    bl_idname = "kn5.tag_surface"
    bl_label = "Tag Surface"
    bl_description = "Add or update AC physical surface prefix (e.g. 1ROAD, 1KERB, 1WALL)"
    bl_options = {'REGISTER', 'UNDO'}

    surface_prefix: StringProperty(name="Prefix", default="1ROAD_")

    def execute(self, context):
        objs = context.selected_objects
        if not objs:
            self.report({'WARNING'}, "No objects selected to tag.")
            return {'CANCELLED'}

        count = 0
        for obj in objs:
            if obj.type != 'MESH':
                continue
            # Strip any existing AC surface prefix
            clean_name = re.sub(r'^(1ROAD|1KERB|1GRASS|1SAND|1WALL|2ROAD)_?', '', obj.name, flags=re.IGNORECASE)
            prefix = self.surface_prefix.rstrip("_") + "_"
            obj.name = prefix + clean_name
            count += 1

        self.report({'INFO'}, f"Tagged {count} object(s) with surface prefix '{self.surface_prefix}'.")
        return {'FINISHED'}


class KN5_OT_ValidateScene(bpy.types.Operator):
    """Performs a comprehensive pre-flight scan of the scene for AC export issues."""
    bl_idname = "kn5.validate_scene"
    bl_label = "Validate Scene for AC"
    bl_description = "Check scene for vertex count limits, missing materials, missing UVs, and unapplied transforms"

    def execute(self, context):
        issues = []
        warnings = []
        mesh_count = 0
        dummy_count = 0

        for obj in context.scene.objects:
            if obj.name.startswith("__"):
                continue

            if obj.type == 'EMPTY':
                dummy_count += 1
                # Check scale
                scale = obj.scale
                if abs(scale[0] - 1.0) > 0.001 or abs(scale[1] - 1.0) > 0.001 or abs(scale[2] - 1.0) > 0.001:
                    warnings.append(f"Dummy '{obj.name}' has non-1.0 scale: ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f}). Recommended to Apply Scale.")

            elif obj.type == 'MESH':
                mesh_count += 1
                mesh = obj.data

                # Check materials
                if not obj.material_slots or not any(slot.material for slot in obj.material_slots):
                    issues.append(f"Mesh '{obj.name}' has no material assigned!")

                for idx, slot in enumerate(obj.material_slots):
                    if not slot.material:
                        issues.append(f"Mesh '{obj.name}' has empty material slot {idx}!")

                # Check UV map
                if not mesh.uv_layers:
                    warnings.append(f"Mesh '{obj.name}' has NO UV map (auto UV fallback will be used).")

                # Check vertex count
                vert_count = len(mesh.vertices)
                if vert_count > 65535:
                    warnings.append(f"Mesh '{obj.name}' has {vert_count:,} vertices (>65,535). Exporter will auto-split it.")

                # Check unapplied scale
                scale = obj.scale
                if abs(scale[0] - 1.0) > 0.001 or abs(scale[1] - 1.0) > 0.001 or abs(scale[2] - 1.0) > 0.001:
                    warnings.append(f"Mesh '{obj.name}' has unapplied scale ({scale[0]:.2f}, {scale[1]:.2f}, {scale[2]:.2f}).")

        # Format report message
        msg_lines = [
            f"=== Assetto Corsa Scene Validation ===",
            f"Total Meshes: {mesh_count}, Total Dummies: {dummy_count}",
            "",
        ]

        if issues:
            msg_lines.append(f"CRITICAL ISSUES ({len(issues)}):")
            for iss in issues:
                msg_lines.append(f"  • {iss}")
            msg_lines.append("")

        if warnings:
            msg_lines.append(f"WARNINGS / RECOMMENDATIONS ({len(warnings)}):")
            for w in warnings[:15]:
                msg_lines.append(f"  • {w}")
            if len(warnings) > 15:
                msg_lines.append(f"  ... and {len(warnings)-15} more warnings.")
            msg_lines.append("")

        if not issues and not warnings:
            msg_lines.append("PERFECT! Scene is 100% clean and ready for KN5 export.")

        full_msg = "\n".join(msg_lines)
        print(full_msg)

        if issues:
            self.report({'ERROR'}, f"Found {len(issues)} critical issue(s). Check System Console for details.")
        elif warnings:
            self.report({'WARNING'}, f"Scene is exportable with {len(warnings)} warning(s). Check System Console.")
        else:
            self.report({'INFO'}, "Scene is 100% ready for KN5 export!")

        return {'FINISHED'}


class KN5_OT_AutoFixScene(bpy.types.Operator):
    """Auto-fixes common export issues: applies transforms and ensures default UVs."""
    bl_idname = "kn5.auto_fix_scene"
    bl_label = "Auto-Fix Scene"
    bl_description = "Applies scale on selected objects and creates default UV maps if missing"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        objs = list(context.selected_objects)
        if not objs:
            objs = [o for o in context.scene.objects if not o.name.startswith("__")]

        fixed_scale = 0
        fixed_uv = 0

        prev_active = context.view_layer.objects.active
        prev_selected = list(context.selected_objects)

        for obj in objs:
            if obj.type == 'MESH':
                # Apply scale if not 1.0
                if any(abs(s - 1.0) > 0.001 for s in obj.scale):
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    try:
                        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                        fixed_scale += 1
                    except Exception as e:
                        print(f"Auto-fix warning on '{obj.name}': {e}")

                # Ensure UV map exists
                if not obj.data.uv_layers:
                    obj.data.uv_layers.new(name="UVMap")
                    fixed_uv += 1

        # Restore previous selection
        bpy.ops.object.select_all(action='DESELECT')
        for o in prev_selected:
            if o.name in context.scene.objects:
                o.select_set(True)
        if prev_active and prev_active.name in context.scene.objects:
            context.view_layer.objects.active = prev_active

        self.report({'INFO'}, f"Auto-fix complete: Applied scale to {fixed_scale} object(s), added UV map to {fixed_uv} mesh(es).")
        return {'FINISHED'}


class KN5_OT_SetupTransparentMeshes(bpy.types.Operator):
    """Automatically detects and configures all glass, windows, and transparent light meshes for Assetto Corsa."""
    bl_idname = "kn5.setup_transparent_meshes"
    bl_label = "Auto-Configure Glass & Transparent Meshes"
    bl_description = "Identifies car windows and light glass, enables transparency, disables shadow casting, and tunes shaders"
    bl_options = {'REGISTER', 'UNDO'}

    tune_materials: BoolProperty(
        name="Tune Glass Materials",
        default=True,
        description="Automatically configures ksPerPixelAlpha shader, blend/depth modes, and realistic glass Fresnel/specular"
    )
    fix_viewport: BoolProperty(
        name="Update Blender Viewport",
        default=True,
        description="Sets BSDF transmission and viewport blend method so glass looks transparent in Blender"
    )

    def execute(self, context):
        glass_keywords = ["wind", "window", "glas", "glass", "cam", "vetro", "vitre", "defrost"]
        non_glass_keywords = ["frame", "line", "trim", "rubber", "base", "housing", "cloth", "int_"]
        internal_light_keywords = ["lamp", "bulb", "ampul", "lenses", "signal", "indicator"]

        glass_objs = []
        bulb_objs = []

        for obj in context.scene.objects:
            if obj.type != 'MESH':
                continue
            name_lower = obj.name.lower()
            mats = [s.material for s in obj.material_slots if s.material]
            mat_names_lower = [m.name.lower() for m in mats]

            is_frame = any(k in name_lower for k in non_glass_keywords)
            has_glass_name = any(k in name_lower for k in glass_keywords) and not is_frame
            has_glass_mat = any(any(k in mn for k in ["window", "glass", "defrost", "vetro", "vitre"]) for mn in mat_names_lower) and not is_frame

            is_internal_bulb = any(k in name_lower for k in internal_light_keywords) or any("bulb" in mn or "ampul" in mn for mn in mat_names_lower)

            if has_glass_name or has_glass_mat:
                glass_objs.append((obj, mats))
            elif is_internal_bulb:
                bulb_objs.append((obj, mats))

        # 1. Configure Glass Objects
        configured_glass_objs = 0
        configured_mats = set()

        for obj, mats in glass_objs:
            ac_obj = getattr(obj, "assettoCorsa", None)
            if ac_obj:
                # Dedicated glass meshes (single material or all glass) are marked transparent
                # Compound objects (e.g. car door with body paint + glass window) remain opaque at object level
                has_opaque_mats = any(not any(k in m.name.lower() for k in ["window", "glass", "defrost", "vetro", "vitre", "glow"]) for m in mats)
                if not has_opaque_mats:
                    ac_obj.transparent = True
                    ac_obj.cast_shadows = False
                    configured_glass_objs += 1
                else:
                    ac_obj.transparent = False
                    ac_obj.cast_shadows = True

            if self.tune_materials:
                for mat in mats:
                    if mat in configured_mats:
                        continue
                    mn = mat.name.lower()
                    if any(k in mn for k in ["window", "glass", "defrost", "vetro", "vitre", "wind"]):
                        ac_mat = getattr(mat, "assettoCorsa", None)
                        if ac_mat:
                            ac_mat.shader_name = "ksPerPixelReflection"
                            ac_mat.blend_mode = "1"
                            ac_mat.depth_mode = "0"
                            ac_mat.alpha_tested = False
                            ac_mat.set_property("ksAmbient", 0.10)
                            ac_mat.set_property("ksDiffuse", 0.10)
                            ac_mat.set_property("ksSpecular", 4.00)
                            ac_mat.set_property("ksSpecularEXP", 450.0)
                            ac_mat.set_property("fresnelC", 0.10)
                            ac_mat.set_property("fresnelEXP", 2.8)
                            ac_mat.set_property("fresnelMaxLevel", 0.65)
                            ac_mat.set_property("isAdditive", 0.0)
                    elif "glow" in mn:
                        ac_mat = getattr(mat, "assettoCorsa", None)
                        if ac_mat:
                            ac_mat.shader_name = "ksPerPixelAlpha"
                            ac_mat.blend_mode = "1"
                            ac_mat.depth_mode = "1"
                            ac_mat.alpha_tested = False
                            ac_mat.set_property("ksAmbient", 0.20)
                            ac_mat.set_property("ksDiffuse", 0.10)
                            ac_mat.set_property("isAdditive", 0.0)

                        if self.fix_viewport:
                            if hasattr(mat, "blend_method"):
                                mat.blend_method = 'BLEND'
                            if hasattr(mat, "shadow_method"):
                                mat.shadow_method = 'NONE'
                            if mat.use_nodes and mat.node_tree:
                                for node in mat.node_tree.nodes:
                                    if node.type == 'BSDF_PRINCIPLED':
                                        trans_sock = node.inputs.get("Transmission Weight") or node.inputs.get("Transmission")
                                        if trans_sock:
                                            trans_sock.default_value = 0.85
                                        if "Roughness" in node.inputs:
                                            node.inputs["Roughness"].default_value = 0.04
                                        if "Alpha" in node.inputs:
                                            node.inputs["Alpha"].default_value = 0.35

                        configured_mats.add(mat)

        # 2. Fix Internal Bulbs / Reflectors (Must be OPAQUE to prevent depth sorting bugs)
        fixed_bulb_objs = 0
        for obj, mats in bulb_objs:
            ac_obj = getattr(obj, "assettoCorsa", None)
            if ac_obj:
                ac_obj.transparent = False
                ac_obj.cast_shadows = True
                fixed_bulb_objs += 1

            for mat in mats:
                mn = mat.name.lower()
                if "bulb" in mn or "ampul" in mn:
                    ac_mat = getattr(mat, "assettoCorsa", None)
                    if ac_mat:
                        ac_mat.shader_name = "ksPerPixel"
                        ac_mat.blend_mode = "0"
                        ac_mat.depth_mode = "0"
                        ac_mat.alpha_tested = False
                    if hasattr(mat, "blend_method"):
                        mat.blend_method = 'OPAQUE'

        msg = f"Glass configured: {configured_glass_objs} mesh(es), {len(configured_mats)} material(s). Fixed {fixed_bulb_objs} internal bulb(s) to Opaque."
        print(f"[KN5 Studio] {msg}")
        self.report({'INFO'}, msg)
        return {'FINISHED'}



# ---------------------------------------------------------------------------
# Lights.ini System - Auto-detect, Import, Export car lights configuration
# ---------------------------------------------------------------------------

# Shaders and material name patterns that indicate emissive/light meshes
_LIGHT_SHADERS = {"gl", "ksperPixelatMultiMap_emissive", "ksemissive"}
_HEADLIGHT_KEYWORDS = {"headlamp", "headlight", "faro", "lamp", "beam", "fog", "antiniebla"}
_BRAKE_KEYWORDS = {"brake", "fren", "rear", "stop", "tail", "ferno", "glow_rear"}
_TURN_KEYWORDS = {"turn", "signal", "blink", "intermitente", "wing_light", "indicator"}
_DISC_KEYWORDS = {"disc", "disk", "rotor", "caliper", "kaliper", "pinza", "pad", "disco"}


def _is_disc_or_wheel_part(mesh_name: str, mat_name: str = "", obj=None) -> bool:
    """Returns True if the object, mesh, or material represents a brake disc/rotor/caliper/wheel part."""
    name_up = mesh_name.upper()
    if name_up.startswith(("DISC_", "WHEEL_", "RIM_", "TYRE_", "TIRE_", "SUSP_")):
        return True
    combined = (mesh_name + " " + mat_name).lower()
    if any(kw in combined for kw in _DISC_KEYWORDS):
        return True
    if obj:
        if obj.parent and any(wp in obj.parent.name.upper() for wp in ["WHEEL_", "SUSP_"]):
            return True
        for slot in getattr(obj, "material_slots", []):
            if slot.material:
                ac = getattr(slot.material, "assettoCorsa", None)
                if ac and getattr(ac, "shader_name", "").lower() == "ksbrakedisc":
                    return True
    return False


def _guess_light_type(mesh_name: str, mat_name: str) -> str:
    """Heuristic to classify a light mesh as HEADLIGHT, BRAKE, or TURN/OTHER."""
    if _is_disc_or_wheel_part(mesh_name, mat_name):
        return "HEADLIGHT"
    combined = (mesh_name + " " + mat_name).lower()
    for kw in _BRAKE_KEYWORDS:
        if kw in combined:
            return "BRAKE"
    for kw in _TURN_KEYWORDS:
        if kw in combined:
            return "TURN"
    for kw in _HEADLIGHT_KEYWORDS:
        if kw in combined:
            return "HEADLIGHT"
    return "HEADLIGHT"


def _default_color_for_type(light_type: str) -> str:
    """Returns a sensible default COLOR value for a given light type."""
    if light_type == "BRAKE":
        return "220,0,0"
    elif light_type == "TURN":
        return "200,50,0"
    return "200,200,100"


def _light_mesh_poll(self, obj):
    return obj is not None and obj.type == 'MESH'


def _select_light_mesh_in_viewport(context, entry):
    """Automatically selects and activates the mesh object in the 3D Viewport."""
    if not context or not hasattr(context, "view_layer") or not entry:
        return
    obj = getattr(entry, "mesh_object", None)
    if not obj and getattr(entry, "mesh_name", ""):
        obj = context.scene.objects.get(entry.mesh_name)
    if obj and obj.name in context.scene.objects:
        try:
            # Deselect all currently selected objects
            for o in context.selected_objects:
                o.select_set(False)
            # Select target object & make it active
            obj.select_set(True)
            context.view_layer.objects.active = obj
        except Exception:
            pass


def _update_light_mesh_name(self, context):
    if self.mesh_object:
        self.mesh_name = self.mesh_object.name
        _select_light_mesh_in_viewport(context, self)


def _on_light_active_index_changed(self, context):
    idx = self.active_index
    if 0 <= idx < len(self.entries):
        _select_light_mesh_in_viewport(context, self.entries[idx])


class KN5_LightEntry(bpy.types.PropertyGroup):
    """A single light entry for the lights.ini system."""
    mesh_name: StringProperty(name="Mesh Name", default="")
    mesh_object: PointerProperty(
        name="Mesh",
        type=bpy.types.Object,
        poll=_light_mesh_poll,
        update=_update_light_mesh_name,
        description="Pick the actual light mesh from the scene or viewport",
    )
    light_type: EnumProperty(
        name="Type",
        items=[
            ('HEADLIGHT', "Headlight (LIGHT)", "Far / Headlight"),
            ('BRAKE', "Brake (BRAKE)", "Fren / Brake light"),
            ('TURN', "Turn/Signal", "Sinyal / Turn indicator"),
        ],
        default='HEADLIGHT',
    )
    color: StringProperty(name="Color", default="200,200,100",
                          description="RGB color intensity (e.g. 200,200,100)")
    off_color: StringProperty(name="Off Color", default="",
                              description="Color when light is off (optional, e.g. 1.7,0,0)")
    pitline: BoolProperty(name="Pitline", default=False,
                          description="Light activates in pit lane")
    special: BoolProperty(name="Special", default=False,
                          description="Special light flag (turn signals, etc.)")


class KN5_LightsSceneProperties(bpy.types.PropertyGroup):
    """Scene-level collection of light entries."""
    entries: bpy.props.CollectionProperty(type=KN5_LightEntry)
    active_index: IntProperty(
        name="Active Light",
        default=0,
        update=_on_light_active_index_changed
    )


class KN5_OT_SelectLightMesh(bpy.types.Operator):
    """Select and focus the chosen light mesh in the 3D Viewport."""
    bl_idname = "kn5.select_light_mesh"
    bl_label = "Select Light Mesh in 3D View"
    bl_description = "Selects and highlights the chosen light mesh in the 3D Viewport"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(name="Index", default=-1)

    def execute(self, context):
        lights_props = getattr(context.scene, "kn5_lights", None)
        if not lights_props:
            return {'CANCELLED'}
        idx = self.index if self.index >= 0 else lights_props.active_index
        if 0 <= idx < len(lights_props.entries):
            entry = lights_props.entries[idx]
            _select_light_mesh_in_viewport(context, entry)
            return {'FINISHED'}
        return {'CANCELLED'}


class KN5_OT_DetectLightMeshes(bpy.types.Operator):
    """Auto-detect emissive/GL meshes in the scene and populate the light list."""
    bl_idname = "kn5.detect_light_meshes"
    bl_label = "Auto-Detect Light Meshes"
    bl_description = "Scans all meshes for GL/emissive shaders and builds a light entry list"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lights_props = context.scene.kn5_lights
        # Keep track of existing entries to avoid duplicates
        existing_names = {e.mesh_name for e in lights_props.entries}

        found = 0
        sorted_objs = sorted(context.scene.objects, key=lambda o: o.name.lower())
        for obj in sorted_objs:
            if obj.type != 'MESH':
                continue
            # Skip any brake disc, caliper, rotor, or wheel component
            if _is_disc_or_wheel_part(obj.name, "", obj):
                continue
            for slot in obj.material_slots:
                mat = slot.material
                if not mat:
                    continue
                if _is_disc_or_wheel_part(obj.name, mat.name, obj):
                    continue
                ac = getattr(mat, "assettoCorsa", None)
                if not ac:
                    continue
                shader = getattr(ac, "shader_name", "")
                if shader.lower() == "ksbrakedisc":
                    continue
                shader_match = (shader.lower() in _LIGHT_SHADERS
                                or "emissive" in shader.lower()
                                or shader.lower() == "gl")
                name_match = any(
                    keyword in (obj.name + " " + mat.name).lower()
                    for keyword in (_HEADLIGHT_KEYWORDS | (_BRAKE_KEYWORDS - {"rear"}) | _TURN_KEYWORDS)
                )
                if shader_match or name_match:
                    mesh_name = obj.name
                    if mesh_name not in existing_names:
                        entry = lights_props.entries.add()
                        entry.mesh_name = mesh_name
                        entry.mesh_object = obj
                        lt = _guess_light_type(mesh_name, mat.name)
                        entry.light_type = lt
                        entry.color = _default_color_for_type(lt)
                        if lt == "BRAKE":
                            entry.off_color = "1.7,0,0"
                        if lt == "TURN":
                            entry.pitline = True
                            entry.special = True
                        existing_names.add(mesh_name)
                        found += 1

        if found == 0:
            self.report({'WARNING'}, "No GL/emissive light meshes found. Make sure materials have GL shader assigned.")
        else:
            self.report({'INFO'}, f"Detected {found} light mesh(es).")
        return {'FINISHED'}


class KN5_OT_ImportLightsINI(bpy.types.Operator, ImportHelper):
    """Import an existing lights.ini and populate the light entry list."""
    bl_idname = "kn5.import_lights_ini"
    bl_label = "Import lights.ini"
    bl_description = "Reads an existing lights.ini file and loads entries into the editor"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ini"
    filter_glob: StringProperty(default="*.ini", options={'HIDDEN'})

    def execute(self, context):
        if not os.path.exists(self.filepath):
            self.report({'ERROR'}, f"File not found: {self.filepath}")
            return {'CANCELLED'}

        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve case
        try:
            config.read(self.filepath, encoding='utf-8')
        except Exception:
            config.read(self.filepath, encoding='latin-1')

        lights_props = context.scene.kn5_lights
        lights_props.entries.clear()

        brake_idx = 0
        light_idx = 0

        for section in config.sections():
            sec_upper = section.upper()
            if sec_upper == "HEADER":
                continue

            name = config.get(section, "NAME", fallback="")
            color = config.get(section, "COLOR", fallback="200,200,100")
            off_color = config.get(section, "OFF_COLOR", fallback="")
            pitline = config.get(section, "PITLINE", fallback="0") == "1"
            special = config.get(section, "SPECIAL", fallback="0") == "1"

            if not name:
                continue

            entry = lights_props.entries.add()
            entry.mesh_name = name
            entry.mesh_object = context.scene.objects.get(name)
            entry.color = color
            entry.off_color = off_color
            entry.pitline = pitline
            entry.special = special

            if sec_upper.startswith("BRAKE"):
                entry.light_type = 'BRAKE'
                brake_idx += 1
            else:
                # Guess from properties
                if special or pitline:
                    entry.light_type = 'TURN'
                else:
                    entry.light_type = 'HEADLIGHT'
                light_idx += 1

        total = len(lights_props.entries)
        self.report({'INFO'}, f"Imported {total} light entries ({brake_idx} brake, {light_idx} headlight/other).")
        return {'FINISHED'}


class KN5_OT_ExportLightsINI(bpy.types.Operator, ExportHelper):
    """Export the current light list to a lights.ini file."""
    bl_idname = "kn5.export_lights_ini"
    bl_label = "Export lights.ini"
    bl_description = "Writes light entries to an Assetto Corsa lights.ini file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ini"
    filter_glob: StringProperty(default="*.ini", options={'HIDDEN'})
    filename: StringProperty(default="lights")

    def invoke(self, context, event):
        data_dir = find_car_data_dir(context)
        if data_dir:
            self.filepath = os.path.join(data_dir, "lights.ini")
        elif bpy.data.filepath:
            self.filepath = os.path.join(os.path.dirname(bpy.data.filepath), "lights.ini")
        else:
            self.filepath = "lights.ini"
        self.filename = "lights"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        if os.path.basename(self.filepath).casefold() != "lights.ini":
            self.report({'ERROR'}, "Assetto Corsa expects this file to be named lights.ini. Choose that exact filename in the car's data folder.")
            return {'CANCELLED'}

        lights_props = context.scene.kn5_lights
        if len(lights_props.entries) == 0:
            self.report({'WARNING'}, "No light entries to export. Use Auto-Detect first.")
            return {'CANCELLED'}

        lines = []
        lines.append("[HEADER]")
        lines.append("VERSION=3")
        lines.append("FLASHING_BLINK_TIME=0.5")
        lines.append("FLASHING_REPEAT=8")
        lines.append("")

        brake_idx = 0
        light_idx = 0
        turn_entries = []

        for entry in lights_props.entries:
            mesh_name = entry.mesh_name.strip() or (
                entry.mesh_object.name if entry.mesh_object else "")
            if not mesh_name:
                continue
            if entry.light_type == 'BRAKE':
                lines.append(f"[BRAKE_{brake_idx}]")
                brake_idx += 1
                lines.append(f"NAME={mesh_name}")
                lines.append(f"COLOR={entry.color}")
                if entry.off_color:
                    lines.append(f"OFF_COLOR={entry.off_color}")
                lines.append("")
            elif entry.light_type == 'TURN':
                turn_entries.append(entry)
            else:
                lines.append(f"[LIGHT_{light_idx}]")
                light_idx += 1
                lines.append(f"NAME={mesh_name}")
                lines.append(f"COLOR={entry.color}")
                if entry.off_color:
                    lines.append(f"OFF_COLOR={entry.off_color}")
                if entry.pitline:
                    lines.append("PITLINE=1")
                if entry.special:
                    lines.append("SPECIAL=1")
                lines.append("")

        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # If turn signals are present, configure them for Custom Shaders Patch (CSP) in extension/ext_config.ini
        if turn_entries:
            try:
                car_dir = find_car_directory(context)
                if not car_dir:
                    car_dir = os.path.dirname(os.path.abspath(self.filepath))
                    if os.path.basename(car_dir).lower() == "data":
                        car_dir = os.path.dirname(car_dir)
                ext_dir = os.path.join(car_dir, "extension")
                os.makedirs(ext_dir, exist_ok=True)
                ext_ini_path = os.path.join(ext_dir, "ext_config.ini")

                left_front, left_side, left_rear = [], [], []
                right_front, right_side, right_rear = [], [], []

                for te in turn_entries:
                    mname = te.mesh_name.strip() or (te.mesh_object.name if te.mesh_object else "")
                    up = mname.upper()
                    obj = te.mesh_object or context.scene.objects.get(mname)
                    pos_x = obj.matrix_world.translation.x if obj else 0.0
                    pos_y = obj.matrix_world.translation.y if obj else 0.0

                    is_left = ("LEFT" in up or "_LF" in up or "_LR" in up or "SOL" in up or "_L_" in up or pos_x > 0.05)
                    is_side = ("WING" in up or "SIDE" in up or "CAMURLUK" in up or abs(pos_y) < 1.1)
                    is_rear = ("REAR" in up or "BACK" in up or "ARKA" in up or "_LR" in up or "_RR" in up or pos_y > 1.1)

                    target_list = (left_rear if is_rear else (left_side if is_side else left_front)) if is_left else \
                                  (right_rear if is_rear else (right_side if is_side else right_front))
                    if mname not in target_list:
                        target_list.append(mname)

                csp_blocks = [
                    "; ==============================================================================",
                    "; CSP TURN SIGNALS / SİNYALLER (Alt + Sol / Alt + Sağ / Alt + Aşağı)",
                    "; =============================================================================="
                ]

                idx_l = 0
                for loc_tag, m_list in [("FRONT", left_front), ("SIDE", left_side), ("BACK", left_rear)]:
                    if m_list:
                        csp_blocks.append(f"[EMISSIVE_TURNSIGNAL_LEFT_{idx_l}]")
                        csp_blocks.append(f"NAME = {', '.join(m_list)}")
                        csp_blocks.append("COLOR = 25, 10, 0, 15")
                        csp_blocks.append("LAG = 0.1")
                        csp_blocks.append("SIMULATE_HEATING = 0")
                        csp_blocks.append(f"LOCATION = {loc_tag}\n")
                        idx_l += 1

                idx_r = 0
                for loc_tag, m_list in [("FRONT", right_front), ("SIDE", right_side), ("BACK", right_rear)]:
                    if m_list:
                        csp_blocks.append(f"[EMISSIVE_TURNSIGNAL_RIGHT_{idx_r}]")
                        csp_blocks.append(f"NAME = {', '.join(m_list)}")
                        csp_blocks.append("COLOR = 25, 10, 0, 15")
                        csp_blocks.append("LAG = 0.1")
                        csp_blocks.append("SIMULATE_HEATING = 0")
                        csp_blocks.append(f"LOCATION = {loc_tag}\n")
                        idx_r += 1

                existing_ext = ""
                if os.path.exists(ext_ini_path):
                    with open(ext_ini_path, "r", encoding="utf-8", errors="ignore") as ef:
                        existing_ext = ef.read()

                cleaned_ext_lines = []
                skipping = False
                for eline in existing_ext.splitlines():
                    if eline.strip().startswith("[EMISSIVE_TURNSIGNAL_"):
                        skipping = True
                        continue
                    elif eline.strip().startswith("[") and skipping:
                        skipping = False
                    if not skipping:
                        cleaned_ext_lines.append(eline)

                base_ext_text = "\n".join(cleaned_ext_lines).rstrip()
                final_ext_text = (base_ext_text + "\n\n" if base_ext_text else "") + "\n".join(csp_blocks) + "\n"
                with open(ext_ini_path, "w", encoding="utf-8") as ef:
                    ef.write(final_ext_text)
            except Exception as e:
                print(f"Error updating CSP turn signals in ext_config.ini: {e}")

        self.report({'INFO'}, f"Exported lights.ini: {brake_idx} brake + {light_idx} light entries (and {len(turn_entries)} turn signals to ext_config.ini) → {self.filepath}")
        return {'FINISHED'}


class KN5_OT_AddLightEntry(bpy.types.Operator):
    """Add a new light entry manually."""
    bl_idname = "kn5.add_light_entry"
    bl_label = "Add Light Entry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lights_props = context.scene.kn5_lights
        entry = lights_props.entries.add()
        # If a mesh is selected, use its name
        if context.active_object and context.active_object.type == 'MESH':
            entry.mesh_name = context.active_object.name
            entry.mesh_object = context.active_object
            mat = context.active_object.active_material
            if mat:
                lt = _guess_light_type(entry.mesh_name, mat.name)
                entry.light_type = lt
                entry.color = _default_color_for_type(lt)
                if lt == "BRAKE":
                    entry.off_color = "1.7,0,0"
                if lt == "TURN":
                    entry.pitline = True
                    entry.special = True
        lights_props.active_index = len(lights_props.entries) - 1
        return {'FINISHED'}


class KN5_OT_RemoveLightEntry(bpy.types.Operator):
    """Remove the selected light entry."""
    bl_idname = "kn5.remove_light_entry"
    bl_label = "Remove Light Entry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lights_props = context.scene.kn5_lights
        idx = lights_props.active_index
        if 0 <= idx < len(lights_props.entries):
            lights_props.entries.remove(idx)
            lights_props.active_index = min(idx, len(lights_props.entries) - 1)
        return {'FINISHED'}


class KN5_OT_ClearLightEntries(bpy.types.Operator):
    """Clear all light entries."""
    bl_idname = "kn5.clear_light_entries"
    bl_label = "Clear All Lights"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.kn5_lights.entries.clear()
        context.scene.kn5_lights.active_index = 0
        self.report({'INFO'}, "Cleared all light entries.")
        return {'FINISHED'}


class KN5_OT_SortLightEntries(bpy.types.Operator):
    """Sort light entries alphabetically by mesh name."""
    bl_idname = "kn5.sort_light_entries"
    bl_label = "Sort Lights A-Z"
    bl_description = "Sorts all light entries alphabetically by mesh name"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lights_props = getattr(context.scene, "kn5_lights", None)
        if not lights_props or len(lights_props.entries) <= 1:
            return {'FINISHED'}

        active_mesh_name = ""
        if 0 <= lights_props.active_index < len(lights_props.entries):
            active_mesh_name = lights_props.entries[lights_props.active_index].mesh_name

        data = []
        for e in lights_props.entries:
            data.append({
                "mesh_name": e.mesh_name,
                "mesh_object": e.mesh_object,
                "light_type": e.light_type,
                "color": e.color,
                "off_color": e.off_color,
                "pitline": e.pitline,
                "special": e.special,
            })

        data.sort(key=lambda x: (x["mesh_name"] or (x["mesh_object"].name if x["mesh_object"] else "")).lower())

        lights_props.entries.clear()
        for idx, d in enumerate(data):
            entry = lights_props.entries.add()
            entry.mesh_name = d["mesh_name"]
            entry.mesh_object = d["mesh_object"]
            entry.light_type = d["light_type"]
            entry.color = d["color"]
            entry.off_color = d["off_color"]
            entry.pitline = d["pitline"]
            entry.special = d["special"]
            if d["mesh_name"] == active_mesh_name:
                lights_props.active_index = idx

        self.report({'INFO'}, f"Sorted {len(lights_props.entries)} light entries alphabetically.")
        return {'FINISHED'}


class KN5_UL_LightEntryList(bpy.types.UIList):
    """UI list for light entries."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            # Type icon
            type_icons = {'HEADLIGHT': 'LIGHT_SUN', 'BRAKE': 'COLORSET_01_VEC', 'TURN': 'COLORSET_09_VEC'}
            ic = type_icons.get(item.light_type, 'LIGHT')
            row.label(text="", icon=ic)
            row.label(text=item.mesh_name or (item.mesh_object.name if item.mesh_object else ""))
            row.label(text=item.light_type, icon='NONE')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.mesh_name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flt_flags = []
        flt_neworder = []

        if items:
            flt_neworder = [
                i[0] for i in sorted(
                    enumerate(items),
                    key=lambda x: (x[1].mesh_name or (x[1].mesh_object.name if x[1].mesh_object else "")).lower()
                )
            ]

        return flt_flags, flt_neworder



# ---------------------------------------------------------------------------
# Car Texture Sync & Automatic Ambient Occlusion (AO) Baking
# ---------------------------------------------------------------------------

def find_car_directory(context=None, filepath=None):
    """Finds the Assetto Corsa car folder containing skins/ or data/."""
    candidates = []
    if filepath:
        candidates.append(os.path.dirname(os.path.abspath(filepath)))
    if bpy.data.filepath:
        candidates.append(os.path.dirname(os.path.abspath(bpy.data.filepath)))

    for base in candidates:
        curr = base
        for _ in range(4):
            if os.path.exists(os.path.join(curr, "skins")) or os.path.exists(os.path.join(curr, "data")):
                return curr
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
    return candidates[0] if candidates else None


def sync_textures_to_car_skins(car_dir, texture_names=None):
    """
    Finds textures (e.g. EXT_body.dds) in car_dir and copies/syncs them
    into all subfolders in car_dir/skins/*/.
    Returns (num_synced, list_of_skin_names).
    """
    if not car_dir or not os.path.exists(car_dir):
        return 0, []
    skins_dir = os.path.join(car_dir, "skins")
    if not os.path.exists(skins_dir):
        return 0, []

    skin_folders = [os.path.join(skins_dir, d) for d in os.listdir(skins_dir)
                    if os.path.isdir(os.path.join(skins_dir, d))]
    if not skin_folders:
        return 0, []

    target_names = texture_names or ["EXT_body.dds", "EXT_body.png"]
    available = []
    for t in target_names:
        src = os.path.join(car_dir, t)
        if os.path.exists(src):
            available.append(src)

    tex_dir = os.path.join(car_dir, "texture")
    if os.path.exists(tex_dir):
        for t in target_names:
            src = os.path.join(tex_dir, t)
            if os.path.exists(src) and src not in available:
                available.append(src)

    if not available:
        return 0, []

    import shutil
    synced_count = 0
    synced_skins = []
    for skin_path in skin_folders:
        skin_name = os.path.basename(skin_path)
        copied_any = False
        for src_file in available:
            dest_file = os.path.join(skin_path, os.path.basename(src_file))
            try:
                shutil.copy2(src_file, dest_file)
                synced_count += 1
                copied_any = True
            except Exception as e:
                print(f"Error copying {src_file} to {dest_file}: {e}")
        if copied_any:
            synced_skins.append(skin_name)

    return synced_count, synced_skins


class KN5_OT_SyncCarSkins(bpy.types.Operator):
    """Synchronize car body textures (EXT_body.dds) to all skin subfolders."""
    bl_idname = "kn5.sync_car_skins"
    bl_label = "Sync Textures to Skins"
    bl_description = "Automatically copies EXT_body.dds from car folder into all skins/*/ folders so changes appear in game/showroom immediately"
    bl_options = {'REGISTER', 'UNDO'}

    car_directory: StringProperty(
        name="Car Directory",
        description="Path to car directory (leave empty to auto-detect from .blend file)",
        default="",
        subtype='DIR_PATH'
    )

    def execute(self, context):
        car_dir = self.car_directory.strip() or find_car_directory(context)
        if not car_dir or not os.path.exists(car_dir):
            self.report({'ERROR'}, "Could not locate Assetto Corsa car directory (ensure file is saved in car folder).")
            return {'CANCELLED'}

        count, skins = sync_textures_to_car_skins(car_dir)
        if count > 0:
            self.report({'INFO'}, f"Synced {count} texture(s) across {len(skins)} skin(s): {', '.join(skins[:5])}")
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"Found skins folder, but no EXT_body.dds found in {car_dir} to sync.")
            return {'CANCELLED'}


class KN5_OT_BakeCarAO(bpy.types.Operator):
    """Automatically bake Ambient Occlusion for all car body panels and sync to all skins."""
    bl_idname = "kn5.bake_car_ao"
    bl_label = "Auto-Bake Car Body AO"
    bl_description = "Bakes full Ambient Occlusion for all body panels using Cycles, converts to DDS, and syncs to all skins"
    bl_options = {'REGISTER', 'UNDO'}

    resolution: EnumProperty(
        name="Resolution",
        items=[
            ("1024", "1024 x 1024", "Fast 1K resolution"),
            ("2048", "2048 x 2048", "Standard 2K resolution (Recommended)"),
            ("4096", "4096 x 4096", "Ultra High 4K resolution"),
        ],
        default="2048"
    )
    samples: IntProperty(name="Cycles Samples", default=24, min=4, max=128)
    margin: IntProperty(name="Bake Margin (px)", default=8, min=0, max=32)
    auto_sync_skins: BoolProperty(name="Auto-Sync to Skins", default=True, description="Immediately copy to all skins/*/EXT_body.dds")
    fill_white: BoolProperty(name="Fill Background White", default=True, description="Sets unmapped/background pixels to white to prevent black artifacts")

    def execute(self, context):
        # 1. Identify target body material and objects
        active_mat = getattr(context, "material", None)
        target_mat_name = "EXT_body"
        if active_mat and "body" in active_mat.name.lower():
            target_mat_name = active_mat.name

        body_objs = []
        for obj in context.scene.objects:
            if obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material and slot.material.name == target_mat_name:
                        body_objs.append(obj)
                        break

        if not body_objs:
            if active_mat:
                for obj in context.scene.objects:
                    if obj.type == 'MESH' and any(s.material == active_mat for s in obj.material_slots):
                        body_objs.append(obj)
            if not body_objs:
                body_objs = [o for o in context.selected_objects if o.type == 'MESH']

        if not body_objs:
            self.report({'ERROR'}, f"No objects found using material '{target_mat_name}' or active material.")
            return {'CANCELLED'}

        # 2. Setup image for baking
        res = int(self.resolution)
        img_name = f"{target_mat_name}.dds"
        bake_img = bpy.data.images.get(img_name)
        if not bake_img or bake_img.size[0] != res or bake_img.size[1] != res:
            if bake_img:
                bpy.data.images.remove(bake_img)
            bake_img = bpy.data.images.new(img_name, width=res, height=res, alpha=True)

        # 3. Inject temp texture node into target materials
        target_materials = set()
        for o in body_objs:
            for s in o.material_slots:
                if s.material:
                    target_materials.add(s.material)

        temp_nodes = []
        for m in target_materials:
            if hasattr(m, "use_nodes"):
                m.use_nodes = True
            if m.node_tree:
                t_node = m.node_tree.nodes.new('ShaderNodeTexImage')
                t_node.name = "__KN5_AO_BAKE__"
                t_node.image = bake_img
                m.node_tree.nodes.active = t_node
                temp_nodes.append((m, t_node))

        # 4. Configure selection and render engine
        bpy.ops.object.select_all(action='DESELECT')
        for o in body_objs:
            o.select_set(True)
        context.view_layer.objects.active = body_objs[0]

        scene = context.scene
        orig_engine = scene.render.engine
        scene.render.engine = 'CYCLES'
        scene.cycles.bake_type = 'AO'
        scene.cycles.samples = self.samples
        scene.render.bake.margin = self.margin

        try:
            self.report({'INFO'}, f"Baking AO for {len(body_objs)} objects at {res}x{res}...")
            bpy.ops.object.bake(type='AO')
        except Exception as e:
            for m, t_node in temp_nodes:
                if m.node_tree and t_node.name in m.node_tree.nodes:
                    m.node_tree.nodes.remove(t_node)
            scene.render.engine = orig_engine
            self.report({'ERROR'}, f"Bake failed: {e}")
            return {'CANCELLED'}

        for m, t_node in temp_nodes:
            if m.node_tree and t_node.name in m.node_tree.nodes:
                m.node_tree.nodes.remove(t_node)
        scene.render.engine = orig_engine

        # 5. Post-process pixels
        pixels = list(bake_img.pixels)
        if self.fill_white:
            num_px = res * res
            for i in range(num_px):
                idx = i * 4
                r, g, b, a = pixels[idx], pixels[idx+1], pixels[idx+2], pixels[idx+3]
                if a < 0.01 or (r < 0.001 and g < 0.001 and b < 0.001):
                    pixels[idx] = 1.0
                    pixels[idx+1] = 1.0
                    pixels[idx+2] = 1.0
                    pixels[idx+3] = 1.0
                else:
                    pixels[idx+3] = 1.0
            bake_img.pixels = pixels

        # 6. Convert to DDS bytes and save
        dds_bytes = rgba_pixels_to_bgra_dds(pixels, res, res)
        car_dir = find_car_directory(context)
        if car_dir:
            out_dds = os.path.join(car_dir, f"{target_mat_name}.dds")
            try:
                with open(out_dds, "wb") as f:
                    f.write(dds_bytes)
            except Exception as e:
                print(f"Failed to write {out_dds}: {e}")

            tex_dir = os.path.join(car_dir, "texture")
            if os.path.exists(tex_dir):
                out_tex_dds = os.path.join(tex_dir, f"{target_mat_name}.dds")
                try:
                    with open(out_tex_dds, "wb") as f:
                        f.write(dds_bytes)
                except Exception:
                    pass

            if self.auto_sync_skins:
                sync_textures_to_car_skins(car_dir, [f"{target_mat_name}.dds"])

        # Update AC material slot
        target_mat = bpy.data.materials.get(target_mat_name)
        if target_mat:
            ac = getattr(target_mat, "assettoCorsa", None)
            if ac:
                found_slot = False
                for slot in ac.texture_slots:
                    if slot.slot_name == "txDiffuse":
                        slot.image = bake_img
                        slot.override_filename = f"{target_mat_name}.dds"
                        found_slot = True
                        break
                if not found_slot:
                    s = ac.texture_slots.add()
                    s.slot_name = "txDiffuse"
                    s.image = bake_img
                    s.override_filename = f"{target_mat_name}.dds"

        self.report({'INFO'}, f"Successfully baked AO ({res}x{res}) for {len(body_objs)} parts and synced to skins!")
        return {'FINISHED'}


class KN5_OT_CreateCleanPaint(bpy.types.Operator):
    """Instantly creates a solid clean paint texture without baking and syncs to all skins."""
    bl_idname = "kn5.create_clean_paint"
    bl_label = "Create Clean Solid Paint"
    bl_description = "Instantly clears all black artifacts by generating a solid neutral base texture and syncing to all skins"
    bl_options = {'REGISTER', 'UNDO'}

    color: FloatVectorProperty(
        name="Paint Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="Base color for clean paint"
    )

    def execute(self, context):
        res = 2048
        pixels = list(self.color) * (res * res)
        dds_bytes = rgba_pixels_to_bgra_dds(pixels, res, res)
        car_dir = find_car_directory(context)
        if not car_dir:
            self.report({'ERROR'}, "Could not locate Assetto Corsa car directory.")
            return {'CANCELLED'}

        out_dds = os.path.join(car_dir, "EXT_body.dds")
        try:
            with open(out_dds, "wb") as f:
                f.write(dds_bytes)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save {out_dds}: {e}")
            return {'CANCELLED'}

        tex_dir = os.path.join(car_dir, "texture")
        if os.path.exists(tex_dir):
            try:
                with open(os.path.join(tex_dir, "EXT_body.dds"), "wb") as f:
                    f.write(dds_bytes)
            except Exception:
                pass

        count, skins = sync_textures_to_car_skins(car_dir, ["EXT_body.dds"])
        self.report({'INFO'}, f"Clean paint generated and synced to {count} skin(s)!")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Object Renaming & Assetto Corsa Naming Checklist Tools
# ---------------------------------------------------------------------------

class KN5_OT_QuickRenameRole(bpy.types.Operator):
    """Assign standard Assetto Corsa name/role to selected object(s)."""
    bl_idname = "kn5.quick_rename_role"
    bl_label = "Assign AC Role Name"
    bl_description = "Renames the active object to the standard Assetto Corsa object/dummy name"
    bl_options = {'REGISTER', 'UNDO'}

    role_name: StringProperty(name="Role Name", default="COCKPIT_HR")

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "Please select an object first.")
            return {'CANCELLED'}

        old_name = obj.name
        obj.name = self.role_name
        self.report({'INFO'}, f"Renamed '{old_name}' -> '{obj.name}'")
        return {'FINISHED'}


class KN5_OT_SmartAutoRename(bpy.types.Operator):
    """Smart scan and auto-rename objects to standard Assetto Corsa naming conventions."""
    bl_idname = "kn5.smart_auto_rename"
    bl_label = "Smart Auto-Rename Objects"
    bl_description = "Intelligently scans scene objects and assigns standard AC names (Wheels, Cockpit, Steer, Glass, Mirrors, Body) based on geometry and keywords"
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(
        name="Scope",
        items=[
            ('SELECTED', "Selected Objects Only", "Only scan and rename currently selected objects"),
            ('ALL', "All Scene Objects", "Scan all objects in the scene"),
        ],
        default='ALL'
    )
    rename_wheels: BoolProperty(name="Rename Wheels & Rims", default=True)
    rename_cockpit: BoolProperty(name="Rename Cockpit & Steering", default=True)
    rename_glass: BoolProperty(name="Rename Glass & Windows", default=True)
    rename_mirrors: BoolProperty(name="Rename Mirrors", default=True)
    rename_body: BoolProperty(name="Rename Body & Panels", default=True)

    def execute(self, context):
        target_objs = context.selected_objects if (self.scope == 'SELECTED' and context.selected_objects) else list(context.scene.objects)
        renamed_count = 0

        def get_world_pos(o):
            if hasattr(o, "matrix_world"):
                return o.matrix_world.translation
            return o.location

        # Compute dynamic center from wheel/susp candidates in target objects
        wheel_candidates = [
            o for o in target_objs
            if any(k in o.name.lower() for k in ['wheel', 'llanta', 'rim', 'tire', 'tyre', 'rueda', 'freno', 'disc', 'disk', 'caliper', 'susp'])
        ]
        if wheel_candidates:
            w_ys = [get_world_pos(o).y for o in wheel_candidates]
            w_xs = [get_world_pos(o).x for o in wheel_candidates]
            center_y = (min(w_ys) + max(w_ys)) / 2.0
            center_x = (min(w_xs) + max(w_xs)) / 2.0
        else:
            center_y = 0.0
            center_x = 0.0

        for obj in target_objs:
            n = obj.name.lower()
            pos = get_world_pos(obj)
            new_name = None

            # 1. Steering wheel
            if self.rename_cockpit and any(k in n for k in ['volante', 'steering', 'steer_wheel', 'steer_mesh', 'int_volante', 'direksiyon']) and 'steer_hr' not in n:
                new_name = "STEER_HR"

            # 2. Cockpit / Interior
            elif self.rename_cockpit and any(k in n for k in ['interior', 'cockpit', 'salpicadero', 'dashboard', 'int_cockpit']) and 'cockpit_hr' not in n and 'steer' not in n:
                if obj.type == 'EMPTY':
                    new_name = "COCKPIT_HR"
                else:
                    new_name = "GEO_COCKPIT_HR"

            # 3. Wheels / Rims / Tyres / Discs
            elif self.rename_wheels and any(k in n for k in ['wheel', 'llanta', 'rim', 'tire', 'tyre', 'rueda', 'freno', 'disc', 'disk', 'caliper', 'kaliper', 'susp']):
                # In Blender coordinate system: -Y is Front, +Y is Rear
                # Facing -Y from behind: +X is Left, -X is Right
                is_front = pos.y < center_y
                is_left = pos.x > center_x

                # Check corner tags in name
                if any(tag in n for tag in ['_lf', '_fl', ' lf', ' fl']) or n.endswith(('lf', 'fl')):
                    is_front, is_left = True, True
                elif any(tag in n for tag in ['_rf', '_fr', ' rf', ' fr']) or n.endswith(('rf', 'fr')):
                    is_front, is_left = True, False
                elif any(tag in n for tag in ['_lr', '_rl', '_bl', ' lr', ' rl', ' bl']) or n.endswith(('lr', 'rl', 'bl')):
                    is_front, is_left = False, True
                elif any(tag in n for tag in ['_rr', '_br', ' rr', ' br']) or n.endswith(('rr', 'br')):
                    is_front, is_left = False, False
                else:
                    if any(k in n for k in ['delantera', 'delant', 'front', 'avant', 'vorne', '_on_', 'on_']):
                        is_front = True
                    elif any(k in n for k in ['trasera', 'tras', 'rear', 'back', 'arriere', 'heck', '_arka_', 'arka_']):
                        is_front = False

                    if any(k in n for k in ['izq', 'izqda', 'left', 'sinistra', 'gauche', 'links', 'sol', '_l_']):
                        is_left = True
                    elif any(k in n for k in ['der', 'derecha', 'right', 'destra', 'droite', 'rechts', 'sag', 'sağ', '_r_']):
                        is_left = False

                prefix = "LF" if (is_front and is_left) else ("RF" if (is_front and not is_left) else ("LR" if (not is_front and is_left) else "RR"))

                if any(k in n for k in ['rim', 'llanta']):
                    new_name = f"RIM_{prefix}"
                elif any(k in n for k in ['caliper', 'kaliper', 'pinza']):
                    new_name = f"CALIPER_{prefix}"
                elif any(k in n for k in ['disc', 'disk', 'rotor', 'freno', 'brake']):
                    new_name = f"DISC_{prefix}"
                elif any(k in n for k in ['susp', 'amortiguador']):
                    new_name = f"SUSP_{prefix}"
                elif any(k in n for k in ['tyre', 'tire']):
                    new_name = f"TYRE_{prefix}"
                else:
                    new_name = f"WHEEL_{prefix}"

            # 4. Mirrors
            elif self.rename_mirrors and any(k in n for k in ['mirror', 'espejo', 'retrovisor', 'ayna']):
                if pos.x > 0.2 or any(k in n for k in ['izq', 'left', 'izqda', 'sol', '_l_']):
                    new_name = "MIRROR_L"
                elif pos.x < -0.2 or any(k in n for k in ['dch', 'der', 'right', 'derecha', 'sag', 'sağ', '_r_']):
                    new_name = "MIRROR_R"
                else:
                    new_name = "MIRROR_C"

            # 5. Glass / Windows
            elif self.rename_glass and any(k in n for k in ['cristal', 'glass', 'window', 'parabrisas', 'luneta', 'cam']):
                if 'int' in n or any(k in n for k in ['interior', 'inside', 'ic_cam', 'iç_cam']):
                    new_name = "INT_GLASS"
                else:
                    new_name = "EXT_GLASS"

            # 6. Body / Chassis
            elif self.rename_body and any(k in n for k in ['chapa', 'body', 'carroceria', 'exterior_body', 'kaporta', 'gövde', 'govde']) and 'door' not in n and 'puerta' not in n and 'kapi' not in n and 'kapı' not in n:
                new_name = "BODY"

            if new_name and obj.name != new_name:
                if new_name in bpy.data.objects and bpy.data.objects[new_name] != obj:
                    obj.name = f"{new_name}_001"
                else:
                    obj.name = new_name
                renamed_count += 1

        self.report({'INFO'}, f"Smart Auto-Rename completed: {renamed_count} object(s) updated.")
        return {'FINISHED'}


class KN5_OT_CreateMissingDummies(bpy.types.Operator):
    """Automatically create all missing required Assetto Corsa dummies and helpers."""
    bl_idname = "kn5.create_missing_dummies"
    bl_label = "Create All Missing Dummies"
    bl_description = "Generates missing essential AC empties (COCKPIT_HR, STEER_HR, DRIVER_POS, DRIVER_EYES, Wheels, Suspensions)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        col = context.collection or context.scene.collection
        created = []

        root = context.scene.objects.get("CAR_ROOT") or context.scene.objects.get("SCENE_ROOT") or context.scene.objects.get("RootNode")
        anchors = compute_smart_cockpit_anchors(context)

        # 1. Cockpit HR
        cockpit = context.scene.objects.get("COCKPIT_HR")
        if not cockpit:
            cockpit = bpy.data.objects.new("COCKPIT_HR", None)
            cockpit.empty_display_type = 'CUBE'
            cockpit.empty_display_size = 0.5
            cockpit.location = anchors["cockpit_pos"]
            if root:
                cockpit.parent = root
            col.objects.link(cockpit)
            created.append("COCKPIT_HR")

        # 2. Steering Wheel dummy
        steer = context.scene.objects.get("STEER_HR")
        if not steer:
            steer = bpy.data.objects.new("STEER_HR", None)
            steer.empty_display_type = 'CIRCLE'
            steer.empty_display_size = anchors["steer_radius"]
            steer.location = anchors["steer_pos"]
            if cockpit:
                steer.parent = cockpit
                steer.matrix_parent_inverse = cockpit.matrix_world.inverted()
            col.objects.link(steer)
            created.append("STEER_HR")

            # Parent steering mesh if unparented
            s_mesh = anchors["steer_mesh"]
            if s_mesh and s_mesh.parent != steer:
                orig_m = s_mesh.matrix_world.copy()
                s_mesh.parent = steer
                s_mesh.matrix_parent_inverse = steer.matrix_world.inverted()
                s_mesh.matrix_world = orig_m

        # 3. Driver Pos & Eyes
        driver_pos = context.scene.objects.get("DRIVER_POS")
        if not driver_pos:
            driver_pos = bpy.data.objects.new("DRIVER_POS", None)
            driver_pos.empty_display_type = 'SINGLE_ARROW'
            driver_pos.empty_display_size = 0.35
            driver_pos.location = anchors["driver_pos"]
            driver_pos.rotation_euler = (0.0, 0.0, math.radians(-90))
            if cockpit:
                driver_pos.parent = cockpit
                driver_pos.matrix_parent_inverse = cockpit.matrix_world.inverted()
            col.objects.link(driver_pos)
            created.append("DRIVER_POS")

        driver_eyes = context.scene.objects.get("DRIVER_EYES")
        if not driver_eyes:
            driver_eyes = bpy.data.objects.new("DRIVER_EYES", None)
            driver_eyes.empty_display_type = 'SPHERE'
            driver_eyes.empty_display_size = 0.12
            driver_eyes.location = anchors["driver_eyes"]
            if driver_pos:
                driver_eyes.parent = driver_pos
                driver_eyes.matrix_parent_inverse = driver_pos.matrix_world.inverted()
            col.objects.link(driver_eyes)
            created.append("DRIVER_EYES")

        # 4. Suspensions & Wheels (-Y is Front, +Y is Rear, +X is Left, -X is Right)
        wheel_positions = {
            "LF": (0.76, -1.28, 0.31),
            "RF": (-0.76, -1.28, 0.31),
            "LR": (0.76, 1.28, 0.31),
            "RR": (-0.76, 1.28, 0.31),
        }
        for side, pos in wheel_positions.items():
            susp = context.scene.objects.get(f"SUSP_{side}")
            if not susp:
                susp = bpy.data.objects.new(f"SUSP_{side}", None)
                susp.empty_display_type = 'SINGLE_ARROW'
                susp.empty_display_size = 0.35
                susp.location = pos
                susp.rotation_euler = (0.0, 0.0, 0.0)
                if root:
                    susp.parent = root
                col.objects.link(susp)
                created.append(f"SUSP_{side}")

            wheel = context.scene.objects.get(f"WHEEL_{side}")
            if not wheel:
                wheel = bpy.data.objects.new(f"WHEEL_{side}", None)
                wheel.empty_display_type = 'CIRCLE'
                wheel.empty_display_size = 0.31
                wheel.location = pos
                wheel.rotation_euler = (0.0, 0.0, 0.0)
                if susp:
                    wheel.parent = susp
                col.objects.link(wheel)
                created.append(f"WHEEL_{side}")

        if created:
            self.report({'INFO'}, f"Created {len(created)} missing dummies: {', '.join(created[:5])}...")
        else:
            self.report({'INFO'}, "All standard dummies are already present!")
        return {'FINISHED'}


class KN5_OT_GeneratePowerGraph(bpy.types.Operator):
    """Reads engine.ini and power.lut to compute torque and power curves, writing them to ui/ui_car.json."""
    bl_idname = "kn5.generate_power_graph"
    bl_label = "Auto-Generate Power Graph (ui_car.json)"
    bl_description = "Calculates torque & power curves from data/power.lut and updates ui/ui_car.json"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import json

        car_dir = find_car_directory(context)
        if not car_dir or not os.path.exists(car_dir):
            self.report({'ERROR'}, "Could not locate Assetto Corsa car directory.")
            return {'CANCELLED'}

        data_dir = os.path.join(car_dir, "data")
        ui_dir = os.path.join(car_dir, "ui")
        os.makedirs(ui_dir, exist_ok=True)
        ui_car_path = os.path.join(ui_dir, "ui_car.json")

        power_file_name = "power.lut"
        engine_ini_path = os.path.join(data_dir, "engine.ini")
        if os.path.exists(engine_ini_path):
            with open(engine_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.strip().upper().startswith("POWER_CURVE"):
                        parts = line.split("=")
                        if len(parts) >= 2:
                            val = parts[1].split(";")[0].strip()
                            if val:
                                power_file_name = val
                                break

        power_lut_path = os.path.join(data_dir, power_file_name)
        if not os.path.exists(power_lut_path):
            alt = os.path.join(data_dir, "power_curva.lut")
            if os.path.exists(alt):
                power_lut_path = alt

        if not os.path.exists(power_lut_path):
            self.report({'ERROR'}, f"Could not find power curve LUT file at {power_lut_path}.")
            return {'CANCELLED'}

        torque_curve = []
        power_curve = []
        max_torque = 0.0
        rpm_at_max_torque = 0
        max_bhp = 0.0
        rpm_at_max_bhp = 0

        with open(power_lut_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("/") or line.startswith(";"):
                    continue
                parts = line.split("|")
                if len(parts) == 2:
                    try:
                        rpm = float(parts[0].strip())
                        torque = float(parts[1].strip())
                        bhp = (torque * rpm) / 7120.8 if rpm > 0 else 0.0
                        torque_curve.append([rpm, round(torque, 1)])
                        power_curve.append([rpm, round(bhp, 1)])
                        if torque > max_torque:
                            max_torque = torque
                            rpm_at_max_torque = int(rpm)
                        if bhp > max_bhp:
                            max_bhp = bhp
                            rpm_at_max_bhp = int(rpm)
                    except ValueError:
                        pass

        if not torque_curve:
            self.report({'ERROR'}, f"No valid curve data found in {power_lut_path}.")
            return {'CANCELLED'}

        ui_data = {}
        if os.path.exists(ui_car_path):
            try:
                with open(ui_car_path, "r", encoding="utf-8", errors="ignore") as f:
                    ui_data = json.load(f)
            except Exception:
                ui_data = {}

        ui_data["torqueCurve"] = torque_curve
        ui_data["powerCurve"] = power_curve
        if "specs" not in ui_data or not isinstance(ui_data["specs"], dict):
            ui_data["specs"] = {}
        ui_data["specs"]["bhp"] = f"{int(round(max_bhp))} bhp"
        ui_data["specs"]["torque"] = f"{int(round(max_torque))} Nm"

        with open(ui_car_path, "w", encoding="utf-8") as f:
            json.dump(ui_data, f, indent=4, ensure_ascii=False)

        msg = f"Generated {len(torque_curve)} points: {int(round(max_bhp))} BHP @ {rpm_at_max_bhp} RPM, {int(round(max_torque))} Nm @ {rpm_at_max_torque} RPM."
        self.report({'INFO'}, f"Updated ui_car.json: {msg}")
        return {'FINISHED'}


REGISTER_CLASSES = (
    KN5_NodeProperties,
    KN5_OT_CreateTrackDummy,
    KN5_OT_SetupCarHierarchy,
    KN5_OT_CreatePartAnimation,
    KN5_OT_ExportAnimationFBX,
    KN5_OT_AutoRigWheels,
    KN5_OT_SyncModelToPhysicsINI,
    KN5_OT_AlignWheelsToPhysics,
    KN5_OT_CreateDriverDummies,
    KN5_OT_ImportDriverKNH,
    KN5_OT_ExportDriverKNH,
    KN5_OT_SetupCarCameras,
    KN5_OT_SwitchActiveCamera,
    KN5_OT_ImportCarCameras,
    KN5_OT_ExportCarCameras,
    KN5_OT_SyncCamerasToIni,
    KN5_OT_TagSurface,
    KN5_OT_ValidateScene,
    KN5_OT_AutoFixScene,
    KN5_OT_SetupTransparentMeshes,
    KN5_LightEntry,
    KN5_LightsSceneProperties,
    KN5_OT_DetectLightMeshes,
    KN5_OT_ImportLightsINI,
    KN5_OT_ExportLightsINI,
    KN5_OT_AddLightEntry,
    KN5_OT_RemoveLightEntry,
    KN5_OT_ClearLightEntries,
    KN5_OT_SortLightEntries,
    KN5_OT_SelectLightMesh,
    KN5_UL_LightEntryList,
    KN5_OT_SyncCarSkins,
    KN5_OT_BakeCarAO,
    KN5_OT_CreateCleanPaint,
    KN5_OT_QuickRenameRole,
    KN5_OT_SmartAutoRename,
    KN5_OT_CreateMissingDummies,
    KN5_OT_GeneratePowerGraph,
)



def register():
    for cls in REGISTER_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.assettoCorsa = PointerProperty(type=KN5_NodeProperties)
    bpy.types.Scene.kn5_lights = PointerProperty(type=KN5_LightsSceneProperties)


def unregister():
    if hasattr(bpy.types.Scene, "kn5_lights"):
        del bpy.types.Scene.kn5_lights
    if hasattr(bpy.types.Object, "assettoCorsa"):
        del bpy.types.Object.assettoCorsa
    for cls in reversed(REGISTER_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
