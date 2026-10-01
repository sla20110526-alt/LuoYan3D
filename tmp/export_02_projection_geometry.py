"""Read the active physical L screen and sweet spot from the opened blend."""

import json
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view


root = Path(bpy.data.filepath).parent
out_dir = root / "renders" / "02_m4v_inverse_projection_test"
out_dir.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
source_size = (960, 960)


def projected_panel(name):
    obj = bpy.data.objects[name]
    assert obj.type == "MESH" and len(obj.data.polygons) == 1, name
    points = []
    for index in obj.data.polygons[0].vertices:
        world = obj.matrix_world @ obj.data.vertices[index].co
        uv = world_to_camera_view(scene, camera, world)
        points.append([uv.x * (source_size[0] - 1), (1 - uv.y) * (source_size[1] - 1)])
    return {"name": name, "dimensions_m": list(obj.dimensions), "quad_bl_br_tr_tl": points}


scene.camera = camera
scene.render.resolution_x, scene.render.resolution_y = source_size
scene.render.resolution_percentage = 100
payload = {
    "source_blend": bpy.data.filepath,
    "source_video": str(root / "视频" / "02.m4v"),
    "source_size": list(source_size),
    "fps": 24,
    "frames": 360,
    "panel_size": [1000, 1800],
    "camera": {
        "name": camera.name,
        "location": list(camera.location),
        "rotation_euler": list(camera.rotation_euler),
        "lens_mm": camera.data.lens,
    },
    "main": projected_panel("LED_MAIN_2.5x4.5m"),
    "side": projected_panel("LED_SIDE_2.5x4.5m"),
}
dest = out_dir / "projection_geometry.json"
dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("PROJECTION_GEOMETRY=" + str(dest), flush=True)
