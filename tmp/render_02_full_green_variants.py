"""Preserve every pixel of 02.m4v in two L-screen layout tests."""

import json
import shutil
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
old = root / "renders" / "02_m4v_inverse_projection_test"
meta = json.loads((old / "projection_geometry.json").read_text(encoding="utf-8"))
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe not found")
source = root / "视频" / "02.m4v"
mask_main = old / "mask_main_960x960.pgm"
mask_side = old / "mask_side_960x960.pgm"
for path in (source, mask_main, mask_side):
    if not path.is_file():
        raise FileNotFoundError(path)


def run(args):
    print("RUN " + Path(str(args[-1])).name, flush=True)
    subprocess.run(args, check=True)


def perspective(panel):
    bl, br, tr, tl = panel["quad_bl_br_tr_tl"]
    values = [tl[0], tl[1], tr[0], tr[1], bl[0], bl[1], br[0], br[1]]
    keys = ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3")
    return "perspective=" + ":".join(f"{key}={value:.9f}" for key, value in zip(keys, values)) + ":sense=destination:interpolation=cubic"


def encode_panel(dest, vf):
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(source), "-vf", vf + ",format=yuv420p", "-an", "-frames:v", "360",
         "-r", "24", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
         "-movflags", "+faststart", str(dest)])


def encode_packed(main, side, dest):
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(main), "-i", str(side), "-i", str(source),
         "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]", "-map", "[v]", "-map", "2:a:0?",
         "-frames:v", "360", "-t", "15", "-r", "24", "-c:v", "libx264",
         "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", str(dest)])


def encode_preview(main, side, dest):
    graph = (
        f"[0:v]scale=960:960:flags=lanczos,{perspective(meta['main'])},format=rgb24[m];"
        f"[1:v]scale=960:960:flags=lanczos,{perspective(meta['side'])},format=rgb24[s];"
        "[3:v]format=gray[mm];[4:v]format=gray[sm];"
        "[m][mm]alphamerge[ma];[s][sm]alphamerge[sa];"
        "color=c=black:s=960x960:r=24:d=15,format=rgb24[base];"
        "[base][ma]overlay=format=rgb[tmp];[tmp][sa]overlay=format=rgb,format=yuv420p[v]"
    )
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(main), "-i", str(side), "-i", str(source),
         "-loop", "1", "-framerate", "24", "-i", str(mask_main),
         "-loop", "1", "-framerate", "24", "-i", str(mask_side),
         "-filter_complex", graph, "-map", "[v]", "-map", "2:a:0?",
         "-frames:v", "360", "-t", "15", "-r", "24", "-c:v", "libx264",
         "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "160k",
         "-movflags", "+faststart", str(dest)])


variants = {
    "full_frame_fill": (
        "crop=480:960:0:0,scale=1000:1800:flags=lanczos",
        "crop=480:960:480:0,scale=1000:1800:flags=lanczos",
    ),
    "full_frame_contain": (
        "scale=520:520:flags=lanczos,pad=960:960:220:220:color=0x075c3b," +
        "perspective=x0=218.812607825:y0=160.407075882:x1=479.500000000:y1=48.062904119:" +
        "x2=206.105749905:y2=838.120397985:x3=479.499914259:y3=907.173932470:" +
        "sense=source:interpolation=cubic,scale=1000:1800:flags=lanczos",
        "scale=520:520:flags=lanczos,pad=960:960:220:220:color=0x075c3b," +
        "perspective=x0=479.500000000:y0=48.062904119:x1=740.187335014:y1=160.407133043:" +
        "x2=479.499914259:y2=907.173932470:x3=752.894135773:y3=838.120426565:" +
        "sense=source:interpolation=cubic,scale=1000:1800:flags=lanczos",
    ),
}

for label, (main_vf, side_vf) in variants.items():
    out = root / "renders" / f"02_m4v_{label}_test"
    out.mkdir(parents=True, exist_ok=True)
    main = out / "01_main_1000x1800.mp4"
    side = out / "02_side_1000x1800.mp4"
    packed = out / "03_packed_2000x1800_TEST.mp4"
    preview = out / "04_sweetspot_960x960_TEST.mp4"
    encode_panel(main, main_vf)
    encode_panel(side, side_vf)
    encode_packed(main, side, packed)
    encode_preview(main, side, preview)
    print("VARIANT=" + label + " DIR=" + str(out), flush=True)
