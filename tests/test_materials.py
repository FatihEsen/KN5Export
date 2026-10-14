# Unit tests for material presets, texture cleaning, and shader parameter mapping

import unittest
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from constants import (
    clean_texture_name,
    match_material_preset,
    MATERIAL_PRESETS,
    SHADER_TEXTURE_SLOTS,
    DEFAULT_SHADER_PROPERTIES,
)


class TestMaterials(unittest.TestCase):
    def test_clean_texture_name(self):
        """Test cleaning and sanitizing texture filenames."""
        # 1. Directory stripping
        self.assertEqual(clean_texture_name("C:\\models\\textures\\diffuse.dds"), "diffuse.dds")
        self.assertEqual(clean_texture_name("/home/user/cars/skin/ext_body.dds"), "ext_body.dds")

        # 2. Duplicate Blender suffix stripping (e.g. .001, .002)
        self.assertEqual(clean_texture_name("wheel.001.dds"), "wheel.dds")
        self.assertEqual(clean_texture_name("diffuse.003"), "diffuse")

        # 3. Duplicate extension stripping
        self.assertEqual(clean_texture_name("carbon.dds.dds"), "carbon.dds")
        self.assertEqual(clean_texture_name("carbon.dds.dds.dds"), "carbon.dds")

        # 4. Force DDS extension
        self.assertEqual(clean_texture_name("rim.png", force_dds=True), "rim.dds")
        self.assertEqual(clean_texture_name("rim.dds", force_dds=True), "rim.dds")

    def test_material_preset_matching(self):
        """Test auto-matching AC material presets from mesh/material names."""
        # Body / Car paint
        self.assertEqual(match_material_preset("EXT_Car_Body"), "CAR_PAINT")
        self.assertEqual(match_material_preset("paint_metallic"), "CAR_PAINT")

        # Glass
        self.assertEqual(match_material_preset("windscreen_front"), "WINDSCREEN")
        self.assertEqual(match_material_preset("window_glass"), "GLASS_CLEAR")

        # Tyres & Rims
        self.assertEqual(match_material_preset("tyre_front_left"), "TIRE_RUBBER")
        self.assertEqual(match_material_preset("tire_compound"), "TIRE_RUBBER")
        self.assertEqual(match_material_preset("wheel_rim_chrome"), "CHROME")

        # Brakes
        self.assertEqual(match_material_preset("brake_disc_f"), "BRAKE_DISC")

        # Track surfaces
        self.assertEqual(match_material_preset("1ROAD_asphalt"), "ROAD_ASPHALT")
        self.assertEqual(match_material_preset("1KERB_exit"), "KERB_CURB")
        self.assertEqual(match_material_preset("1GRASS_green"), "GRASS_TERRAIN")

    def test_constants_definitions(self):
        """Test that every preset defines valid shader and properties."""
        for preset_name, preset_data in MATERIAL_PRESETS.items():
            self.assertIn("shader", preset_data)
            self.assertIn("label", preset_data)
            shader = preset_data["shader"]
            # Ensure shader texture slots exist
            self.assertIn(shader, SHADER_TEXTURE_SLOTS)


if __name__ == "__main__":
    unittest.main()
