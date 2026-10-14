# 🏎️ Assetto Corsa KN5 Studio - Comprehensive Guide & Documentation

This directory contains technical guides, workflow documentation, and architecture references for **Assetto Corsa KN5 Studio**.

---

## 📑 Table of Contents
1. [Car Modding Workflow (Zero to KN5)](#1-car-modding-workflow-zero-to-kn5)
2. [Batch LOD Export Guide](#2-batch-lod-export-guide)
3. [Kunos Shader & CSP PBR Presets](#3-kunos-shader--csp-pbr-presets)
4. [Track Modding: AI Lines & Splines](#4-track-modding-ai-lines--splines)
5. [Physics & Camera Synchronization](#5-physics--camera-synchronization)
6. [Troubleshooting & Common Pitfalls](#6-troubleshooting--common-pitfalls)

---

## 1. Car Modding Workflow (Zero to KN5)

### Step 1: Hierarchy Setup
Assetto Corsa requires a strict node structure:
* **Direct Wheel Dummies**: `WHEEL_LF`, `WHEEL_RF`, `WHEEL_LR`, `WHEEL_RR` must be direct children of the model root (no intermediate dummy like `CAR_ROOT`).
* **Calipers**: Brake calipers must be parented under `SUSP_LF/RF/LR/RR` so they turn with steering but never spin with wheels.
* **One-Click Rigging**: In the N-Panel (`KN5 Studio`), click **`Auto-Rig Wheels & Rims`**.

### Step 2: Pre-Flight Check & Diagnostics
1. Click **`Validate Scene`**: checks for non-uniform object scale, missing UV maps, unapplied rotations, and vertex count limits.
2. Click **`Audit Textures`**: verifies all mapped texture files exist on disk or packed in Blender.
3. Click **`Repair Links`**: automatically resolves relative and case-insensitive paths.

### Step 3: Export
* **File > Export > Assetto Corsa (.kn5)**
* Select `Embedded DDS` (recommended for cars) or `External References`.
* Choose `Version 5 (Universal)` for maximum compatibility across original AC, Content Manager, and CSP.

---

## 2. Batch LOD Export Guide

Assetto Corsa uses separate `.kn5` models for distance level-of-detail and collisions:
- `[car_name].kn5` (Main model / LOD 0)
- `[car_name]_lod_b.kn5` (Mid distance)
- `[car_name]_lod_c.kn5` (Far distance)
- `[car_name]_lod_d.kn5` (Ultra-far / low poly)
- `collider.kn5` (Simplified collision mesh)

### Setup in Blender:
Create collections in your scene using standard naming:
```
Scene Collection
├── LOD_A      # (or LOD0, main)
├── LOD_B      # (or LOD1)
├── LOD_C      # (or LOD2)
├── LOD_D      # (or LOD3)
└── COLLIDER   # (or Collision)
```

### Running Batch Export:
1. In the N-Panel, click **`Batch Export LODs`** (or `File > Export > Assetto Corsa Batch LODs (.kn5)`).
2. Choose your car root directory and specify the base car name (e.g. `supra_mk4`).
3. The exporter will detect each collection and generate all matching `.kn5` files simultaneously.

---

## 3. Kunos Shader & CSP PBR Presets

KN5 Studio supports native Kunos Direct3D 9 shaders and modern CSP (Custom Shaders Patch) PBR extensions.

| Preset | AC Shader | Key Properties | CSP ext_config.ini Block |
|---|---|---|---|
| **Car Paint** | `ksPerPixel` / `ksPerPixelNM` | `ksSpecular=0.75`, `fresnelC=0.1` | `[Material_CarPaint_Metallic]` with FlakesK |
| **Clear Glass** | `ksPerPixelAlpha` | BlendMode=AlphaBlend, Depth=Normal | `[Material_Glass]` with Refraction Thickness |
| **Windscreen** | `ksWindscreen` | BlendMode=AlphaBlend, RainFX ready | `[Material_Windscreen]` with RainFX wipe pass |
| **Chrome** | `ksPerPixelReflection` | `ksSpecular=0.9`, High reflection | `[Material_Chrome]` Metalness=0.95 |
| **Tyres** | `ksTyres` | Low specular, tire deformation ready | Standard PBR |
| **Brake Discs** | `ksBrakeDisc` | Heat glow binding on secondary UV | Glowing brake disc effects |

To automatically generate CSP PBR blocks, click **`Generate CSP Config (ext_config.ini)`** in the Material Tools panel.

---

## 4. Track Modding: AI Lines & Splines

### AI Lines (`.ai`)
* **`fast_lane.ai`**: The optimal racing line for bots.
* **`pit_lane.ai`**: Pit entry, speed limiter, and exit lane.
* **Importing**: `File > Import > Assetto Corsa AI Line (.ai)`. Generates the ideal path and left/right physical track limits.
* **Exporting**: Select your path mesh and choose `File > Export > Assetto Corsa AI Line (.ai)`.

### Track Splines (`.csv`)
* `side_l.csv` and `side_r.csv` dictate physical track boundaries for off-track penalties.
* `groove.csv` defines dynamic rubbering and tire marks.
* Built-in tools automatically calculate `0.0 - 1.0` PoT (Percentage of Track) along the spline.

---

## 5. Physics & Camera Synchronization

* **`Auto-Sync 3D Model to Physics INIs`**:
  Calculates actual 3D wheelbase, front/rear track widths, tyre radii, and `GRAPHICS_OFFSET`, then previews or updates `suspensions.ini` and `car.ini`.
* **Cameras**:
  Generates `AC_CAM_DRIVEREYES`, `AC_CAM_BONNET`, `AC_CAM_BUMPER`, and chase empties aligned with real driver viewpoints.
* **Lights**:
  Detects all `GL` emissive meshes and writes `data/lights.ini` + CSP turning indicator sections.

---

## 6. Troubleshooting & Common Pitfalls

1. **Missing texture warnings on export:**
   - Run `Audit Textures` to find broken relative paths, then `Repair Links`.
2. **Glass appears completely opaque or black in AC:**
   - Ensure the material blend mode is set to `Alpha Blend` (mode 1) and depth mode is `Normal` (mode 0).
3. **Wheels do not rotate or steer in game:**
   - Check that wheel meshes are parented to `WHEEL_LF/RF/LR/RR` and the dummy transforms are at the center of the wheel hubs. Run `Auto-Rig Wheels & Rims`.
4. **Vertex limit overflow:**
   - KN5 Studio automatically splits meshes exceeding 65,535 vertices into `_SUB0`, `_SUB1` submeshes. No manual chopping needed.
