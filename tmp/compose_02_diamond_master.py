"""Keep the perspective-diamond cuboid while preserving the bottle silhouette."""

import shutil
import subprocess
from pathlib import Path

import numpy as np


root = Path(__file__).resolve().parents[1]
out = root / "renders" / "02_m4v_diamond_box_test"
source = root / "视频" / "02.m4v"
base_video = root / "renders" / "02_m4v_full_frame_fill_test" / "04_sweetspot_960x960_TEST.mp4"
front_video = root / "renders" / "02_m4v_green_round_bottle_test" / "04_sweetspot_960x960_TEST.mp4"
master = out / "00_diamond_composite_master_960x960.mp4"
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe not found")
for path in (source, base_video, front_video):
    if not path.is_file():
        raise FileNotFoundError(path)

frame_size = 960 * 960 * 3
x_grid = np.arange(960, dtype=np.float32)[None, :]
y_grid = np.arange(960, dtype=np.float32)

# Bottle/honey contours at sampled animation frames. Width is measured from
# the picture centre. The contour constrains the foreground extraction so
# moving sunlight and the gold ceiling are not mistaken for the bottle.
envelopes = {
    180: ([380, 410, 455, 520, 620, 720, 770, 800],
          [0, 55, 125, 155, 165, 155, 125, 0]),
    200: ([310, 330, 380, 430, 500, 650, 745, 780],
          [0, 50, 90, 150, 165, 160, 130, 0]),
    220: ([276, 282, 320, 400, 500, 700, 740, 750, 758],
          [0, 50, 65, 85, 92, 92, 82, 65, 0]),
    240: ([213, 219, 260, 320, 450, 700, 760, 777, 785, 792],
          [0, 55, 65, 80, 110, 110, 100, 95, 70, 0]),
    260: ([145, 151, 200, 260, 350, 700, 760, 800, 818, 832],
          [0, 60, 70, 95, 125, 125, 115, 115, 100, 0]),
    289: ([65, 73, 112, 140, 180, 205, 240, 275, 430, 775, 825, 858, 880, 889],
          [0, 64, 67, 66, 85, 100, 127, 140, 143, 143, 140, 130, 122, 0]),
    359: ([55, 62, 105, 140, 180, 210, 250, 285, 440, 785, 830, 865, 890, 900],
          [0, 65, 68, 68, 88, 105, 132, 145, 147, 147, 143, 133, 122, 0]),
}
profile = {frame: np.interp(y_grid, ys, widths, left=0, right=0)
           for frame, (ys, widths) in envelopes.items()}
keys = sorted(profile)


def envelope(frame):
    if frame <= keys[0]:
        width = profile[keys[0]]
    elif frame >= keys[-1]:
        width = profile[keys[-1]]
    else:
        high = next(key for key in keys if key >= frame)
        low = keys[keys.index(high) - 1]
        mix = (frame - low) / (high - low)
        width = profile[low] * (1 - mix) + profile[high] * mix
    return (np.abs(x_grid - 480.0) < width[:, None]) & (width[:, None] > 0)


def row_matte(front, clean_front, guard):
    diff = np.max(np.abs(front.astype(np.int16) - clean_front.astype(np.int16)), axis=2)
    left = np.full(960, 480.0, dtype=np.float32)
    right = np.full(960, 480.0, dtype=np.float32)
    for row in range(60, 900):
        xs = np.where((diff[row, 300:660] > 30) & guard[row, 300:660])[0]
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
    alpha = np.clip((x_grid - left[:, None]) / 4, 0, 1) * np.clip(
        (right[:, None] - x_grid) / 4, 0, 1)
    alpha[:lo] = 0
    alpha[hi + 1:] = 0
    return alpha * guard


def read_exact(pipe):
    chunks = []
    remaining = frame_size
    while remaining:
        data = pipe.read(remaining)
        if not data:
            raise EOFError("A decoder ended before all 360 frames were read")
        chunks.append(data)
        remaining -= len(data)
    return np.frombuffer(b"".join(chunks), dtype=np.uint8).reshape((960, 960, 3)).copy()


def decoder(path):
    return subprocess.Popen([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path),
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


base_decoder = decoder(base_video)
front_decoder = decoder(front_video)
encoder = subprocess.Popen([
    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
    "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "960x960", "-r", "24", "-i", "-",
    "-i", str(source), "-map", "0:v", "-map", "1:a:0?", "-frames:v", "360",
    "-t", "15", "-c:v", "libx264", "-preset", "medium", "-crf", "15",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
    "-movflags", "+faststart", str(master),
], stdin=subprocess.PIPE)

base_clean = None
front_clean = None
previous_alpha = None
try:
    for frame in range(360):
        base = read_exact(base_decoder.stdout)
        front = read_exact(front_decoder.stdout)
        if frame == 0:
            base_clean = base.copy()
            front_clean = front.copy()
        if frame < 214:
            composed = base
        else:
            transition = np.clip((frame - 214) / 3.0, 0.0, 1.0)
            transition = transition * transition * (3 - 2 * transition)
            matte = row_matte(front, front_clean, envelope(frame))
            if previous_alpha is not None:
                matte = 0.75 * matte + 0.25 * previous_alpha
            previous_alpha = matte
            # Inside the object, morph from the original live footage to the
            # round corrected object; outside, dissolve to clean cuboid walls.
            background = base * (1 - transition) + base_clean * transition
            subject = base * (1 - transition) + front * transition
            composed = np.rint(background * (1 - matte[:, :, None]) +
                                subject * matte[:, :, None]).astype(np.uint8)
        encoder.stdin.write(composed.tobytes())
        if frame % 30 == 0 or frame == 359:
            print(f"COMPOSITE {frame + 1}/360", flush=True)
finally:
    encoder.stdin.close()
    encoder_code = encoder.wait()
    base_decoder.stdout.close()
    front_decoder.stdout.close()
    base_code = base_decoder.wait()
    front_code = front_decoder.wait()
if encoder_code or base_code or front_code:
    raise RuntimeError(f"ffmpeg failure: encoder={encoder_code}, base={base_code}, front={front_code}")
print("MASTER=" + str(master), flush=True)
