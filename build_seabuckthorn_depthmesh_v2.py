"""Build and inspect a 7.5 s 2.5D keyframe on the two physical L LED faces.

The source artwork is mapped to a non-planar image mesh: its branch stays near
the screen while its fruit and juice come toward the nominal sweet spot.
Only the view-dependent render is inverse-projected onto the physical LEDs.
This is a single-view illusion, not stereoscopic or multi-view 3D.
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_correct_virtual_frame_effect as frame
import validate_seabuckthorn_inverse_projection as core


SOURCE = ROOT / "图片" / "沙棘果枝果汁_透明前景_v1.png"
OUT = ROOT / "renders" / "seabuckthorn_depthmesh_v2"
OUT.mkdir(parents=True, exist_ok=True)
BLEND = ROOT / "Lscreen_seabuckthorn_depthmesh_v2.blend"
W = H = 1536
PANEL = (1000, 1800)
ART_X = ART_Y = 390.0
ART_SCALE = 0.62


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def clean_source():
    src = bpy.data.images.load(str(SOURCE), check_existing=False)
    src.colorspace_settings.name = "sRGB"
    rgba = core.image_to_array(src)
    alpha = rgba[:, :, 3]
    # The generated extraction has colored pixels along its cut edge. Pull
    # the alpha inward by two source pixels so the red/yellow fringe is muted.
    for _ in range(2):
        padded = np.pad(alpha, 1, mode="constant")
        alpha = np.minimum.reduce(
            [padded[1:-1, 1:-1], padded[:-2, 1:-1],
             padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]]
        )
    rgba[:, :, 3] = alpha
    path = OUT / "01_foreground_edge_cleaned.png"
    return core.save_array(path, rgba, "SEABUCKTHORN_DEPTHMESH_CLEAN_RGBA")


def camera_ray_point(camera, px, py, distance):
    width = distance * camera.data.sensor_width / camera.data.lens
    height = width * H / W
    local = Vector(((px / W - 0.5) * width,
                    (0.5 - py / H) * height,
                    -distance))
    return camera.matrix_world @ local


def make_depth_mesh(camera, image):
    # Source image UVs remain geometrically connected; each vertex is placed
    # on its camera ray at a semantic depth. From the fixed sweet spot, this
    # does not stretch the source fruit, while the Blender scene has actual
    # front/behind positions for future animation and validation.
    n = 72
    verts = []
    uv_values = []
    depths = []
    for j in range(n + 1):
        top_to_bottom = j / n
        for i in range(n + 1):
            left_to_right = i / n
            px = ART_X + left_to_right * 1254.0 * ART_SCALE
            py = ART_Y + top_to_bottom * 1254.0 * ART_SCALE
            fruit = float(smoothstep(0.38, 0.72, left_to_right) *
                          (1.0 - smoothstep(0.58, 0.82, top_to_bottom)))
            juice = float(smoothstep(0.61, 0.83, top_to_bottom))
            distance = 6.45 - 1.15 * fruit - 1.35 * juice
            verts.append(camera_ray_point(camera, px, py, distance))
            uv_values.append((left_to_right, 1.0 - top_to_bottom))
            depths.append(distance)

    faces = []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + n + 1, a + n + 2, a + 1))

    mesh = bpy.data.meshes.new("SEABUCKTHORN_SEMANTIC_DEPTHMESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("ART_BRANCH_BERRIES_JUICE_2p5D_DEPTHMESH", mesh)
    collection = bpy.data.collections.new("05_SEABUCKTHORN_DEPTH_ASSET")
    bpy.context.scene.collection.children.link(collection)
    collection.objects.link(obj)
    uv_layer = mesh.uv_layers.new(name="ART_UV")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uv_values[vertex_index]

    mat = bpy.data.materials.new("MAT_SEABUCKTHORN_TRANSPARENT_EMISSION")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(tex.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    mat.surface_render_method = "DITHERED"
    mat.use_transparency_overlap = False
    obj.data.materials.append(mat)
    obj["depth_min_m_from_eye"] = min(depths)
    obj["depth_max_m_from_eye"] = max(depths)
    obj["depth_method"] = "Each source pixel follows its sweet-spot camera ray; branch back, fruit forward, juice frontmost."
    return obj, collection


def quiet_room():
    virtual = bpy.data.collections["01_VIRTUAL_CALIBRATION_ROOM"]
    virtual.hide_render = False
    bpy.data.collections["02_CROSS_CORNER_CUBE"].hide_render = True
    bpy.data.collections["03_PHYSICAL_LED_PREVIEW"].hide_render = True
    for obj in virtual.objects:
        name = obj.name
        material_name = obj.data.materials[0].name if getattr(obj.data, "materials", None) and obj.data.materials else ""
        if name == "SWEET_SPOT_TO_CORNER_PLANE_FLOOR_TRACE":
            obj.hide_render = True
        elif material_name == "MAT_GRID_MINOR_CYAN":
            obj.hide_render = True
        elif name.startswith("GRID_CEILING"):
            obj.hide_render = True
        elif name.startswith("GRID_"):
            # Keep only sparse lines. These are background space cues, not an
            # aperture frame or physical LED border.
            tail = name.rsplit("_", 1)[-1]
            try:
                index = int(tail)
            except ValueError:
                index = 0
            obj.hide_render = (index % 5 != 0)
        else:
            obj.hide_render = False

    for name, rgb in (
        ("MAT_REF_FLOOR_GREEN", (0.002, 0.030, 0.020)),
        ("MAT_REF_WALL_GREEN", (0.002, 0.040, 0.029)),
        ("MAT_REF_CEILING_GREEN", (0.001, 0.018, 0.015)),
    ):
        mat = bpy.data.materials.get(name)
        if mat and mat.use_nodes:
            shader = mat.node_tree.nodes.get("Principled BSDF")
            if shader:
                shader.inputs["Base Color"].default_value = (*rgb, 1.0)
                field = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
                if field:
                    field.default_value = (*rgb, 1.0)
                strength = shader.inputs.get("Emission Strength")
                if strength:
                    strength.default_value = 0.35

    gold = bpy.data.materials.get("MAT_GRID_MAJOR_WHITE")
    if gold and gold.use_nodes:
        shader = gold.node_tree.nodes.get("Principled BSDF")
        if shader:
            shader.inputs["Base Color"].default_value = (0.11, 0.062, 0.024, 1.0)
            field = shader.inputs.get("Emission Color") or shader.inputs.get("Emission")
            if field:
                field.default_value = (0.22, 0.105, 0.027, 1.0)
            strength = shader.inputs.get("Emission Strength")
            if strength:
                strength.default_value = 0.35


def read_image(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    return core.image_to_array(image)


def main():
    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    scene.camera = camera
    scene.render.resolution_x = W
    scene.render.resolution_y = H
    image = clean_source()
    asset, collection = make_depth_mesh(camera, image)
    quiet_room()
    frame.configure_scene(scene)
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    virtual_render = OUT / "02_blender_virtual_room_and_depth_asset_1536.png"
    frame.render(scene, camera, (W, H), virtual_render)

    scene.render.resolution_x = W
    scene.render.resolution_y = H
    main_quad = core.projected_quad(scene, camera, main_screen, (W, H))
    side_quad = core.projected_quad(scene, camera, side_screen, (W, H))
    mask = core.inside_convex_quad(W, H, main_quad) | core.inside_convex_quad(W, H, side_quad)
    target = read_image(virtual_render)
    target[~mask, :3] = 0.0
    target[:, :, 3] = 1.0
    core.save_array(OUT / "03_masked_sweetspot_target_1536.png", target, "DEPTHMESH_MASKED_TARGET")

    main_pixels = core.warp_quad_to_rect(target, main_quad, PANEL)
    side_pixels = core.warp_quad_to_rect(target, side_quad, PANEL)
    main_image = core.save_array(OUT / "04_main_prewarped_1000x1800.png", main_pixels, "DEPTHMESH_MAIN")
    side_image = core.save_array(OUT / "05_side_prewarped_1000x1800.png", side_pixels, "DEPTHMESH_SIDE")
    core.save_array(OUT / "06_controller_packed_2000x1800.png",
                    np.concatenate((main_pixels, side_pixels), axis=1), "DEPTHMESH_PACKED")

    core.replace_material(main_screen, core.make_emission_material("MAT_DEPTHMESH_LED_MAIN", main_image))
    core.replace_material(side_screen, core.make_emission_material("MAT_DEPTHMESH_LED_SIDE", side_image))
    bpy.data.collections["01_VIRTUAL_CALIBRATION_ROOM"].hide_render = True
    collection.hide_render = True
    bpy.data.collections["03_PHYSICAL_LED_PREVIEW"].hide_render = False
    main_screen.hide_render = False
    side_screen.hide_render = False
    reprojection = OUT / "07_blender_physical_L_reprojection_1536.png"
    frame.render(scene, camera, (W, H), reprojection)
    landscape_camera = bpy.data.objects.get("CAM_FRAME_EFFECT_LANDSCAPE")
    if landscape_camera:
        frame.render(scene, landscape_camera, (2048, 1156),
                     OUT / "08_landscape_review_2048x1156.png")
    scene.camera = camera
    scene["prototype_status"] = "Work-in-progress keyframe; must pass visual review before client delivery"
    scene["projection"] = "2.5 x 4.5 m + 2.5 x 4.5 m physical 90-degree LED, fixed 45-degree sweet spot"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    reproject = read_image(reprojection)
    mae = float(np.mean(np.abs(reproject[mask, :3] - target[mask, :3])))
    seam = float(np.mean(np.abs(main_pixels[200:1600, -1, :3] - side_pixels[200:1600, 0, :3])))
    report = (
        "SEABUCKTHORN 7.5 S DEPTH-MESH PROTOTYPE\n"
        "======================================\n"
        "Physical LED: 2.5 m x 4.5 m + 2.5 m x 4.5 m, 90 degrees, floor-mounted.\n"
        "Viewpoint: 45-degree bisector, 6.5 m from corner, 1.6 m eye level (provisional).\n"
        "No white frame, physical bezel, floor LED or top LED.\n"
        f"Mesh source: {SOURCE}\n"
        f"Depth from eye: {asset['depth_min_m_from_eye']:.3f} to {asset['depth_max_m_from_eye']:.3f} m.\n"
        f"Physical screen roundtrip RGB MAE: {mae:.6f}.\n"
        f"Panel edge RGB MAE: {seam:.6f}.\n"
        "STATUS: numerical geometry checked; visual acceptance requires inspection of render.\n"
    )
    (OUT / "quality_review.txt").write_text(report, encoding="utf-8")
    print(report, flush=True)
    print(f"REPROJECTION={reprojection}", flush=True)
    print(f"BLEND={BLEND}", flush=True)


if __name__ == "__main__":
    main()
