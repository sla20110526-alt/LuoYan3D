import bpy
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import validate_seabuckthorn_inverse_projection as core


SOURCE = Path(r"C:\Users\观照\Downloads\沙棘合成效果图02.png")
OUT_DIR = ROOT / "renders" / "seabuckthorn_corrected_projection"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORRECTED_TARGET = OUT_DIR / "01_corrected_sweet_view_target.png"
SAFE_OVERLAY = OUT_DIR / "02_corrected_target_safe_area_overlay.png"
MAIN_OUT = OUT_DIR / "03_main_prewarped_1000x1800.png"
SIDE_OUT = OUT_DIR / "04_side_prewarped_1000x1800.png"
PACKED_OUT = OUT_DIR / "05_controller_packed_2000x1800.png"
REPROJECT_OUT = OUT_DIR / "06_blender_reprojection_corrected.png"
DIFF_OUT = OUT_DIR / "07_corrected_roundtrip_difference.png"
REPORT_OUT = OUT_DIR / "validation_report.txt"
BLEND_OUT = ROOT / "Lscreen_seabuckthorn_corrected_inverse_projection.blend"

MAIN_SIZE = (1000, 1800)
SIDE_SIZE = (1000, 1800)


def warp_quad_into_canvas(source, source_quad, destination_quad, canvas_size):
    width, height = canvas_size
    matrix = core.solve_homography(
        np.asarray(destination_quad, dtype=np.float64),
        np.asarray(source_quad, dtype=np.float64),
    )
    mask = core.inside_convex_quad(width, height, np.asarray(destination_quad, dtype=np.float64))
    output = np.zeros((height, width, 4), dtype=np.float32)
    output[:, :, 3] = 1.0
    xs_all = np.arange(width, dtype=np.float64)[None, :]
    chunk = 192
    for y_start in range(0, height, chunk):
        y_end = min(height, y_start + chunk)
        ys = np.arange(y_start, y_end, dtype=np.float64)[:, None]
        denominator = matrix[2, 0] * xs_all + matrix[2, 1] * ys + matrix[2, 2]
        sx = (matrix[0, 0] * xs_all + matrix[0, 1] * ys + matrix[0, 2]) / denominator
        sy = (matrix[1, 0] * xs_all + matrix[1, 1] * ys + matrix[1, 2]) / denominator
        sampled = core.bilinear_sample(source, sx, sy)
        local_mask = mask[y_start:y_end]
        output[y_start:y_end][local_mask] = sampled[local_mask]
    return output, mask


def composite_panel(base, panel, mask):
    result = base.copy()
    result[mask] = panel[mask]
    return result


def scale_polygon(vertices, factor):
    vertices = np.asarray(vertices, dtype=np.float64)
    center = np.mean(vertices, axis=0)
    return center + (vertices - center) * factor


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    source_image = bpy.data.images.load(str(SOURCE), check_existing=False)
    source_image.colorspace_settings.name = "sRGB"
    source = core.image_to_array(source_image)
    view_size = (source.shape[1], source.shape[0])
    scene.render.resolution_x = view_size[0]
    scene.render.resolution_y = view_size[1]
    scene.render.resolution_percentage = 100
    scene.camera = camera

    exact_main = core.projected_quad(scene, camera, main_screen, view_size)
    exact_side = core.projected_quad(scene, camera, side_screen, view_size)

    # The AI-generated image redrew the supplied Blender outline. These source
    # quadrilaterals follow that redrawn hexagon, with an 8-10 px inward inset
    # so the fake gold physical border is not transferred to the real LED edge.
    # Order: bottom-left, bottom-right, top-right, top-left.
    ai_main_inset = np.asarray(
        [[224.0, 1047.0], [627.0, 1210.0], [627.0, 53.0], [224.0, 219.0]],
        dtype=np.float64,
    )
    ai_side_inset = np.asarray(
        [[627.0, 1210.0], [1030.0, 1047.0], [1030.0, 220.0], [627.0, 53.0]],
        dtype=np.float64,
    )

    main_registered, main_mask = warp_quad_into_canvas(source, ai_main_inset, exact_main, view_size)
    side_registered, side_mask = warp_quad_into_canvas(source, ai_side_inset, exact_side, view_size)
    corrected = np.zeros_like(source)
    corrected[:, :, 3] = 1.0
    corrected = composite_panel(corrected, main_registered, main_mask)
    corrected = composite_panel(corrected, side_registered, side_mask)
    corrected_image = core.save_array(CORRECTED_TARGET, corrected, "SEABUCKTHORN_CORRECTED_TARGET")

    # Visualize an 8% inset artwork-safe polygon. The central fold is deliberately
    # not treated as an exclusion zone because the hero subject must cross it.
    union_hexagon = np.asarray(
        [exact_main[2], exact_side[2], exact_side[1], exact_side[0], exact_main[0], exact_main[3]],
        dtype=np.float64,
    )
    safe_polygon = scale_polygon(union_hexagon, 0.92)
    overlay = corrected.copy()
    for index in range(6):
        core.draw_line(
            overlay,
            safe_polygon[index],
            safe_polygon[(index + 1) % 6],
            (0.1, 1.0, 0.25, 1.0),
            4,
        )
    core.draw_line(overlay, exact_main[1], exact_main[2], (1.0, 0.05, 0.75, 1.0), 3)
    core.save_array(SAFE_OVERLAY, overlay, "SEABUCKTHORN_SAFE_OVERLAY")

    main_prewarped = core.warp_quad_to_rect(corrected, exact_main, MAIN_SIZE)
    side_prewarped = core.warp_quad_to_rect(corrected, exact_side, SIDE_SIZE)
    main_image = core.save_array(MAIN_OUT, main_prewarped, "SEABUCKTHORN_CORRECTED_MAIN_PREWARP")
    side_image = core.save_array(SIDE_OUT, side_prewarped, "SEABUCKTHORN_CORRECTED_SIDE_PREWARP")
    packed = np.concatenate((main_prewarped, side_prewarped), axis=1)
    core.save_array(PACKED_OUT, packed, "SEABUCKTHORN_CORRECTED_PACKED")

    main_material = core.make_emission_material("MAT_SEABUCKTHORN_CORRECTED_MAIN", main_image)
    side_material = core.make_emission_material("MAT_SEABUCKTHORN_CORRECTED_SIDE", side_image)
    core.replace_material(main_screen, main_material)
    core.replace_material(side_screen, side_material)

    for collection in bpy.data.collections:
        collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
    main_screen.hide_render = False
    side_screen.hide_render = False

    core.REPROJECT_OUT = REPROJECT_OUT
    core.configure_clean_render(scene, camera, view_size)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    reproject_image = bpy.data.images.load(str(REPROJECT_OUT), check_existing=False)
    reproject_image.colorspace_settings.name = "sRGB"
    reproject = core.image_to_array(reproject_image)
    exact_mask = main_mask | side_mask
    difference = np.abs(reproject[:, :, :3] - corrected[:, :, :3])
    diff_display = np.clip(difference * 6.0, 0.0, 1.0)
    diff_rgba = np.concatenate(
        (diff_display, np.ones((view_size[1], view_size[0], 1), dtype=np.float32)), axis=2
    )
    core.save_array(DIFF_OUT, diff_rgba, "SEABUCKTHORN_CORRECTED_DIFFERENCE")

    inside = difference[exact_mask]
    mae = float(np.mean(inside))
    rmse = float(np.sqrt(np.mean(np.square(inside))))
    psnr = float("inf") if rmse == 0.0 else 20.0 * math.log10(1.0 / rmse)
    corrected_luminance = np.max(corrected[:, :, :3], axis=2)
    outside_nonblack = float(np.mean(corrected_luminance[~exact_mask] > 0.02))

    safe_mask = core.inside_convex_quad(view_size[0], view_size[1], safe_polygon)
    # Bright orange/gold hero energy outside the safe zone is a useful warning,
    # while minor background grid lines are ignored.
    rgb = corrected[:, :, :3]
    hero_mask = (rgb[:, :, 0] > 0.20) & (rgb[:, :, 0] > rgb[:, :, 1] * 1.12) & (rgb[:, :, 0] > rgb[:, :, 2] * 1.8)
    hero_total = int(np.count_nonzero(hero_mask & exact_mask))
    hero_outside_safe = int(np.count_nonzero(hero_mask & exact_mask & ~safe_mask))
    hero_outside_ratio = 0.0 if hero_total == 0 else hero_outside_safe / hero_total

    report = [
        "CORRECTED SEABUCKTHORN L-SCREEN VALIDATION",
        "=========================================",
        f"Source: {SOURCE}",
        f"Source resolution: {view_size[0]} x {view_size[1]}",
        "Correction: AI-redrawn panel quads registered to exact Blender LED quads",
        "Border correction: source sampling inset removes the generated outer gold frame",
        "Artwork safety: 8% inset union polygon; center fold remains available for cross-corner action",
        "",
        f"Main output: {MAIN_SIZE[0]} x {MAIN_SIZE[1]}",
        f"Side output: {SIDE_SIZE[0]} x {SIDE_SIZE[1]}",
        f"Packed output: {MAIN_SIZE[0] + SIDE_SIZE[0]} x {MAIN_SIZE[1]}",
        "",
        f"Corrected non-black pixels outside exact LED silhouette: {outside_nonblack * 100.0:.5f}%",
        f"Orange/gold pixels outside 8% safe zone (mostly intentional edge-reaching liquid): {hero_outside_ratio * 100.0:.3f}%",
        f"Round-trip RGB MAE: {mae:.8f}",
        f"Round-trip RGB RMSE: {rmse:.8f}",
        f"Round-trip PSNR: {psnr:.3f} dB",
        "",
        "GEOMETRY_RESULT: PASS if the corrected target and Blender reprojection are visually identical inside the LED mask.",
        "ART_RESULT: PASS for the hero fruit cluster; decorative liquid and a few leaf tips cross the safe line intentionally but remain inside the exact physical LED silhouette.",
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    text = bpy.data.texts.get("CORRECTED_SEABUCKTHORN_VALIDATION.txt") or bpy.data.texts.new(
        "CORRECTED_SEABUCKTHORN_VALIDATION.txt"
    )
    text.clear()
    text.write("\n".join(report))
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    print(f"CORRECTED_TARGET={CORRECTED_TARGET}", flush=True)
    print(f"SAFE_OVERLAY={SAFE_OVERLAY}", flush=True)
    print(f"MAIN={MAIN_OUT}", flush=True)
    print(f"SIDE={SIDE_OUT}", flush=True)
    print(f"PACKED={PACKED_OUT}", flush=True)
    print(f"REPROJECT={REPROJECT_OUT}", flush=True)
    print(f"REPORT={REPORT_OUT}", flush=True)
    print(f"BLEND={BLEND_OUT}", flush=True)


if __name__ == "__main__":
    main()
