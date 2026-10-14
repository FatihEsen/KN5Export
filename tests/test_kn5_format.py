# Unit tests for Assetto Corsa KN5 format binary serialization/deserialization

import io
import unittest
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kn5_format import (
    KN5Model,
    KN5Node,
    KN5Mesh,
    KN5Vertex,
    KN5Material,
    KN5Texture,
    KN5ShaderProperty,
    NODE_TYPE_DUMMY,
    NODE_TYPE_MESH,
)
from constants import DEFAULT_VERSION


class TestKN5Format(unittest.TestCase):
    def test_empty_model_roundtrip(self):
        """Test serializing and parsing an empty KN5 model container."""
        model = KN5Model(version=DEFAULT_VERSION)
        model.root_node = KN5Node("RootNode", NODE_TYPE_DUMMY)

        buffer = io.BytesIO()
        model.to_stream(buffer)
        buffer.seek(0)

        loaded = KN5Model.from_stream(buffer)
        self.assertEqual(loaded.version, DEFAULT_VERSION)
        self.assertEqual(len(loaded.textures), 0)
        self.assertEqual(len(loaded.materials), 0)
        self.assertIsNotNone(loaded.root_node)
        self.assertEqual(loaded.root_node.name, "RootNode")
        self.assertEqual(loaded.root_node.node_type, NODE_TYPE_DUMMY)

    def test_model_with_materials_and_textures(self):
        """Test roundtrip serialization of textures, materials, and shader properties."""
        model = KN5Model(version=DEFAULT_VERSION)

        # Textures
        tex1 = KN5Texture(name="body.dds", data=b"DDS " + b"\x00" * 124 + b"FAKE_PIXELS", active=1)
        tex2 = KN5Texture(name="glass.dds", data=b"", active=0)
        model.textures.extend([tex1, tex2])

        # Material
        mat = KN5Material(name="BodyPaint", shader="ksPerPixelNM")
        mat.blend_mode = 0
        mat.alpha_tested = False
        mat.depth_mode = 0
        mat.add_property("ksDiffuse", a=0.25)
        mat.add_property("ksAmbient", a=0.35)
        mat.add_property("ksSpecular", a=0.5, b=(0.1, 0.2))
        mat.add_texture_mapping("txDiffuse", "body.dds")
        mat.add_texture_mapping("txNormal", "body_nm.dds")
        model.materials.append(mat)

        # Nodes
        root = KN5Node("CAR_ROOT", NODE_TYPE_DUMMY)
        mesh_node = KN5Mesh("EXT_BODY")
        mesh_node.material_id = 0
        mesh_node.cast_shadows = True
        mesh_node.visible = True
        mesh_node.transparent = False

        # Add 3 vertices (1 triangle)
        v1 = KN5Vertex((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0), (1.0, 0.0, 0.0))
        v2 = KN5Vertex((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0), (1.0, 0.0, 0.0))
        v3 = KN5Vertex((0.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 1.0), (1.0, 0.0, 0.0))
        mesh_node.vertices.extend([v1, v2, v3])
        mesh_node.indices.extend([0, 1, 2])
        mesh_node.calculate_bounding_sphere()

        root.add_child(mesh_node)
        model.root_node = root

        # Serialize
        buffer = io.BytesIO()
        model.to_stream(buffer)
        buffer.seek(0)

        # Deserialize and verify
        loaded = KN5Model.from_stream(buffer)
        self.assertEqual(loaded.version, 5)
        self.assertEqual(len(loaded.textures), 2)
        self.assertEqual(loaded.textures[0].name, "body.dds")
        self.assertEqual(loaded.textures[0].data, tex1.data)
        self.assertEqual(loaded.textures[0].active, 1)
        self.assertEqual(loaded.textures[1].name, "glass.dds")
        self.assertEqual(loaded.textures[1].data, b"")
        self.assertEqual(loaded.textures[1].active, 0)

        # Verify material
        self.assertEqual(len(loaded.materials), 1)
        l_mat = loaded.materials[0]
        self.assertEqual(l_mat.name, "BodyPaint")
        self.assertEqual(l_mat.shader, "ksPerPixelNM")
        self.assertEqual(len(l_mat.properties), 3)
        self.assertEqual(l_mat.properties[0].name, "ksDiffuse")
        self.assertAlmostEqual(l_mat.properties[0].valueA, 0.25, places=4)
        self.assertEqual(len(l_mat.texture_mappings), 2)
        self.assertEqual(l_mat.texture_mappings[0][0], "txDiffuse")
        self.assertEqual(l_mat.texture_mappings[0][2], "body.dds")

        # Verify hierarchy
        self.assertIsNotNone(loaded.root_node)
        self.assertEqual(loaded.root_node.name, "CAR_ROOT")
        self.assertEqual(len(loaded.root_node.children), 1)

        l_mesh = loaded.root_node.children[0]
        self.assertIsInstance(l_mesh, KN5Mesh)
        self.assertEqual(l_mesh.name, "EXT_BODY")
        self.assertEqual(l_mesh.material_id, 0)
        self.assertEqual(len(l_mesh.vertices), 3)
        self.assertEqual(len(l_mesh.indices), 3)
        self.assertEqual(l_mesh.indices, [0, 1, 2])
        self.assertAlmostEqual(l_mesh.vertices[1].position[0], 1.0, places=4)

    def test_version_6_roundtrip(self):
        """Test KN5 Version 6 (DLC with extra header flag)."""
        model = KN5Model(version=6)
        model.extra = 42
        model.root_node = KN5Node("V6Root", NODE_TYPE_DUMMY)

        buffer = io.BytesIO()
        model.to_stream(buffer)
        buffer.seek(0)

        loaded = KN5Model.from_stream(buffer)
        self.assertEqual(loaded.version, 6)
        self.assertEqual(loaded.extra, 42)
        self.assertEqual(loaded.root_node.name, "V6Root")


if __name__ == "__main__":
    unittest.main()
