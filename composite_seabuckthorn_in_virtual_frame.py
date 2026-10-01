"""Place the supplied sea-buckthorn still using an invisible layout guide.

The artwork is mapped to each panel in UV space.  The former white portal is
only a placement guide: the final image has a dark, uninterrupted LED field.
Sampling the same source beyond the guide lets leaves and juice droplets
remain visible in the outer dark part of the physical LED.
"""

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


SOURCE = Path(r"C:\Users\观照\Downloads\沙棘合成效果图02.png")
OUT_DIR = ROOT / "renders" / "seabuckthorn_no_visible_frame"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAIN_OUT = OUT_DIR / "01_main_panel_1000x1800.png"
SIDE_OUT = OUT_DIR / "02_side_panel_1000x1800.png"
PACKED_OUT = OUT_DIR / "03_controller_packed_2000x1800.png"
SQUARE_OUT = OUT_DIR / "04_sweet_spot_square_1536x1536.png"
LANDSCAPE_OUT = OUT_DIR / "05_sweet_spot_landscape_2048x1156.png"
REPORT_OUT = OUT_DIR / "composite_report.txt"
BLEND_OUT = ROOT / "Lscreen_seabuckthorn_no_visible_frame.blend"

PANEL_W = 1000
PANEL_H = 1800
TOP = 252
BOTTOM = 1548
MAIN_OUTER = 315
SIDE_OUTER = 684
RIM_HALF = 19

# Source artwork's redraw of the old screen, ordered bottom-left,
# bottom-right, top-right, top-left.  Values are the previously validated
# 8-10px inward registration, avoiding the old gold physical outline.
SOURCE_MAIN = np.asarray(
    [[224.0, 1047.0], [627.0, 1210.0], [627.0, 53.0], [224.0, 219.0]],
    dtype=np.float64,
)
SOURCE_SIDE = np.asarray(
    [[627.0, 1210.0], [1030.0, 1047.0], [1030.0, 220.0], [627.0, 53.0]],
    dtype=np.float64,
)


def image_array(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    return core.image_to_array(image)


def sample_artwork(source, source_quad, target_quad):
    """Extend one projective transform across the entire physical panel."""
    matrix = core.solve_homography(target_quad, source_quad)
    result = np.zeros((PANEL_H, PANEL_W, 4), dtype=np.float32)
    xx = np.arange(PANEL_W, dtype=np.float64)[None, :]
    for row in range(0, PANEL_H, 128):
        end = min(PANEL_H, row + 128)
        yy = np.arange(row, end, dtype=np.float64)[:, None]
        denominator = matrix[2, 0] * xx + matrix[2, 1] * yy + matrix[2, 2]
        sx = (matrix[0, 0] * xx + matrix[0, 1] * yy + matrix[0, 2]) / denominator
        sy = (matrix[1, 0] * xx + matrix[1, 1] * yy + matrix[1, 2]) / denominator
        result[row:end] = core.bilinear_sample(source, sx, sy)
    return result


def foreground_alpha(rgb):
    """Recover antialiased objects against the source's pure black exterior."""
    bright = np.max(rgb, axis=2)
    return np.clip((bright - 0.008) / 0.035, 0.0, 1.0)


def dark_led_panel():
    yy, xx = np.mgrid[0:PANEL_H, 0:PANEL_W]
    edge = np.minimum.reduce((xx, PANEL_W - 1 - xx, yy, PANEL_H - 1 - yy))
    glow = np.clip(edge / 210.0, 0.0, 1.0)
    level = 0.047 + 0.019 * glow
    base = np.empty((PANEL_H, PANEL_W, 4), dtype=np.float32)
    base[:, :, 0] = level * 0.88
    base[:, :, 1] = level * 0.94
    base[:, :, 2] = level
    base[:, :, 3] = 1.0
    return base


def composite_panel(source, base, source_quad, panel):
    if panel == "main":
        x0, x1 = MAIN_OUTER, PANEL_W - 1
    else:
        x0, x1 = 0, SIDE_OUTER
    target_quad = np.asarray(
        [[x0, BOTTOM], [x1, BOTTOM], [x1, TOP], [x0, TOP]],
        dtype=np.float64,
    )
    sampled = sample_artwork(source, source_quad, target_quad)
    result = base.copy()
    yy, xx = np.mgrid[0:PANEL_H, 0:PANEL_W]

    # The former white outline is a coordinate guide only.  Fade the source
    # room into the dark LED around it, leaving no visible rectangular frame.
    if panel == "main":
        side_weight = np.clip((xx - x0) / 110.0, 0.0, 1.0)
    else:
        side_weight = np.clip((x1 - xx) / 110.0, 0.0, 1.0)
    top_weight = np.clip((yy - TOP) / 105.0, 0.0, 1.0)
    bottom_weight = np.clip((BOTTOM - yy) / 105.0, 0.0, 1.0)
    room_weight = side_weight * top_weight * bottom_weight
    if panel == "side":
        red, green, blue = (sampled[:, :, index] for index in range(3))
        orange = (red > 0.24) & (green > 0.12) & (red > green * 1.12) & (green > blue * 1.18)
        leaf = (
            (red > 0.18) & (green > 0.21) & (green > red * 0.83)
            & (green > blue * 1.25) & (red > blue * 1.18)
        )
        subject = orange | leaf
        subject = np.maximum.reduce(
            [subject, np.roll(subject, 1, axis=0), np.roll(subject, -1, axis=0),
             np.roll(subject, 1, axis=1), np.roll(subject, -1, axis=1)]
        )
        subject_alpha = np.clip((np.max(sampled[:, :, :3], axis=2) - 0.07) / 0.12, 0.0, 1.0)
        right_subject = (
            (xx >= x1 - 175) & (xx <= x1)
            & (yy >= TOP + 55) & (yy <= BOTTOM - 45)
        )
        room_weight = np.maximum(room_weight, subject_alpha * subject * right_subject)
    result[:, :, :3] = (
        sampled[:, :, :3] * room_weight[:, :, None]
        + base[:, :, :3] * (1.0 - room_weight[:, :, None])
    )

    overflow = foreground_alpha(sampled[:, :, :3])
    # The right-hand leaf and juice droplets can remain fully opaque after
    # leaving the former layout guide; no outline is rendered there.
    if panel == "main":
        overflow[:] = 0.0
    else:
        x_fade = np.clip((xx - (x1 - 20.0)) / 45.0, 0.0, 1.0)
        x_limit = xx <= x1 + 190
        fade_in = np.clip((yy - (TOP + 45)) / 70.0, 0.0, 1.0)
        fade_out = np.clip(((BOTTOM + 25) - yy) / 125.0, 0.0, 1.0)
        overflow *= x_limit.astype(np.float32) * x_fade * fade_in * fade_out
    result[:, :, :3] = (
        sampled[:, :, :3] * overflow[:, :, None]
        + result[:, :, :3] * (1.0 - overflow[:, :, None])
    )
    result[:, :, 3] = 1.0
    return result, overflow


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    scene = bpy.context.scene
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    square_camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    landscape_camera = bpy.data.objects["CAM_FRAME_EFFECT_LANDSCAPE"]

    source = image_array(SOURCE)
    main_base = dark_led_panel()
    side_base = dark_led_panel()
    main_pixels, main_overflow = composite_panel(source, main_base, SOURCE_MAIN, "main")
    side_pixels, side_overflow = composite_panel(source, side_base, SOURCE_SIDE, "side")

    main_image = core.save_array(MAIN_OUT, main_pixels, "SEABUCKTHORN_WHITE_PORTAL_MAIN")
    side_image = core.save_array(SIDE_OUT, side_pixels, "SEABUCKTHORN_WHITE_PORTAL_SIDE")
    core.save_array(
        PACKED_OUT,
        np.concatenate((main_pixels, side_pixels), axis=1),
        "SEABUCKTHORN_WHITE_PORTAL_PACKED",
    )
    core.replace_material(main_screen, core.make_emission_material("MAT_SEABUCKTHORN_WHITE_PORTAL_MAIN", main_image))
    core.replace_material(side_screen, core.make_emission_material("MAT_SEABUCKTHORN_WHITE_PORTAL_SIDE", side_image))

    frame.configure_scene(scene)
    frame.render(scene, square_camera, (1536, 1536), SQUARE_OUT)
    frame.render(scene, landscape_camera, (2048, 1156), LANDSCAPE_OUT)
    scene.camera = square_camera
    scene["composite_source"] = str(SOURCE)
    scene["composite_rule"] = "Former white portal is an invisible placement guide; artwork fades into dark LED with right-side leaf/juice overflow."
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    # Pixel values along the two UV seam edges should agree before the
    # panels are reprojected, demonstrating a single continuous source.
    seam_region = slice(TOP + RIM_HALF + 2, BOTTOM - RIM_HALF - 2)
    seam_mae = float(np.mean(np.abs(
        main_pixels[seam_region, -1, :3] - side_pixels[seam_region, 0, :3]
    )))
    report = [
        "SEABUCKTHORN WITH INVISIBLE LAYOUT GUIDE",
        "=======================================",
        f"Source artwork: {SOURCE}",
        "Physical LED: 2.5m x 4.5m main + 2.5m x 4.5m side, 90 degrees.",
        "Main content: projectively placed using the former white outline as an invisible guide.",
        "Visible white outline: none; source background fades into the dark LED field.",
        "Overflow: right-side leaf and juice droplets stay visible in the outer dark LED area.",
        "No artwork is intentionally placed beyond the physical LED boundary.",
        f"Main overflow pixels: {int(np.count_nonzero(main_overflow > 0.1))}",
        f"Side overflow pixels: {int(np.count_nonzero(side_overflow > 0.1))}",
        f"Panel-seam RGB mean absolute difference (0..1): {seam_mae:.6f}",
        "Status: still-frame composition and sweet-spot preview; perceived depth remains viewpoint-dependent.",
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)
    print(f"BLEND={BLEND_OUT}", flush=True)
    print(f"PREVIEW={LANDSCAPE_OUT}", flush=True)
    print(f"PACKED={PACKED_OUT}", flush=True)


if __name__ == "__main__":
    main()
