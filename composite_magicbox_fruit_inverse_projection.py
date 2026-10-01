"""Place the supplied transparent sea-buckthorn art in the virtual sand box.

The composite is authored for the provisional 45-degree sweet spot, inverse-
projected to two 2.5 x 4.5 m LED faces, and re-rendered in Blender to test it.
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_correct_virtual_frame_effect as frame
import validate_seabuckthorn_inverse_projection as core


BOX = ROOT / "图片" / "沙棘沙地时空盒内框_概念图_v2.png"
FRUIT = ROOT / "图片" / "沙棘果枝果汁_透明前景_v1.png"
OUT = ROOT / "renders" / "magicbox_fruit_inverse_projection"
OUT.mkdir(parents=True, exist_ok=True)
BLEND = ROOT / "Lscreen_magicbox_fruit_inverse_projection.blend"

SIZE = (1254, 1254)
PANEL = (1000, 1800)  # Simulation grid only; controller pixel map not supplied.
FRUIT_SCALE = 0.52
FRUIT_LEFT = 301.0
FRUIT_TOP = 328.0


def read_image(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    return core.image_to_array(image)


def clean_alpha(rgba):
    result = rgba.copy()
    alpha = result[:, :, 3]
    # The provided PNG contains tiny colored fringe pixels. Alpha erosion is
    # limited to two source pixels so most delicate droplets remain intact.
    for _ in range(2):
        padded = np.pad(alpha, 1, mode="constant")
        alpha = np.minimum.reduce(
            [padded[1:-1, 1:-1], padded[:-2, 1:-1],
             padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]]
        )
    result[:, :, 3] = alpha
    return result


def compose(base, subject, led_mask):
    h, w = base.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    sx = (xx - FRUIT_LEFT) / FRUIT_SCALE
    sy = (yy - FRUIT_TOP) / FRUIT_SCALE
    hero = core.bilinear_sample(subject, sx, sy)
    alpha = np.clip(hero[:, :, 3], 0.0, 1.0)
    total = int(np.count_nonzero(alpha > 0.10))
    clipped = int(np.count_nonzero((alpha > 0.10) & ~led_mask))

    target = base.copy()
    target[:, :, :3] = hero[:, :, :3] * alpha[:, :, None] + base[:, :, :3] * (1.0 - alpha[:, :, None])
    target[:, :, 3] = 1.0
    target[~led_mask, :3] = 0.0

    # A narrow conceptual side-frame overflow check. The visual review is
    # authoritative because the top and bottom gold rails are perspective V's.
    side_overflow = int(np.count_nonzero((alpha > 0.10) & led_mask & ((xx < 335) | (xx > 916))))
    return target, total, clipped, side_overflow


def make_landscape_camera(scene, camera):
    landscape = bpy.data.objects.get("CAM_MAGICBOX_LANDSCAPE_REVIEW")
    if landscape is None:
        landscape = camera.copy()
        landscape.data = camera.data.copy()
        landscape.name = "CAM_MAGICBOX_LANDSCAPE_REVIEW"
        bpy.data.collections["04_PROJECTION_CAMERAS"].objects.link(landscape)
    landscape.location = camera.location
    landscape.rotation_euler = camera.rotation_euler
    landscape.data.lens = 25.5
    landscape.data.sensor_width = 36.0
    landscape.data.sensor_fit = "HORIZONTAL"
    return landscape


def main():
    if not BOX.is_file() or not FRUIT.is_file():
        raise FileNotFoundError(f"Missing asset: box={BOX.is_file()}, fruit={FRUIT.is_file()}")

    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    base = read_image(BOX)
    subject = clean_alpha(read_image(FRUIT))
    if base.shape[:2] != (SIZE[1], SIZE[0]) or subject.shape[:2] != base.shape[:2]:
        raise ValueError(f"Unexpected image sizes: base={base.shape}, subject={subject.shape}")

    main_quad = core.projected_quad(scene, camera, main_screen, SIZE)
    side_quad = core.projected_quad(scene, camera, side_screen, SIZE)
    main_mask = core.inside_convex_quad(*SIZE, main_quad)
    side_mask = core.inside_convex_quad(*SIZE, side_quad)
    led_mask = main_mask | side_mask
    target, subject_pixels, clipped_pixels, side_overflow = compose(base, subject, led_mask)
    core.save_array(OUT / "01_sweetspot_composite_1254.png", target, "MAGICBOX_FRUIT_SWEETSPOT_TARGET")

    # Geometric diagnostic: whether the AI concept's dark screen silhouette
    # agrees with the exact physical LED polygons in this Blender camera.
    base_bright = np.max(base[:, :, :3], axis=2) > 0.025
    concept_extra = int(np.count_nonzero(base_bright & ~led_mask))
    concept_missing = int(np.count_nonzero(led_mask & ~base_bright))

    main_pixels = core.warp_quad_to_rect(target, main_quad, PANEL)
    side_pixels = core.warp_quad_to_rect(target, side_quad, PANEL)
    main_image = core.save_array(OUT / "02_main_prewarped_1000x1800.png", main_pixels, "MAGICBOX_FRUIT_MAIN")
    side_image = core.save_array(OUT / "03_side_prewarped_1000x1800.png", side_pixels, "MAGICBOX_FRUIT_SIDE")
    core.save_array(OUT / "04_controller_packed_2000x1800.png",
                    np.concatenate((main_pixels, side_pixels), axis=1), "MAGICBOX_FRUIT_PACKED")

    core.replace_material(main_screen, core.make_emission_material("MAT_MAGICBOX_FRUIT_MAIN", main_image))
    core.replace_material(side_screen, core.make_emission_material("MAT_MAGICBOX_FRUIT_SIDE", side_image))
    for collection in bpy.data.collections:
        collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
    main_screen.hide_render = False
    side_screen.hide_render = False
    frame.configure_scene(scene)
    frame.render(scene, camera, SIZE, OUT / "05_blender_sweetspot_reprojection_1254.png")
    landscape_camera = make_landscape_camera(scene, camera)
    frame.render(scene, landscape_camera, (2048, 1156), OUT / "06_blender_landscape_review_2048x1156.png")
    scene.camera = camera
    scene["screen_geometry"] = "Two vertical 2.5 m x 4.5 m LED faces at 90 degrees; no top or floor LED"
    scene["target"] = "7.5-second sea-buckthorn fruit/juice in virtual sand time-space box"
    scene["viewpoint"] = "Provisional 45-degree sweet spot, 6.5 m plan distance, 1.6 m eye height"
    scene["pixel_map_status"] = "1000 x 1800 per face is for simulation only; venue pixel map required for delivery"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    reprojection = read_image(OUT / "05_blender_sweetspot_reprojection_1254.png")
    difference = np.abs(reprojection[:, :, :3] - target[:, :, :3])
    mae = float(np.mean(difference[led_mask]))
    seam_mae = float(np.mean(np.abs(main_pixels[180:1620, -1, :3] - side_pixels[180:1620, 0, :3])))
    clipped_pct = 100.0 * clipped_pixels / max(1, subject_pixels)
    report = [
        "MAGIC BOX + SEA-BUCKTHORN BLENDER INVERSE-PROJECTION TEST",
        "========================================================",
        f"Background: {BOX}",
        f"Foreground: {FRUIT}",
        f"Foreground transform in sweet-spot canvas: scale={FRUIT_SCALE:.3f}, left={FRUIT_LEFT:.1f}, top={FRUIT_TOP:.1f} px.",
        "Physical LEDs: 2.5 m x 4.5 m + 2.5 m x 4.5 m, vertical, 90 degrees; no physical top/floor LED.",
        "Nominal viewer: 45-degree bisector, 6.5 m from corner, eye height 1.6 m.",
        f"Main projected quad: {np.array2string(main_quad, precision=2)}",
        f"Side projected quad: {np.array2string(side_quad, precision=2)}",
        f"Subject pixels outside physical LED: {clipped_pixels}/{subject_pixels} ({clipped_pct:.4f}%).",
        f"Subject pixels outside approximate inner side-frame but inside LED: {side_overflow}.",
        f"Blender round-trip RGB MAE inside physical LED: {mae:.6f}.",
        f"Packed corner-edge RGB MAE: {seam_mae:.6f}.",
        f"Concept silhouette bright pixels outside exact LED: {concept_extra}; dark/missing within LED: {concept_missing}.",
        "NOTE: 1000x1800 per panel is a TEST raster, not the client's confirmed controller pixel map.",
        "VISUAL STATUS: pending inspection; numeric agreement alone is not a naked-eye-3D effect approval.",
    ]
    (OUT / "validation_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)
    print(f"BLEND={BLEND}", flush=True)


if __name__ == "__main__":
    main()
