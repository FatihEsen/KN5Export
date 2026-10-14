# Assetto Corsa KN5 Studio - Material & Shader System
# Handles AC shader parameters, property groups, presets, and Principled BSDF synchronization.

import bpy
import os
import re
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
try:
    from .constants import (
        MATERIAL_BLEND_MODES,
        MATERIAL_DEPTH_MODES,
        SHADER_TEXTURE_SLOTS,
        DEFAULT_SHADER_PROPERTIES,
        MATERIAL_PRESETS,
        match_material_preset,
        clean_texture_name,
    )
except (ImportError, ValueError):
    from constants import (
        MATERIAL_BLEND_MODES,
        MATERIAL_DEPTH_MODES,
        SHADER_TEXTURE_SLOTS,
        DEFAULT_SHADER_PROPERTIES,
        MATERIAL_PRESETS,
        match_material_preset,
        clean_texture_name,
    )


class KN5_ShaderPropertyItem(bpy.types.PropertyGroup):
    """Stores one uniform shader property (e.g. ksDiffuse, fresnelC)."""
    name: StringProperty(name="Property Name", default="ksDiffuse")
    valueA: FloatProperty(name="Value A", default=0.0)
    valueB: FloatVectorProperty(name="Value B", size=2, default=(0.0, 0.0))
    valueC: FloatVectorProperty(name="Value C", size=3, default=(0.0, 0.0, 0.0))
    valueD: FloatVectorProperty(name="Value D", size=4, default=(0.0, 0.0, 0.0, 0.0))


def clean_texture_name(name: str, force_dds: bool = False) -> str:
    """
    Cleans up a texture filename:
    1. Removes any directory paths (returns basename only).
    2. Strips Blender duplicate numeric suffixes (e.g. .001, .002).
    3. Prevents duplicate extensions like .dds.dds.
    4. If force_dds is True, ensures the extension is .dds.
    """
    if not name:
        return ""
    name = os.path.basename(name.replace("\\", "/")).strip()
    # Strip Blender duplicate suffix e.g. .001, .002 (either at end or before extension)
    name = re.sub(r'\.\d{3,}(?=\.[a-zA-Z0-9]+$|$)', '', name)
    while name.lower().endswith(".dds.dds"):
        name = name[:-4]
    if force_dds:
        root, _ = os.path.splitext(name)
        name = root + ".dds"
    return name


class KN5_TextureSlotItem(bpy.types.PropertyGroup):
    """Stores a texture slot binding (e.g. txDiffuse -> my_texture.dds)."""
    slot_name: StringProperty(name="Slot Name", default="txDiffuse")
    image: PointerProperty(name="Image", type=bpy.types.Image)
    override_filename: StringProperty(name="Override Filename", default="")

    @property
    def effective_filename(self) -> str:
        raw = ""
        if self.override_filename.strip():
            raw = self.override_filename.strip()
        elif self.image:
            raw = self.image.name
        if not raw:
            return ""
        return clean_texture_name(raw, force_dds=False)


def _get_preset_items(self, context):
    items = [("NONE", "Select Preset...", "Choose a pre-configured material preset")]
    for key, data in MATERIAL_PRESETS.items():
        items.append((key, data["label"], f"Apply {data['label']} shader and properties"))
    return items


class KN5_MaterialProperties(bpy.types.PropertyGroup):
    """Assetto Corsa specific material properties attached to bpy.types.Material."""
    shader_name: StringProperty(
        name="Shader",
        default="ksPerPixel",
        description="Assetto Corsa shader name"
    )
    blend_mode: EnumProperty(
        name="Blend Mode",
        items=MATERIAL_BLEND_MODES,
        default="0",
        description="Surface transparency blend mode"
    )
    alpha_tested: BoolProperty(
        name="Alpha Tested",
        default=False,
        description="Enable 1-bit alpha threshold testing"
    )
    depth_mode: EnumProperty(
        name="Depth Mode",
        items=MATERIAL_DEPTH_MODES,
        default="0",
        description="Depth testing and writing mode"
    )
    shader_properties: CollectionProperty(type=KN5_ShaderPropertyItem)
    shader_properties_active: IntProperty(name="Active Property", default=0)

    texture_slots: CollectionProperty(type=KN5_TextureSlotItem)
    texture_slots_active: IntProperty(name="Active Texture Slot", default=0)

    preset_selector: EnumProperty(
        name="Preset",
        items=_get_preset_items,
        description="Apply standard Assetto Corsa material preset"
    )

    def get_property(self, name: str) -> float:
        for prop in self.shader_properties:
            if prop.name == name:
                return prop.valueA
        return DEFAULT_SHADER_PROPERTIES.get(name, 0.0)

    def set_property(self, name: str, value: float):
        for prop in self.shader_properties:
            if prop.name == name:
                prop.valueA = float(value)
                return
        item = self.shader_properties.add()
        item.name = name
        item.valueA = float(value)

    def ensure_default_slots_for_shader(self, shader_name: str):
        """Ensures the appropriate texture slot entries exist for the given shader."""
        expected_slots = SHADER_TEXTURE_SLOTS.get(shader_name, ["txDiffuse"])
        existing_slot_names = [s.slot_name for s in self.texture_slots]
        for slot in expected_slots:
            if slot not in existing_slot_names:
                item = self.texture_slots.add()
                item.slot_name = slot


def _texture_basename(filename: str) -> str:
    return clean_texture_name(filename or "", force_dds=False).casefold()


def _image_is_available(image: bpy.types.Image) -> bool:
    """Whether an image can provide pixels or a source file to the exporter."""
    if not image:
        return False
    if image.source != 'FILE' or image.packed_file:
        return True
    try:
        filepath = bpy.path.abspath(image.filepath) if image.filepath else ""
    except (AttributeError, RuntimeError):
        filepath = ""
    return bool(filepath and os.path.isfile(filepath))


def _connected_texture_image(material: bpy.types.Material, slot_name: str,
                             preferred_filename: str = ""):
    """Find an image node that matches a filename or feeds the requested shader input."""
    if not material.use_nodes or not material.node_tree:
        return None

    image_nodes = [node for node in material.node_tree.nodes
                   if node.type == 'TEX_IMAGE' and node.image]
    wanted = _texture_basename(preferred_filename)
    for node in image_nodes:
        names = {_texture_basename(node.image.name),
                 _texture_basename(node.image.filepath)}
        if wanted and wanted in names:
            return node.image

    for node in image_nodes:
        for output in node.outputs:
            for link in output.links:
                if (slot_name == 'txDiffuse'
                        and link.to_node.type == 'BSDF_PRINCIPLED'
                        and link.to_socket.name == 'Base Color'):
                    return node.image
                if slot_name == 'txNormal' and link.to_node.type == 'NORMAL_MAP':
                    return node.image

    if slot_name == 'txDiffuse' and len(image_nodes) == 1:
        return image_nodes[0].image
    return None


def find_texture_image(material: bpy.types.Material, slot_name: str,
                       preferred_filename: str = "", search_disk: bool = False):
    """Resolve a texture slot from its Blender image, nodes, or nearby texture files."""
    assigned_image = None
    ac = getattr(material, "assettoCorsa", None)
    if ac:
        for slot in ac.texture_slots:
            if slot.slot_name == slot_name:
                if slot.image:
                    assigned_image = slot.image
                    if not search_disk or _image_is_available(slot.image):
                        return slot.image
                if not preferred_filename:
                    preferred_filename = slot.effective_filename

    wanted = _texture_basename(preferred_filename)
    matching_images = []
    if wanted:
        for image in bpy.data.images:
            if wanted in {_texture_basename(image.name),
                          _texture_basename(image.filepath)}:
                matching_images.append(image)
        if matching_images:
            if not search_disk:
                return matching_images[0]
            available_matches = [image for image in matching_images
                                 if _image_is_available(image)]
            if available_matches:
                return available_matches[0]

    if search_disk and preferred_filename:
        requested_path = bpy.path.abspath(preferred_filename)
        candidates = [requested_path] if os.path.isfile(requested_path) else []
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""
        roots = []
        if blend_dir:
            roots.extend((blend_dir, os.path.join(blend_dir, "texture"),
                          os.path.join(os.path.dirname(blend_dir), "texture")))
        roots = list(dict.fromkeys(os.path.abspath(root) for root in roots if root))

        requested_base = os.path.basename(preferred_filename.replace("\\", "/"))
        for root in roots:
            if not os.path.isdir(root):
                continue
            try:
                entries = [entry for entry in os.scandir(root) if entry.is_file()]
            except OSError:
                continue
            exact = [entry.path for entry in entries
                     if entry.name.casefold() == requested_base.casefold()]
            candidates.extend(exact)

        for filepath in dict.fromkeys(candidates):
            try:
                return bpy.data.images.load(filepath, check_existing=True)
            except (OSError, RuntimeError):
                continue

    node_image = _connected_texture_image(material, slot_name, preferred_filename)
    for image in [node_image, *matching_images, assigned_image]:
        if image and (not search_disk or _image_is_available(image)):
            return image
    return None


def audit_texture_bindings(objects, texture_mode='EMBEDDED_DDS'):
    """Return actionable missing-image and missing-file warnings for exported materials."""
    issues = []
    materials = set()
    for obj in objects:
        if obj.type == 'MESH':
            materials.update(slot.material for slot in obj.material_slots if slot.material)
            if not obj.data.uv_layers:
                for material_slot in obj.material_slots:
                    material = material_slot.material
                    ac = getattr(material, "assettoCorsa", None) if material else None
                    if ac and any(slot.slot_name == 'txDiffuse'
                                  and (slot.effective_filename or slot.image)
                                  for slot in ac.texture_slots):
                        issues.append(
                            f"{obj.name}: diffuse texture is assigned but the mesh has no UV map."
                        )
                        break

    for material in sorted(materials, key=lambda item: item.name.casefold()):
        ac = getattr(material, "assettoCorsa", None)
        if not ac:
            node_image = _connected_texture_image(material, 'txDiffuse')
            if node_image and not _image_is_available(node_image):
                issues.append(
                    f"{material.name} / txDiffuse: '{node_image.name}' has no linked or loaded image."
                )
            continue
        if not ac.texture_slots:
            node_image = _connected_texture_image(material, 'txDiffuse')
            if node_image and not _image_is_available(node_image):
                issues.append(
                    f"{material.name} / txDiffuse: '{node_image.name}' has no linked or loaded image."
                )
            elif node_image:
                issues.append(
                    f"{material.name}: Blender has a diffuse image node but no AC txDiffuse slot; use Repair Links."
                )
            continue
        for slot in ac.texture_slots:
            filename = slot.effective_filename
            image = find_texture_image(
                material, slot.slot_name, filename, search_disk=True)
            if not filename and image:
                filename = image.name
            if not filename and not image:
                continue
            if not image:
                issues.append(
                    f"{material.name} / {slot.slot_name}: '{filename}' has no linked or loaded image."
                )
                continue

            if texture_mode == 'EXTERNAL':
                filepath = bpy.path.abspath(image.filepath) if image.filepath else ""
                if not filepath or not os.path.isfile(filepath):
                    issues.append(
                        f"{material.name} / {slot.slot_name}: external image file for '{image.name}' is unavailable."
                    )
    return issues


def sync_material_nodes(mat: bpy.types.Material):
    """Configures Blender Principled BSDF node tree to visually match AC shader & preset in viewport."""
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    ac = mat.assettoCorsa

    # Find or create Principled BSDF
    bsdf = None
    for n in nodes:
        if n.type == 'BSDF_PRINCIPLED':
            bsdf = n
            break
    if not bsdf:
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (200, 300)

    # Find or create Material Output
    output = None
    for n in nodes:
        if n.type == 'OUTPUT_MATERIAL':
            output = n
            break
    if not output:
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (600, 300)

    if not any(link.to_node == output for link in links):
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    preset_key = getattr(ac, "preset_selector", "NONE")
    shader_name = ac.shader_name or ""

    # Transparency / Blend mode handling
    is_transparent = (
        ac.blend_mode == "1"
        or "Alpha" in shader_name
        or "Windscreen" in shader_name
        or preset_key in ("GLASS_CLEAR", "WINDSCREEN", "LIGHT_EMISSIVE_GL")
    )
    is_cutout = ac.blend_mode == "2" or ac.alpha_tested or "AT" in shader_name

    if is_transparent:
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'NONE'
        if hasattr(mat, "surface_render_method"):
            try:
                mat.surface_render_method = 'DITHERED'
            except Exception:
                pass
    elif is_cutout:
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'CLIP'
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = 'CLIP'
    else:
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'OPAQUE'

    # Preset-specific visual tweaks for real-time viewport feedback
    if preset_key in ("GLASS_CLEAR", "WINDSCREEN") or "Windscreen" in shader_name:
        # Glass: transparent, low roughness, reflective
        trans_socket = bsdf.inputs.get("Transmission Weight") or bsdf.inputs.get("Transmission")
        if trans_socket:
            trans_socket.default_value = 0.88
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.02
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 0.30
        if "IOR" in bsdf.inputs:
            bsdf.inputs["IOR"].default_value = 1.52
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 1.0, 1.0)

    elif preset_key == "LIGHT_EMISSIVE_GL" or shader_name == "GL":
        # Bulbs, headlights, dash lights, warning lights
        emiss_color = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emiss_color:
            emiss_color.default_value = (1.0, 0.95, 0.75, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = 5.0
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = 0.90

    elif preset_key == "CHROME":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 1.0
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.03
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)

    elif preset_key == "CAR_PAINT":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.15
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.12
        coat_socket = bsdf.inputs.get("Coat Weight") or bsdf.inputs.get("Clearcoat")
        if coat_socket:
            coat_socket.default_value = 1.0
        coat_rough = bsdf.inputs.get("Coat Roughness") or bsdf.inputs.get("Clearcoat Roughness")
        if coat_rough:
            coat_rough.default_value = 0.04

    elif preset_key == "TIRE_RUBBER" or shader_name == "ksTyres":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.85

    elif preset_key == "BRAKE_DISC" or shader_name == "ksBrakeDisc":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.85
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.35

    elif preset_key == "INTERIOR_MATTE":
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.70

    else:
        # Standard specular calculation
        exp = ac.get_property("ksSpecularEXP")
        if exp > 0 and "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = max(0.02, min(1.0, 1.0 - (exp / 250.0) ** 0.5))

    spec = ac.get_property("ksSpecular")
    spec_socket = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get("Specular")
    if spec_socket:
        spec_socket.default_value = min(1.0, max(0.0, spec))

    # Link textures
    for slot in ac.texture_slots:
        if slot.image:
            tex_node = None
            for n in nodes:
                if n.type == 'TEX_IMAGE' and n.image == slot.image:
                    tex_node = n
                    break
            if not tex_node:
                tex_node = nodes.new(type='ShaderNodeTexImage')
                tex_node.image = slot.image

            if slot.slot_name == "txDiffuse":
                tex_node.location = (-400, 300)
                links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                if is_transparent or is_cutout:
                    if "Alpha" in bsdf.inputs and "Alpha" in tex_node.outputs:
                        links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            elif slot.slot_name == "txNormal":
                tex_node.location = (-400, -100)
                normal_map_node = None
                for n in nodes:
                    if n.type == 'NORMAL_MAP':
                        normal_map_node = n
                        break
                if not normal_map_node:
                    normal_map_node = nodes.new(type='ShaderNodeNormalMap')
                    normal_map_node.location = (-100, -100)
                links.new(tex_node.outputs['Color'], normal_map_node.inputs['Color'])
                if "Normal" in bsdf.inputs:
                    links.new(normal_map_node.outputs['Normal'], bsdf.inputs['Normal'])


def apply_preset_to_material(mat: bpy.types.Material, preset_key: str, sync_nodes: bool = True) -> bool:
    """Configures AC shader, flags, uniform properties, and slots from a preset."""
    if preset_key not in MATERIAL_PRESETS:
        return False

    preset = MATERIAL_PRESETS[preset_key]
    ac = mat.assettoCorsa
    ac.preset_selector = preset_key
    ac.shader_name = preset["shader"]
    ac.blend_mode = str(preset["blend_mode"])
    ac.alpha_tested = preset["alpha_tested"]
    ac.depth_mode = str(preset["depth_mode"])

    # Shader properties
    for prop_name, prop_val in preset["props"].items():
        ac.set_property(prop_name, prop_val)

    # Texture slots
    for slot in preset.get("slots", ["txDiffuse"]):
        if slot not in [s.slot_name for s in ac.texture_slots]:
            s = ac.texture_slots.add()
            s.slot_name = slot

    if sync_nodes:
        sync_material_nodes(mat)

    return True


class KN5_OT_ApplyMaterialPreset(bpy.types.Operator):
    """Applies the selected Assetto Corsa material preset."""
    bl_idname = "kn5.apply_material_preset"
    bl_label = "Apply Preset"
    bl_description = "Apply the chosen shader preset and parameters to this material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def execute(self, context):
        mat = context.material
        ac = mat.assettoCorsa
        preset_key = ac.preset_selector
        if preset_key == "NONE" or preset_key not in MATERIAL_PRESETS:
            self.report({'WARNING'}, "Please select a valid preset from the list.")
            return {'CANCELLED'}

        apply_preset_to_material(mat, preset_key, sync_nodes=True)
        self.report({'INFO'}, f"Applied preset '{MATERIAL_PRESETS[preset_key]['label']}' to '{mat.name}'.")
        return {'FINISHED'}


class KN5_OT_SyncToNodes(bpy.types.Operator):
    """Generates / updates Blender shader nodes to reflect AC shader parameters."""
    bl_idname = "kn5.sync_to_nodes"
    bl_label = "Sync to Blender Nodes"
    bl_description = "Configure Blender Principled BSDF nodes to match AC shader parameters for viewport preview"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def execute(self, context):
        sync_material_nodes(context.material)
        self.report({'INFO'}, f"Synced nodes for '{context.material.name}'.")
        return {'FINISHED'}


class KN5_OT_AutoDetectMaterial(bpy.types.Operator):
    """Auto-detects and configures shader preset (Glass, Bulb, Paint, Chrome, etc.) for active material."""
    bl_idname = "kn5.auto_detect_material"
    bl_label = "Auto-Detect Preset"
    bl_description = "Automatically detects material type from name and configures shader, transparency, and properties"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.material is not None

    def execute(self, context):
        mat = context.material
        preset_key = match_material_preset(mat.name)
        if not preset_key:
            # Fall back to node texture detection
            bpy.ops.kn5.sync_from_nodes()
            self.report({'INFO'}, f"No specific preset matched for '{mat.name}'. Updated diffuse/normal textures.")
            return {'FINISHED'}

        apply_preset_to_material(mat, preset_key, sync_nodes=True)
        label = MATERIAL_PRESETS[preset_key]["label"]
        self.report({'INFO'}, f"Auto-detected '{mat.name}' as '{label}'.")
        return {'FINISHED'}


class KN5_OT_AutoDetectAllMaterials(bpy.types.Operator):
    """Batch auto-configures materials (Glass, Bulbs, Paint, Tyres, etc.) across the scene."""
    bl_idname = "kn5.auto_detect_all_materials"
    bl_label = "Auto-Configure Materials"
    bl_description = "Scans materials, automatically detects glass, bulbs, paint, chrome, etc. and sets shaders & transparency"
    bl_options = {'REGISTER', 'UNDO'}

    scope: EnumProperty(
        name="Scope",
        items=[
            ("SCENE", "Visible Scene Objects", "Process materials assigned to objects in current scene"),
            ("SELECTED", "Selected Objects Only", "Only process materials on selected objects"),
            ("ALL", "All Materials in Blend File", "Process all materials in blend file"),
        ],
        default="SCENE"
    )
    overwrite_existing: BoolProperty(
        name="Overwrite Custom Settings",
        default=False,
        description="Whether to overwrite materials that already have custom AC shaders configured"
    )

    def execute(self, context):
        if self.scope == "ALL":
            target_materials = list(bpy.data.materials)
        elif self.scope == "SELECTED":
            target_materials = []
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for slot in obj.material_slots:
                        if slot.material and slot.material not in target_materials:
                            target_materials.append(slot.material)
        else:
            target_materials = []
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    for slot in obj.material_slots:
                        if slot.material and slot.material not in target_materials:
                            target_materials.append(slot.material)

        configured = 0
        details = []

        for mat in target_materials:
            if not mat or mat.name.startswith("__"):
                continue

            ac = getattr(mat, "assettoCorsa", None)
            if not self.overwrite_existing and ac:
                # If already configured with non-default shader or blend mode, skip
                if ac.preset_selector != "NONE" or ac.blend_mode != "0" or (ac.shader_name and ac.shader_name != "ksPerPixel"):
                    continue

            preset_key = match_material_preset(mat.name)
            if preset_key:
                apply_preset_to_material(mat, preset_key, sync_nodes=True)
                configured += 1
                details.append(f"  • {mat.name} -> {MATERIAL_PRESETS[preset_key]['label']}")

        if details:
            print("=== Assetto Corsa Material Auto-Detection ===")
            print("\n".join(details))
            self.report({'INFO'}, f"Auto-configured {configured} material(s): Glass, Bulbs, Paint, Tyres, etc.")
        else:
            self.report({'INFO'}, "No matching unconfigured materials found.")

        return {'FINISHED'}



class KN5_OT_SyncFromNodes(bpy.types.Operator):
    """Inspects existing Blender material node tree and infers AC shader & textures."""
    bl_idname = "kn5.sync_from_nodes"
    bl_label = "Auto-Detect from Nodes"
    bl_description = "Automatically populate AC shader, diffuse, and normal textures from existing material nodes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.material.use_nodes

    def execute(self, context):
        mat = context.material
        nodes = mat.node_tree.nodes
        ac = mat.assettoCorsa

        diffuse_img = None
        normal_img = None

        # Look for Principled BSDF connections
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                for out in node.outputs:
                    for link in out.links:
                        to_node = link.to_node
                        to_socket = link.to_socket.name
                        if to_node.type == 'BSDF_PRINCIPLED' and to_socket == 'Base Color':
                            diffuse_img = node.image
                        elif to_node.type == 'NORMAL_MAP':
                            normal_img = node.image

        # If not connected directly, pick the first image textures
        if not diffuse_img:
            img_nodes = [n for n in nodes if n.type == 'TEX_IMAGE' and n.image]
            if img_nodes:
                diffuse_img = img_nodes[0].image
                if len(img_nodes) > 1:
                    normal_img = img_nodes[1].image

        # Assign slots
        if normal_img:
            ac.shader_name = "ksPerPixelNM"
        else:
            ac.shader_name = "ksPerPixel"

        ac.ensure_default_slots_for_shader(ac.shader_name)

        for slot in ac.texture_slots:
            if slot.slot_name == "txDiffuse" and diffuse_img:
                slot.image = diffuse_img
            elif slot.slot_name == "txNormal" and normal_img:
                slot.image = normal_img

        self.report({'INFO'}, f"Auto-detected textures: Diffuse='{diffuse_img.name if diffuse_img else 'None'}', Normal='{normal_img.name if normal_img else 'None'}'.")
        return {'FINISHED'}


class KN5_OT_AuditRepairTextures(bpy.types.Operator):
    """Audit Assetto Corsa texture links and optionally reconnect available images."""
    bl_idname = "kn5.audit_repair_textures"
    bl_label = "Audit / Repair Textures"
    bl_description = "Find missing texture images and reconnect matching files or Blender image nodes"
    bl_options = {'REGISTER', 'UNDO'}

    repair: BoolProperty(name="Repair Links", default=False, options={'HIDDEN'})
    current_material: BoolProperty(name="Current Material Only", default=False, options={'HIDDEN'})

    def execute(self, context):
        if self.current_material:
            materials = [context.material] if context.material else []
            material_objects = [obj for obj in context.scene.objects
                               if obj.type == 'MESH' and any(slot.material == context.material
                                                            for slot in obj.material_slots)]
        else:
            materials = sorted(
                {slot.material for obj in context.scene.objects if obj.type == 'MESH'
                 for slot in obj.material_slots if slot.material},
                key=lambda item: item.name.casefold(),
            )
            material_objects = [obj for obj in context.scene.objects if obj.type == 'MESH']

        if not materials:
            self.report({'WARNING'}, "No mesh materials found to inspect.")
            return {'CANCELLED'}

        repaired = 0
        problems = []
        for material in materials:
            ac = getattr(material, "assettoCorsa", None)
            if not ac:
                continue

            # Seed missing slot records from recognized image-node connections.
            if self.repair:
                for slot_name in ("txDiffuse", "txNormal"):
                    if any(slot.slot_name == slot_name for slot in ac.texture_slots):
                        continue
                    image = _connected_texture_image(material, slot_name)
                    if image:
                        slot = ac.texture_slots.add()
                        slot.slot_name = slot_name
                        slot.image = image
                        repaired += 1

            for slot in ac.texture_slots:
                filename = slot.effective_filename
                if self.repair and filename:
                    image = find_texture_image(
                        material, slot.slot_name, filename, search_disk=True)
                else:
                    image = slot.image or find_texture_image(
                        material, slot.slot_name, filename, search_disk=False)
                if image:
                    if slot.image != image:
                        slot.image = image
                        if filename and not slot.override_filename:
                            slot.override_filename = filename
                        repaired += 1
                    continue
                if filename:
                    problems.append(
                        f"{material.name} / {slot.slot_name}: image not found for '{filename}'."
                    )

        # Report UV gaps only where a diffuse map is actually configured.
        for obj in material_objects:
            if not obj.data.uv_layers:
                for slot in obj.material_slots:
                    material = slot.material
                    ac = getattr(material, "assettoCorsa", None) if material else None
                    if ac and any(item.slot_name == 'txDiffuse' and item.effective_filename
                                  for item in ac.texture_slots):
                        problems.append(f"{obj.name}: diffuse texture is assigned but the mesh has no UV map.")
                        break

        lines = [f"Texture audit: {len(materials)} material(s), {repaired} link(s) repaired."]
        if problems:
            lines.extend(problems[:40])
            if len(problems) > 40:
                lines.append(f"... and {len(problems) - 40} more issue(s).")
        else:
            lines.append("No missing AC texture links or diffuse UV issues found.")
        print("\n".join(lines))

        if problems:
            self.report({'WARNING'}, f"{repaired} repaired; {len(problems)} texture issue(s). See System Console.")
        elif repaired:
            self.report({'INFO'}, f"Repaired {repaired} texture link(s).")
        else:
            self.report({'INFO'}, "Texture audit found no missing links.")
        return {'FINISHED'}


class KN5_OT_AddShaderProperty(bpy.types.Operator):
    bl_idname = "kn5.add_shader_property"
    bl_label = "Add Shader Property"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mat = context.material
        mat.assettoCorsa.shader_properties.add()
        return {'FINISHED'}


class KN5_OT_RemoveShaderProperty(bpy.types.Operator):
    bl_idname = "kn5.remove_shader_property"
    bl_label = "Remove Shader Property"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ac = context.material.assettoCorsa
        if ac.shader_properties_active >= 0 and ac.shader_properties_active < len(ac.shader_properties):
            ac.shader_properties.remove(ac.shader_properties_active)
        return {'FINISHED'}


class KN5_OT_AddTextureSlot(bpy.types.Operator):
    bl_idname = "kn5.add_texture_slot"
    bl_label = "Add Texture Slot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        mat = context.material
        mat.assettoCorsa.texture_slots.add()
        return {'FINISHED'}


class KN5_OT_RemoveTextureSlot(bpy.types.Operator):
    bl_idname = "kn5.remove_texture_slot"
    bl_label = "Remove Texture Slot"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ac = context.material.assettoCorsa
        if ac.texture_slots_active >= 0 and ac.texture_slots_active < len(ac.texture_slots):
            ac.texture_slots.remove(ac.texture_slots_active)
        return {'FINISHED'}


class KN5_OT_SetupGlossyPaintChrome(bpy.types.Operator):
    """Automatically applies high-gloss car paint and mirror-like chrome presets across all vehicle materials."""
    bl_idname = "kn5.setup_glossy_paint_chrome"
    bl_label = "Apply High-Gloss Paint & Chrome"
    bl_description = "Applies high-gloss clearcoat paint and high-reflection chrome to vehicle materials"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        paint_keywords = {"body", "paint", "carpaint", "chassis", "carroceria", "pintura", "ext_body"}
        chrome_keywords = {"chrome", "krom", "cromo", "badge", "exhaust", "emblem", "logo", "grille_chrome", "mirror_chrome", "trim"}

        updated_paint = []
        updated_chrome = []

        for mat in bpy.data.materials:
            name_low = mat.name.lower()
            if any(k in name_low for k in chrome_keywords):
                apply_preset_to_material(mat, "CHROME", sync_nodes=True)
                updated_chrome.append(mat.name)
            elif any(k in name_low for k in paint_keywords):
                apply_preset_to_material(mat, "CAR_PAINT", sync_nodes=True)
                updated_paint.append(mat.name)

        msg = f"Applied glossy presets to {len(updated_paint)} paint material(s) and {len(updated_chrome)} chrome material(s)."
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class KN5_OT_GenerateCSPConfig(bpy.types.Operator):
    """Generates or updates extension/ext_config.ini with Custom Shaders Patch PBR Car Paint and Chrome settings."""
    bl_idname = "kn5.generate_csp_config"
    bl_label = "Generate CSP Config (ext_config.ini)"
    bl_description = "Creates extension/ext_config.ini with PBR Metallic Car Paint, clearcoat flakes, and real metalness chrome"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            from .tools import find_car_directory
        except (ImportError, ValueError):
            from tools import find_car_directory

        car_dir = find_car_directory(context)
        if not car_dir or not os.path.exists(car_dir):
            self.report({'ERROR'}, "Could not locate Assetto Corsa car directory.")
            return {'CANCELLED'}

        ext_dir = os.path.join(car_dir, "extension")
        os.makedirs(ext_dir, exist_ok=True)
        ext_ini_path = os.path.join(ext_dir, "ext_config.ini")

        paint_mats = []
        chrome_mats = []
        windscreen_mats = []
        glass_mats = []
        for mat in bpy.data.materials:
            n_low = mat.name.lower()
            if any(k in n_low for k in ["chrome", "krom", "badge", "exhaust", "emblem"]):
                if mat.name not in chrome_mats:
                    chrome_mats.append(mat.name)
            elif any(k in n_low for k in ["windscreen", "windshield", "on_cam", "cam_on"]):
                if mat.name not in windscreen_mats:
                    windscreen_mats.append(mat.name)
            elif any(k in n_low for k in ["glass", "cam", "window", "pencere"]):
                if mat.name not in glass_mats:
                    glass_mats.append(mat.name)
            elif any(k in n_low for k in ["body", "paint", "carpaint", "ext_body"]):
                if mat.name not in paint_mats:
                    paint_mats.append(mat.name)

        if not paint_mats:
            paint_mats = ["EXT_body"]
        if not chrome_mats:
            chrome_mats = ["EXT_chrome", "badge"]

        existing_content = ""
        if os.path.exists(ext_ini_path):
            with open(ext_ini_path, "r", encoding="utf-8", errors="ignore") as f:
                existing_content = f.read()

        new_blocks = []
        if "common/materials_carpaint.ini" not in existing_content:
            new_blocks.append("[INCLUDE]\nINCLUDE = common/materials_carpaint.ini")

        if "[Material_CarPaint_Metallic]" not in existing_content:
            p_list = ", ".join(paint_mats)
            new_blocks.append(f"[Material_CarPaint_Metallic]\nMaterials = {p_list}\nFlakesK = 0.5\nClearCoatThickness = 0.25\nSpecularColor = 1, 1, 1\nBrightnessAdjustment = 0.95")

        if "[Material_Chrome]" not in existing_content:
            c_list = ", ".join(chrome_mats)
            new_blocks.append(f"[Material_Chrome]\nMaterials = {c_list}\nMetalness = 0.95\nRoughness = 0.05")

        if windscreen_mats and "[Material_Windscreen]" not in existing_content:
            w_list = ", ".join(windscreen_mats)
            new_blocks.append(f"[Material_Windscreen]\nMaterials = {w_list}\nCarInterior = COCKPIT_HR\nMaskPass = 1")

        if glass_mats and "[Material_Glass]" not in existing_content:
            g_list = ", ".join(glass_mats)
            new_blocks.append(f"[Material_Glass]\nMaterials = {g_list}\nThickness = 0.005")

        if new_blocks:
            separator = "\n\n" if existing_content and not existing_content.endswith("\n\n") else ""
            with open(ext_ini_path, "a", encoding="utf-8") as f:
                f.write(separator + "\n\n".join(new_blocks) + "\n")
            self.report({'INFO'}, f"Updated {ext_ini_path} with CSP Paint, Chrome, RainFX Windscreen & Glass!")
        else:
            self.report({'INFO'}, "CSP extension sections are already up to date in ext_config.ini.")

        return {'FINISHED'}


REGISTER_CLASSES = (
    KN5_ShaderPropertyItem,
    KN5_TextureSlotItem,
    KN5_MaterialProperties,
    KN5_OT_ApplyMaterialPreset,
    KN5_OT_SyncToNodes,
    KN5_OT_SyncFromNodes,
    KN5_OT_AuditRepairTextures,
    KN5_OT_AutoDetectMaterial,
    KN5_OT_AutoDetectAllMaterials,
    KN5_OT_SetupGlossyPaintChrome,
    KN5_OT_GenerateCSPConfig,
    KN5_OT_AddShaderProperty,
    KN5_OT_RemoveShaderProperty,
    KN5_OT_AddTextureSlot,
    KN5_OT_RemoveTextureSlot,
)


def register():
    for cls in REGISTER_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Material.assettoCorsa = PointerProperty(type=KN5_MaterialProperties)


def unregister():
    if hasattr(bpy.types.Material, "assettoCorsa"):
        del bpy.types.Material.assettoCorsa
    for cls in reversed(REGISTER_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
