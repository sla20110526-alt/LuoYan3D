"""Verify a layer-separated sea-buckthorn still on the exact two-face LED."""

import math
import sys
from pathlib import Path

import bpy
import numpy as np


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_correct_virtual_frame_effect as frame
import validate_seabuckthorn_inverse_projection as core


FOREGROUND = ROOT / "图片" / "沙棘果枝果汁_透明前景_v1.png"
OUT_DIR = ROOT / "renders" / "seabuckthorn_layered_sweetspot_test"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_OUT = OUT_DIR / "01_unwarped_sweetspot_composition_1536.png"
MAIN_OUT = OUT_DIR / "02_main_prewarped_1000x1800.png"
SIDE_OUT = OUT_DIR / "03_side_prewarped_1000x1800.png"
PACKED_OUT = OUT_DIR / "04_controller_packed_2000x1800.png"
REPROJECT_OUT = OUT_DIR / "05_blender_reprojection_1536.png"
LANDSCAPE_OUT = OUT_DIR / "06_landscape_review_2048x1156.png"
REPORT_OUT = OUT_DIR / "quality_review.txt"
BLEND_OUT = ROOT / "Lscreen_seabuckthorn_layered_sweetspot_test.blend"

CANVAS = (1536, 1536)
PANEL = (1000, 1800)
FOREGROUND_SCALE = 0.62
FOREGROUND_ORIGIN = (390.0, 390.0)


def read_image(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    return core.image_to_array(image)


def compose_target(foreground, main_mask, side_mask):
    width, height = CANVAS
    yy, xx = np.mgrid[0:height, 0:width]
    xx = xx.astype(np.float32)
    yy = yy.astype(np.float32)
    screen_mask = main_mask | side_mask

    # The complete screen is a single dark environment, with no inner frame
    # and no rectangular photograph boundary.  A broad warm left light and
    # muted green center give the separated foreground some depth context.
    center_glow = np.exp(-(((xx - 760.0) / 390.0) ** 2 + ((yy - 775.0) / 500.0) ** 2) * 1.4)
    warm_glow = np.exp(-(((xx - 500.0) / 270.0) ** 2 + ((yy - 460.0) / 330.0) ** 2) * 1.7)
    target = np.zeros((height, width, 4), dtype=np.float32)
    target[:, :, 3] = 1.0
    target[:, :, 0] = 0.006 + 0.025 * center_glow + 0.030 * warm_glow
    target[:, :, 1] = 0.010 + 0.070 * center_glow + 0.023 * warm_glow
    target[:, :, 2] = 0.008 + 0.055 * center_glow + 0.007 * warm_glow
    target[side_mask, :3] *= np.array([0.78, 0.84, 0.82], dtype=np.float32)

    sx = (xx - FOREGROUND_ORIGIN[0]) / FOREGROUND_SCALE
    sy = (yy - FOREGROUND_ORIGIN[1]) / FOREGROUND_SCALE
    hero = core.bilinear_sample(foreground, sx, sy)
    alpha = np.clip((hero[:, :, 3] - 0.025) / 0.975, 0.0, 1.0)
    outside_hero = int(np.count_nonzero((alpha > 0.10) & ~screen_mask))
    total_hero = int(np.count_nonzero(alpha > 0.10))
    target[:, :, :3] = hero[:, :, :3] * alpha[:, :, None] + target[:, :, :3] * (1.0 - alpha[:, :, None])
    target[~screen_mask, :3] = 0.0
    return target, outside_hero, total_hero


def main():
    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    landscape_camera = bpy.data.objects["CAM_FRAME_EFFECT_LANDSCAPE"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = CANVAS
    foreground = read_image(FOREGROUND)
    main_quad = core.projected_quad(scene, camera, main_screen, CANVAS)
    side_quad = core.projected_quad(scene, camera, side_screen, CANVAS)
    main_mask = core.inside_convex_quad(*CANVAS, main_quad)
    side_mask = core.inside_convex_quad(*CANVAS, side_quad)
    target, outside_hero, total_hero = compose_target(foreground, main_mask, side_mask)
    core.save_array(TARGET_OUT, target, "SEABUCKTHORN_LAYERED_UNWARPED_TARGET")

    main_pixels = core.warp_quad_to_rect(target, main_quad, PANEL)
    side_pixels = core.warp_quad_to_rect(target, side_quad, PANEL)
    main_image = core.save_array(MAIN_OUT, main_pixels, "SEABUCKTHORN_LAYERED_MAIN_PREWARP")
    side_image = core.save_array(SIDE_OUT, side_pixels, "SEABUCKTHORN_LAYERED_SIDE_PREWARP")
    core.save_array(
        PACKED_OUT, np.concatenate((main_pixels, side_pixels), axis=1),
        "SEABUCKTHORN_LAYERED_PACKED",
    )

    core.replace_material(main_screen, core.make_emission_material("MAT_SEABUCKTHORN_LAYERED_MAIN", main_image))
    core.replace_material(side_screen, core.make_emission_material("MAT_SEABUCKTHORN_LAYERED_SIDE", side_image))
    frame.configure_scene(scene)
    frame.render(scene, camera, CANVAS, REPROJECT_OUT)
    frame.render(scene, landscape_camera, (2048, 1156), LANDSCAPE_OUT)
    scene.camera = camera
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    reproject = read_image(REPROJECT_OUT)
    mask = main_mask | side_mask
    error = np.abs(reproject[:, :, :3] - target[:, :, :3])
    mae = float(np.mean(error[mask]))
    seam_mae = float(np.mean(np.abs(main_pixels[200:1600, -1, :3] - side_pixels[200:1600, 0, :3])))
    outside_pct = outside_hero * 100.0 / max(1, total_hero)
    report = [
        "LAYER-SEPARATED SEA-BUCKTHORN SWEET-SPOT TEST",
        "=============================================",
        f"Transparent foreground: {FOREGROUND}",
        "Background: procedurally built continuous dark LED scene; no white frame and no rectangular source-photo edge.",
        "Foreground: one planar transparent layer with uniform image scale, preserving berry shape in the sweet-spot target.",
        "Projection: exact Blender 2.5m x 4.5m + 2.5m x 4.5m panels at 90 degrees.",
        f"Foreground pixels clipped by physical screen: {outside_hero}/{total_hero} ({outside_pct:.3f}%).",
        f"Packed panel seam RGB MAE: {seam_mae:.6f}.",
        f"Sweet-spot reprojection RGB MAE: {mae:.6f}.",
        "QUALITY LIMIT: a single foreground cutout has no independently controllable branch, berry and juice depth; this is a placement test, not a finished 3D hero frame.",
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)
    print(f"REPROJECT={REPROJECT_OUT}", flush=True)
    print(f"BLEND={BLEND_OUT}", flush=True)


if __name__ == "__main__":
    main()
