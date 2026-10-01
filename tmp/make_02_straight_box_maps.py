"""Make panel remap textures that retain the gold box's straight silhouette."""

import json
from pathlib import Path

import numpy as np


root = Path(__file__).resolve().parents[1]
meta = json.loads((root / "renders" / "02_m4v_inverse_projection_test" /
                   "projection_geometry.json").read_text(encoding="utf-8"))
out = root / "renders" / "02_m4v_straight_box_test"
out.mkdir(parents=True, exist_ok=True)
panel_w, panel_h = meta["panel_size"]
source_w, source_h = meta["source_size"]
upscale = 2


def solve_homography(points_from, points_to):
    rows = []
    values = []
    for (x, y), (u, v) in zip(points_from, points_to):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.extend([u, v])
    h = np.linalg.solve(np.asarray(rows, dtype=np.float64),
                        np.asarray(values, dtype=np.float64))
    return np.asarray([[h[0], h[1], h[2]],
                       [h[3], h[4], h[5]],
                       [h[6], h[7], 1.0]])


def write_pgm(path, array):
    height, width = array.shape
    with path.open("wb") as handle:
        handle.write(f"P5\n{width} {height}\n65535\n".encode("ascii"))
        handle.write(np.ascontiguousarray(array.astype(">u2")).tobytes())


def left_x_warp(target_x):
    # At x=235 the straight gold side maps to the source's x=122.
    # The bottle stays close to a uniform scale at the centre; most of the
    # compression is pushed into the green and the scenery beside the box.
    knots = ((206.0, 0.0, 4.20),
             (235.0, 122.0, 2.60),
             (335.0, 320.0, 1.25),
             (479.5, 479.5, 1.10))
    result = np.zeros_like(target_x)
    for (x0, y0, m0), (x1, y1, m1) in zip(knots[:-1], knots[1:]):
        selected = (target_x >= x0) & (target_x <= x1)
        t = (target_x[selected] - x0) / (x1 - x0)
        h00 = 2 * t**3 - 3 * t**2 + 1
        h10 = t**3 - 2 * t**2 + t
        h01 = -2 * t**3 + 3 * t**2
        h11 = t**3 - t**2
        result[selected] = (h00 * y0 + h10 * (x1 - x0) * m0 +
                            h01 * y1 + h11 * (x1 - x0) * m1)
    return result


def source_x(projected_x):
    left = projected_x <= 479.5
    mirrored_x = np.where(left, projected_x, 959.0 - projected_x)
    mapped_left = left_x_warp(np.maximum(mirrored_x, 206.0))
    mapped = np.where(left, mapped_left, 959.0 - mapped_left)
    return np.clip(mapped, 0, 959)


def source_y(projected_y):
    # The top and bottom gold edges remain horizontal at y=180 and y=795.
    return np.interp(projected_y, [48.0, 180.0, 795.0, 907.0],
                     [0.0, 112.0, 800.0, 959.0])


def make_panel(label):
    quad = np.asarray(meta[label]["quad_bl_br_tr_tl"], dtype=np.float64)
    rect = np.asarray([[0, panel_h - 1], [panel_w - 1, panel_h - 1],
                       [panel_w - 1, 0], [0, 0]], dtype=np.float64)
    matrix = solve_homography(rect, quad)
    xx = np.arange(panel_w, dtype=np.float64)[None, :]
    xmap = np.empty((panel_h, panel_w), dtype=np.uint16)
    ymap = np.empty((panel_h, panel_w), dtype=np.uint16)
    min_dx = float("inf")
    for y0 in range(0, panel_h, 128):
        y1 = min(panel_h, y0 + 128)
        yy = np.arange(y0, y1, dtype=np.float64)[:, None]
        den = matrix[2, 0] * xx + matrix[2, 1] * yy + matrix[2, 2]
        projected_x = (matrix[0, 0] * xx + matrix[0, 1] * yy + matrix[0, 2]) / den
        projected_y = (matrix[1, 0] * xx + matrix[1, 1] * yy + matrix[1, 2]) / den
        sx = source_x(projected_x)
        sy = source_y(projected_y)
        min_dx = min(min_dx, float(np.diff(sx, axis=1).min()))
        xmap[y0:y1] = np.rint(sx * upscale)
        ymap[y0:y1] = np.rint(sy * upscale)
    if min_dx <= 0:
        raise RuntimeError(f"{label} x-map folded: min derivative {min_dx}")
    write_pgm(out / f"{label}_xmap_1000x1800.pgm", xmap)
    write_pgm(out / f"{label}_ymap_1000x1800.pgm", ymap)
    print(f"{label}: min_dx={min_dx:.6f}", flush=True)


make_panel("main")
make_panel("side")
