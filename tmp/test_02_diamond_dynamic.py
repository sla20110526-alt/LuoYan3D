"""Compare foreground mattes over the diamond cuboid at key animation frames."""

import shutil
import subprocess
from pathlib import Path

import numpy as np


root = Path(__file__).resolve().parents[1]
out = root / "renders" / "02_m4v_diamond_box_test"
clean_path = root / "renders" / "02_m4v_green_round_bottle_test" / "blender_sweetspot_frame_001.png"
ffmpeg = shutil.which("ffmpeg.exe")


def read_png(path):
    raw = subprocess.check_output([ffmpeg, "-hide_banner", "-loglevel", "error",
                                   "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return np.frombuffer(raw, dtype=np.uint8).reshape((960, 960, 3)).copy()


def write_png(path, rgb):
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "960x960",
                    "-i", "-", "-frames:v", "1", str(path)],
                   input=rgb.tobytes(), check=True)


ENVELOPES = {
    160: ([570, 605, 650, 720, 770, 795, 805], [0, 45, 95, 150, 155, 115, 0]),
    180: ([380, 410, 455, 520, 620, 720, 770, 800], [0, 55, 125, 155, 165, 155, 125, 0]),
    200: ([310, 330, 380, 430, 500, 650, 745, 780], [0, 50, 90, 150, 165, 160, 130, 0]),
    220: ([276, 282, 320, 400, 500, 700, 740, 750, 758], [0, 50, 65, 85, 92, 92, 82, 65, 0]),
    240: ([213, 219, 260, 320, 450, 700, 760, 777, 785, 792], [0, 55, 65, 80, 110, 110, 100, 95, 70, 0]),
    260: ([145, 151, 200, 260, 350, 700, 760, 800, 818, 832], [0, 60, 70, 95, 125, 125, 115, 115, 100, 0]),
}


def envelope(n):
    ys, widths = ENVELOPES[n]
    hw = np.interp(np.arange(960), ys, widths, left=0, right=0)
    x = np.arange(960)[None, :]
    return ((np.abs(x - 480) < hw[:, None]) & (hw[:, None] > 0)).astype(np.float32)


def row_matte(diff, guard):
    left = np.full(960, 480.0)
    right = np.full(960, 480.0)
    for row in range(60, 900):
        xs = np.where((diff[row, 300:660] > 30) & (guard[row, 300:660] > 0))[0]
        if xs.size:
            left[row] = xs[0] + 300 - 5
            right[row] = xs[-1] + 300 + 5
    active = np.flatnonzero(right > left)
    if not active.size:
        return np.zeros((960, 960), dtype=np.float32)
    lo, hi = int(active[0]), int(active[-1])
    for edge in (left, right):
        edge[lo:hi + 1] = np.interp(np.arange(lo, hi + 1), active, edge[active])
        padded = np.pad(edge[lo:hi + 1], (5, 5), mode="edge")
        med = np.asarray([np.median(padded[i:i + 11]) for i in range(hi - lo + 1)])
        edge[lo:hi + 1] = np.convolve(np.pad(med, (2, 2), mode="edge"),
                                      [1, 2, 3, 2, 1], mode="valid") / 9
    x = np.arange(960, dtype=np.float32)[None, :]
    alpha = np.clip((x - left[:, None]) / 4, 0, 1) * np.clip((right[:, None] - x) / 4, 0, 1)
    alpha[:lo] = 0
    alpha[hi + 1:] = 0
    return alpha * guard


def pixel_matte(diff, guard):
    binary = np.zeros((960, 960), dtype=np.float32)
    binary[60:900, 300:660] = (diff[60:900, 300:660] > 30).astype(np.float32)
    binary *= guard
    for _ in range(2):
        binary = np.maximum.reduce((binary, np.roll(binary, 1, 0),
                                    np.roll(binary, -1, 0), np.roll(binary, 1, 1),
                                    np.roll(binary, -1, 1)))
    for axis in (0, 1):
        padded = np.pad(binary, ((2, 2), (0, 0)) if axis == 0 else ((0, 0), (2, 2)), mode="edge")
        if axis == 0:
            binary = sum(padded[i:i + 960] for i in range(5)) / 5
        else:
            binary = sum(padded[:, i:i + 960] for i in range(5)) / 5
    return binary * guard


clean = read_png(clean_path)
base_clean = read_png(root / "renders" / "02_m4v_full_frame_fill_test" /
                      "blender_sweetspot_frame_001.png")
for n in (160, 180, 200, 220, 240, 260):
    base = read_png(out / f"base_{n}.png")
    front = read_png(out / f"front_{n}.png")
    diff = np.max(np.abs(front.astype(np.int16) - clean.astype(np.int16)), axis=2)
    guard = envelope(n)
    for label, alpha in (("row", row_matte(diff, guard)), ("pixel", pixel_matte(diff, guard))):
        rgb = np.rint(front * alpha[:, :, None] + base * (1 - alpha[:, :, None])).astype(np.uint8)
        write_png(out / f"diamond_{label}_{n}.png", rgb)
        rgb_clean = np.rint(front * alpha[:, :, None] +
                            base_clean * (1 - alpha[:, :, None])).astype(np.uint8)
        write_png(out / f"diamond_clean_{label}_{n}.png", rgb_clean)
    print("frame", n, "diffmax", int(diff.max()), flush=True)
