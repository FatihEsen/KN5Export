# Assetto Corsa KN5 Studio - Constants and Definitions
# Developed for Blender 3.6 LTS, 4.x, and 5.x

import re
import os


KN5_MAGIC = b"sc6969"
SUPPORTED_VERSIONS = (5, 6)
DEFAULT_VERSION = 5

# Node Types
NODE_TYPE_DUMMY = 1
NODE_TYPE_MESH = 2
NODE_TYPE_SKINNED = 3

NODE_TYPE_NAMES = {
    NODE_TYPE_DUMMY: "Dummy / Node",
    NODE_TYPE_MESH: "Mesh",
    NODE_TYPE_SKINNED: "Skinned Mesh",
}

# Material Blend Modes
BLEND_OPAQUE = 0
BLEND_ALPHA_BLEND = 1
BLEND_ALPHA_TO_COVERAGE = 2

MATERIAL_BLEND_MODES = [
    ("0", "Opaque", "Standard opaque geometry (no transparency)", 0),
    ("1", "Alpha Blend", "Smooth alpha blending (glass, smoke, soft gradients)", 1),
    ("2", "Alpha to Coverage", "Screen-door / MSAA alpha testing (foliage, grilles)", 2),
]

# Material Depth Modes
DEPTH_NORMAL = 0
DEPTH_NO_WRITE = 1
DEPTH_OFF = 2

MATERIAL_DEPTH_MODES = [
    ("0", "Normal", "Standard depth testing and writing", 0),
    ("1", "No Write", "Depth test enabled, depth write disabled (transparent surfaces)", 1),
    ("2", "Off", "Depth test and depth write disabled", 2),
]

# Standard Assetto Corsa Shaders
AC_SHADERS = [
    ("ksPerPixel", "ksPerPixel (Basic Diffuse)", "Standard diffuse lighting without normal map"),
    ("ksPerPixelNM", "ksPerPixelNM (Normal Map)", "Diffuse lighting with tangent-space normal map"),
    ("ksPerPixelNM_detail", "ksPerPixelNM_detail", "Diffuse + Normal Map + Detail Normal/Diffuse Map"),
    ("ksPerPixelMultiMap", "ksPerPixelMultiMap (PBR MultiMap)", "MultiMap texture with txMaps (Red: Specular, Green: Gloss, Blue: AO)"),
    ("ksPerPixelMultiMap_damage_dirt", "ksPerPixelMultiMap_damage_dirt (Car Body Paint)", "Full vehicle body paint with dirt, damage, and clearcoat"),
    ("ksPerPixelAlpha", "ksPerPixelAlpha (Transparent)", "Alpha-blended surface for decals, gauges, soft glass"),
    ("ksPerPixelReflection", "ksPerPixelReflection (Reflective Glass)", "Dynamic cubemap reflection + alpha transparency for vehicle windows/glass"),
    ("ksPerPixelAT", "ksPerPixelAT (Alpha Cutout)", "Hard alpha cutout for fences, grilles, trees"),
    ("ksPerPixelAT_NM", "ksPerPixelAT_NM (Cutout + Normal)", "Hard alpha cutout with normal map"),
    ("ksWindscreen", "ksWindscreen (Cockpit Glass)", "Windscreen glass shader with wiper mask and reflections"),
    ("ksTyres", "ksTyres (Tire Rubber)", "Tire shader with dynamic rotation blur slot"),
    ("ksBrakeDisc", "ksBrakeDisc (Brake Glow)", "Brake disc shader with temperature glowing emission"),
    ("ksTree", "ksTree (Foliage/Trees)", "Vegetation shader optimized for leaves and tree branches"),
    ("ksGrass", "ksGrass (Track Grass)", "Track terrain grass shader with detail overlay"),
    ("GL", "GL (Additive Emissive)", "Additive glowing shader for dashboard warning lights, headlights, and flares"),
]

# Standard Texture Slot Names per Shader
SHADER_TEXTURE_SLOTS = {
    "ksPerPixel": ["txDiffuse"],
    "ksPerPixelNM": ["txDiffuse", "txNormal"],
    "ksPerPixelNM_detail": ["txDiffuse", "txNormal", "txDetail"],
    "ksPerPixelMultiMap": ["txDiffuse", "txNormal", "txMaps", "txDetail"],
    "ksPerPixelMultiMap_damage_dirt": ["txDiffuse", "txNormal", "txMaps", "txDetail", "txDamage", "txDust"],
    "ksPerPixelAlpha": ["txDiffuse"],
    "ksPerPixelReflection": ["txDiffuse"],
    "ksPerPixelAT": ["txDiffuse"],
    "ksPerPixelAT_NM": ["txDiffuse", "txNormal"],
    "ksWindscreen": ["txDiffuse", "txNormal", "txMask"],
    "ksTyres": ["txDiffuse", "txNormal", "txBlur"],
    "ksBrakeDisc": ["txDiffuse", "txNormal", "txGlow"],
    "ksTree": ["txDiffuse"],
    "ksGrass": ["txDiffuse", "txVariation"],
    "GL": ["txDiffuse"],
}

# Default Shader Properties and recommended values
DEFAULT_SHADER_PROPERTIES = {
    "ksAmbient": 0.40,
    "ksDiffuse": 0.40,
    "ksSpecular": 0.30,
    "ksSpecularEXP": 50.0,
    "fresnelC": 0.08,
    "fresnelEXP": 4.5,
    "fresnelMaxLevel": 0.70,
    "isAdditive": 0.0,
    "useDetail": 0.0,
    "detailUVMultiplier": 1.0,
}

# Pre-defined Material Presets for 1-click professional setups
MATERIAL_PRESETS = {
    "CAR_PAINT": {
        "label": "Car Paint (Gloss & Reflection)",
        "shader": "ksPerPixel",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 0.30,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.75,
            "ksSpecularEXP": 140.0,
            "fresnelC": 0.10,
            "fresnelEXP": 4.5,
            "fresnelMaxLevel": 0.88,
        },
    },
    "CHROME": {
        "label": "Chrome / Rim Alloy (Reflective)",
        "shader": "ksPerPixelReflection",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 0.20,
            "ksDiffuse": 0.20,
            "ksSpecular": 3.00,
            "ksSpecularEXP": 350.0,
            "fresnelC": 0.65,
            "fresnelEXP": 1.8,
            "fresnelMaxLevel": 0.98,
            "isAdditive": 0.0,
        },
    },
    "GLASS_CLEAR": {
        "label": "Glass (Transparent Reflective Windows)",
        "shader": "ksPerPixelReflection",
        "blend_mode": BLEND_ALPHA_BLEND,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 0.10,
            "ksDiffuse": 0.10,
            "ksSpecular": 4.00,
            "ksSpecularEXP": 450.0,
            "fresnelC": 0.10,
            "fresnelEXP": 2.8,
            "fresnelMaxLevel": 0.65,
            "isAdditive": 0.0,
        },
    },
    "WINDSCREEN": {
        "label": "Cockpit Windscreen (with Wiper Mask)",
        "shader": "ksWindscreen",
        "blend_mode": BLEND_ALPHA_BLEND,
        "alpha_tested": False,
        "depth_mode": DEPTH_NO_WRITE,
        "slots": ["txDiffuse", "txNormal", "txMask"],
        "props": {
            "ksAmbient": 0.20,
            "ksDiffuse": 0.10,
            "ksSpecular": 0.90,
            "ksSpecularEXP": 120.0,
            "fresnelC": 0.15,
            "fresnelEXP": 4.2,
            "fresnelMaxLevel": 0.85,
        },
    },
    "CARBON_FIBER": {
        "label": "Carbon Fiber / Composite",
        "shader": "ksPerPixelNM_detail",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal", "txDetail"],
        "props": {
            "ksAmbient": 0.30,
            "ksDiffuse": 0.30,
            "ksSpecular": 0.50,
            "ksSpecularEXP": 40.0,
            "fresnelC": 0.10,
            "fresnelEXP": 4.5,
            "fresnelMaxLevel": 0.60,
            "useDetail": 1.0,
            "detailUVMultiplier": 25.0,
        },
    },
    "TIRE_RUBBER": {
        "label": "Tire Rubber",
        "shader": "ksTyres",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal", "txBlur"],
        "props": {
            "ksAmbient": 0.30,
            "ksDiffuse": 0.35,
            "ksSpecular": 0.15,
            "ksSpecularEXP": 12.0,
            "fresnelC": 0.05,
            "fresnelEXP": 5.0,
            "fresnelMaxLevel": 0.25,
        },
    },
    "BRAKE_DISC": {
        "label": "Brake Disc (with Glow slot)",
        "shader": "ksBrakeDisc",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal", "txGlow"],
        "props": {
            "ksAmbient": 0.40,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.60,
            "ksSpecularEXP": 60.0,
        },
    },
    "BRAKE_CALIPER": {
        "label": "Brake Caliper (Metal)",
        "shader": "ksPerPixelNM",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal"],
        "props": {
            "ksAmbient": 0.35,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.40,
            "ksSpecularEXP": 35.0,
            "fresnelC": 0.08,
            "fresnelEXP": 4.5,
            "fresnelMaxLevel": 0.50,
        },
    },
    "INTERIOR_MATTE": {
        "label": "Interior Plastic / Leather (Matte)",
        "shader": "ksPerPixelNM",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal"],
        "props": {
            "ksAmbient": 0.30,
            "ksDiffuse": 0.35,
            "ksSpecular": 0.12,
            "ksSpecularEXP": 15.0,
            "fresnelC": 0.04,
            "fresnelEXP": 5.0,
            "fresnelMaxLevel": 0.20,
        },
    },
    "ROAD_ASPHALT": {
        "label": "Track Road Asphalt (1ROAD)",
        "shader": "ksPerPixelNM_detail",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal", "txDetail"],
        "props": {
            "ksAmbient": 0.35,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.20,
            "ksSpecularEXP": 25.0,
            "fresnelC": 0.04,
            "fresnelEXP": 5.0,
            "fresnelMaxLevel": 0.30,
            "useDetail": 1.0,
            "detailUVMultiplier": 60.0,
        },
    },
    "KERB_CURB": {
        "label": "Track Kerb / Curb (1KERB)",
        "shader": "ksPerPixelNM_detail",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal", "txDetail"],
        "props": {
            "ksAmbient": 0.40,
            "ksDiffuse": 0.45,
            "ksSpecular": 0.25,
            "ksSpecularEXP": 30.0,
            "useDetail": 1.0,
            "detailUVMultiplier": 40.0,
        },
    },
    "GRASS_TERRAIN": {
        "label": "Track Grass Terrain (1GRASS)",
        "shader": "ksGrass",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txVariation"],
        "props": {
            "ksAmbient": 0.40,
            "ksDiffuse": 0.45,
            "ksSpecular": 0.05,
            "ksSpecularEXP": 5.0,
        },
    },
    "WALL_BARRIER": {
        "label": "Track Wall / Armco Barrier (1WALL)",
        "shader": "ksPerPixelNM",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse", "txNormal"],
        "props": {
            "ksAmbient": 0.40,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.30,
            "ksSpecularEXP": 40.0,
        },
    },
    "FOLIAGE_CUTOUT": {
        "label": "Foliage / Fences (Alpha Cutout)",
        "shader": "ksPerPixelAT",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": True,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 0.40,
            "ksDiffuse": 0.45,
            "ksSpecular": 0.05,
            "ksSpecularEXP": 8.0,
        },
    },
    "LIGHT_BULBS_OPAQUE": {
        "label": "Headlight Bulbs / Reflectors (Opaque)",
        "shader": "ksPerPixel",
        "blend_mode": BLEND_OPAQUE,
        "alpha_tested": False,
        "depth_mode": DEPTH_NORMAL,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 0.35,
            "ksDiffuse": 0.40,
            "ksSpecular": 0.50,
            "ksSpecularEXP": 40.0,
        },
    },
    "LIGHT_EMISSIVE_GL": {
        "label": "Light Glow / Dash Warning (GL Additive)",
        "shader": "GL",
        "blend_mode": BLEND_ALPHA_BLEND,
        "alpha_tested": False,
        "depth_mode": DEPTH_NO_WRITE,
        "slots": ["txDiffuse"],
        "props": {
            "ksAmbient": 1.0,
            "ksDiffuse": 1.0,
            "isAdditive": 1.0,
        },
    },
}

# Standard Track Objects and Prefixes
TRACK_SURFACES = [
    ("1ROAD", "Road (High Grip Physics Surface)", "Drivable road asphalt/tarmac"),
    ("1KERB", "Kerb / Curb", "Track kerb with rumble physics"),
    ("1GRASS", "Grass", "Off-track grass with reduced grip"),
    ("1SAND", "Sand / Gravel Trap", "Runoff sand/gravel that decelerates cars"),
    ("1WALL", "Wall / Barrier", "Rigid collision barrier"),
    ("2ROAD", "Non-Collidable Road / Detail", "Visual road element without collision"),
]

# Track Spawn Point Patterns
TRACK_DUMMIES = [
    ("AC_START_", "Grid Start Position", "Starting grid slot (e.g. AC_START_0, AC_START_1)"),
    ("AC_PIT_", "Pit Box Spawn", "Pit lane stall location (e.g. AC_PIT_0)"),
    ("AC_HOTLAP_START_", "Hotlap Spawn", "Location for practice/hotlap session start"),
    ("AC_TIME_0_L", "Split / Lap Timer Left Gate", "Left post of timing checkpoint gate"),
    ("AC_TIME_0_R", "Split / Lap Timer Right Gate", "Right post of timing checkpoint gate"),
    ("AC_AUDIO_REVERB", "Audio Reverb Zone", "Triggers acoustic reverb environmental effect"),
    ("AC_CREW_", "Pit Crew Position", "Location where pit crew models appear"),
]

# Vehicle Standard Dummy Hierarchy
CAR_DUMMIES = [
    ("SUSP_LF", "Suspension Front-Left"),
    ("SUSP_RF", "Suspension Front-Right"),
    ("SUSP_LR", "Suspension Rear-Left"),
    ("SUSP_RR", "Suspension Rear-Right"),
    ("WHEEL_LF", "Wheel Front-Left"),
    ("WHEEL_RF", "Wheel Front-Right"),
    ("WHEEL_LR", "Wheel Rear-Left"),
    ("WHEEL_RR", "Wheel Rear-Right"),
    ("COCKPIT_HR", "Cockpit High-Res Interior"),
    ("STEER_HR", "Steering Wheel High-Res"),
]

# Intelligent Material Name Patterns for Auto-Configuration
MATERIAL_NAME_PATTERNS = [
    # 1. Windscreen / Windshield
    (r"(?:windscreen|windshield|wind_shield|on_cam|oncam)", "WINDSCREEN"),
    # 2. Glass / Transparent Windows / Headlight Outer Glass / Defroster
    (r"(?:glass|window|cam(?:\b|_)|vetro|vitre|fenster|defrost|far_cam|stop_cam)", "GLASS_CLEAR"),
    # 3. Light Bulbs, Interior Headlight Reflectors (Opaque geometry behind glass)
    (r"(?:bulb|bulbs|ampul|reflector|faro_interno)", "LIGHT_BULBS_OPAQUE"),
    # 4. Emissive / Dashboard Glow / Additive Warning Lights
    (r"(?:glow|emissive|isadditive|dial|dash_warning|gauge_glow|dash_light)", "LIGHT_EMISSIVE_GL"),
    # 4. Chrome / Mirrors / Reflective Silver
    (r"(?:chrome|krom|mirror|ayna|espejo|spiegel|silver_gloss)", "CHROME"),
    # 5. Carbon Fiber
    (r"(?:carbon|karbon)", "CARBON_FIBER"),
    # 6. Tyres / Tires / Rubber
    (r"(?:tyre|tire|rubber|lastik|pneu|reifen)", "TIRE_RUBBER"),
    # 7. Brake Caliper (Metal Painted)
    (r"(?:caliper|kaliper|pinza)", "BRAKE_CALIPER"),
    # 7.1 Brake Disc / Rotor
    (r"(?:rotor|brake|disc|disk|disque|fren)", "BRAKE_DISC"),
    # 8. Car Paint / Bodywork / Chassis / Skin
    (r"(?:body|carpaint|paint|exterior|ext_body|chassis|skin|kaporta|livery|boya)", "CAR_PAINT"),
    # 9. Interior / Leather / Plastic / Fabric / Matte
    (r"(?:plastic|plastik|interior|int_|cuero|leather|deri|cloth|kumas|kumaş|fabric|dash|steering|direksiyon|seat|koltuk)", "INTERIOR_MATTE"),
    # 10. Track Road Surfaces
    (r"(?:1road|\broad\b|asphalt|asfalt|tarmac|pavement|sidewalk)", "ROAD_ASPHALT"),
    # 11. Track Kerb
    (r"(?:1kerb|\bkerb\b|\bcurb\b)", "KERB_CURB"),
    # 12. Track Grass Terrain
    (r"(?:1grass|\bgrass\b|çim|cim)", "GRASS_TERRAIN"),
    # 13. Track Wall / Barriers
    (r"(?:1wall|\bwall\b|barrier|armco|guardrail|duvar)", "WALL_BARRIER"),
    # 14. Foliage / Cutout Vegetation
    (r"(?:tree|leaf|leaves|foliage|agac|ağaç|yaprak|fence|cutout)", "FOLIAGE_CUTOUT"),
]


def match_material_preset(material_name: str):
    """
    Intelligently identifies the best matching Assetto Corsa material preset based on name.
    Returns preset key (e.g. 'GLASS_CLEAR', 'LIGHT_EMISSIVE_GL', 'CAR_PAINT') or None.
    """
    if not material_name:
        return None

    # Clean name: remove Blender duplicate suffixes like .001, submesh suffixes like _SUB0
    clean = re.sub(r"\.\d+$", "", material_name)
    clean = re.sub(r"_SUB\d+$", "", clean, flags=re.IGNORECASE)
    clean = clean.strip().lower()

    for pattern, preset_key in MATERIAL_NAME_PATTERNS:
        if re.search(pattern, clean, flags=re.IGNORECASE):
            if preset_key in MATERIAL_PRESETS:
                return preset_key

    return None


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


