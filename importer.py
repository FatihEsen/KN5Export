# Assetto Corsa KN5 Studio - High-Precision KN5 Importer
# Rebuilds complete scene hierarchy, meshes, materials, and extracts embedded textures.

import bpy
import mathutils
import os
import time
from typing import Dict, List, Tuple, Optional
from bpy_extras.io_utils import ImportHelper
from bpy.props import (
    BoolProperty,
    StringProperty,
)

try:
    from .constants import (
        NODE_TYPE_DUMMY,
        NODE_TYPE_MESH,
    )
    from .kn5_format import (
        KN5Model,
        KN5Node,
        KN5Mesh,
        KN5Texture,
        KN5Material,
    )
    from .dds import save_dds_file
except (ImportError, ValueError):
    from constants import (
        NODE_TYPE_DUMMY,
        NODE_TYPE_MESH,
    )
    from kn5_format import (
        KN5Model,
        KN5Node,
        KN5Mesh,
        KN5Texture,
        KN5Material,
    )
    from dds import save_dds_file


def convert_ac_to_blender_vector(v: Tuple[float, float, float]) -> mathutils.Vector:
    """Converts AC DirectX vector (X right, Y up, Z forward) to Blender (X right, Y forward, Z up)."""
    return mathutils.Vector((v[0], -v[2], v[1]))


def convert_ac_to_blender_matrix(col_major_16: List[float]) -> mathutils.Matrix:
    """Converts column-major DirectX 4x4 matrix from KN5 into Blender row-major Matrix."""
    # Build 4x4 from column-major
    m = mathutils.Matrix([
        [col_major_16[0], col_major_16[4], col_major_16[8],  col_major_16[12]],
        [col_major_16[1], col_major_16[5], col_major_16[9],  col_major_16[13]],
        [col_major_16[2], col_major_16[6], col_major_16[10], col_major_16[14]],
        [col_major_16[3], col_major_16[7], col_major_16[11], col_major_16[15]],
    ])

    loc, rot, scale = m.decompose()
    # Convert location: (x, y, z) -> (x, -z, y)
    b_loc = convert_ac_to_blender_vector((loc[0], loc[1], loc[2]))

    # Convert rotation axis
    axis, angle = rot.to_axis_angle()
    b_axis = mathutils.Vector((axis[0], -axis[2], axis[1]))
    if b_axis.length_squared > 0.00001:
        b_rot = mathutils.Quaternion(b_axis, angle)
    else:
        b_rot = mathutils.Quaternion()

    # Convert scale: AC (x, y, z) -> Blender (sx, sz, sy)
    b_scale = (scale[0], scale[2], scale[1])

    mat_loc = mathutils.Matrix.Translation(b_loc)
    mat_rot = b_rot.to_matrix().to_4x4()
    mat_scale = mathutils.Matrix.Diagonal((*b_scale, 1.0))

    return mat_loc @ mat_rot @ mat_scale


class KN5Importer:
    def __init__(self, context, filepath: str, options: dict):
        self.context = context
        self.filepath = filepath
        self.options = options
        self.tex_dir = os.path.join(os.path.dirname(os.path.abspath(filepath)), "texture")

        self.loaded_images: Dict[str, bpy.types.Image] = {}
        self.loaded_materials: List[bpy.types.Material] = []

        self.created_objects = 0
        self.created_vertices = 0
        self.created_triangles = 0

    def load(self):
        model = KN5Model.from_file(self.filepath)

        # 1. Extract textures
        if self.options.get("extract_textures", True) and model.textures:
            self._extract_textures(model.textures)

        # 2. Build Blender materials
        if self.options.get("create_materials", True):
            self._create_materials(model.materials)

        # 3. Create collection for imported objects
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        collection = bpy.data.collections.new(base_name)
        self.context.scene.collection.children.link(collection)

        # 4. Reconstruct Scene Hierarchy
        if model.root_node:
            self._import_node_recursive(model.root_node, parent_obj=None, collection=collection)

    def _extract_textures(self, textures: List[KN5Texture]):
        """Saves embedded textures to disk and loads them into Blender."""
        os.makedirs(self.tex_dir, exist_ok=True)

        for tex in textures:
            if not tex.name:
                continue
            # KN5 texture names are references, not paths. Keep extraction inside
            # the companion texture directory and refresh prior imports.
            tex_name = os.path.basename(tex.name.replace("\\", "/"))
            tex_path = os.path.join(self.tex_dir, tex_name)

            if tex.data:
                save_dds_file(tex_path, tex.data)

            # Load into Blender if file exists on disk
            if os.path.exists(tex_path):
                try:
                    img = bpy.data.images.load(tex_path, check_existing=True)
                    if tex.data and img.packed_file:
                        # A packed image cannot be refreshed from its filepath.
                        # Load a fresh datablock from the newly extracted bytes.
                        img = bpy.data.images.load(tex_path, check_existing=False)
                    elif tex.data:
                        # Blender may cache a datablock by filepath after its DDS
                        # was replaced. Reload its pixels as well.
                        img.reload()
                    self.loaded_images[tex.name] = img
                except Exception as e:
                    print(f"Warning: Could not load texture '{tex.name}' into Blender: {e}")

    def _create_materials(self, materials: List[KN5Material]):
        """Generates Blender materials with AC shader properties and node trees."""
        for mat_data in materials:
            mat = bpy.data.materials.new(name=mat_data.name)
            mat.use_nodes = True
            ac = getattr(mat, "assettoCorsa", None)

            if ac:
                ac.shader_name = mat_data.shader
                ac.blend_mode = str(mat_data.blend_mode)
                ac.alpha_tested = mat_data.alpha_tested
                ac.depth_mode = str(mat_data.depth_mode)

                # Set shader properties
                for prop in mat_data.properties:
                    item = ac.shader_properties.add()
                    item.name = prop.name
                    item.valueA = prop.valueA
                    item.valueB = prop.valueB
                    item.valueC = prop.valueC
                    item.valueD = prop.valueD

                # Set texture slots
                for slot_name, _, tex_name in mat_data.texture_mappings:
                    slot = ac.texture_slots.add()
                    slot.slot_name = slot_name
                    slot.override_filename = tex_name
                    if tex_name in self.loaded_images:
                        slot.image = self.loaded_images[tex_name]

            # Build shader nodes for viewport preview
            self._setup_material_nodes(mat, mat_data)
            self.loaded_materials.append(mat)

    def _setup_material_nodes(self, mat: bpy.types.Material, mat_data: KN5Material):
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (400, 300)

        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 300)
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

        # Blend mode
        if mat_data.blend_mode == 1:
            mat.blend_method = 'BLEND'
        elif mat_data.blend_mode == 2 or mat_data.alpha_tested:
            mat.blend_method = 'CLIP'
        else:
            mat.blend_method = 'OPAQUE'

        # Textures
        for slot_name, _, tex_name in mat_data.texture_mappings:
            img = self.loaded_images.get(tex_name)
            if not img:
                continue

            tex_node = nodes.new(type='ShaderNodeTexImage')
            tex_node.image = img

            if slot_name == "txDiffuse":
                tex_node.location = (-400, 300)
                links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
                if (mat_data.blend_mode != 0 or mat_data.alpha_tested) and "Alpha" in bsdf.inputs:
                    links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
            elif slot_name == "txNormal":
                tex_node.location = (-400, -100)
                norm_node = nodes.new(type='ShaderNodeNormalMap')
                norm_node.location = (-100, -100)
                links.new(tex_node.outputs['Color'], norm_node.inputs['Color'])
                if "Normal" in bsdf.inputs:
                    links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])

    def _import_node_recursive(self, node: KN5Node, parent_obj: Optional[bpy.types.Object], collection: bpy.types.Collection):
        created_obj = None

        if node.node_type == NODE_TYPE_DUMMY:
            empty = bpy.data.objects.new(node.name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 0.5
            empty.matrix_local = convert_ac_to_blender_matrix(node.transform)
            collection.objects.link(empty)

            if parent_obj:
                empty.parent = parent_obj

            created_obj = empty
            self.created_objects += 1

        elif node.node_type == NODE_TYPE_MESH:
            mesh_data: KN5Mesh = node
            mesh_obj = self._create_blender_mesh(mesh_data)
            collection.objects.link(mesh_obj)

            if parent_obj:
                mesh_obj.parent = parent_obj

            created_obj = mesh_obj
            self.created_objects += 1

        # Process children
        for child in node.children:
            self._import_node_recursive(child, parent_obj=created_obj, collection=collection)

    def _create_blender_mesh(self, kn5_mesh: KN5Mesh) -> bpy.types.Object:
        """Constructs a Blender mesh from KN5 vertex and index arrays."""
        mesh = bpy.data.meshes.new(name=kn5_mesh.name)

        # 1. Vertices coordinates
        verts = [convert_ac_to_blender_vector(v.position) for v in kn5_mesh.vertices]

        # 2. Triangles: reverse winding order from DirectX (i0, i2, i1)
        raw_indices = kn5_mesh.indices
        faces = []
        for i in range(0, len(raw_indices), 3):
            # DirectX CW to Blender CCW
            faces.append((raw_indices[i], raw_indices[i + 2], raw_indices[i + 1]))

        mesh.from_pydata(verts, [], faces)
        mesh.update()

        # 3. Custom Normals & UVs
        if kn5_mesh.vertices:
            # Set UV coordinates
            uv_layer = mesh.uv_layers.new(name="UVMap")
            for loop in mesh.loops:
                v_idx = loop.vertex_index
                uv = kn5_mesh.vertices[v_idx].uv
                # Reverse V-flip: 1.0 - V
                uv_layer.data[loop.index].uv = (uv[0], 1.0 - uv[1])

            # Assign custom split corner normals
            custom_normals = [convert_ac_to_blender_vector(kn5_mesh.vertices[loop.vertex_index].normal) for loop in mesh.loops]
            mesh.normals_split_custom_set(custom_normals)

        # 4. Assign Material
        if 0 <= kn5_mesh.material_id < len(self.loaded_materials):
            mesh.materials.append(self.loaded_materials[kn5_mesh.material_id])

        obj = bpy.data.objects.new(kn5_mesh.name, mesh)

        # AC Object custom properties
        ac = getattr(obj, "assettoCorsa", None)
        if ac:
            ac.cast_shadows = kn5_mesh.cast_shadows
            ac.visible = kn5_mesh.visible
            ac.transparent = kn5_mesh.transparent
            ac.renderable = kn5_mesh.renderable
            ac.layer = kn5_mesh.layer
            ac.lod_in = kn5_mesh.lod_in
            ac.lod_out = kn5_mesh.lod_out

        self.created_vertices += len(kn5_mesh.vertices)
        self.created_triangles += len(faces)
        return obj


class ImportKN5(bpy.types.Operator, ImportHelper):
    """Import an Assetto Corsa (.kn5) model into the current scene."""
    bl_idname = "import_scene.kn5"
    bl_label = "Import KN5"
    bl_description = "Import Assetto Corsa KN5 model file with hierarchy, meshes, materials, and textures"

    filename_ext = ".kn5"
    filter_glob: StringProperty(default="*.kn5", options={'HIDDEN'})

    extract_textures: BoolProperty(
        name="Extract Textures",
        description="Extract embedded DDS textures to a /texture folder and load into Blender",
        default=True
    )

    create_materials: BoolProperty(
        name="Create Materials",
        description="Generate Blender materials with AC shader properties and node trees",
        default=True
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Import Options", icon='IMPORT')
        box.prop(self, "extract_textures")
        box.prop(self, "create_materials")

    def execute(self, context):
        t0 = time.time()
        options = {
            "extract_textures": self.extract_textures,
            "create_materials": self.create_materials,
        }

        try:
            importer = KN5Importer(context, self.filepath, options)
            importer.load()

            dt = time.time() - t0
            summary = (
                f"Import Complete in {dt:.2f}s!\n"
                f"Created Objects: {importer.created_objects} | "
                f"Vertices: {importer.created_vertices:,} | "
                f"Triangles: {importer.created_triangles:,} | "
                f"Materials: {len(importer.loaded_materials)} | "
                f"Textures: {len(importer.loaded_images)}"
            )
            print(summary)
            self.report({'INFO'}, summary)
            return {'FINISHED'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"KN5 Import Failed: {e}")
            return {'CANCELLED'}


def menu_func_import(self, context):
    self.layout.operator(ImportKN5.bl_idname, text="Assetto Corsa (.kn5)")


REGISTER_CLASSES = (
    ImportKN5,
)


def register():
    for cls in REGISTER_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except Exception:
        pass
    for cls in reversed(REGISTER_CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
