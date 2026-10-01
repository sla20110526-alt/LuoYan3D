import bpy
import math
import sys
from pathlib import Path

import numpy as np
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import validate_seabuckthorn_inverse_projection as core


OUT_DIR = ROOT / "renders" / "correct_virtual_frame"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAIN_OUT = OUT_DIR / "01_main_panel_virtual_frame_1000x1800.png"
SIDE_OUT = OUT_DIR / "02_side_panel_virtual_frame_1000x1800.png"
PACKED_OUT = OUT_DIR / "03_controller_virtual_frame_2000x1800.png"
SQUARE_OUT = OUT_DIR / "04_correct_frame_effect_square_1536x1536.png"
LANDSCAPE_OUT = OUT_DIR / "05_correct_frame_effect_landscape_2048x1156.png"
BLEND_OUT = ROOT / "Lscreen_correct_virtual_white_frame.blend"
REPORT_OUT = OUT_DIR / "frame_definition.txt"

PANEL_W = 1000
PANEL_H = 1800


def add_soft_rect(array, x0, x1, y0, y1, color):
    x0 = max(0, int(round(x0)))
    x1 = min(array.shape[1], int(round(x1)))
    y0 = max(0, int(round(y0)))
    y1 = min(array.shape[0], int(round(y1)))
    if x1 > x0 and y1 > y0:
        array[y0:y1, x0:x1, :3] = color
        array[y0:y1, x0:x1, 3] = 1.0


def make_panel(panel):
    h, w = PANEL_H, PANEL_W
    yy, xx = np.mgrid[0:h, 0:w]

    # The entire dark area is active LED content, not a physical frame.
    edge_distance = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]).astype(np.float32)
    vignette = np.clip(edge_distance / 180.0, 0.0, 1.0)
    # This near-black area is illuminated LED content.  It must remain
    # distinguishable from the unlit black background in a preview.
    dark = 0.060 + 0.020 * vignette
    image = np.zeros((h, w, 4), dtype=np.float32)
    image[:, :, 0] = dark * 0.82
    image[:, :, 1] = dark * 0.88
    image[:, :, 2] = dark
    image[:, :, 3] = 1.0

    top = 252
    bottom = 1548
    frame_half = 19
    bevel_outer = 8
    bevel_inner = 5

    if panel == "main":
        outer = 315
        seam = w - 1
        active = (xx >= outer) & (xx <= seam) & (yy >= top) & (yy <= bottom)
        depth_t = np.clip((xx - outer) / max(1.0, seam - outer), 0.0, 1.0)
        wall_base = np.array([0.82, 0.83, 0.85], dtype=np.float32)
        vertical_line_x = outer
    else:
        seam = 0
        outer = 684
        active = (xx >= seam) & (xx <= outer) & (yy >= top) & (yy <= bottom)
        depth_t = np.clip((outer - xx) / max(1.0, outer - seam), 0.0, 1.0)
        wall_base = np.array([0.88, 0.89, 0.91], dtype=np.float32)
        vertical_line_x = outer

    ceiling_boundary = top + 255.0 * depth_t
    floor_boundary = bottom - 275.0 * depth_t

    ceiling = active & (yy <= ceiling_boundary)
    wall = active & (yy > ceiling_boundary) & (yy < floor_boundary)
    floor = active & (yy >= floor_boundary)

    # Soft lighting gives the virtual white room enough depth without introducing
    # a second physical border at the center fold.
    horizontal_light = 0.96 + 0.04 * (1.0 - depth_t)
    vertical_light = 0.97 + 0.03 * np.clip((bottom - yy) / max(1.0, bottom - top), 0.0, 1.0)

    for channel, base in enumerate((0.87, 0.88, 0.90)):
        image[:, :, channel][ceiling] = np.clip(base * horizontal_light[ceiling], 0.0, 1.0)
    for channel in range(3):
        image[:, :, channel][wall] = np.clip(
            wall_base[channel] * horizontal_light[wall] * vertical_light[wall], 0.0, 1.0
        )
    for channel, base in enumerate((0.78, 0.79, 0.82)):
        image[:, :, channel][floor] = np.clip(base * horizontal_light[floor], 0.0, 1.0)

    # Thin plane boundaries make the room read as a single recessed box.
    boundary_distance_top = np.abs(yy - ceiling_boundary)
    boundary_distance_bottom = np.abs(yy - floor_boundary)
    boundary_mask = active & ((boundary_distance_top <= 2.0) | (boundary_distance_bottom <= 2.0))
    image[:, :, :3][boundary_mask] *= 0.78

    # Virtual white portal frame: top, bottom and the two outside verticals.
    # No frame is drawn on the central fold, so the two screens remain seamless.
    x_start, x_end = (outer, w) if panel == "main" else (0, outer + 1)
    shadow = np.array([0.31, 0.32, 0.35], dtype=np.float32)
    white = np.array([0.91, 0.92, 0.94], dtype=np.float32)
    highlight = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    inner_gray = np.array([0.70, 0.72, 0.75], dtype=np.float32)

    add_soft_rect(image, x_start, x_end, top - frame_half - bevel_outer, top + frame_half + bevel_outer, shadow)
    add_soft_rect(image, x_start, x_end, bottom - frame_half - bevel_outer, bottom + frame_half + bevel_outer, shadow)
    add_soft_rect(
        image,
        vertical_line_x - frame_half - bevel_outer,
        vertical_line_x + frame_half + bevel_outer,
        top - frame_half,
        bottom + frame_half,
        shadow,
    )

    add_soft_rect(image, x_start, x_end, top - frame_half, top + frame_half, white)
    add_soft_rect(image, x_start, x_end, bottom - frame_half, bottom + frame_half, white)
    add_soft_rect(
        image,
        vertical_line_x - frame_half,
        vertical_line_x + frame_half,
        top - frame_half,
        bottom + frame_half,
        white,
    )

    add_soft_rect(image, x_start, x_end, top - frame_half, top - frame_half + bevel_inner, highlight)
    add_soft_rect(image, x_start, x_end, top + frame_half - bevel_inner, top + frame_half, inner_gray)
    add_soft_rect(image, x_start, x_end, bottom - frame_half, bottom - frame_half + bevel_inner, highlight)
    add_soft_rect(image, x_start, x_end, bottom + frame_half - bevel_inner, bottom + frame_half, inner_gray)

    if panel == "main":
        add_soft_rect(
            image,
            vertical_line_x - frame_half,
            vertical_line_x - frame_half + bevel_inner,
            top - frame_half,
            bottom + frame_half,
            highlight,
        )
        add_soft_rect(
            image,
            vertical_line_x + frame_half - bevel_inner,
            vertical_line_x + frame_half,
            top - frame_half,
            bottom + frame_half,
            inner_gray,
        )
    else:
        add_soft_rect(
            image,
            vertical_line_x - frame_half,
            vertical_line_x - frame_half + bevel_inner,
            top - frame_half,
            bottom + frame_half,
            inner_gray,
        )
        add_soft_rect(
            image,
            vertical_line_x + frame_half - bevel_inner,
            vertical_line_x + frame_half,
            top - frame_half,
            bottom + frame_half,
            highlight,
        )

    # A subtle one-pixel active-screen edge makes the outer silhouette visible
    # against the black world without implying a physical bezel.
    edge_color = np.array([0.13, 0.13, 0.14], dtype=np.float32)
    image[0:3, :, :3] = edge_color
    image[-3:, :, :3] = edge_color
    if panel == "main":
        image[:, 0:3, :3] = edge_color
    else:
        image[:, -3:, :3] = edge_color

    return image


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def configure_scene(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    world = scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0


def render(scene, camera, size, path):
    scene.camera = camera
    scene.render.resolution_x = size[0]
    scene.render.resolution_y = size[1]
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main():
    scene = bpy.context.scene
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    square_camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]

    main_pixels = make_panel("main")
    side_pixels = make_panel("side")
    main_image = core.save_array(MAIN_OUT, main_pixels, "VIRTUAL_FRAME_MAIN")
    side_image = core.save_array(SIDE_OUT, side_pixels, "VIRTUAL_FRAME_SIDE")
    core.save_array(PACKED_OUT, np.concatenate((main_pixels, side_pixels), axis=1), "VIRTUAL_FRAME_PACKED")

    main_material = core.make_emission_material("MAT_VIRTUAL_FRAME_MAIN", main_image)
    side_material = core.make_emission_material("MAT_VIRTUAL_FRAME_SIDE", side_image)
    core.replace_material(main_screen, main_material)
    core.replace_material(side_screen, side_material)

    for collection in bpy.data.collections:
        collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
    main_screen.hide_render = False
    side_screen.hide_render = False

    square_camera.data.lens = 47.0
    square_camera.data.sensor_width = 36.0
    square_camera.data.sensor_fit = "HORIZONTAL"
    look_at(square_camera, Vector((-0.625, 0.625, 2.25)))
    square_camera["role"] = "production sweet-spot frame-effect camera"

    landscape_camera = bpy.data.objects.get("CAM_FRAME_EFFECT_LANDSCAPE")
    if landscape_camera is None:
        landscape_camera = square_camera.copy()
        landscape_camera.data = square_camera.data.copy()
        landscape_camera.name = "CAM_FRAME_EFFECT_LANDSCAPE"
        bpy.data.collections["04_PROJECTION_CAMERAS"].objects.link(landscape_camera)
    landscape_camera.location = square_camera.location
    landscape_camera.data.lens = 25.5
    landscape_camera.data.sensor_width = 36.0
    landscape_camera.data.sensor_fit = "HORIZONTAL"
    look_at(landscape_camera, Vector((-0.625, 0.625, 2.25)))
    landscape_camera["role"] = "landscape presentation preview only; same physical viewpoint"

    configure_scene(scene)
    render(scene, square_camera, (1536, 1536), SQUARE_OUT)
    render(scene, landscape_camera, (2048, 1156), LANDSCAPE_OUT)

    scene.camera = square_camera
    scene["frame_definition"] = (
        "Entire dark outer L-shaped area is active LED; inner white frame is virtual content and may be crossed by fruit/liquid."
    )
    scene["physical_screen"] = "2.5m x 4.5m main + 2.5m x 4.5m side; 90 degrees; no physical bezel"
    scene["production_sweet_spot"] = "45-degree bisector; plan radius 6.5m; eye height 1.6m"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    report = [
        "CORRECT VIRTUAL FRAME DEFINITION",
        "================================",
        "Physical LED: two equal 2.5m x 4.5m vertical faces at 90 degrees.",
        "Outer dark L-shaped polygon: entire active LED surface, not a bezel.",
        "Inner white portal frame: virtual screen content only.",
        "White-room interior: recessed virtual box rendered inside the portal.",
        "Overflow rule: later fruit, leaves and juice may cross the white portal frame but must remain inside the outer physical LED silhouette.",
        "No top LED, no floor LED, no physical frame and no center seam object.",
        "No product, fruit, liquid, text or logo included in this frame-only deliverable.",
        "The supplied reference is used for the virtual white-room style and aperture spacing.",
        "Its outer silhouette is wider than the confirmed 2.5m + 2.5m x 4.5m LED geometry",
        "when seen from the provisional 6.5m/1.6m sweet spot; physical geometry takes precedence.",
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)
    print(f"SQUARE={SQUARE_OUT}", flush=True)
    print(f"LANDSCAPE={LANDSCAPE_OUT}", flush=True)
    print(f"PACKED={PACKED_OUT}", flush=True)
    print(f"BLEND={BLEND_OUT}", flush=True)


if __name__ == "__main__":
    main()
