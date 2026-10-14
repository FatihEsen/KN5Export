# Unit tests for DDS header parsing, generation, and pixel conversion

import unittest
import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dds import (
    is_dds_bytes,
    parse_dds_header,
    build_dds_header_uncompressed_bgra,
    build_dds_header_dxt,
    rgba_pixels_to_bgra_dds,
    create_solid_color_dds,
    create_flat_normal_map_dds,
    create_glass_tint_dds,
    DDS_MAGIC,
    FOURCC_DXT1,
    FOURCC_DXT5,
)


class TestDDS(unittest.TestCase):
    def test_is_dds_bytes(self):
        """Test DDS magic identifier detection."""
        self.assertFalse(is_dds_bytes(b""))
        self.assertFalse(is_dds_bytes(b"PNG\r\n\x1a\n" + b"\x00" * 120))
        valid_dummy = DDS_MAGIC + b"\x00" * 124
        self.assertTrue(is_dds_bytes(valid_dummy))

    def test_uncompressed_bgra_header(self):
        """Test building and parsing 32-bit uncompressed BGRA DDS header."""
        header = build_dds_header_uncompressed_bgra(256, 128)
        self.assertEqual(len(header), 128)
        self.assertTrue(is_dds_bytes(header))

        info = parse_dds_header(header)
        self.assertEqual(info.width, 256)
        self.assertEqual(info.height, 128)
        self.assertEqual(info.format_name, "B8G8R8A8")
        self.assertEqual(info.bits_per_pixel, 32)
        self.assertFalse(info.is_compressed)

    def test_dxt_compressed_header(self):
        """Test building and parsing DXT1 and DXT5 compressed headers."""
        header_dxt1 = build_dds_header_dxt(512, 512, FOURCC_DXT1, mipmaps=4)
        info1 = parse_dds_header(header_dxt1)
        self.assertEqual(info1.width, 512)
        self.assertEqual(info1.height, 512)
        self.assertEqual(info1.fourcc, FOURCC_DXT1)
        self.assertEqual(info1.format_name, "DXT1")
        self.assertTrue(info1.is_compressed)

        header_dxt5 = build_dds_header_dxt(1024, 1024, FOURCC_DXT5, mipmaps=1)
        info5 = parse_dds_header(header_dxt5)
        self.assertEqual(info5.format_name, "DXT5")

    def test_rgba_to_bgra_pixel_conversion(self):
        """Test converting flat float RGBA pixels to 32-bit BGRA DDS."""
        width, height = 4, 4
        # 4x4 red pixels: RGBA = (1.0, 0.0, 0.0, 1.0)
        pixels = [1.0, 0.0, 0.0, 1.0] * (width * height)

        dds_bytes = rgba_pixels_to_bgra_dds(pixels, width, height)
        self.assertTrue(is_dds_bytes(dds_bytes))
        self.assertEqual(len(dds_bytes), 128 + width * height * 4)

        # Check first pixel after 128-byte header: BGRA format
        # Red in BGRA: B=0, G=0, R=255, A=255
        pixel_data = dds_bytes[128:]
        self.assertEqual(pixel_data[0], 0)    # Blue
        self.assertEqual(pixel_data[1], 0)    # Green
        self.assertEqual(pixel_data[2], 255)  # Red
        self.assertEqual(pixel_data[3], 255)  # Alpha

    def test_solid_color_and_normal_map_helpers(self):
        """Test built-in procedural DDS generators."""
        white_dds = create_solid_color_dds(255, 255, 255, 255, 2, 2)
        self.assertEqual(len(white_dds), 128 + 2 * 2 * 4)

        normal_dds = create_flat_normal_map_dds(2, 2)
        self.assertEqual(len(normal_dds), 128 + 2 * 2 * 4)
        # Flat normal map: Blue=255, Green=128, Red=128, Alpha=255
        pixel = normal_dds[128:132]
        self.assertEqual(list(pixel), [255, 128, 128, 255])

        glass_dds = create_glass_tint_dds(2, 2, alpha=90)
        self.assertEqual(len(glass_dds), 128 + 2 * 2 * 4)
        self.assertEqual(glass_dds[131], 90)


if __name__ == "__main__":
    unittest.main()
