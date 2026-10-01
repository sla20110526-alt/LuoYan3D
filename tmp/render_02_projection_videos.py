"""Create test-only L-panel, packed, and sweet-spot videos from 02.m4v."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


root = Path(__file__).resolve().parents[1]
out = root / "renders" / "02_m4v_inverse_projection_test"
meta = json.loads((out / "projection_geometry.json").read_text(encoding="utf-8"))
ffmpeg = shutil.which("ffmpeg.exe")
if not ffmpeg:
    raise RuntimeError("ffmpeg.exe was not found")
source = Path(meta["source_video"])
if not source.is_file():
    raise FileNotFoundError(source)
width, height = meta["source_size"]
panel_w, panel_h = meta["panel_size"]
frame_count = meta["frames"]
fps = meta["fps"]


def coords(panel):
    bl, br, tr, tl = panel["quad_bl_br_tr_tl"]
    return [tl, tr, bl, br]


def perspective(panel, sense):
    tl, tr, bl, br = coords(panel)
    vals = [tl[0], tl[1], tr[0], tr[1], bl[0], bl[1], br[0], br[1]]
    terms = [f"{key}={value:.9f}" for key, value in zip(
        ("x0", "y0", "x1", "y1", "x2", "y2", "x3", "y3"), vals
    )]
    return "perspective=" + ":".join(terms) + f":sense={sense}:interpolation=cubic"


def run(args):
    print("RUN " + Path(str(args[0])).name + " -> " + Path(str(args[-1])).name, flush=True)
    subprocess.run(args, check=True)


def write_quad_mask(panel, path):
    points = panel["quad_bl_br_tr_tl"]
    orientation = None
    for edge in range(4):
        ax, ay = points[edge]
        bx, by = points[(edge + 1) % 4]
        cx, cy = points[(edge + 2) % 4]
        cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(cross) > 1e-8:
            orientation = 1 if cross > 0 else -1
            break
    if orientation is None:
        raise ValueError("Degenerate screen quad")
    edges = []
    for index in range(4):
        ax, ay = points[index]
        bx, by = points[(index + 1) % 4]
        edges.append((ax, ay, bx - ax, by - ay))
    with path.open("wb") as handle:
        handle.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        for y in range(height):
            row = bytearray(width)
            for x in range(width):
                inside = all(orientation * (dx * (y - ay) - dy * (x - ax)) >= -0.5
                             for ax, ay, dx, dy in edges)
                row[x] = 255 if inside else 0
            handle.write(row)


main = out / "01_main_prewarped_1000x1800.mp4"
side = out / "02_side_prewarped_1000x1800.mp4"
packed = out / "03_controller_packed_2000x1800_TEST.mp4"
preview = out / "04_sweetspot_roundtrip_960x960_TEST.mp4"

if "--preview-only" not in sys.argv:
    for panel_name, dest in (("main", main), ("side", side)):
        filt = perspective(meta[panel_name], "source") + f",scale={panel_w}:{panel_h}:flags=lanczos,format=yuv420p"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y",
             "-i", str(source), "-vf", filt, "-an", "-frames:v", str(frame_count),
             "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "16",
             "-movflags", "+faststart", str(dest)])

    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y",
         "-i", str(main), "-i", str(side), "-i", str(source),
         "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]", "-map", "[v]", "-map", "2:a:0?",
         "-frames:v", str(frame_count), "-t", "15", "-r", str(fps),
         "-c:v", "libx264", "-preset", "medium", "-crf", "17",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(packed)])

# The two screen faces occupy disjoint polygons in the sweet-spot view.
# Reprojecting the encoded panel videos and adding them reveals the exact
# physical silhouette and any source content clipped by that silhouette.
main_mask = out / "mask_main_960x960.pgm"
side_mask = out / "mask_side_960x960.pgm"
write_quad_mask(meta["main"], main_mask)
write_quad_mask(meta["side"], side_mask)
filter_graph = (
    f"[0:v]scale={width}:{height}:flags=lanczos,{perspective(meta['main'], 'destination')},format=rgb24[m];"
    f"[1:v]scale={width}:{height}:flags=lanczos,{perspective(meta['side'], 'destination')},format=rgb24[s];"
    "[3:v]format=gray[mm];[4:v]format=gray[sm];"
    "[m][mm]alphamerge[ma];[s][sm]alphamerge[sa];"
    f"color=c=black:s={width}x{height}:r={fps}:d=15,format=rgb24[base];"
    "[base][ma]overlay=format=rgb[tmp];[tmp][sa]overlay=format=rgb,format=yuv420p[v]"
)
run([ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y",
     "-i", str(main), "-i", str(side), "-i", str(source),
     "-loop", "1", "-framerate", str(fps), "-i", str(main_mask),
     "-loop", "1", "-framerate", str(fps), "-i", str(side_mask),
     "-filter_complex", filter_graph, "-map", "[v]", "-map", "2:a:0?",
     "-frames:v", str(frame_count), "-t", "15", "-r", str(fps),
     "-c:v", "libx264", "-preset", "medium", "-crf", "17",
     "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(preview)])

print("MAIN=" + str(main), flush=True)
print("SIDE=" + str(side), flush=True)
print("PACKED=" + str(packed), flush=True)
print("PREVIEW=" + str(preview), flush=True)
