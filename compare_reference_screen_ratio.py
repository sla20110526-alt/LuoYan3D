import bpy
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import validate_seabuckthorn_inverse_projection as core


REFERENCE = ROOT / "图片" / "参考.png"
OUT_DIR = ROOT / "renders" / "reference_screen_ratio_check"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OVERLAY_OUT = OUT_DIR / "01_reference_outer_screen_vs_blender_overlay.png"
REPORT_OUT = OUT_DIR / "ratio_check_report.txt"


def main():
    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    reference_image = bpy.data.images.load(str(REFERENCE), check_existing=False)
    reference_image.colorspace_settings.name = "sRGB"
    reference = core.image_to_array(reference_image)
    height, width = reference.shape[:2]
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.camera = camera

    # Outer black polygon of the complete physical screen in the supplied
    # reference. The inner white frame is deliberately excluded: it is content.
    # Order: top-center, top-right, bottom-right, bottom-center, bottom-left, top-left.
    reference_hex = np.asarray(
        [[1024.0, 26.0], [1431.0, 120.0], [1435.0, 1000.0],
         [1023.0, 1104.0], [610.0, 1000.0], [613.0, 120.0]],
        dtype=np.float64,
    )

    main_quad = core.projected_quad(scene, camera, main_screen, (width, height))
    side_quad = core.projected_quad(scene, camera, side_screen, (width, height))
    model_hex = np.asarray(
        [main_quad[2], side_quad[2], side_quad[1], side_quad[0], main_quad[0], main_quad[3]],
        dtype=np.float64,
    )

    # Compare proportions, not framing: fit the Blender silhouette to the same
    # top-center and bottom-center height while preserving its aspect ratio.
    reference_height = reference_hex[3, 1] - reference_hex[0, 1]
    model_height = model_hex[3, 1] - model_hex[0, 1]
    scale = reference_height / model_height
    model_fitted = (model_hex - model_hex[0]) * scale + reference_hex[0]
    center_dx = reference_hex[3, 0] - model_fitted[3, 0]
    model_fitted[:, 0] += center_dx * 0.5

    overlay = reference.copy()
    for index in range(6):
        core.draw_line(
            overlay,
            reference_hex[index],
            reference_hex[(index + 1) % 6],
            (1.0, 0.05, 0.72, 1.0),
            5,
        )
        core.draw_line(
            overlay,
            model_fitted[index],
            model_fitted[(index + 1) % 6],
            (0.0, 1.0, 1.0, 1.0),
            5,
        )
    core.save_array(OVERLAY_OUT, overlay, "REFERENCE_SCREEN_RATIO_OVERLAY")

    reference_width = float(np.max(reference_hex[:, 0]) - np.min(reference_hex[:, 0]))
    model_width = float(np.max(model_fitted[:, 0]) - np.min(model_fitted[:, 0]))
    reference_ratio = reference_width / reference_height
    model_ratio = model_width / reference_height
    width_delta = (reference_width / model_width - 1.0) * 100.0

    reference_top_drop = float((reference_hex[1, 1] + reference_hex[5, 1]) * 0.5 - reference_hex[0, 1])
    model_top_drop = float((model_fitted[1, 1] + model_fitted[5, 1]) * 0.5 - model_fitted[0, 1])
    reference_bottom_drop = float(reference_hex[3, 1] - (reference_hex[2, 1] + reference_hex[4, 1]) * 0.5)
    model_bottom_drop = float(model_fitted[3, 1] - (model_fitted[2, 1] + model_fitted[4, 1]) * 0.5)

    report = [
        "REFERENCE OUTER-SCREEN VS CURRENT BLENDER MODEL",
        "================================================",
        "Interpretation: the outer black hexagon is the complete LED screen; the inner white frame is virtual content.",
        "Blender model: two equal 2.5m x 4.5m panels, 90-degree corner.",
        "Blender view: 45-degree bisector, 6.5m plan radius, eye height 1.6m.",
        "Comparison method: equalize outer-screen projected height, preserve each silhouette's width/height proportion.",
        "",
        f"Reference image size: {width} x {height}",
        f"Reference projected outer width/height: {reference_ratio:.6f}",
        f"Current Blender projected outer width/height: {model_ratio:.6f}",
        f"Reference appears wider than current Blender model by: {width_delta:.3f}% at equal projected height",
        f"Reference top V-depth: {reference_top_drop:.3f}px; fitted Blender top V-depth: {model_top_drop:.3f}px",
        f"Reference bottom V-depth: {reference_bottom_drop:.3f}px; fitted Blender bottom V-depth: {model_bottom_drop:.3f}px",
        "",
        "RESULT: NOT AN EXACT MATCH in the current calibrated view.",
        "The physical panel ratio may still be compatible with equal 2.5m x 4.5m faces, but the reference uses a farther/higher-looking viewpoint and a wider, shallower projected silhouette.",
        "Overlay colors: magenta = supplied reference outer screen; cyan = current Blender silhouette fitted to the same height.",
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report), flush=True)
    print(f"OVERLAY={OVERLAY_OUT}", flush=True)
    print(f"REPORT={REPORT_OUT}", flush=True)


if __name__ == "__main__":
    main()
