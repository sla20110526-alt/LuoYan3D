import math
import os
import sys

from mathutils import Vector


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import build_corner_calibration_test as test


# Confirmed physical LED configuration: two equal vertical faces.
test.MAIN_W = 2.5
test.SIDE_W = 2.5
test.SCREEN_H = 4.5

# Provisional symmetric sweet spot: 6.5 m plan radius on the 45-degree bisector.
axis = 6.5 / math.sqrt(2.0)
test.EYE = Vector((axis, -axis, 1.60))

test.FRAME_CROSS = 37
test.CUBE_START = (-1.70, 0.50, 2.15)
test.CUBE_END = (-0.50, 1.70, 2.15)
test.PREVIEW_TARGET = (-0.90, 0.90, 2.25)

# 200 px/m diagnostic raster: equal 500 px panels, 900 px high.
test.MAIN_RES = (500, 900)
test.SIDE_RES = (500, 900)
test.PACKED_RES = (1000, 900)
test.PREVIEW_RES = (960, 540)

test.OUT_DIR = os.path.join(ROOT_DIR, "renders", "corner_calibration_2p5x2p5_v2")
os.makedirs(test.OUT_DIR, exist_ok=True)
test.BLEND_PATH = os.path.join(ROOT_DIR, "L_LED_corner_calibration_2p5x2p5_v2.blend")
test.REPORT_PATH = os.path.join(test.OUT_DIR, "projection_validation_2p5x2p5.txt")

test.MAIN_VIDEO = os.path.join(test.OUT_DIR, "01_main_panel_500x900.mp4")
test.SIDE_VIDEO = os.path.join(test.OUT_DIR, "02_side_panel_500x900.mp4")
test.PACKED_VIDEO = os.path.join(test.OUT_DIR, "03_one_controller_packed_1000x900.mp4")
test.PREVIEW_VIDEO = os.path.join(test.OUT_DIR, "04_sweet_spot_reprojection_preview_960x540.mp4")

test.MAIN_STILL = os.path.join(test.OUT_DIR, "01_main_panel_crossing_frame.png")
test.SIDE_STILL = os.path.join(test.OUT_DIR, "02_side_panel_crossing_frame.png")
test.PACKED_STILL = os.path.join(test.OUT_DIR, "03_one_controller_crossing_frame.png")
test.PREVIEW_STILL = os.path.join(test.OUT_DIR, "04_sweet_spot_crossing_frame.png")


if __name__ == "__main__":
    test.main()
