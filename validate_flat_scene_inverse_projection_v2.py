"""Project the user-designated flat scene through the existing L-screen model."""

from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_seabuckthorn_inverse_projection as base


ROOT = Path(__file__).resolve().parent
base.SOURCE = ROOT / "图片" / "资产" / "沙棘时空盒_1比1双屏轮廓适配_候选v3.png"
base.OUT_DIR = ROOT / "renders" / "flat_scene_inverse_projection_v3"
base.OUT_DIR.mkdir(parents=True, exist_ok=True)
base.MAIN_OUT = base.OUT_DIR / "01_main_prewarped_1000x1800.png"
base.SIDE_OUT = base.OUT_DIR / "02_side_prewarped_1000x1800.png"
base.PACKED_OUT = base.OUT_DIR / "03_controller_packed_2000x1800.png"
base.TARGET_MASKED_OUT = base.OUT_DIR / "04_target_masked_to_exact_LED_source_resolution.png"
base.TARGET_OVERLAY_OUT = base.OUT_DIR / "05_target_with_exact_LED_outline_source_resolution.png"
base.REPROJECT_OUT = base.OUT_DIR / "06_blender_reprojection_from_sweet_spot_source_resolution.png"
base.DIFF_OUT = base.OUT_DIR / "07_roundtrip_difference_heatmap.png"
base.REPORT_OUT = base.OUT_DIR / "validation_report.txt"
base.BLEND_OUT = ROOT / "Lscreen_magicbox_FLAT_SCENE_INVERSE_PROJECTION_V3.blend"


if __name__ == "__main__":
    scene = bpy.context.scene
    for layer in scene.view_layers:
        layer.use = layer.name == "02_检查实体双屏"
    scene.use_nodes = False

    base.main()
