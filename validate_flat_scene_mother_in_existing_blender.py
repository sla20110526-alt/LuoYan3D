"""Place the square unfolded candidate on the existing two physical LED faces.

Run with Blender in background using Lscreen_magicbox_SCREEN_MODEL_READY.blend.
This writes a separate inspection .blend and renders; it never saves over the source.
"""

from pathlib import Path

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "图片" / "资产" / "沙棘时空盒_1比1双屏展开平面_候选v1.png"
OUT = ROOT / "renders" / "flat_scene_mother_blender_check_v1"
OUT.mkdir(parents=True, exist_ok=True)
MAIN_NAME = "LED_MAIN_2.5x4.5m"
SIDE_NAME = "LED_SIDE_2.5x4.5m"


def as_top_down(image):
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape((height, width, 4))[::-1].copy()


def save_image(name, top_down, path):
    height, width = top_down.shape[:2]
    image = bpy.data.images.new(name, width=width, height=height, alpha=True)
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(np.ascontiguousarray(top_down[::-1]).reshape(-1))
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    image.pack()
    return image


def put_on_panel(obj, image):
    material = bpy.data.materials.new("CHECK_FLAT_SCENE_" + obj.name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    emission.inputs["Strength"].default_value = 1.0
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.hide_render = False


def render_view(scene, camera_name, width, height, path):
    scene.camera = bpy.data.objects[camera_name]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main():
    scene = bpy.context.scene
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    for name in (MAIN_NAME, SIDE_NAME, "CAM_SWEET_SPOT_PREVIEW"):
        if name not in bpy.data.objects:
            raise RuntimeError("Missing object in existing project: " + name)

    source_image = bpy.data.images.load(str(SOURCE), check_existing=False)
    source_image.colorspace_settings.name = "sRGB"
    source = as_top_down(source_image)
    height, width = source.shape[:2]
    if width != height or width % 2:
        raise AssertionError("Expected an even-width square candidate")

    # The two 2.5 x 4.5 m faces unfold to 5:4.5 = 10:9. Put this active
    # rectangle in the square without stretching the candidate's geometry.
    active_height = round(width * 0.9)
    crop_top = (height - active_height) // 2
    crop_bottom = crop_top + active_height
    active = source[crop_top:crop_bottom]
    halfway = width // 2
    left = active[:, :halfway]
    right = active[:, halfway:]
    main_image = save_image("CHECK_FLAT_MAIN", left, OUT / "01_main_panel.png")
    side_image = save_image("CHECK_FLAT_SIDE", right, OUT / "02_side_panel.png")
    save_image("CHECK_FLAT_PACKED", active, OUT / "03_unfolded_active_10x9.png")

    put_on_panel(bpy.data.objects[MAIN_NAME], main_image)
    put_on_panel(bpy.data.objects[SIDE_NAME], side_image)
    for layer in scene.view_layers:
        layer.use = layer.name == "02_检查实体双屏"
    scene.use_nodes = False
    for obj in scene.objects:
        if obj.name not in (MAIN_NAME, SIDE_NAME) and obj.type != "CAMERA":
            obj.hide_render = True

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
        background.inputs["Strength"].default_value = 0.0
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.film_transparent = False

    render_view(scene, "CAM_SWEET_SPOT_PREVIEW", 1254, 1254, OUT / "04_sweetspot_on_existing_LED.png")
    if "CAM_SCREEN_MODEL_OBLIQUE" in bpy.data.objects:
        render_view(scene, "CAM_SCREEN_MODEL_OBLIQUE", 1600, 1000, OUT / "05_oblique_on_existing_LED.png")

    scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    scene.render.resolution_x = 1254
    scene.render.resolution_y = 1254
    scene["场景母图检查来源"] = str(SOURCE)
    scene["检查说明"] = "方形图按10:9有效区裁切，左右等分后直接贴入原2.5x4.5米双屏；仅静帧候选检查。"
    blend_path = ROOT / "Lscreen_magicbox_FLAT_SCENE_CANDIDATE_CHECK.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=False)

    report = "\n".join(
        [
            "FLAT SCENE MOTHER / EXISTING BLENDER LED CHECK",
            f"Source blend: {ROOT / 'Lscreen_magicbox_SCREEN_MODEL_READY.blend'}",
            f"Candidate: {SOURCE}",
            f"Candidate size: {width} x {height}",
            f"Active square crop: y={crop_top}:{crop_bottom}, size={width} x {active_height}",
            f"Each panel texture: {halfway} x {active_height}",
            "Physical model: original 2.5m x 4.5m main and side LED faces, 90 degrees",
            "No inverse projection applied: testing the generated unfolded art directly on the LED UVs.",
            "Sweet-spot camera and screen geometry are inherited from the existing blend.",
            f"Check blend: {blend_path}",
            f"Sweet-spot render: {OUT / '04_sweetspot_on_existing_LED.png'}",
            "This is a static simulated viewpoint, not final site/controller acceptance.",
        ]
    )
    (OUT / "check_report.txt").write_text(report, encoding="utf-8")
    print(report, flush=True)


if __name__ == "__main__":
    main()
