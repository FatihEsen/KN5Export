# Assetto Corsa KN5 Studio - Pure Python DDS Handler & Encoder
# Provides DDS header parsing, generation, and encoding without external binary dependencies.

import struct
import os

DDS_MAGIC = b"DDS "

# DDSD (DirectDraw Surface Description) Flags
DDSD_CAPS = 0x00000001
DDSD_HEIGHT = 0x00000002
DDSD_WIDTH = 0x00000004
DDSD_PITCH = 0x00000008
DDSD_PIXELFORMAT = 0x00001000
DDSD_MIPMAPCOUNT = 0x00020000
DDSD_LINEARSIZE = 0x00080000

# DDPF (Pixel Format) Flags
DDPF_ALPHAPIXELS = 0x00000001
DDPF_ALPHA = 0x00000002
DDPF_FOURCC = 0x00000004
DDPF_RGB = 0x00000040

# DDSCAPS (Caps) Flags
DDSCAPS_COMPLEX = 0x00000008
DDSCAPS_TEXTURE = 0x00001000
DDSCAPS_MIPMAP = 0x00400000

# FourCC Codes
FOURCC_DXT1 = b"DXT1"
FOURCC_DXT3 = b"DXT3"
FOURCC_DXT5 = b"DXT5"
FOURCC_ATI1 = b"ATI1"
FOURCC_ATI2 = b"ATI2"
FOURCC_BC7 = b"BC7\0"


class DDSInfo:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.mipmaps = 1
        self.format_name = "UNKNOWN"
        self.fourcc = b""
        self.bits_per_pixel = 0
        self.is_compressed = False


def is_dds_bytes(data: bytes) -> bool:
    """Checks if data begins with the DDS magic header."""
    return len(data) >= 128 and data[:4] == DDS_MAGIC


def parse_dds_header(data: bytes) -> DDSInfo:
    """Parses DDS header bytes and returns DDSInfo metadata."""
    if not is_dds_bytes(data):
        raise ValueError("Data is not a valid DDS stream (missing 'DDS ' magic)")

    info = DDSInfo()
    # Header format:
    # 0..4: Magic 'DDS '
    # 4..8: dwSize (124)
    # 8..12: dwFlags
    # 12..16: dwHeight
    # 16..20: dwWidth
    # 20..24: dwPitchOrLinearSize
    # 24..28: dwDepth
    # 28..32: dwMipMapCount
    # 76..80: ddspf.dwSize (32)
    # 80..84: ddspf.dwFlags
    # 84..88: ddspf.dwFourCC
    # 88..92: ddspf.dwRGBBitCount
    height, width, pitch, depth, mipmaps = struct.unpack("<5I", data[12:32])
    info.width = width
    info.height = height
    info.mipmaps = max(1, mipmaps)

    pf_flags, fourcc, rgb_bits = struct.unpack("<I4sI", data[80:92])
    info.fourcc = fourcc
    info.bits_per_pixel = rgb_bits

    if pf_flags & DDPF_FOURCC:
        info.is_compressed = True
        info.format_name = fourcc.decode("ascii", errors="ignore").strip("\0")
    elif pf_flags & DDPF_RGB:
        info.is_compressed = False
        r_mask, g_mask, b_mask, a_mask = struct.unpack("<4I", data[96:112])
        if rgb_bits == 32:
            if b_mask == 0x000000FF and r_mask == 0x00FF0000:
                info.format_name = "B8G8R8A8"
            elif r_mask == 0x000000FF and b_mask == 0x00FF0000:
                info.format_name = "R8G8B8A8"
            else:
                info.format_name = "RGB32"
        elif rgb_bits == 24:
            info.format_name = "B8G8R8"
    return info


def build_dds_header_uncompressed_bgra(width: int, height: int) -> bytes:
    """Builds a standard 128-byte DDS header for uncompressed 32-bit BGRA image data."""
    dw_magic = DDS_MAGIC
    dw_size = 124
    dw_flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT
    dw_height = height
    dw_width = width
    dw_pitch = width * 4
    dw_depth = 0
    dw_mipmaps = 1
    dw_reserved1 = b"\x00" * 44

    # Pixel Format: 32 bytes
    pf_size = 32
    pf_flags = DDPF_RGB | DDPF_ALPHAPIXELS
    pf_fourcc = b"\x00\x00\x00\x00"
    pf_rgb_bits = 32
    pf_r_mask = 0x00FF0000
    pf_g_mask = 0x0000FF00
    pf_b_mask = 0x000000FF
    pf_a_mask = 0xFF000000

    pixel_format = struct.pack(
        "<II4sIIIII",
        pf_size,
        pf_flags,
        pf_fourcc,
        pf_rgb_bits,
        pf_r_mask,
        pf_g_mask,
        pf_b_mask,
        pf_a_mask,
    )

    dw_caps = DDSCAPS_TEXTURE
    dw_caps2 = 0
    dw_caps3 = 0
    dw_caps4 = 0
    dw_reserved2 = 0

    header_body = struct.pack(
        "<IIIIIII44s",
        dw_size,
        dw_flags,
        dw_height,
        dw_width,
        dw_pitch,
        dw_depth,
        dw_mipmaps,
        dw_reserved1,
    ) + pixel_format + struct.pack(
        "<IIIII",
        dw_caps,
        dw_caps2,
        dw_caps3,
        dw_caps4,
        dw_reserved2,
    )

    return dw_magic + header_body


def build_dds_header_dxt(width: int, height: int, fourcc: bytes, mipmaps: int = 1) -> bytes:
    """Builds a standard 128-byte DDS header for DXT compressed texture (DXT1, DXT5)."""
    dw_magic = DDS_MAGIC
    dw_size = 124
    dw_flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE
    if mipmaps > 1:
        dw_flags |= DDSD_MIPMAPCOUNT
    dw_height = height
    dw_width = width
    block_size = 8 if fourcc == FOURCC_DXT1 else 16
    linear_size = max(1, ((width + 3) // 4)) * max(1, ((height + 3) // 4)) * block_size
    dw_depth = 0
    dw_mipmaps = mipmaps
    dw_reserved1 = b"\x00" * 44

    # Pixel format
    pf_size = 32
    pf_flags = DDPF_FOURCC
    pf_fourcc = fourcc
    pf_rgb_bits = 0
    pf_r_mask = 0
    pf_g_mask = 0
    pf_b_mask = 0
    pf_a_mask = 0

    pixel_format = struct.pack(
        "<II4sIIIII",
        pf_size,
        pf_flags,
        pf_fourcc,
        pf_rgb_bits,
        pf_r_mask,
        pf_g_mask,
        pf_b_mask,
        pf_a_mask,
    )

    dw_caps = DDSCAPS_TEXTURE
    if mipmaps > 1:
        dw_caps |= DDSCAPS_COMPLEX | DDSCAPS_MIPMAP
    dw_caps2 = 0
    dw_caps3 = 0
    dw_caps4 = 0
    dw_reserved2 = 0

    header_body = struct.pack(
        "<IIIIIII44s",
        dw_size,
        dw_flags,
        dw_height,
        dw_width,
        linear_size,
        dw_depth,
        dw_mipmaps,
        dw_reserved1,
    ) + pixel_format + struct.pack(
        "<IIIII",
        dw_caps,
        dw_caps2,
        dw_caps3,
        dw_caps4,
        dw_reserved2,
    )

    return dw_magic + header_body


def create_flat_normal_map_dds(width: int = 4, height: int = 4) -> bytes:
    """Creates a standard flat normal map DDS (RGB 128, 128, 255) for AC shaders."""
    header = build_dds_header_uncompressed_bgra(width, height)
    # BGRA: Blue=255, Green=128, Red=128, Alpha=255
    pixel = bytes([255, 128, 128, 255])
    return header + (pixel * (width * height))


def create_glass_tint_dds(width: int = 4, height: int = 4, alpha: int = 80) -> bytes:
    """Creates a subtle ice-blue transparent glass tint DDS texture for AC glass shaders."""
    header = build_dds_header_uncompressed_bgra(width, height)
    # BGRA: Blue=255, Green=235, Red=215, Alpha=alpha (e.g. 80/255 ~= 31% opacity)
    pixel = bytes([255, 235, 215, max(1, min(255, alpha))])
    return header + (pixel * (width * height))


def create_solid_color_dds(r: int = 255, g: int = 255, b: int = 255, a: int = 255, width: int = 4, height: int = 4) -> bytes:
    """Creates a solid color uncompressed BGRA DDS texture."""
    header = build_dds_header_uncompressed_bgra(width, height)
    pixel = bytes([b & 0xFF, g & 0xFF, r & 0xFF, a & 0xFF])
    return header + (pixel * (width * height))


def rgba_pixels_to_bgra_dds(pixels: list, width: int, height: int, fallback_alpha: float = 1.0) -> bytes:
    """
    Converts a flat list of normalized RGBA float pixels (from Blender image.pixels)
    into a complete uncompressed 32-bit BGRA DDS byte buffer.
    If image has completely zero/transparent alpha throughout, replaces with fallback_alpha.
    """
    header = build_dds_header_uncompressed_bgra(width, height)
    num_pixels = width * height
    pixel_data = bytearray(num_pixels * 4)

    # Check if image has non-zero alpha
    has_valid_alpha = any(pixels[i * 4 + 3] > 0.01 for i in range(min(num_pixels, 1000)))

    # Note: Blender pixels are stored bottom-to-top (row 0 is bottom).
    # DirectX DDS expects top-to-bottom! We flip rows during conversion.
    out_idx = 0
    for y in range(height - 1, -1, -1):
        row_start = y * width * 4
        for x in range(width):
            src_idx = row_start + x * 4
            r = int(min(max(pixels[src_idx], 0.0), 1.0) * 255.0)
            g = int(min(max(pixels[src_idx + 1], 0.0), 1.0) * 255.0)
            b = int(min(max(pixels[src_idx + 2], 0.0), 1.0) * 255.0)
            if has_valid_alpha:
                a_float = pixels[src_idx + 3]
            else:
                a_float = fallback_alpha
            a = int(min(max(a_float, 0.0), 1.0) * 255.0)

            # Store in BGRA order
            pixel_data[out_idx] = b
            pixel_data[out_idx + 1] = g
            pixel_data[out_idx + 2] = r
            pixel_data[out_idx + 3] = a
            out_idx += 4

    return header + bytes(pixel_data)


def save_dds_file(filepath: str, dds_data: bytes):
    """Saves raw DDS byte data to disk, ensuring directory existence."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(dds_data)

