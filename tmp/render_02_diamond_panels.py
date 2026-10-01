"""Project the composite cuboid view back to the two physical LED faces."""

import json
import shutil
import subprocess
from pathlib import Path


root = Path(__file__).resolve().parents[1]
out = root / "renders" / "02_m4v_diamond_box_test"
old = root / "renders" / "02_m4v_inverse_projection_test"
meta = json.loads((old / "projection_geometry.json").read_text(encoding="utf-8"))
source = out / "00_diamond_composite_master_960x960.mp4"
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe not found")


def perspective(panel, sense):
    bl, br, tr, tl = panel["quad_bl_br_tr_tl"]
    values = [tl[0], tl[1], tr[0], tr[1], bl[0], bl[1], br[0], br[1]]
    keys = ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3")
    return "perspective=" + ":".join(
        f"{key}={value:.9f}" for key, value in zip(keys, values)
    ) + f":sense={sense}:interpolation=cubic"


def run(label, args):
    print("RENDER " + label, flush=True)
    subprocess.run(args, check=True)


main = out / "01_main_1000x1800.mp4"
side = out / "02_side_1000x1800.mp4"
for label, path in (("main", main), ("side", side)):
    filt = perspective(meta[label], "source") + ",scale=1000:1800:flags=lanczos,format=yuv420p"
    run(label, [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source), "-vf", filt, "-map", "0:v", "-an",
                "-frames:v", "360", "-r", "24", "-c:v", "libx264",
                "-preset", "medium", "-crf", "16", "-movflags", "+faststart", str(path)])

packed = out / "03_packed_2000x1800_TEST.mp4"
run("packed", [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
               "-i", str(main), "-i", str(side), "-i", str(source),
               "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]", "-map", "[v]",
               "-map", "2:a:0?", "-frames:v", "360", "-t", "15", "-r", "24",
               "-c:v", "libx264", "-preset", "medium", "-crf", "17",
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(packed)])

graph = (
    f"[0:v]scale=960:960:flags=lanczos,{perspective(meta['main'], 'destination')},format=rgb24[m];"
    f"[1:v]scale=960:960:flags=lanczos,{perspective(meta['side'], 'destination')},format=rgb24[s];"
    "[3:v]format=gray[mm];[4:v]format=gray[sm];"
    "[m][mm]alphamerge[ma];[s][sm]alphamerge[sa];"
    "color=c=black:s=960x960:r=24:d=15,format=rgb24[base];"
    "[base][ma]overlay=format=rgb[tmp];"
    "[tmp][sa]overlay=format=rgb,format=yuv420p[v]"
)
preview = out / "04_sweetspot_roundtrip_960x960_TEST.mp4"
run("sweetspot roundtrip", [
    ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
    "-i", str(main), "-i", str(side), "-i", str(source),
    "-loop", "1", "-framerate", "24", "-i", str(old / "mask_main_960x960.pgm"),
    "-loop", "1", "-framerate", "24", "-i", str(old / "mask_side_960x960.pgm"),
    "-filter_complex", graph, "-map", "[v]", "-map", "2:a:0?",
    "-frames:v", "360", "-t", "15", "-r", "24", "-c:v", "libx264",
    "-preset", "medium", "-crf", "17", "-c:a", "aac", "-b:a", "160k",
    "-movflags", "+faststart", str(preview),
])
print("OUTPUT=" + str(out), flush=True)
