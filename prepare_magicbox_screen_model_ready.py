"""Make the real 2-panel LED mesh, not the virtual artwork, the opening viewport."""

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Lscreen_magicbox_SCREEN_MODEL_READY.blend"
REVIEW = ROOT / "renders" / "magicbox_editable_validation" / "07_实体L屏模型_斜视角检查.png"
REPORT = ROOT / "renders" / "magicbox_editable_validation" / "实体L屏几何检查.txt"


def set_excluded(layer, collection_name, excluded):
    def walk(node):
        if node.collection.name == collection_name:
            node.exclude = excluded
            return True
        return any(walk(child) for child in node.children)
    if not walk(layer.layer_collection):
        raise RuntimeError(f"Collection not found in view layer: {collection_name}")


def panel_geometry(obj):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if len(verts) != 4:
        raise AssertionError(f"Expected one quad for {obj.name}, got {len(verts)} vertices")
    edges = [float((verts[(i + 1) % 4] - verts[i]).length) for i in range(4)]
    horizontal = (verts[1] - verts[0]).normalized()
    vertical = (verts[3] - verts[0]).normalized()
    normal = horizontal.cross(vertical).normalized()
    return verts, edges, normal


def material_image(obj):
    if not obj.data.materials:
        return None
    for node in obj.data.materials[0].node_tree.nodes:
        if node.type == "TEX_IMAGE":
            return node.image
    return None


def main():
    scene = bpy.context.scene
    main_led = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_led = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    model_layer = scene.view_layers["01_编辑虚拟盒子"]
    playback_layer = scene.view_layers["02_检查实体双屏"]
    screen_coll = bpy.data.collections["03_PHYSICAL_LED_PREVIEW"]
    screen_coll.hide_viewport = False
    screen_coll.hide_render = False
    for obj in (main_led, side_led):
        obj.hide_viewport = False
        obj.hide_render = False
        obj.hide_set(False)

    main_v, main_edges, main_normal = panel_geometry(main_led)
    side_v, side_edges, side_normal = panel_geometry(side_led)
    edge_length = (main_v[1] - side_v[0]).length
    top_edge_length = (main_v[2] - side_v[3]).length
    angle = math.degrees(math.acos(max(-1.0, min(1.0, main_normal.dot(side_normal)))))
    for name, edges in ((main_led.name, main_edges), (side_led.name, side_edges)):
        if not all(abs(edges[i] - expected) < 1e-5 for i, expected in enumerate((2.5, 4.5, 2.5, 4.5))):
            raise AssertionError(f"Incorrect edge lengths on {name}: {edges}")
    if edge_length > 1e-5 or top_edge_length > 1e-5 or abs(angle - 90.0) > 1e-5:
        raise AssertionError(f"Incorrect corner: bottom={edge_length}, top={top_edge_length}, angle={angle}")
    if abs(min(v.z for v in main_v + side_v)) > 1e-6:
        raise AssertionError("LED lower edge is not on the floor (Z=0)")

    main_img = material_image(main_led)
    side_img = material_image(side_led)
    if not main_img or not side_img or not main_img.packed_file or not side_img.packed_file:
        raise AssertionError("LED panel textures are missing or not packed into the .blend")
    if (main_img.size[0], main_img.size[1]) != (1000, 1800) or (side_img.size[0], side_img.size[1]) != (1000, 1800):
        raise AssertionError("Unexpected preview pixel dimensions")

    # Open in a perspective 3D viewport, with the physical textured L screen
    # selected as the active layer. No render image is used as the interface.
    scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.shading.type = "MATERIAL"
            space.region_3d.view_perspective = "PERSP"
            space.region_3d.view_rotation = scene.camera.rotation_euler.to_quaternion()
            space.region_3d.view_location = Vector((-.30, .30, 2.25))
            space.region_3d.view_distance = 7.0
            space.overlay.show_overlays = True
            space.overlay.show_floor = True
            space.overlay.show_axis_x = True
            space.overlay.show_axis_y = True

    if bpy.context.window:
        bpy.context.window.view_layer = playback_layer

    scene["默认显示"] = "02_检查实体双屏；在三维视图材质模式下直接观察两个贴有预畸变图的LED网格面"
    scene["屏幕几何核对"] = "主屏2.5x4.5m; 侧屏2.5x4.5m; 夹角90deg; 两面共用一条4.5m竖边; 下缘Z=0"
    scene["提示"] = "改看时空盒可切视图层 01_编辑虚拟盒子；其顶盖和底座不是实体LED"

    # A second camera documents that the art is physically attached to an L,
    # not a single front-facing picture plane. This image is supplementary;
    # the .blend opens in the editable viewport above.
    camera_data = bpy.data.cameras.new("CAM_SCREEN_MODEL_OBLIQUE_DATA")
    oblique = bpy.data.objects.new("CAM_SCREEN_MODEL_OBLIQUE", camera_data)
    bpy.data.collections["04_PROJECTION_CAMERAS"].objects.link(oblique)
    oblique.location = (5.1, -7.0, 3.0)
    direction = Vector((-.35, .35, 2.25)) - oblique.location
    oblique.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 39.0
    scene.camera = oblique
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(REVIEW)
    for layer in scene.view_layers:
        layer.use = (layer == playback_layer)
    bpy.ops.render.render(write_still=True)
    scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    scene.render.resolution_x = 1254
    scene.render.resolution_y = 1254
    model_layer.use = True
    playback_layer.use = True
    if bpy.context.window:
        bpy.context.window.view_layer = playback_layer

    lines = [
        "REAL PHYSICAL L LED MESH CHECK",
        f"Main quad world vertices: {[tuple(round(c, 5) for c in v) for v in main_v]}",
        f"Side quad world vertices: {[tuple(round(c, 5) for c in v) for v in side_v]}",
        f"Main edges (m): {[round(x, 5) for x in main_edges]}",
        f"Side edges (m): {[round(x, 5) for x in side_edges]}",
        f"Face-normal angle (deg): {angle:.5f}",
        f"Shared bottom / top corner distance (m): {edge_length:.6f} / {top_edge_length:.6f}",
        f"Floor contact Z (m): {min(v.z for v in main_v + side_v):.6f}",
        f"Main texture: {main_img.name} {tuple(main_img.size)} packed={bool(main_img.packed_file)}",
        f"Side texture: {side_img.name} {tuple(side_img.size)} packed={bool(side_img.packed_file)}",
        "Pixel dimensions above are for simulation, not the customer's approved controller map.",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=False)
    print("\n".join(lines), flush=True)
    print(f"SCREEN_MODEL_READY={OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
