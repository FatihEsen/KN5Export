# Assetto Corsa KN5 Studio - High-Performance KN5 Exporter
# Developed for Blender 3.6 LTS, 4.x, and 5.x

import bpy
import bmesh
import mathutils
import os
import re
import time
from typing import List, Dict, Tuple, Optional, Set
from bpy_extras.io_utils import ExportHelper
from bpy.props import (
    BoolProperty,
    EnumProperty,
    StringProperty,
)

try:
    from .constants import (
        DEFAULT_VERSION,
        NODE_TYPE_DUMMY,
        MATERIAL_PRESETS,
        match_material_preset,
    )
    from .kn5_format import (
        KN5Model,
        KN5Node,
        KN5Mesh,
        KN5Vertex,
        KN5Texture,
        KN5Material,
    )
    from .dds import (
        is_dds_bytes,
        image_to_bgra_dds,
        rgba_pixels_to_bgra_dds,
        build_dds_header_uncompressed_bgra,
        create_flat_normal_map_dds,
        create_glass_tint_dds,
        create_solid_color_dds,
    )
    from .materials import audit_texture_bindings, find_texture_image, clean_texture_name
    from .tools import sync_textures_to_car_skins
except (ImportError, ValueError):
    from constants import (
        DEFAULT_VERSION,
        NODE_TYPE_DUMMY,
        MATERIAL_PRESETS,
        match_material_preset,
    )
    from kn5_format import (
        KN5Model,
        KN5Node,
        KN5Mesh,
        KN5Vertex,
        KN5Texture,
        KN5Material,
    )
    from dds import (
        is_dds_bytes,
        image_to_bgra_dds,
        rgba_pixels_to_bgra_dds,
        build_dds_header_uncompressed_bgra,
        create_flat_normal_map_dds,
        create_glass_tint_dds,
        create_solid_color_dds,
    )
    from materials import audit_texture_bindings, find_texture_image, clean_texture_name
    from tools import sync_textures_to_car_skins


def convert_vector3(v: mathutils.Vector) -> Tuple[float, float, float]:
    """Converts Blender vector (X right, Y forward, Z up) to AC DirectX (X right, Y up, Z forward)."""
    return (float(v[0]), float(v[2]), float(-v[1]))


def convert_matrix(m: mathutils.Matrix, force_unit_scale: bool = False) -> List[float]:
    """
    Converts Blender 4x4 transform matrix to Assetto Corsa column-major DirectX 4x4 matrix.
    DirectX basis transformation: T = diag(1, 1, -1) with Y/Z swap.
    """
    loc, rot, scale = m.decompose()
    # Convert translation
    c_loc = convert_vector3(loc)
    # Convert rotation
    axis, angle = rot.to_axis_angle()
    c_axis = mathutils.Vector((axis[0], axis[2], -axis[1]))
    if c_axis.length_squared > 0.00001:
        c_rot = mathutils.Quaternion(c_axis, angle)
    else:
        c_rot = mathutils.Quaternion()

    # Reconstruct DirectX matrix
    mat_loc = mathutils.Matrix.Translation(c_loc)
    mat_rot = c_rot.to_matrix().to_4x4()
    if force_unit_scale:
        mat_scale = mathutils.Matrix.Identity(4)
    else:
        mat_scale = mathutils.Matrix.Diagonal((scale[0], scale[2], scale[1], 1.0))
    res = mat_loc @ mat_rot @ mat_scale

    # Output in column-major order (DirectX convention)
    col_major = []
    for col in range(4):
        for row in range(4):
            col_major.append(float(res[row][col]))
    return col_major



def identity_matrix16() -> List[float]:
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
    ]


class SubmeshData:
    def __init__(self, material_id: int):
        self.material_id = material_id
        self.vertices: List[KN5Vertex] = []
        self.indices: List[int] = []


class KN5Exporter:
    def __init__(self, context, filepath: str, options: dict):
        self.context = context
        self.filepath = filepath
        self.options = options
        self.warnings: List[str] = []

        self.material_map: Dict[str, int] = {}
        self.materials: List[KN5Material] = []
        self.texture_map: Dict[str, Optional[bpy.types.Image]] = {}

        self.total_vertices = 0
        self.total_triangles = 0
        self.total_meshes = 0

        self.virtual_children: Dict[bpy.types.Object, List[bpy.types.Object]] = {}
        self.virtual_parent: Dict[bpy.types.Object, bpy.types.Object] = {}

    def export(self) -> KN5Model:
        model = KN5Model(version=int(self.options.get("version", DEFAULT_VERSION)))

        # 1. Collect target objects
        target_objects = self._get_target_objects()
        texture_issues = audit_texture_bindings(
            target_objects, self.options.get("texture_mode", "EMBEDDED_DDS"))
        self.warnings.extend(texture_issues)
        missing_textures = [issue for issue in texture_issues
                            if "no linked or loaded image" in issue
                            or "external image file" in issue]
        texture_mode = self.options.get("texture_mode", "EMBEDDED_DDS")
        if missing_textures and texture_mode == "EMBEDDED_DDS":
            details = "\n".join(missing_textures[:10])
            more = len(missing_textures) - 10
            if more > 0:
                details += f"\n... and {more} more missing texture(s)."
            raise ValueError(
                "KN5 export stopped because mapped textures are unavailable. "
                "Use Audit / Repair Textures and relink the missing images.\n" + details
            )

        # 2. Build materials & collect textures
        self._build_materials(target_objects)

        # 3. Process textures into KN5Texture objects
        model.textures = self._process_textures()
        model.materials = self.materials

        # 4. Auto-detect and fix wheel & rim hierarchy if enabled
        if self.options.get("auto_fix_wheels", True):
            self._prepare_wheel_hierarchy(target_objects)

        # 5. Build scene graph hierarchy
        car_name = os.path.splitext(os.path.basename(self.filepath))[0]
        root_node = KN5Node(name=car_name, node_type=NODE_TYPE_DUMMY)
        root_node.transform = identity_matrix16()

        # In Assetto Corsa KN5, root_node IS the car container.
        # Wheel dummies (WHEEL_LF, WHEEL_RF, WHEEL_LR, WHEEL_RR) MUST be direct children
        # of root_node for physics attachments and Showroom "Align using data" to function.
        # An intermediate dummy named 'CAR_ROOT' or matching the car name must NEVER exist
        # in the KN5 node tree. If CAR_ROOT exists in Blender, dissolve it: do not export
        # CAR_ROOT itself, and treat its direct children as direct children of root_node.
        car_root_obj = next((o for o in target_objects if o.name.upper() in ("CAR_ROOT", "ROOT", car_name.upper())), None)

        corners = ["LF", "RF", "LR", "RR"]
        wheel_dummy_objs = set()
        for o in target_objects:
            up = o.name.upper()
            if up == "WHELL_RR" or any(up == f"WHEEL_{c}" or up.startswith(f"WHEEL_{c}.") for c in corners):
                wheel_dummy_objs.add(o)

        top_objects = []
        for o in target_objects:
            if o == car_root_obj:
                continue
            if o in self.virtual_parent:
                continue
            if o in wheel_dummy_objs:
                top_objects.append(o)
                continue
            if o.parent is None or o.parent == car_root_obj or o.parent not in target_objects:
                top_objects.append(o)

        for obj in top_objects:
            child_node = self._export_object_recursive(obj, target_objects, car_root_obj, wheel_dummy_objs)
            if child_node:
                root_node.add_child(child_node)

        model.root_node = root_node
        return model

    def _prepare_wheel_hierarchy(self, target_objects: List[bpy.types.Object]):
        """Detects unparented rims, tires, and brake discs and pairs them with their WHEEL_XX dummy."""
        corners = ["LF", "RF", "LR", "RR"]
        wheel_dummies: Dict[str, bpy.types.Object] = {}
        susp_dummies: Dict[str, bpy.types.Object] = {}

        # Locate wheel and suspension dummies
        for obj in target_objects:
            if obj.type != 'EMPTY':
                continue
            up = obj.name.upper()
            if up == "WHELL_RR":
                wheel_dummies["RR"] = obj
            for c in corners:
                if up == f"WHEEL_{c}" or up.startswith(f"WHEEL_{c}."):
                    wheel_dummies[c] = obj
                elif up == f"SUSP_{c}" or up.startswith(f"SUSP_{c}."):
                    susp_dummies[c] = obj

        if not wheel_dummies and not susp_dummies:
            return

        ignored_keywords = [
            'LIGHT', 'LAMP', 'LAMB', 'LAMBA', 'FAR', 'STOP', 'FREN', 'SIGNAL', 'SINYAL',
            'EMISSIVE', 'REFL', 'REFLECTOR', 'GL', 'ANTIFOG', 'FOG', 'HEADLIGHT', 'TAILLIGHT',
            'BRAKELIGHT', 'INDICATOR', 'GLASS', 'WINDOW', 'WINDSHIELD', 'MIRROR', 'DOOR',
            'BODY', 'BUMPER', 'HOOD', 'BONNET', 'TRUNK', 'BOOT', 'ROOF', 'WING', 'SPOILER',
            'CHASSIS', 'COCKPIT', 'INTERIOR', 'STEER', 'SEAT', 'CHAIR', 'PEDAL', 'HANDBRAKE',
            'SHIFTER', 'GEAR', 'LEVER', 'DASH', 'CLUSTER', 'CONSOLE', 'EXHAUST', 'ENGINE',
            'WIPER', 'BASE', 'RAIL', 'COLUMN',
        ]

        # Check scene kn5_lights collection to protect all declared light meshes
        scene_light_names = set()
        scene_lights = getattr(self.context.scene, "kn5_lights", None)
        if scene_lights:
            for entry in scene_lights.entries:
                if entry.mesh_name:
                    scene_light_names.add(entry.mesh_name.upper())
                if entry.mesh_object:
                    scene_light_names.add(entry.mesh_object.name.upper())

        def _get_wheel_corner(name: str) -> Optional[str]:
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

        for obj in target_objects:
            if obj.type != 'MESH':
                continue
            name_upper = obj.name.upper()

            # 1. Skip if registered in lights list or has light/interior/body keywords
            if name_upper in scene_light_names:
                continue
            if any(k in name_upper for k in ignored_keywords):
                continue

            # 2. Check if caliper vs rotating wheel component
            is_caliper = (
                any(k in name_upper for k in caliper_keywords)
                or name_upper.startswith(("CALIPER_", "KALIPER_", "PINZA_"))
            )

            is_wheel_part = (
                any(k in name_upper for k in wheel_keywords)
                or name_upper.startswith(("RIM_", "TYRE_", "TIRE_", "WHEEL_MESH_", "DISC_", "DISK_", "ROTOR_"))
            )
            # Check material shader as well (ksBrakeDisc)
            if not is_wheel_part and not is_caliper:
                for slot in getattr(obj, "material_slots", []):
                    if slot.material:
                        ac = getattr(slot.material, "assettoCorsa", None)
                        if ac and getattr(ac, "shader_name", "").lower() == "ksbrakedisc":
                            is_wheel_part = True
                            break

            if not is_wheel_part and not is_caliper:
                continue

            # 3. Match corner with strict boundary matching
            matched_corner = _get_wheel_corner(name_upper)
            if not matched_corner:
                continue

            if is_caliper:
                # Brake calipers must NOT rotate with the wheel spin!
                # In Assetto Corsa, calipers belong under SUSP_XX (steers & moves with suspension, but does not roll/spin).
                if matched_corner in susp_dummies:
                    s_dummy = susp_dummies[matched_corner]
                    curr = obj.parent
                    is_child = False
                    while curr:
                        if curr == s_dummy:
                            is_child = True
                            break
                        curr = curr.parent

                    if not is_child:
                        if s_dummy not in self.virtual_children:
                            self.virtual_children[s_dummy] = []
                        self.virtual_children[s_dummy].append(obj)
                        self.virtual_parent[obj] = s_dummy
                        self.warnings.append(f"Auto-parented brake caliper '{obj.name}' under '{s_dummy.name}' (knuckle/suspension) for KN5 export so it will not spin.")
                else:
                    self.warnings.append(f"Brake caliper '{obj.name}' kept static (not parented to spinning WHEEL_{matched_corner}).")
            elif is_wheel_part and matched_corner in wheel_dummies:
                dummy = wheel_dummies[matched_corner]
                # If obj is not already a descendant of this dummy, adopt it
                curr = obj.parent
                is_child = False
                while curr:
                    if curr == dummy:
                        is_child = True
                        break
                    curr = curr.parent

                if not is_child:
                    if dummy not in self.virtual_children:
                        self.virtual_children[dummy] = []
                    self.virtual_children[dummy].append(obj)
                    self.virtual_parent[obj] = dummy
                    self.warnings.append(f"Auto-parented '{obj.name}' under '{dummy.name}' for KN5 export.")

    def _get_target_objects(self) -> List[bpy.types.Object]:
        if "target_objects" in self.options and self.options["target_objects"] is not None:
            return [o for o in self.options["target_objects"] if not o.name.startswith("__")]
        if self.options.get("target_collection"):
            col = self.options["target_collection"]
            return [o for o in col.all_objects if not o.name.startswith("__")]
        if self.options.get("selection_only", False):
            selected = [o for o in self.context.selected_objects if not o.name.startswith("__")]
            if not selected:
                raise ValueError("No objects selected to export!")
            return selected
        return [o for o in self.context.scene.objects if not o.name.startswith("__")]

    def _build_materials(self, objects: List[bpy.types.Object]):
        """Collects all unique materials used by target objects and prepares KN5Material records."""
        used_materials = set()
        for obj in objects:
            if obj.type == 'MESH':
                for slot in obj.material_slots:
                    if slot.material and not slot.material.name.startswith("__"):
                        used_materials.add(slot.material)

        # Ensure at least one default material if scene has none
        if not used_materials:
            default_mat = bpy.data.materials.new(name="DefaultMaterial")
            used_materials.add(default_mat)

        for mat in sorted(used_materials, key=lambda m: m.name):
            kn5_mat = self._convert_blender_material(mat)
            mat_id = len(self.materials)
            self.material_map[mat.name] = mat_id
            self.materials.append(kn5_mat)

    def _convert_blender_material(self, mat: bpy.types.Material) -> KN5Material:
        kn5_mat = KN5Material(name=mat.name)
        ac = getattr(mat, "assettoCorsa", None)

        def add_texture_binding(slot):
            tex_name = slot.effective_filename
            # A stale Image datablock can exist while its source file has disappeared.
            image = find_texture_image(
                mat, slot.slot_name, tex_name, search_disk=True)
            if not tex_name and image:
                tex_name = image.name
            force_dds = (self.options.get("texture_mode", "EMBEDDED_DDS") == "EMBEDDED_DDS")
            tex_name = clean_texture_name(tex_name, force_dds=force_dds)
            if tex_name:
                kn5_mat.add_texture_mapping(slot.slot_name, tex_name)
                if image or self.options.get("texture_mode", "EMBEDDED_DDS") == "EXTERNAL":
                    self.texture_map[tex_name] = image

        auto_detect = self.options.get("auto_detect_materials", True)
        matched_preset_key = match_material_preset(mat.name) if auto_detect else None

        has_custom_ac = False
        if ac:
            if ac.preset_selector != "NONE" or ac.blend_mode != "0" or (ac.shader_name and ac.shader_name != "ksPerPixel") or len(ac.shader_properties) > 0:
                has_custom_ac = True

        if has_custom_ac and ac:
            kn5_mat.shader = ac.shader_name or "ksPerPixel"
            kn5_mat.blend_mode = int(ac.blend_mode)
            kn5_mat.alpha_tested = ac.alpha_tested
            kn5_mat.depth_mode = int(ac.depth_mode)

            # Copy custom shader properties
            for prop in ac.shader_properties:
                kn5_mat.add_property(prop.name, prop.valueA, prop.valueB, prop.valueC, prop.valueD)

            # Copy texture mappings
            for slot in ac.texture_slots:
                add_texture_binding(slot)

        elif matched_preset_key and matched_preset_key in MATERIAL_PRESETS:
            # Auto-detected preset (Glass, Bulb, Chrome, Paint, Tyres, etc.)
            preset = MATERIAL_PRESETS[matched_preset_key]
            kn5_mat.shader = preset["shader"]
            kn5_mat.blend_mode = int(preset["blend_mode"])
            kn5_mat.alpha_tested = bool(preset["alpha_tested"])
            kn5_mat.depth_mode = int(preset["depth_mode"])

            for p_name, p_val in preset["props"].items():
                kn5_mat.add_property(p_name, p_val)

            # Copy any user texture slots if defined
            if ac:
                for slot in ac.texture_slots:
                    add_texture_binding(slot)

        else:
            if ac:
                kn5_mat.shader = ac.shader_name or "ksPerPixel"
                kn5_mat.blend_mode = int(ac.blend_mode)
                kn5_mat.alpha_tested = ac.alpha_tested
                kn5_mat.depth_mode = int(ac.depth_mode)

                for prop in ac.shader_properties:
                    kn5_mat.add_property(prop.name, prop.valueA, prop.valueB, prop.valueC, prop.valueD)

                for slot in ac.texture_slots:
                    add_texture_binding(slot)

        # Determine transparency and shader requirements
        is_transparent = (
            kn5_mat.blend_mode == 1
            or kn5_mat.shader in ("ksWindscreen", "ksPerPixelAlpha")
            or matched_preset_key in ("GLASS_CLEAR", "WINDSCREEN")
            or getattr(mat, "blend_method", "OPAQUE") == "BLEND"
        )

        if is_transparent:
            kn5_mat.blend_mode = 1  # BLEND_ALPHA_BLEND
            # For reflective glass (ksPerPixelReflection / ksWindscreen), keep DEPTH_NORMAL (0) like Kunos cars
            if kn5_mat.shader in ("ksPerPixelReflection", "ksWindscreen"):
                kn5_mat.depth_mode = 0  # DEPTH_NORMAL
            elif ac and hasattr(ac, "depth_mode"):
                kn5_mat.depth_mode = int(ac.depth_mode)
            else:
                kn5_mat.depth_mode = 1  # DEPTH_NO_WRITE
            kn5_mat.alpha_tested = False
            if kn5_mat.shader == "ksPerPixel":
                kn5_mat.shader = "ksPerPixelAlpha"

        # Defaults if no properties were specified
        if not kn5_mat.properties:
            if is_transparent:
                kn5_mat.add_property("ksAmbient", 0.25)
                kn5_mat.add_property("ksDiffuse", 0.20)
                kn5_mat.add_property("ksSpecular", 1.00)
                kn5_mat.add_property("ksSpecularEXP", 120.0)
                kn5_mat.add_property("fresnelC", 0.20)
                kn5_mat.add_property("fresnelEXP", 4.0)
                kn5_mat.add_property("fresnelMaxLevel", 0.90)
            else:
                kn5_mat.add_property("ksAmbient", 0.35)
                kn5_mat.add_property("ksDiffuse", 0.40)
                kn5_mat.add_property("ksSpecular", 0.30)
                kn5_mat.add_property("ksSpecularEXP", 30.0)

        # Ensure required textures exist for Assetto Corsa DirectX 11 pipeline
        existing_slots = [t[0] for t in kn5_mat.texture_mappings]

        if "txDiffuse" not in existing_slots:
            diffuse_img = find_texture_image(mat, "txDiffuse", search_disk=True) if (mat.use_nodes and mat.node_tree) else None
            if diffuse_img:
                force_dds = (self.options.get("texture_mode", "EMBEDDED_DDS") == "EMBEDDED_DDS")
                img_name = clean_texture_name(diffuse_img.name, force_dds=force_dds)
                kn5_mat.add_texture_mapping("txDiffuse", img_name)
                self.texture_map[img_name] = diffuse_img
            else:
                # Provide appropriate procedural texture fallback
                if is_transparent:
                    fallback_tex = "default_glass.dds"
                    kn5_mat.add_texture_mapping("txDiffuse", fallback_tex)
                    if fallback_tex not in self.texture_map:
                        self.texture_map[fallback_tex] = create_glass_tint_dds(4, 4, alpha=80)
                else:
                    fallback_tex = "default_white.dds"
                    kn5_mat.add_texture_mapping("txDiffuse", fallback_tex)
                    if fallback_tex not in self.texture_map:
                        self.texture_map[fallback_tex] = create_solid_color_dds(255, 255, 255, 255, 4, 4)

        if kn5_mat.shader == "ksWindscreen":
            # ksWindscreen requires txNormal and txMask
            existing_slots = [t[0] for t in kn5_mat.texture_mappings]
            if "txNormal" not in existing_slots:
                normal_img = find_texture_image(mat, "txNormal", search_disk=True) if (mat.use_nodes and mat.node_tree) else None
                if normal_img:
                    norm_name = clean_texture_name(normal_img.name, force_dds=True)
                    kn5_mat.add_texture_mapping("txNormal", norm_name)
                    self.texture_map[norm_name] = normal_img
                else:
                    kn5_mat.add_texture_mapping("txNormal", "flat_nm.dds")
                    if "flat_nm.dds" not in self.texture_map:
                        self.texture_map["flat_nm.dds"] = create_flat_normal_map_dds(4, 4)

            if "txMask" not in existing_slots:
                mask_img = find_texture_image(mat, "txMask", search_disk=True) if (mat.use_nodes and mat.node_tree) else None
                if mask_img:
                    mask_name = clean_texture_name(mask_img.name, force_dds=True)
                    kn5_mat.add_texture_mapping("txMask", mask_name)
                    self.texture_map[mask_name] = mask_img
                else:
                    kn5_mat.add_texture_mapping("txMask", "default_mask.dds")
                    if "default_mask.dds" not in self.texture_map:
                        self.texture_map["default_mask.dds"] = create_solid_color_dds(255, 255, 255, 255, 4, 4)

        return kn5_mat

    def _process_textures(self) -> List[KN5Texture]:
        """Encodes textures into KN5 format (embedded DDS or filename-only)."""
        tex_mode = self.options.get("texture_mode", "EMBEDDED_DDS")
        result: List[KN5Texture] = []

        for tex_name, image in self.texture_map.items():
            if tex_mode == "EXTERNAL":
                # External texture reference: empty data payload
                result.append(KN5Texture(name=tex_name, data=b"", active=1))
                continue

            # Embedded texture
            tex_bytes = self._extract_image_bytes(image)
            result.append(KN5Texture(name=tex_name, data=tex_bytes, active=1))

        return result

    def _extract_image_bytes(self, image) -> bytes:
        """Extracts or converts image to DDS byte buffer."""
        # 0. If pre-generated DDS byte payload
        if isinstance(image, (bytes, bytearray)):
            return bytes(image)

        if not image:
            return build_dds_header_uncompressed_bgra(1, 1) + b"\xFF\xFF\xFF\xFF"

        # 1. If original file on disk is already DDS, read directly
        if getattr(image, "filepath", None):
            clean_path = bpy.path.abspath(image.filepath)
            if os.path.exists(clean_path) and clean_path.lower().endswith(".dds"):
                try:
                    with open(clean_path, "rb") as f:
                        data = f.read()
                        if is_dds_bytes(data):
                            return data
                except Exception as e:
                    self.warnings.append(f"Could not read DDS file from disk: {e}")

        # 2. If packed file exists and is DDS
        if getattr(image, "packed_file", None) and is_dds_bytes(image.packed_file.data):
            return image.packed_file.data

        # 3. Convert image pixels directly to 32-bit BGRA DDS
        if hasattr(image, "size") and image.size[0] > 0 and image.size[1] > 0:
            try:
                return image_to_bgra_dds(image, fallback_alpha=0.35)
            except Exception as e:
                self.warnings.append(f"Failed to convert image '{image.name}' to DDS: {e}")

        # 4. Fallback 1x1 white dummy texture
        return build_dds_header_uncompressed_bgra(1, 1) + b"\xFF\xFF\xFF\xFF"

    def _export_object_recursive(self, obj: bpy.types.Object, allowed_objects: List[bpy.types.Object], car_root_obj: Optional[bpy.types.Object] = None, wheel_dummy_objs: Optional[Set[bpy.types.Object]] = None) -> Optional[KN5Node]:
        """Recursively exports an object and its children into KN5 nodes."""
        if obj.name.startswith("__") or obj == car_root_obj:
            return None

        # Sanitize known typos and duplicate suffixes for standard AC empties
        clean_name = "WHEEL_RR" if obj.name.upper() == "WHELL_RR" else obj.name
        if obj.type == 'EMPTY':
            standard_dummies = [
                "WHEEL_LF", "WHEEL_RF", "WHEEL_LR", "WHEEL_RR",
                "SUSP_LF", "SUSP_RF", "SUSP_LR", "SUSP_RR",
                "COCKPIT_HR", "STEER_HR", "DRIVER_POS", "DRIVER_EYES", "CAR_ROOT"
            ]
            for sd in standard_dummies:
                if obj.name.upper() == sd or obj.name.upper().startswith(sd + "."):
                    clean_name = sd
                    break

        # Determine effective local transform (accounting for parent or virtual parenting)
        if obj in self.virtual_parent:
            p_dummy = self.virtual_parent[obj]
            local_mat = p_dummy.matrix_world.inverted() @ obj.matrix_world
        elif wheel_dummy_objs and obj in wheel_dummy_objs:
            # Wheel dummies are direct children of root_node in AC (DirectX origin)
            if car_root_obj and obj.parent == car_root_obj:
                local_mat = car_root_obj.matrix_world.inverted() @ obj.matrix_world
            elif obj.parent and obj.parent in allowed_objects:
                local_mat = obj.matrix_world
            else:
                local_mat = obj.matrix_world
        elif obj.parent and obj.parent in allowed_objects and obj.parent != car_root_obj:
            local_mat = obj.parent.matrix_world.inverted() @ obj.matrix_world
        elif car_root_obj and obj.parent == car_root_obj:
            local_mat = car_root_obj.matrix_world.inverted() @ obj.matrix_world
        else:
            local_mat = obj.matrix_world

        # Filter valid children: exclude ones adopted elsewhere, exclude dissolved root and wheel dummies
        valid_children = [
            c for c in obj.children
            if c in allowed_objects
            and not c.name.startswith("__")
            and c not in self.virtual_parent
            and c != car_root_obj
            and (not wheel_dummy_objs or c not in wheel_dummy_objs)
        ]
        if obj in self.virtual_children:
            for vc in self.virtual_children[obj]:
                if vc in allowed_objects and vc not in valid_children and vc != car_root_obj and (not wheel_dummy_objs or vc not in wheel_dummy_objs):
                    valid_children.append(vc)

        if obj.type == 'EMPTY':
            dummy = KN5Node(name=clean_name, node_type=NODE_TYPE_DUMMY)
            dummy.transform = convert_matrix(local_mat)
            for child in valid_children:
                c_node = self._export_object_recursive(child, allowed_objects, car_root_obj, wheel_dummy_objs)
                if c_node:
                    dummy.add_child(c_node)
            return dummy

        elif obj.type == 'MESH':
            loc, rot, scale = local_mat.decompose()
            has_non_unit_scale = any(abs(s - 1.0) > 1e-4 for s in scale)
            has_transform = (loc.length_squared > 1e-6) or (rot.angle > 1e-4) or has_non_unit_scale

            # Always bake scale into vertex coordinates so that meshes match real-world AC scale
            submeshes = self._process_mesh_geometry(obj, scale_vec=scale if has_non_unit_scale else None)

            needs_wrapper = bool(valid_children) or len(submeshes) > 1 or has_transform

            if needs_wrapper:
                parent_dummy = KN5Node(name=clean_name, node_type=NODE_TYPE_DUMMY)
                parent_dummy.transform = convert_matrix(local_mat, force_unit_scale=True)

                # Add submeshes as children
                for idx, sm in enumerate(submeshes):
                    sm_name = f"{clean_name}_SUB{idx}" if len(submeshes) > 1 else clean_name
                    mesh_node = self._create_kn5_mesh_node(obj, sm_name, sm)
                    parent_dummy.add_child(mesh_node)

                # Add real & virtual children
                for child in valid_children:
                    c_node = self._export_object_recursive(child, allowed_objects, car_root_obj, wheel_dummy_objs)
                    if c_node:
                        parent_dummy.add_child(c_node)

                return parent_dummy
            else:
                # Single submesh, no children, identity transform
                if submeshes:
                    single_mesh = self._create_kn5_mesh_node(obj, clean_name, submeshes[0])
                    return single_mesh
                else:
                    empty_dummy = KN5Node(name=clean_name, node_type=NODE_TYPE_DUMMY)
                    empty_dummy.transform = convert_matrix(local_mat, force_unit_scale=True)
                    return empty_dummy

        return None

    def _create_kn5_mesh_node(self, obj: bpy.types.Object, name: str, sm: SubmeshData) -> KN5Mesh:
        mesh = KN5Mesh(name=name)
        mesh.material_id = sm.material_id
        mesh.vertices = sm.vertices
        mesh.indices = sm.indices
        mesh.calculate_bounding_sphere()

        ac = getattr(obj, "assettoCorsa", None)
        if ac:
            mesh.cast_shadows = ac.cast_shadows
            mesh.visible = ac.visible
            mesh.transparent = ac.transparent
            mesh.renderable = ac.renderable
            mesh.layer = ac.layer
            mesh.lod_in = ac.lod_in
            mesh.lod_out = ac.lod_out

        is_mat_transparent = False
        if sm.material_id < len(self.materials):
            mat = self.materials[sm.material_id]
            if mat.blend_mode == 1 or mat.shader in ("ksWindscreen", "ksPerPixelAlpha"):
                is_mat_transparent = True

        # When an object has multiple material slots (e.g. car door with body paint + window glass),
        # only submeshes that actually use a transparent material should be transparent!
        # Opaque submeshes (metal door skin) must remain opaque.
        name_upper = obj.name.upper()
        is_opaque_wheel_or_body = any(name_upper.startswith(p) for p in ("RIM_", "TYRE_", "TIRE_", "WHEEL_", "DISC_", "CALIPER_", "BODY", "CHASSIS"))

        if is_opaque_wheel_or_body:
            mesh.transparent = False
            mesh.cast_shadows = True
        elif len(obj.material_slots) > 1:
            mesh.transparent = is_mat_transparent
            mesh.cast_shadows = False if mesh.transparent else (ac.cast_shadows if ac else True)
        else:
            mesh.transparent = is_mat_transparent or (ac.transparent if ac else False)
            mesh.cast_shadows = False if mesh.transparent else (ac.cast_shadows if ac else True)

        self.total_vertices += len(mesh.vertices)
        self.total_triangles += len(mesh.indices) // 3
        self.total_meshes += 1
        return mesh

    def _process_mesh_geometry(self, obj: bpy.types.Object, scale_vec: Optional[mathutils.Vector] = None) -> List[SubmeshData]:
        """Triangulates, calculates tangents, transforms coordinates, and splits by material."""
        apply_modifiers = self.options.get("apply_modifiers", True)

        # Evaluate mesh
        if apply_modifiers:
            depsgraph = self.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(depsgraph)
            mesh = eval_obj.to_mesh()
        else:
            mesh = obj.to_mesh()

        if not mesh or not mesh.polygons:
            if mesh:
                obj.to_mesh_clear()
            return []

        # Triangulate via bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()

        # Ensure custom split normals are evaluated (Blender <= 4.0 backwards compatibility)
        if hasattr(mesh, "calc_normals_split"):
            try:
                mesh.calc_normals_split()
            except Exception:
                pass

        # Ensure tangents
        mesh.calc_loop_triangles()
        has_uv = bool(mesh.uv_layers)
        if has_uv:
            try:
                mesh.calc_tangents()
            except Exception as e:
                self.warnings.append(f"Tangents calculation note on '{obj.name}': {e}")

        uv_data = mesh.uv_layers.active.data if has_uv else None
        mesh_verts = mesh.vertices
        mesh_loops = mesh.loops
        mesh_tris = mesh.loop_triangles

        # Group triangles by material slot
        tri_by_mat: Dict[int, list] = {}
        for tri in mesh_tris:
            m_idx = tri.material_index
            if m_idx not in tri_by_mat:
                tri_by_mat[m_idx] = []
            tri_by_mat[m_idx].append(tri)

        submeshes: List[SubmeshData] = []

        # Prepare scale vectors if non-unit scale needs baking
        has_scale = scale_vec is not None
        is_reflected = False
        if has_scale:
            det = scale_vec.x * scale_vec.y * scale_vec.z
            is_reflected = (det < 0.0)
            inv_scale = mathutils.Vector((
                1.0 / scale_vec.x if abs(scale_vec.x) > 1e-6 else 1.0,
                1.0 / scale_vec.y if abs(scale_vec.y) > 1e-6 else 1.0,
                1.0 / scale_vec.z if abs(scale_vec.z) > 1e-6 else 1.0,
            ))

        for m_idx, tris in tri_by_mat.items():
            # Resolve material ID
            mat_name = "DefaultMaterial"
            if m_idx < len(obj.material_slots) and obj.material_slots[m_idx].material:
                mat_name = obj.material_slots[m_idx].material.name
            target_mat_id = self.material_map.get(mat_name, 0)

            # Build indexed vertices for this material group
            vert_lookup: Dict[tuple, int] = {}
            current_sm = SubmeshData(target_mat_id)

            for tri in tris:
                # If we approach 65,530 vertices, split into next submesh
                if len(current_sm.vertices) > 65530:
                    submeshes.append(current_sm)
                    current_sm = SubmeshData(target_mat_id)
                    vert_lookup.clear()

                tri_indices = []
                for loop_idx in tri.loops:
                    loop = mesh_loops[loop_idx]
                    raw_pos = mesh_verts[loop.vertex_index].co
                    raw_norm = loop.normal
                    if raw_norm.length_squared < 1e-6:
                        raw_norm = mesh_verts[loop.vertex_index].normal
                    raw_tangent = getattr(loop, "tangent", mathutils.Vector((1.0, 0.0, 0.0)))

                    if has_scale:
                        raw_pos = mathutils.Vector((
                            raw_pos.x * scale_vec.x,
                            raw_pos.y * scale_vec.y,
                            raw_pos.z * scale_vec.z
                        ))
                        raw_norm = mathutils.Vector((
                            raw_norm.x * inv_scale.x,
                            raw_norm.y * inv_scale.y,
                            raw_norm.z * inv_scale.z
                        )).normalized()
                        raw_tangent = mathutils.Vector((
                            raw_tangent.x * scale_vec.x,
                            raw_tangent.y * scale_vec.y,
                            raw_tangent.z * scale_vec.z
                        )).normalized()

                    c_pos = convert_vector3(raw_pos)
                    c_norm = convert_vector3(raw_norm)
                    c_tan = convert_vector3(raw_tangent)

                    if uv_data:
                        raw_uv = uv_data[loop_idx].uv
                        # DirectX UV: V is inverted (1.0 - V)
                        c_uv = (float(raw_uv[0]), float(1.0 - raw_uv[1]))
                    else:
                        c_uv = (0.0, 0.0)

                    # Deduplication key rounded to 5 decimal places
                    key = (
                        round(c_pos[0], 5), round(c_pos[1], 5), round(c_pos[2], 5),
                        round(c_norm[0], 4), round(c_norm[1], 4), round(c_norm[2], 4),
                        round(c_uv[0], 5), round(c_uv[1], 5),
                    )

                    if key in vert_lookup:
                        idx = vert_lookup[key]
                    else:
                        idx = len(current_sm.vertices)
                        vert_lookup[key] = idx
                        current_sm.vertices.append(KN5Vertex(c_pos, c_norm, c_uv, c_tan))

                    tri_indices.append(idx)

                # Coordinate swap (Y to -Z) reflects handedness, so (1, 2, 0) maintains CW winding.
                # Under reflection (negative scale determinant), winding must be inverted (0, 2, 1)
                # to prevent DirectX backface culling from inverting front/back faces.
                if is_reflected:
                    current_sm.indices.extend((tri_indices[0], tri_indices[2], tri_indices[1]))
                else:
                    current_sm.indices.extend((tri_indices[1], tri_indices[2], tri_indices[0]))

            if current_sm.vertices:

                submeshes.append(current_sm)

        obj.to_mesh_clear()
        return submeshes


class ExportKN5(bpy.types.Operator, ExportHelper):
    """Export scene or selection to Assetto Corsa (.kn5) format."""
    bl_idname = "export_scene.kn5"
    bl_label = "Export KN5"
    bl_description = "Export active scene or selection to Assetto Corsa KN5 binary file"

    filename_ext = ".kn5"
    filter_glob: StringProperty(default="*.kn5", options={'HIDDEN'})

    version: EnumProperty(
        name="KN5 Version",
        items=[
            ("5", "Version 5 (Universal)", "Standard non-DLC version supported by all AC versions & Content Manager"),
            ("6", "Version 6", "Version 6 format with DLC tag header"),
        ],
        default="5"
    )

    texture_mode: EnumProperty(
        name="Textures",
        items=[
            ("EMBEDDED_DDS", "Embedded DDS", "Pack textures as embedded DDS inside the KN5 container"),
            ("EXTERNAL", "External References", "Reference texture files externally (smaller KN5, standard for tracks)"),
        ],
        default="EMBEDDED_DDS"
    )

    selection_only: BoolProperty(
        name="Selected Objects Only",
        description="Export only selected objects",
        default=False
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers to meshes during export",
        default=True
    )

    auto_detect_materials: BoolProperty(
        name="Auto-Detect Shaders",
        description="Automatically assigns AC shaders and transparency (Glass, Bulbs, Paint, Tyres) to unconfigured materials based on name",
        default=True
    )

    auto_fix_wheels: BoolProperty(
        name="Auto-Rig Wheels & Rims",
        description="Ensures rims, tires, and brake discs are properly parented under WHEEL_XX dummies so they rotate and steer in Assetto Corsa",
        default=True
    )

    sync_skins: BoolProperty(
        name="Auto-Sync Skins",
        description="Automatically copies diffuse/AO textures into all car skin subfolders after export",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Export Settings", icon='SETTINGS')
        box.prop(self, "version")
        box.prop(self, "texture_mode")
        box.prop(self, "selection_only")
        box.prop(self, "apply_modifiers")
        box.prop(self, "auto_detect_materials")
        box.prop(self, "auto_fix_wheels")
        box.prop(self, "sync_skins")

    def execute(self, context):
        t0 = time.time()
        options = {
            "version": int(self.version),
            "texture_mode": self.texture_mode,
            "selection_only": self.selection_only,
            "apply_modifiers": self.apply_modifiers,
            "auto_detect_materials": self.auto_detect_materials,
            "auto_fix_wheels": self.auto_fix_wheels,
        }


        try:
            exporter = KN5Exporter(context, self.filepath, options)
            model = exporter.export()
            model.to_file(self.filepath)

            # Auto-sync textures to skin folders if requested
            if self.sync_skins:
                try:
                    car_dir = os.path.dirname(os.path.abspath(self.filepath))
                    count, skins = sync_textures_to_car_skins(car_dir)
                    if count > 0:
                        exporter.warnings.append(f"Auto-synced textures to {len(skins)} skin folder(s).")
                except Exception as e:
                    print(f"Skin auto-sync note: {e}")

            dt = time.time() - t0
            file_size_mb = os.path.getsize(self.filepath) / (1024 * 1024)

            summary = (
                f"Export Complete in {dt:.2f}s!\n"
                f"Meshes: {exporter.total_meshes} | "
                f"Vertices: {exporter.total_vertices:,} | "
                f"Triangles: {exporter.total_triangles:,} | "
                f"Materials: {len(model.materials)} | "
                f"Textures: {len(model.textures)} | Warnings: {len(exporter.warnings)} | "
                f"File: {file_size_mb:.2f} MB"
            )
            print(summary)
            if exporter.warnings:
                print("=== KN5 Export Warnings ===\n" + "\n".join(exporter.warnings))
                for warning in exporter.warnings[:5]:
                    self.report({'WARNING'}, warning[:240])
                if len(exporter.warnings) > 5:
                    self.report({'WARNING'}, f"... and {len(exporter.warnings) - 5} more warning(s).")
                self.report({'WARNING'}, f"Export complete with {len(exporter.warnings)} warning(s). See System Console.")
            else:
                self.report({'INFO'}, summary)
            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"KN5 Export Failed: {e}")
            return {'CANCELLED'}


def find_lod_collections(scene) -> Dict[str, bpy.types.Collection]:
    """Finds LOD collections matching standard Assetto Corsa naming conventions."""
    patterns = {
        "LOD_A": r"(?:^|[_\s-])(?:lod[_\s-]?0|lod[_\s-]?a|main|body[_\s-]?lod0)(?:$|[_\s-])",
        "LOD_B": r"(?:^|[_\s-])(?:lod[_\s-]?1|lod[_\s-]?b|body[_\s-]?lod1)(?:$|[_\s-])",
        "LOD_C": r"(?:^|[_\s-])(?:lod[_\s-]?2|lod[_\s-]?c|body[_\s-]?lod2)(?:$|[_\s-])",
        "LOD_D": r"(?:^|[_\s-])(?:lod[_\s-]?3|lod[_\s-]?d|body[_\s-]?lod3)(?:$|[_\s-])",
        "COLLIDER": r"(?:^|[_\s-])(?:collider|colliders|collision)(?:$|[_\s-])",
    }
    found = {}
    for col in scene.collection.children:
        name_lower = col.name.lower()
        for role, pattern in patterns.items():
            if re.search(pattern, name_lower, flags=re.IGNORECASE):
                if role not in found:
                    found[role] = col
    return found


class KN5_OT_BatchExportLODs(bpy.types.Operator, ExportHelper):
    """Batch export car LODs (LOD_A, LOD_B, LOD_C, LOD_D, COLLIDER) to separate KN5 files."""
    bl_idname = "export_scene.kn5_batch_lods"
    bl_label = "Batch Export LODs (.kn5)"
    bl_description = "Export LOD collections to standard Assetto Corsa KN5 files in target folder"

    filename_ext = ".kn5"
    filter_glob: StringProperty(default="*.kn5", options={'HIDDEN'})

    version: EnumProperty(
        name="KN5 Version",
        items=[
            ("5", "Version 5 (Universal)", "Standard non-DLC version supported by all AC versions & Content Manager"),
            ("6", "Version 6", "Version 6 format with DLC tag header"),
        ],
        default="5"
    )

    texture_mode: EnumProperty(
        name="Textures",
        items=[
            ("EMBEDDED_DDS", "Embedded DDS", "Pack textures as embedded DDS inside the KN5 container"),
            ("EXTERNAL", "External References", "Reference texture files externally (smaller KN5)"),
        ],
        default="EMBEDDED_DDS"
    )

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers to meshes during export",
        default=True
    )

    auto_detect_materials: BoolProperty(
        name="Auto-Detect Shaders",
        default=True
    )

    auto_fix_wheels: BoolProperty(
        name="Auto-Rig Wheels & Rims",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Batch LOD Settings", icon='SETTINGS')
        box.prop(self, "version")
        box.prop(self, "texture_mode")
        box.prop(self, "apply_modifiers")
        box.prop(self, "auto_detect_materials")
        box.prop(self, "auto_fix_wheels")

        lods = find_lod_collections(context.scene)
        box_lods = layout.box()
        box_lods.label(text="Detected LOD Collections:", icon='GROUP')
        if lods:
            for role, col in sorted(lods.items()):
                box_lods.label(text=f"• {role} -> '{col.name}'", icon='CHECKMARK')
        else:
            box_lods.label(text="No LOD collections found! Name collections LOD_A, LOD_B, etc.", icon='ERROR')

    def execute(self, context):
        base_dir = os.path.dirname(os.path.abspath(self.filepath))
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        clean_car_name = re.sub(r"_lod_[a-d]$", "", base_name, flags=re.IGNORECASE)

        lods = find_lod_collections(context.scene)
        if not lods:
            self.report({'ERROR'}, "No LOD collections detected in scene! Create collections like LOD_A, LOD_B, COLLIDER.")
            return {'CANCELLED'}

        exported = []
        errors = []

        mapping = {
            "LOD_A": f"{clean_car_name}.kn5",
            "LOD_B": f"{clean_car_name}_lod_b.kn5",
            "LOD_C": f"{clean_car_name}_lod_c.kn5",
            "LOD_D": f"{clean_car_name}_lod_d.kn5",
            "COLLIDER": "collider.kn5",
        }

        for role, col in lods.items():
            out_filename = mapping.get(role, f"{clean_car_name}_{role.lower()}.kn5")
            out_path = os.path.join(base_dir, out_filename)

            options = {
                "version": int(self.version),
                "texture_mode": self.texture_mode,
                "apply_modifiers": self.apply_modifiers,
                "auto_detect_materials": self.auto_detect_materials,
                "auto_fix_wheels": self.auto_fix_wheels,
                "target_collection": col,
            }

            try:
                exporter = KN5Exporter(context, out_path, options)
                model = exporter.export()
                model.to_file(out_path)
                size_mb = os.path.getsize(out_path) / (1024 * 1024)
                exported.append(f"{out_filename} ({size_mb:.2f} MB, {exporter.total_meshes} meshes)")
            except Exception as e:
                errors.append(f"{out_filename}: {e}")

        if errors:
            self.report({'WARNING'}, f"Batch exported {len(exported)} file(s), {len(errors)} error(s). See console.")
            for err in errors:
                print(f"[Batch LOD Error] {err}")
        else:
            self.report({'INFO'}, f"Batch Export Complete: {', '.join(exported)}")

        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(ExportKN5.bl_idname, text="Assetto Corsa (.kn5)")
    self.layout.operator(KN5_OT_BatchExportLODs.bl_idname, text="Assetto Corsa Batch LODs (.kn5)")


REGISTER_CLASSES = (
    ExportKN5,
    KN5_OT_BatchExportLODs,
)


def register():
    for cls in REGISTER_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    except Exception:
        pass
    for cls in reversed(REGISTER_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

