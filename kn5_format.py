# Assetto Corsa KN5 Studio - Binary KN5 Format Specification & I/O
# Implements full parsing and serializing of KN5 Version 5 and Version 6 models.

import struct
import io
import os
import math
from typing import List, Tuple, Optional
try:
    from .constants import (
        KN5_MAGIC,
        DEFAULT_VERSION,
        NODE_TYPE_DUMMY,
        NODE_TYPE_MESH,
        NODE_TYPE_SKINNED,
        BLEND_OPAQUE,
        DEPTH_NORMAL,
    )
except (ImportError, ValueError):
    from constants import (
        KN5_MAGIC,
        DEFAULT_VERSION,
        NODE_TYPE_DUMMY,
        NODE_TYPE_MESH,
        NODE_TYPE_SKINNED,
        BLEND_OPAQUE,
        DEPTH_NORMAL,
    )


class KN5Texture:
    """Represents a texture in the KN5 container."""
    def __init__(self, name: str = "", data: bytes = b"", active: int = 1):
        self.active = active
        self.name = name
        self.data = data

    @property
    def size(self) -> int:
        return len(self.data)

    def __repr__(self):
        return f"<KN5Texture '{self.name}', size={self.size} bytes, active={self.active}>"


class KN5ShaderProperty:
    """Represents a uniform shader parameter (up to 10 floats)."""
    def __init__(self, name: str = "", a: float = 0.0,
                 b: Tuple[float, float] = (0.0, 0.0),
                 c: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 d: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)):
        self.name = name
        self.valueA = float(a)
        self.valueB = (float(b[0]), float(b[1]))
        self.valueC = (float(c[0]), float(c[1]), float(c[2]))
        self.valueD = (float(d[0]), float(d[1]), float(d[2]), float(d[3]))

    def __repr__(self):
        return f"<KN5ShaderProperty '{self.name}', A={self.valueA:.3f}>"


class KN5Material:
    """Represents a surface material with shader bindings."""
    def __init__(self, name: str = "Default", shader: str = "ksPerPixel"):
        self.name = name
        self.shader = shader
        self.blend_mode = BLEND_OPAQUE
        self.alpha_tested = False
        self.depth_mode = DEPTH_NORMAL
        self.properties: List[KN5ShaderProperty] = []
        # list of tuples: (slot_name, slot_id, texture_filename)
        self.texture_mappings: List[Tuple[str, int, str]] = []

    def add_property(self, name: str, a: float = 0.0,
                     b: Tuple[float, float] = (0.0, 0.0),
                     c: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                     d: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)):
        prop = KN5ShaderProperty(name, a, b, c, d)
        self.properties.append(prop)
        return prop

    def add_texture_mapping(self, slot_name: str, texture_filename: str):
        slot_id = len(self.texture_mappings)
        self.texture_mappings.append((slot_name, slot_id, texture_filename))

    def __repr__(self):
        return (f"<KN5Material '{self.name}', shader='{self.shader}', "
                f"props={len(self.properties)}, texs={len(self.texture_mappings)}>")


class KN5Vertex:
    """Represents a single vertex with position, normal, UV, and tangent vector."""
    __slots__ = ("position", "normal", "uv", "tangent")

    def __init__(self,
                 position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                 normal: Tuple[float, float, float] = (0.0, 1.0, 0.0),
                 uv: Tuple[float, float] = (0.0, 0.0),
                 tangent: Tuple[float, float, float] = (1.0, 0.0, 0.0)):
        self.position = position
        self.normal = normal
        self.uv = uv
        self.tangent = tangent

    def __repr__(self):
        return f"<KN5Vertex pos={self.position}, uv={self.uv}>"


class KN5Node:
    """Represents a transform node (Empty / Dummy) or base node in the hierarchy."""
    def __init__(self, name: str = "Root", node_type: int = NODE_TYPE_DUMMY):
        self.name = name
        self.node_type = node_type
        self.active = True
        # 4x4 matrix as list of 16 floats (column-major in DirectX storage)
        self.transform = [
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0
        ]
        self.children: List['KN5Node'] = []

    def add_child(self, child: 'KN5Node'):
        self.children.append(child)

    @property
    def is_mesh(self) -> bool:
        return self.node_type == NODE_TYPE_MESH

    def __repr__(self):
        return f"<KN5Node '{self.name}', type={self.node_type}, children={len(self.children)}>"


class KN5Mesh(KN5Node):
    """Represents a renderable geometry node with vertices, indices, and material."""
    def __init__(self, name: str = "Mesh"):
        super().__init__(name=name, node_type=NODE_TYPE_MESH)
        self.cast_shadows = True
        self.visible = True
        self.transparent = False
        self.vertices: List[KN5Vertex] = []
        self.indices: List[int] = []
        self.material_id = 0
        self.layer = 0
        self.lod_in = 0.0
        self.lod_out = 0.0
        self.sphere_center = (0.0, 0.0, 0.0)
        self.sphere_radius = 0.0
        self.renderable = True

    def calculate_bounding_sphere(self):
        """Computes minimal enclosing bounding sphere center and radius."""
        if not self.vertices:
            self.sphere_center = (0.0, 0.0, 0.0)
            self.sphere_radius = 0.0
            return

        min_x = min(v.position[0] for v in self.vertices)
        max_x = max(v.position[0] for v in self.vertices)
        min_y = min(v.position[1] for v in self.vertices)
        max_y = max(v.position[1] for v in self.vertices)
        min_z = min(v.position[2] for v in self.vertices)
        max_z = max(v.position[2] for v in self.vertices)

        cx = min_x + (max_x - min_x) * 0.5
        cy = min_y + (max_y - min_y) * 0.5
        cz = min_z + (max_z - min_z) * 0.5
        self.sphere_center = (cx, cy, cz)

        max_dist_sq = 0.0
        for v in self.vertices:
            dx = v.position[0] - cx
            dy = v.position[1] - cy
            dz = v.position[2] - cz
            dist_sq = dx * dx + dy * dy + dz * dz
            if dist_sq > max_dist_sq:
                max_dist_sq = dist_sq
        self.sphere_radius = math.sqrt(max_dist_sq)

    def __repr__(self):
        return (f"<KN5Mesh '{self.name}', verts={len(self.vertices)}, "
                f"tris={len(self.indices)//3}, mat_id={self.material_id}>")


class KN5Model:
    """Represents a complete KN5 container file."""
    def __init__(self, version: int = DEFAULT_VERSION):
        self.version = version
        self.extra = 0
        self.textures: List[KN5Texture] = []
        self.materials: List[KN5Material] = []
        self.root_node: Optional[KN5Node] = None

    @classmethod
    def from_file(cls, filepath: str) -> 'KN5Model':
        """Loads a KN5 model from a file path."""
        with open(filepath, "rb") as f:
            return cls.from_stream(f)

    @classmethod
    def from_stream(cls, stream: io.BufferedIOBase) -> 'KN5Model':
        """Reads a KN5 model from an open binary stream."""
        model = cls()
        reader = _KN5BinaryReader(stream)

        # 1. Header
        magic = stream.read(6)
        if magic != KN5_MAGIC:
            raise ValueError(f"Invalid KN5 header magic: expected {KN5_MAGIC}, got {magic}")

        model.version = reader.read_uint()
        if model.version > 5:
            model.extra = reader.read_uint()

        # 2. Textures
        tex_count = reader.read_int()
        for _ in range(tex_count):
            active = reader.read_int()
            name = reader.read_string()
            size = reader.read_uint()
            data = stream.read(size)
            model.textures.append(KN5Texture(name=name, data=data, active=active))

        # 3. Materials
        mat_count = reader.read_int()
        for _ in range(mat_count):
            mat = KN5Material()
            mat.name = reader.read_string()
            mat.shader = reader.read_string()
            mat.blend_mode = reader.read_byte()
            mat.alpha_tested = reader.read_bool()
            mat.depth_mode = reader.read_uint()

            prop_count = reader.read_uint()
            for _ in range(prop_count):
                pname = reader.read_string()
                va = reader.read_float()
                vb = reader.read_float2()
                vc = reader.read_float3()
                vd = reader.read_float4()
                mat.properties.append(KN5ShaderProperty(pname, va, vb, vc, vd))

            mapping_count = reader.read_uint()
            for _ in range(mapping_count):
                slot_name = reader.read_string()
                slot_id = reader.read_uint()
                tex_name = reader.read_string()
                mat.texture_mappings.append((slot_name, slot_id, tex_name))

            model.materials.append(mat)

        # 4. Scene Graph Nodes
        def read_node() -> KN5Node:
            node_type = reader.read_uint()
            name = reader.read_string()
            num_children = reader.read_uint()
            active = reader.read_bool()

            node: KN5Node
            if node_type == NODE_TYPE_DUMMY:
                node = KN5Node(name=name, node_type=NODE_TYPE_DUMMY)
                node.active = active
                node.transform = list(reader.read_matrix16())
            elif node_type == NODE_TYPE_MESH:
                mesh = KN5Mesh(name=name)
                mesh.active = active
                mesh.cast_shadows = reader.read_bool()
                mesh.visible = reader.read_bool()
                mesh.transparent = reader.read_bool()

                vert_count = reader.read_uint()
                mesh.vertices = [None] * vert_count
                for i in range(vert_count):
                    pos = reader.read_float3()
                    norm = reader.read_float3()
                    uv = reader.read_float2()
                    tan = reader.read_float3()
                    mesh.vertices[i] = KN5Vertex(pos, norm, uv, tan)

                idx_count = reader.read_uint()
                mesh.indices = list(reader.read_ushort_array(idx_count))
                mesh.material_id = reader.read_uint()
                mesh.layer = reader.read_uint()
                mesh.lod_in = reader.read_float()
                mesh.lod_out = reader.read_float()
                mesh.sphere_center = reader.read_float3()
                mesh.sphere_radius = reader.read_float()
                mesh.renderable = reader.read_bool()
                node = mesh
            elif node_type == NODE_TYPE_SKINNED:
                mesh = KN5Mesh(name=name)
                mesh.node_type = NODE_TYPE_SKINNED
                mesh.active = active
                mesh.cast_shadows = reader.read_bool()
                mesh.visible = reader.read_bool()
                mesh.transparent = reader.read_bool()

                bone_count = reader.read_uint()
                for _ in range(bone_count):
                    _bname = reader.read_string()
                    _bmat = reader.read_matrix16()

                vert_count = reader.read_uint()
                mesh.vertices = [None] * vert_count
                for i in range(vert_count):
                    pos = reader.read_float3()
                    norm = reader.read_float3()
                    uv = reader.read_float2()
                    tan = reader.read_float3()
                    weights = reader.read_float4()
                    bone_indices = reader.read_float4()
                    mesh.vertices[i] = KN5Vertex(pos, norm, uv, tan)

                idx_count = reader.read_uint()
                mesh.indices = list(reader.read_ushort_array(idx_count))
                mesh.material_id = reader.read_uint()
                mesh.layer = reader.read_uint()
                mesh.lod_in = reader.read_float()
                mesh.lod_out = reader.read_float()
                node = mesh
            else:
                raise ValueError(f"Unsupported KN5 node type: {node_type} on '{name}'")

            for _ in range(num_children):
                node.add_child(read_node())

            return node

        model.root_node = read_node()
        return model

    def to_file(self, filepath: str):
        """Serializes the KN5 model to a file on disk."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "wb") as f:
            self.to_stream(f)

    def to_stream(self, stream: io.BufferedIOBase):
        """Writes the KN5 model to a binary stream."""
        writer = _KN5BinaryWriter(stream)

        # 1. Header
        stream.write(KN5_MAGIC)
        writer.write_uint(self.version)
        if self.version > 5:
            writer.write_uint(self.extra)

        # 2. Textures
        writer.write_int(len(self.textures))
        for tex in self.textures:
            writer.write_int(tex.active)
            writer.write_string(tex.name)
            writer.write_uint(len(tex.data))
            stream.write(tex.data)

        # 3. Materials
        writer.write_int(len(self.materials))
        for mat in self.materials:
            writer.write_string(mat.name)
            writer.write_string(mat.shader)
            writer.write_byte(mat.blend_mode)
            writer.write_bool(mat.alpha_tested)
            writer.write_uint(mat.depth_mode)

            writer.write_uint(len(mat.properties))
            for prop in mat.properties:
                writer.write_string(prop.name)
                writer.write_float(prop.valueA)
                writer.write_float2(prop.valueB)
                writer.write_float3(prop.valueC)
                writer.write_float4(prop.valueD)

            writer.write_uint(len(mat.texture_mappings))
            for slot_idx, mapping in enumerate(mat.texture_mappings):
                slot_name, _, tex_name = mapping
                writer.write_string(slot_name)
                writer.write_uint(slot_idx)
                writer.write_string(tex_name)

        # 4. Scene Graph Nodes
        def write_node(node: KN5Node):
            writer.write_uint(node.node_type)
            writer.write_string(node.name)
            writer.write_uint(len(node.children))
            writer.write_bool(node.active)

            if node.node_type == NODE_TYPE_DUMMY:
                writer.write_matrix16(node.transform)
            elif node.node_type == NODE_TYPE_MESH:
                mesh: KN5Mesh = node
                writer.write_bool(mesh.cast_shadows)
                writer.write_bool(mesh.visible)
                writer.write_bool(mesh.transparent)

                # Vertices (44 bytes each)
                writer.write_uint(len(mesh.vertices))
                for v in mesh.vertices:
                    writer.write_float3(v.position)
                    writer.write_float3(v.normal)
                    writer.write_float2(v.uv)
                    writer.write_float3(v.tangent)

                # Indices (uint16)
                writer.write_uint(len(mesh.indices))
                writer.write_ushort_array(mesh.indices)

                writer.write_uint(mesh.material_id)
                writer.write_uint(mesh.layer)
                writer.write_float(mesh.lod_in)
                writer.write_float(mesh.lod_out)
                writer.write_float3(mesh.sphere_center)
                writer.write_float(mesh.sphere_radius)
                writer.write_bool(mesh.renderable)

            for child in node.children:
                write_node(child)

        if self.root_node:
            write_node(self.root_node)
        else:
            # Fallback empty dummy root node
            empty_root = KN5Node("Root", NODE_TYPE_DUMMY)
            write_node(empty_root)


class _KN5BinaryReader:
    """Helper for reading structured binary fields from stream."""
    __slots__ = ("stream",)

    def __init__(self, stream: io.BufferedIOBase):
        self.stream = stream

    def read_byte(self) -> int:
        return struct.unpack("<B", self.stream.read(1))[0]

    def read_bool(self) -> bool:
        return struct.unpack("<?", self.stream.read(1))[0]

    def read_int(self) -> int:
        return struct.unpack("<i", self.stream.read(4))[0]

    def read_uint(self) -> int:
        return struct.unpack("<I", self.stream.read(4))[0]

    def read_float(self) -> float:
        return struct.unpack("<f", self.stream.read(4))[0]

    def read_float2(self) -> Tuple[float, float]:
        return struct.unpack("<2f", self.stream.read(8))

    def read_float3(self) -> Tuple[float, float, float]:
        return struct.unpack("<3f", self.stream.read(12))

    def read_float4(self) -> Tuple[float, float, float, float]:
        return struct.unpack("<4f", self.stream.read(16))

    def read_matrix16(self) -> Tuple[float, ...]:
        return struct.unpack("<16f", self.stream.read(64))

    def read_ushort_array(self, count: int) -> Tuple[int, ...]:
        return struct.unpack(f"<{count}H", self.stream.read(count * 2))

    def read_string(self) -> str:
        length = self.read_uint()
        if length == 0:
            return ""
        data = self.stream.read(length)
        return data.decode("utf-8", errors="replace")


class _KN5BinaryWriter:
    """Helper for writing structured binary fields to stream."""
    __slots__ = ("stream",)

    def __init__(self, stream: io.BufferedIOBase):
        self.stream = stream

    def write_byte(self, val: int):
        self.stream.write(struct.pack("<B", val))

    def write_bool(self, val: bool):
        self.stream.write(struct.pack("<?", val))

    def write_int(self, val: int):
        self.stream.write(struct.pack("<i", val))

    def write_uint(self, val: int):
        self.stream.write(struct.pack("<I", val))

    def write_float(self, val: float):
        self.stream.write(struct.pack("<f", val))

    def write_float2(self, val: Tuple[float, float]):
        self.stream.write(struct.pack("<2f", val[0], val[1]))

    def write_float3(self, val: Tuple[float, float, float]):
        self.stream.write(struct.pack("<3f", val[0], val[1], val[2]))

    def write_float4(self, val: Tuple[float, float, float, float]):
        self.stream.write(struct.pack("<4f", val[0], val[1], val[2], val[3]))

    def write_matrix16(self, matrix: List[float]):
        self.stream.write(struct.pack("<16f", *matrix[:16]))

    def write_ushort_array(self, indices: List[int]):
        count = len(indices)
        if count > 0:
            self.stream.write(struct.pack(f"<{count}H", *indices))

    def write_string(self, text: str):
        encoded = text.encode("utf-8")
        self.write_uint(len(encoded))
        self.stream.write(encoded)
