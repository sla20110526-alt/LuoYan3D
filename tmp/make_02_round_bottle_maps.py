"""Blend full-frame side coverage into exact sweet-spot geometry near the bottle."""

import json
from pathlib import Path

import numpy as np


root = Path(__file__).resolve().parents[1]
meta_path = root / "renders" / "02_m4v_inverse_projection_test" / "projection_geometry.json"
meta = json.loads(meta_path.read_text(encoding="utf-8"))
out = root / "renders" / "02_m4v_green_round_bottle_test"
out.mkdir(parents=True, exist_ok=True)
panel_w, panel_h = meta["panel_size"]
source_w, source_h = meta["source_size"]
source_upscale = 2


def solve_homography(points_from, points_to):
    rows = []
    values = []
    for (x, y), (u, v) in zip(points_from, points_to):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.extend([u, v])
    h = np.linalg.solve(np.asarray(rows, dtype=np.float64), np.asarray(values, dtype=np.float64))
    return np.asarray([[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]])


def write_pgm(path, array):
    height, width = array.shape
    with path.open("wb") as handle:
        handle.write(f"P5\n{width} {height}\n65535\n".encode("ascii"))
        handle.write(np.ascontiguousarray(array.astype(">u2")).tobytes())


def make_panel(label):
    quad = np.asarray(meta[label]["quad_bl_br_tr_tl"], dtype=np.float64)
    rect = np.asarray([[0, panel_h - 1], [panel_w - 1, panel_h - 1],
                       [panel_w - 1, 0], [0, 0]], dtype=np.float64)
    matrix = solve_homography(rect, quad)
    xx = np.arange(panel_w, dtype=np.float64)[None, :]
    normalized_x = xx / (panel_w - 1)
    if label == "main":
        distance_from_outer = normalized_x
        fill_x = normalized_x * ((source_w - 1) / 2)
    else:
        distance_from_outer = 1 - normalized_x
        fill_x = (source_w - 1) / 2 + normalized_x * ((source_w - 1) / 2)

    # The first 5% of each panel carries the complete green outer edge.
    # By 45% from that edge, sampling follows the model's inverse projection.
    t = np.clip((distance_from_outer - 0.05) / 0.40, 0, 1)
    weight = t * t * (3 - 2 * t)
    xmap_path = out / f"{label}_xmap_1000x1800.pgm"
    ymap_path = out / f"{label}_ymap_1000x1800.pgm"
    xmap = np.empty((panel_h, panel_w), dtype=np.uint16)
    ymap = np.empty((panel_h, panel_w), dtype=np.uint16)
    min_dx = float("inf")
    for y0 in range(0, panel_h, 128):
        y1 = min(panel_h, y0 + 128)
        yy = np.arange(y0, y1, dtype=np.float64)[:, None]
        den = matrix[2, 0] * xx + matrix[2, 1] * yy + matrix[2, 2]
        inverse_x = (matrix[0, 0] * xx + matrix[0, 1] * yy + matrix[0, 2]) / den
        inverse_y = (matrix[1, 0] * xx + matrix[1, 1] * yy + matrix[1, 2]) / den
        fill_y = yy * (source_h - 1) / (panel_h - 1)
        sample_x = (1 - weight) * fill_x + weight * inverse_x
        sample_y = (1 - weight) * fill_y + weight * inverse_y
        local_dx = np.diff(sample_x, axis=1)
        min_dx = min(min_dx, float(local_dx.min()))
        # FFmpeg's remap reads absolute integer coordinates. Sampling from a
        # 2x Lanczos-upscaled source gives subpixel precision in this test.
        xmap[y0:y1] = np.rint(np.clip(sample_x * source_upscale, 0, source_w * source_upscale - 1))
        ymap[y0:y1] = np.rint(np.clip(sample_y * source_upscale, 0, source_h * source_upscale - 1))
    if min_dx <= 0:
        raise RuntimeError(f"{label} x-map folds back (min derivative {min_dx})")
    write_pgm(xmap_path, xmap)
    write_pgm(ymap_path, ymap)
    print(f"{label}: {xmap_path.name}, {ymap_path.name}, min_dx={min_dx:.6f}", flush=True)


make_panel("main")
make_panel("side")
