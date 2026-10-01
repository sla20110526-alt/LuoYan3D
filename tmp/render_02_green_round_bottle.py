"""Render the complete green 02.m4v with locally corrected bottle geometry."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[1]
straight_box = "--straight-box" in sys.argv
out = root / "renders" / ("02_m4v_straight_box_test" if straight_box else
                          "02_m4v_green_round_bottle_test")
old = root / "renders" / "02_m4v_inverse_projection_test"
source = root / "视频" / "02.m4v"
meta = json.loads((old / "projection_geometry.json").read_text(encoding="utf-8"))
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe not found")


def run(label, args):
    print("RENDER " + label, flush=True)
    subprocess.run(args, check=True)


def perspective(panel):
    bl, br, tr, tl = panel["quad_bl_br_tr_tl"]
    values = [tl[0], tl[1], tr[0], tr[1], bl[0], bl[1], br[0], br[1]]
    keys = ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3")
    return "perspective=" + ":".join(
        f"{key}={value:.9f}" for key, value in zip(keys, values)
    ) + ":sense=destination:interpolation=cubic"


def encode_panel(label, dest):
    xmap = out / f"{label}_xmap_1000x1800.pgm"
    ymap = out / f"{label}_ymap_1000x1800.pgm"
    for path in (source, xmap, ymap):
        if not path.is_file():
            raise FileNotFoundError(path)
    graph = (
        "[0:v]scale=1920:1920:flags=lanczos,format=rgb24[src];"
        "[src][1:v][2:v]remap=fill=black,format=yuv420p[out]"
    )
    run(label, [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-loop", "1", "-framerate", "24", "-i", str(xmap),
        "-loop", "1", "-framerate", "24", "-i", str(ymap),
        "-filter_complex", graph,
        "-map", "[out]", "-an", "-frames:v", "360", "-r", "24",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-movflags", "+faststart", str(dest),
    ])


def encode_packed(main, side, dest):
    run("packed", [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(main), "-i", str(side), "-i", str(source),
        "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]",
        "-map", "[v]", "-map", "2:a:0?", "-frames:v", "360", "-t", "15",
        "-r", "24", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest),
    ])


def encode_preview(main, side, dest):
    graph = (
        f"[0:v]scale=960:960:flags=lanczos,{perspective(meta['main'])},format=rgb24[m];"
        f"[1:v]scale=960:960:flags=lanczos,{perspective(meta['side'])},format=rgb24[s];"
        "[3:v]format=gray[mm];[4:v]format=gray[sm];"
        "[m][mm]alphamerge[ma];[s][sm]alphamerge[sa];"
        "color=c=black:s=960x960:r=24:d=15,format=rgb24[base];"
        "[base][ma]overlay=format=rgb[tmp];"
        "[tmp][sa]overlay=format=rgb,format=yuv420p[v]"
    )
    run("sweetspot preview", [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(main), "-i", str(side), "-i", str(source),
        "-loop", "1", "-framerate", "24", "-i", str(old / "mask_main_960x960.pgm"),
        "-loop", "1", "-framerate", "24", "-i", str(old / "mask_side_960x960.pgm"),
        "-filter_complex", graph, "-map", "[v]", "-map", "2:a:0?",
        "-frames:v", "360", "-t", "15", "-r", "24", "-c:v", "libx264",
        "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(dest),
    ])


out.mkdir(parents=True, exist_ok=True)
main = out / "01_main_1000x1800.mp4"
side = out / "02_side_1000x1800.mp4"
encode_panel("main", main)
encode_panel("side", side)
encode_packed(main, side, out / "03_packed_2000x1800_TEST.mp4")
encode_preview(main, side, out / "04_sweetspot_960x960_TEST.mp4")
print("OUTPUT=" + str(out), flush=True)
