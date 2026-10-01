import bpy
import math
import os
from pathlib import Path

import numpy as np
from bpy_extras.object_utils import world_to_camera_view


ROOT = Path(__file__).resolve().parent
SOURCE = Path(r"C:\Users\观照\Downloads\沙棘合成效果图02.png")
OUT_DIR = ROOT / "renders" / "seabuckthorn_inverse_projection_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MAIN_OUT = OUT_DIR / "01_main_prewarped_1000x1800.png"
SIDE_OUT = OUT_DIR / "02_side_prewarped_1000x1800.png"
PACKED_OUT = OUT_DIR / "03_controller_packed_2000x1800.png"
TARGET_MASKED_OUT = OUT_DIR / "04_target_masked_to_exact_LED_source_resolution.png"
TARGET_OVERLAY_OUT = OUT_DIR / "05_target_with_exact_LED_outline_source_resolution.png"
REPROJECT_OUT = OUT_DIR / "06_blender_reprojection_from_sweet_spot_source_resolution.png"
DIFF_OUT = OUT_DIR / "07_roundtrip_difference_heatmap.png"
REPORT_OUT = OUT_DIR / "validation_report.txt"
BLEND_OUT = ROOT / "Lscreen_seabuckthorn_inverse_projection_validation.blend"

MAIN_SIZE = (1000, 1800)
SIDE_SIZE = (1000, 1800)


def image_to_array(image):
    width, height = image.size
    flat = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(flat)
    # Blender pixel storage starts at the lower-left; calculations below use top-left.
    return flat.reshape((height, width, 4))[::-1].copy()


def save_array(path, array, name):
    height, width = array.shape[:2]
    if array.shape[2] == 3:
        alpha = np.ones((height, width, 1), dtype=array.dtype)
        array = np.concatenate((array, alpha), axis=2)
    image = bpy.data.images.get(name)
    if image is not None:
        bpy.data.images.remove(image)
    image = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=False)
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(np.ascontiguousarray(array[::-1]).reshape(-1))
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    return image


def solve_homography(points_from, points_to):
    rows = []
    values = []
    for (x, y), (u, v) in zip(points_from, points_to):
        rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        values.extend([u, v])
    h = np.linalg.solve(np.asarray(rows, dtype=np.float64), np.asarray(values, dtype=np.float64))
    return np.asarray(
        [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]],
        dtype=np.float64,
    )


def bilinear_sample(image, sx, sy):
    height, width = image.shape[:2]
    valid = (sx >= 0.0) & (sx <= width - 1.0) & (sy >= 0.0) & (sy <= height - 1.0)
    sx_clip = np.clip(sx, 0.0, width - 1.0)
    sy_clip = np.clip(sy, 0.0, height - 1.0)
    x0 = np.floor(sx_clip).astype(np.int32)
    y0 = np.floor(sy_clip).astype(np.int32)
    x1 = np.minimum(x0 + 1, width - 1)
    y1 = np.minimum(y0 + 1, height - 1)
    wx = (sx_clip - x0)[..., None]
    wy = (sy_clip - y0)[..., None]
    top = image[y0, x0] * (1.0 - wx) + image[y0, x1] * wx
    bottom = image[y1, x0] * (1.0 - wx) + image[y1, x1] * wx
    sampled = top * (1.0 - wy) + bottom * wy
    sampled[~valid] = 0.0
    return sampled.astype(np.float32)


def warp_quad_to_rect(source, source_quad, out_size):
    out_width, out_height = out_size
    rect = np.asarray(
        [[0.0, out_height - 1.0], [out_width - 1.0, out_height - 1.0],
         [out_width - 1.0, 0.0], [0.0, 0.0]],
        dtype=np.float64,
    )
    matrix = solve_homography(rect, np.asarray(source_quad, dtype=np.float64))
    result = np.empty((out_height, out_width, 4), dtype=np.float32)
    xs = np.arange(out_width, dtype=np.float64)[None, :]
    chunk = 192
    for y_start in range(0, out_height, chunk):
        y_end = min(out_height, y_start + chunk)
        ys = np.arange(y_start, y_end, dtype=np.float64)[:, None]
        denominator = matrix[2, 0] * xs + matrix[2, 1] * ys + matrix[2, 2]
        sx = (matrix[0, 0] * xs + matrix[0, 1] * ys + matrix[0, 2]) / denominator
        sy = (matrix[1, 0] * xs + matrix[1, 1] * ys + matrix[1, 2]) / denominator
        result[y_start:y_end] = bilinear_sample(source, sx, sy)
    return result


def projected_quad(scene, camera, obj, image_size):
    width, height = image_size
    # Polygon loop order matches the panel UV order:
    # bottom-left, bottom-right, top-right, top-left as seen from the sweet spot.
    polygon = obj.data.polygons[0]
    coords = []
    for vertex_index in polygon.vertices:
        world = obj.matrix_world @ obj.data.vertices[vertex_index].co
        co = world_to_camera_view(scene, camera, world)
        coords.append((co.x * (width - 1.0), (1.0 - co.y) * (height - 1.0)))
    return np.asarray(coords, dtype=np.float64)


def inside_convex_quad(width, height, quad):
    yy, xx = np.mgrid[0:height, 0:width]
    points_x = xx.astype(np.float64)
    points_y = yy.astype(np.float64)
    signs = []
    for index in range(4):
        a = quad[index]
        b = quad[(index + 1) % 4]
        cross = (b[0] - a[0]) * (points_y - a[1]) - (b[1] - a[1]) * (points_x - a[0])
        signs.append(cross)
    stack = np.stack(signs, axis=0)
    return np.all(stack >= -0.75, axis=0) | np.all(stack <= 0.75, axis=0)


def draw_line(image, a, b, color, thickness=4):
    height, width = image.shape[:2]
    length = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1])) * 2)
    ts = np.linspace(0.0, 1.0, length)
    xs = np.rint(a[0] + (b[0] - a[0]) * ts).astype(np.int32)
    ys = np.rint(a[1] + (b[1] - a[1]) * ts).astype(np.int32)
    radius = max(1, thickness // 2)
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            px = np.clip(xs + dx, 0, width - 1)
            py = np.clip(ys + dy, 0, height - 1)
            image[py, px, :3] = color[:3]
            image[py, px, 3] = color[3]


def make_emission_material(name, image):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    texture.extension = "CLIP"
    emission.inputs["Strength"].default_value = 1.0
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def replace_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


def configure_clean_render(scene, camera, view_size):
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = view_size[0]
    scene.render.resolution_y = view_size[1]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.filepath = str(REPROJECT_OUT)
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "None"
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    world = scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.0


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    target_image = bpy.data.images.load(str(SOURCE), check_existing=False)
    target_image.colorspace_settings.name = "sRGB"
    target = image_to_array(target_image)
    view_size = (target.shape[1], target.shape[0])
    scene.render.resolution_x = view_size[0]
    scene.render.resolution_y = view_size[1]
    scene.render.resolution_percentage = 100
    scene.camera = camera

    main_quad = projected_quad(scene, camera, main_screen, view_size)
    side_quad = projected_quad(scene, camera, side_screen, view_size)

    print("MAIN_PROJECTED_QUAD=" + np.array2string(main_quad, precision=3), flush=True)
    print("SIDE_PROJECTED_QUAD=" + np.array2string(side_quad, precision=3), flush=True)

    main_prewarped = warp_quad_to_rect(target, main_quad, MAIN_SIZE)
    side_prewarped = warp_quad_to_rect(target, side_quad, SIDE_SIZE)
    main_image = save_array(MAIN_OUT, main_prewarped, "SEABUCKTHORN_MAIN_PREWARP")
    side_image = save_array(SIDE_OUT, side_prewarped, "SEABUCKTHORN_SIDE_PREWARP")
    packed = np.concatenate((main_prewarped, side_prewarped), axis=1)
    save_array(PACKED_OUT, packed, "SEABUCKTHORN_CONTROLLER_PACKED")

    main_mask = inside_convex_quad(view_size[0], view_size[1], main_quad)
    side_mask = inside_convex_quad(view_size[0], view_size[1], side_quad)
    led_mask = main_mask | side_mask
    target_masked = target.copy()
    target_masked[~led_mask, :3] = 0.0
    target_masked[~led_mask, 3] = 1.0
    save_array(TARGET_MASKED_OUT, target_masked, "SEABUCKTHORN_TARGET_MASKED")

    overlay = target.copy()
    for index in range(4):
        draw_line(overlay, main_quad[index], main_quad[(index + 1) % 4], (0.0, 1.0, 1.0, 1.0), 4)
        draw_line(overlay, side_quad[index], side_quad[(index + 1) % 4], (1.0, 0.1, 0.75, 1.0), 4)
    save_array(TARGET_OVERLAY_OUT, overlay, "SEABUCKTHORN_TARGET_OVERLAY")

    main_material = make_emission_material("MAT_SEABUCKTHORN_MAIN_PREWARP", main_image)
    side_material = make_emission_material("MAT_SEABUCKTHORN_SIDE_PREWARP", side_image)
    replace_material(main_screen, main_material)
    replace_material(side_screen, side_material)

    # Show only the two physical LED faces for the round-trip proof.
    for collection in bpy.data.collections:
        collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
    main_screen.hide_render = False
    side_screen.hide_render = False

    configure_clean_render(scene, camera, view_size)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    reproject_image = bpy.data.images.load(str(REPROJECT_OUT), check_existing=False)
    reproject_image.colorspace_settings.name = "sRGB"
    reproject = image_to_array(reproject_image)
    difference = np.abs(reproject[:, :, :3] - target_masked[:, :, :3])
    difference_display = np.clip(difference * 6.0, 0.0, 1.0)
    difference_rgba = np.concatenate(
        (difference_display, np.ones((view_size[1], view_size[0], 1), dtype=np.float32)), axis=2
    )
    save_array(DIFF_OUT, difference_rgba, "SEABUCKTHORN_ROUNDTRIP_DIFFERENCE")

    inside_values = difference[led_mask]
    mae = float(np.mean(inside_values))
    rmse = float(np.sqrt(np.mean(np.square(inside_values))))
    psnr = float("inf") if rmse == 0.0 else 20.0 * math.log10(1.0 / rmse)
    source_luminance = np.max(target[:, :, :3], axis=2)
    outside_nonblack = float(np.mean(source_luminance[~led_mask] > 0.02))
    outside_energy = float(np.mean(source_luminance[~led_mask]))

    report_lines = [
        "SEABUCKTHORN L-SCREEN INVERSE-PROJECTION VALIDATION",
        "===================================================",
        f"Source target: {SOURCE}",
        "Physical LED: 2.5m x 4.5m main + 2.5m x 4.5m side, 90 degrees",
        "Sweet spot: 45-degree bisector, plan radius 6.5m, eye height 1.6m",
        f"Target view: {view_size[0]} x {view_size[1]}",
        f"Main prewarp: {MAIN_SIZE[0]} x {MAIN_SIZE[1]}",
        f"Side prewarp: {SIDE_SIZE[0]} x {SIDE_SIZE[1]}",
        f"Packed controller canvas: {MAIN_SIZE[0] + SIDE_SIZE[0]} x {MAIN_SIZE[1]}",
        "",
        f"Main projected quad px: {main_quad.tolist()}",
        f"Side projected quad px: {side_quad.tolist()}",
        "",
        f"Round-trip RGB MAE inside LED mask: {mae:.8f}",
        f"Round-trip RGB RMSE inside LED mask: {rmse:.8f}",
        f"Round-trip PSNR inside LED mask: {psnr:.3f} dB",
        f"Non-black source pixels outside physical LED silhouette: {outside_nonblack * 100.0:.3f}%",
        f"Mean source brightness outside physical LED silhouette: {outside_energy:.8f}",
        "",
        "PASS_CRITERION: reprojection visually restores the target inside the exact physical LED polygons.",
        "IMPORTANT: source details outside the physical LED silhouette cannot be displayed and are intentionally clipped.",
    ]
    REPORT_OUT.write_text("\n".join(report_lines), encoding="utf-8")
    text_block = bpy.data.texts.get("SEABUCKTHORN_VALIDATION_REPORT.txt") or bpy.data.texts.new(
        "SEABUCKTHORN_VALIDATION_REPORT.txt"
    )
    text_block.clear()
    text_block.write("\n".join(report_lines))
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_OUT))

    print(f"MAIN_PREWARP={MAIN_OUT}", flush=True)
    print(f"SIDE_PREWARP={SIDE_OUT}", flush=True)
    print(f"PACKED={PACKED_OUT}", flush=True)
    print(f"REPROJECT={REPROJECT_OUT}", flush=True)
    print(f"DIFFERENCE={DIFF_OUT}", flush=True)
    print(f"REPORT={REPORT_OUT}", flush=True)
    print(f"BLEND={BLEND_OUT}", flush=True)


if __name__ == "__main__":
    main()
