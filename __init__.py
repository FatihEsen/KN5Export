# Assetto Corsa KN5 Studio
# High-precision exporter, importer, AI line, track spline, camera, and material toolset for Assetto Corsa.
# Compatible with Blender 3.6 LTS, 4.x, and 5.x.

bl_info = {
    "name": "Assetto Corsa KN5 Studio",
    "author": "Antigravity & Fatih (with leBluem AC CSV/AI tools)",
    "version": (2, 6, 0),
    "blender": (3, 6, 0),
    "location": "File > Import/Export > Assetto Corsa & 3D Viewport Sidebar > KN5 Studio",
    "description": "Assetto Corsa KN5 3D model importer/exporter, AI Line (.ai), Track Splines (.csv), Cameras/Checkpoints (.ini), and .fbx.ini material persistence toolset.",
    "doc_url": "https://github.com",
    "tracker_url": "",
    "category": "Import-Export",
}

import bpy

if "materials" in globals() or "materials" in locals():
    import importlib
    for _name in ("materials", "tools", "exporter", "importer", "track_ai", "track_csv", "track_ini", "fbx_ini", "ui"):
        if _name in globals() and globals()[_name] is not None:
            try:
                importlib.reload(globals()[_name])
            except Exception:
                pass

try:
    from . import materials
    from . import tools
    from . import exporter
    from . import importer
    from . import track_ai
    from . import track_csv
    from . import track_ini
    from . import fbx_ini
    from . import ui
except (ImportError, ValueError):
    import materials
    import tools
    import exporter
    import importer
    import track_ai
    import track_csv
    import track_ini
    import fbx_ini
    import ui


def register():
    materials.register()
    tools.register()
    exporter.register()
    importer.register()
    track_ai.register()
    track_csv.register()
    track_ini.register()
    fbx_ini.register()
    ui.register()


def unregister():
    ui.unregister()
    fbx_ini.unregister()
    track_ini.unregister()
    track_csv.unregister()
    track_ai.unregister()
    importer.unregister()
    exporter.unregister()
    tools.unregister()
    materials.unregister()


if __name__ == "__main__":
    register()
