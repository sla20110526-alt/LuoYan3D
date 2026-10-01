"""Preview the cuboid silhouette with an independently preserved round bottle."""

import shutil
import subprocess
from pathlib import Path

import numpy as np


root = Path(__file__).resolve().parents[1]
base_dir = root / "renders" / "02_m4v_full_frame_fill_test"
front_dir = root / "renders" / "02_m4v_green_round_bottle_test"
out_dir = root / "renders" / "02_m4v_diamond_box_test"
out_dir.mkdir(parents=True, exist_ok=True)
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe not found")


def read_png(path):
    raw = subprocess.check_output([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ])
    return np.frombuffer(raw, dtype=np.uint8).reshape((960, 960, 3)).copy()


def write_png(path, rgb):
    subprocess.run([
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "960x960",
        "-i", "-", "-frames:v", "1", str(path)
    ], input=rgb.tobytes(), check=True)


base = read_png(base_dir / "blender_sweetspot_frame_289.png")
base_clean = read_png(base_dir / "blender_sweetspot_frame_001.png")
front = read_png(front_dir / "blender_sweetspot_frame_289.png")
clean = read_png(front_dir / "blender_sweetspot_frame_001.png")
diff = np.max(np.abs(front.astype(np.int16) - clean.astype(np.int16)), axis=2).astype(np.uint8)
write_png(out_dir / "foreground_difference_289.png", np.repeat(diff[:, :, None], 3, axis=2))
for sample_y in (75, 110, 150, 180, 200, 240, 280, 350, 450, 600, 775, 825, 860, 880):
    print(f"y={sample_y}", end=" ")
    for threshold in (20, 30, 40, 60):
        xs = np.where(diff[sample_y, 300:660] > threshold)[0]
        if len(xs):
            print(f"T{threshold}:{xs[0]+300}-{xs[-1]+300}", end=" ")
    print()
y = np.arange(960, dtype=np.float32)[:, None]
x = np.arange(960, dtype=np.float32)[None, :]
half_width = np.interp(
    y[:, 0],
    [65, 73, 112, 140, 180, 205, 240, 275, 430, 775, 825, 858, 880, 889],
    [0, 64, 67, 66, 85, 100, 127, 140, 143, 143, 140, 130, 122, 0]
)[:, None]
horizontal = np.clip((half_width - np.abs(x - 480.0)) / 3.0, 0, 1)
vertical = np.clip((y - 67) / 5, 0, 1) * np.clip((887 - y) / 5, 0, 1)
alpha = (horizontal * vertical)[:, :, None]
result = np.rint(front * alpha + base * (1 - alpha)).astype(np.uint8)
write_png(out_dir / "diamond_bottle_frame_289_PREVIEW.png", result)
left_edge = np.full(960, 480.0)
right_edge = np.full(960, 480.0)
for row in range(65, 890):
    candidate = np.where(diff[row, 300:660] > 30)[0]
    if candidate.size:
        guard = float(half_width[row, 0]) + 4
        left_edge[row] = max(candidate[0] + 300 - 5, 480 - guard)
        right_edge[row] = min(candidate[-1] + 300 + 5, 480 + guard)
valid = right_edge > left_edge
active_rows = np.flatnonzero(valid)
lo, hi = int(active_rows[0]), int(active_rows[-1])
for edges in (left_edge, right_edge):
    edges[lo:hi + 1] = np.interp(np.arange(lo, hi + 1), active_rows, edges[active_rows])
    padded = np.pad(edges[lo:hi + 1], (5, 5), mode="edge")
    median = np.asarray([np.median(padded[i:i + 11]) for i in range(hi - lo + 1)])
    edges[lo:hi + 1] = np.convolve(np.pad(median, (2, 2), mode="edge"),
                                   [1, 2, 3, 2, 1], mode="valid") / 9
valid[lo:hi + 1] = True
diff_alpha = np.clip((x - left_edge[:, None]) / 4, 0, 1) * np.clip(
    (right_edge[:, None] - x) / 4, 0, 1)
diff_alpha *= valid[:, None]
diff_result = np.rint(front * diff_alpha[:, :, None] +
                      base * (1 - diff_alpha[:, :, None])).astype(np.uint8)
write_png(out_dir / "diamond_bottle_diffmask_289_PREVIEW.png", diff_result)
cleanbase_result = np.rint(front * diff_alpha[:, :, None] +
                           base_clean * (1 - diff_alpha[:, :, None])).astype(np.uint8)
write_png(out_dir / "diamond_bottle_cleanbase_289_PREVIEW.png", cleanbase_result)
print(out_dir / "diamond_bottle_frame_289_PREVIEW.png", flush=True)
