# 🏎️ Assetto Corsa KN5 Studio for Blender

[![Blender](https://img.shields.io/badge/Blender-3.6%20%7C%204.x%20%7C%205.x-orange?logo=blender)](https://www.blender.org)
[![Version](https://img.shields.io/badge/version-2.6.0-blue)](blender_manifest.toml)
[![License](https://img.shields.io/badge/license-CC0--1.0-lightgrey)](LICENSE)
[![AC](https://img.shields.io/badge/Assetto%20Corsa-kn5%20v5%20%7C%20v6-red)]()

**All-in-one Assetto Corsa modding studio, directly inside Blender. No ksEditor needed.**

Export `.kn5` cars, tracks & objects, import any `.kn5` back for editing, manage AI lines (`.ai`), track splines (`.csv`), cameras (`.ini`) and material persistence (`.fbx.ini`) — with full Kunos shader support and CSP-ready presets.

> 🇹🇷 Türkçe özet aşağıda: [Türkçe Kurulum ve Kullanım](#-türkçe-kurulum-ve-kullanım)

---

## ✨ Why KN5 Studio?

| Before (ksEditor workflow) | With KN5 Studio |
|---|---|
| FBX → ksEditor → manual material fix → broken hierarchy | **One-click Export .kn5 from Blender** |
| Lost dummies, flipped normals, missing tangents | Preserved `WHEEL_*`, `SUSP_*`, `COCKPIT_HR`, custom normals, tangents, UVs |
| External DDS converters | Built-in pure-Python DDS packer (BGRA uncompressed) |
| Separate tools for AI / CSV / cameras | Integrated AI, spline, camera, lights, physics sync |

---

## 🚀 Features

### 1. Direct KN5 Export (v5 Universal + v6 DLC)
- Valid `.kn5` readable by AC, Content Manager and CSP
- `CAR_ROOT` dissolve logic — `WHEEL_*` always become root children for physics & showroom align
- Auto submesh split: `OBJ_SUB0`, `OBJ_SUB1` per material
- 65,535 vertex guard — auto-split on 16-bit index overflow
- Blender `(X,Y,Z)` → DirectX `(X,Z,-Y)` with correct winding, normals, tangents, `1.0-V` UV flip
- Embedded DDS or External reference modes
- Missing-texture fail-fast with `Audit / Repair` hint instead of silent black textures

### 2. Full KN5 Import
- Hierarchy, split normals, UVs, shader params rebuild
- Embedded DDS auto-extract to `/texture` and link to Principled BSDF
- Edit → re-export round-trip

### 3. 🎨 Kunos Shader System
`ksPerPixel`, `ksPerPixelNM`, `ksPerPixelNM_detail`, `ksPerPixelMultiMap`, `ksPerPixelMultiMap_damage_dirt`, `ksPerPixelAlpha`, `ksPerPixelReflection`, `ksPerPixelAT`, `ksPerPixelAT_NM`, `ksWindscreen`, `ksTyres`, `ksBrakeDisc`, `ksTree`, `ksGrass`, `GL`

One-click presets:
- 🚗 Car Paint / Chrome / Carbon / Interior Matte
- 🪟 Windscreen + Glass / Tire / Brake Disc+Glow
- 🛣️ `1ROAD`, `1KERB`, `1GRASS`, `1WALL` / Foliage Cutout / `GL` Emissive
- ⚡ **Auto-Detect by name** (`glass`, `bulb`, `chrome`, `tyre`, `body`, `1road`...) on import and on export

### 4. 🤖 AI Lines (`.ai`)
`fast_lane.ai` / `pit_lane.ai` read-write, left/right borders, 18 telemetry channels as separate meshes, fixed-width or mesh-based borders, reverse / shift start support.

### 5. 🛣️ Splines (`.csv`)
`side_l.csv`, `side_r.csv`, `groove.csv`, PoT `0.0-1.0` auto-calc, closed-loop / A2B hillclimb mode.

### 6. 📷 Cameras & Points (`.ini`)
`camera.ini`, `cameras.ini`, `overlay.ini`, `audio_sources.ini` ⇄ Empties or mesh spline.

### 7. 🪄 Extras for car modders
- Auto-Rig Wheels: typo fix `WHELL_RR`, `RIM/TYRE/DISC/CALIPER` → `WHEEL_*` / `SUSP_*` (calipers never spin)
- Driver rig: `DRIVER_POS`, `DRIVER_EYES`, `driver_base_pos.knh` import/export
- Camera rig: `AC_CAM_DRIVEREYES/BONNET/BUMPER/CHASE` ⇄ `car.ini [GRAPHICS]`
- Physics sync: wheelbase / track / tyre radius / `GRAPHICS_OFFSET` → `suspensions.ini`, `car.ini`, `tyres.ini`, `colliders.ini`, `aero.ini`
- Lights: auto-detect `GL` meshes → `data/lights.ini` + CSP `ext_config.ini` turn signals
- AO bake: Cycles AO → `EXT_body.dds` → sync to all `skins/*/`
- CSP PBR: `ext_config.ini` CarPaint Metallic + Chrome blocks

---

## 📦 Installation

Works on **Blender 3.6 LTS, 4.x, 5.0 / 5.2**.

**Option A — From Disk (recommended):**
1. Zip this folder as `KN5Export.zip` (keep `__init__.py` + `blender_manifest.toml` at root)
2. Blender → `Edit → Preferences → Add-ons → Install from Disk` (4.2+: `Get Extensions → Install from Disk`)
3. Enable `Assetto Corsa KN5 Studio`
4. `N-Panel → KN5 Studio` appears in 3D Viewport

**Option B — Dev sync (Windows):**
```powershell
.\sync_to_blender.ps1
```
Copies `*.py` to `%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\kn5_studio`

---

## ⚡ Quick Start

**Export car:**
1. `KN5 Studio → Validate Scene` → `Repair Links` if needed
2. `Auto-Rig Wheels & Rims`, `Auto-Configure All Materials`
3. `Export KN5` → `Embedded DDS`, `Version 5 Universal`

**Import for edit:**
`File → Import → Assetto Corsa (.kn5)` with `Extract Textures` on.

**Track AI:**
Select `ideal_line` mesh (+ `*_border_left/right`) → `File → Export → Assetto Corsa AI Line (.ai)`

File menu entries:
- Import: `.kn5`, `.ai`, `.csv`, `.ini`, `.fbx.ini`
- Export: `.kn5`, `.ai`, `.csv`, `.ini`

---

## 📁 Project Structure

```
KN5Export/
├── __init__.py          # Add-on entry, register/unregister
├── blender_manifest.toml# Blender 4.2+ extension manifest
├── kn5_format.py        # KN5 v5/v6 binary reader/writer
├── exporter.py          # Blender → KN5 (matrix, submesh, DDS pack)
├── importer.py          # KN5 → Blender (hierarchy, materials, DDS extract)
├── materials.py         # AC shaders, presets, node sync, audit/repair
├── dds.py               # Pure-Python DDS header/encode/decode
├── tools.py             # Car/track tools: rig, physics, cameras, lights, AO, rename
├── track_ai.py          # .ai load/save
├── track_csv.py         # .csv load/save
├── track_ini.py         # camera/checkpoint .ini
├── fbx_ini.py           # .fbx.ini persistence (ALPHABLEND/ALPHATEST)
├── ui.py                # N-Panel + Material/Object panels
└── constants.py         # Shaders, presets, name patterns
```

Coordinate convention used everywhere: `Blender (X,Y,Z) ⇄ AC (X,Z,-Y)`.

---

## 🛠️ Requirements & Notes

- No external binaries, no Pillow, no numpy — pure Blender Python + `struct`
- Textures embedded as uncompressed 32-bit BGRA DDS for max compatibility
- For tracks prefer `External References` mode (smaller KN5)
- `lights.ini` export enforces exact `lights.ini` filename in `car/data/`
- Animations: use `Create Door / Wiper Animation` → `Export FBX for ksEditor` → build `.ksanim` in ksEditor (KN5 itself stores no keyframes)

---

## ❓ Troubleshooting

| Problem | Fix |
|---|---|
| `export stopped ... missing images` | `KN5 Studio → Repair Links`, relink in `Material → Texture Slots` |
| Glass black / opaque | Name contains `glass/window`, Apply `GLASS_CLEAR` or `WINDSCREEN`, check `Alpha Blend` |
| Wheels don't spin / steer | Run `Auto-Rig Wheels`, ensure meshes under `WHEEL_LF/RF/LR/RR`, calipers under `SUSP_*` |
| `GRAPHICS_OFFSET` wrong | Run `Auto-Sync 3D Model to Physics INIs` or `Check Wheels vs INI` |
| Bulbs glow through body | Bulb meshes must be `Opaque`, not `Transparent` — use `LIGHT_BULBS_OPAQUE` |

Console (`Window → Toggle System Console`) always shows full export summary + warnings.

---

## 🇹🇷 Türkçe Kurulum ve Kullanım

**Kurulum (Blender 3.6 / 4.x / 5.x):**
1. Bu klasörü `KN5Export.zip` yap
2. `Düzenle → Tercihler → Eklentiler → Diskten Kur`
3. `Assetto Corsa KN5 Studio` eklentisini etkinleştir
4. 3D Viewport'ta `N → KN5 Studio` sekmesi açılır

**Hızlı Export:**
`Validate Scene` → `Auto-Rig Wheels` → `Auto-Configure All Materials` → `Export KN5 (Embedded DDS, Version 5)`

**Önemli:** Eksik doku varsa export durur, `Audit / Repair Textures` ile bağla. Cam için `GLASS_CLEAR`, far arkası ampul için opaque `LIGHT_BULBS_OPAQUE` kullan. Kaliperler `SUSP_*` altında olmalı, dönmemeli.

---

## 🤝 Contributing

1. Fork → feature branch → PR
2. `python -m py_compile *.py` temiz olmalı
3. Blender 3.6 ve 4.x/5.x'te test edin
4. Kişisel path eklemeyin (`tools.py:find_car_data_dir` gibi)

## 👥 Credits

- Antigravity & Fatih — core KN5 import/export, shader & rig systems
- leBluem AC CSV/AI tools integration
- Kunos Simulazioni — Assetto Corsa format reference

## 📄 License

CC0 1.0 Universal — see `LICENSE`.
You can copy, modify, distribute and use for any purpose, including commercial, without asking permission.

---
*Teams / issues / screenshots PR'ları hoş geldiniz — iyi modlamalar! 🏁*
