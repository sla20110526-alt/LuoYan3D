"""Build an editable, single-view virtual magic box and validate on two real LED faces.

The source concept is camera-projected onto four separate meshes. This is
single-view 2.5D scene geometry, NOT an independently modeled desert or a
multi-view hologram. The gold rails are actual selectable Blender curves.
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


ART = ROOT / "图片" / "沙棘沙地时空盒内框_概念图_v2.png"
FRUIT = ROOT / "图片" / "沙棘果枝果汁_透明前景_v1.png"
OUT = ROOT / "renders" / "magicbox_editable_validation"
OUT.mkdir(parents=True, exist_ok=True)
BLEND = ROOT / "Lscreen_magicbox_editable_3D_validation.blend"
SIZE = (1254, 1254)
PANEL = (1000, 1800)  # Demonstration raster, not the customer's pixel map.


def collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def point_at_distance(camera, px, py, distance):
    width = distance * camera.data.sensor_width / camera.data.lens
    height = width * SIZE[1] / SIZE[0]
    local = Vector(((px / SIZE[0] - .5) * width,
                    (.5 - py / SIZE[1]) * height, -distance))
    return camera.matrix_world @ local


def intersect_plane(camera, px, py, axis, value):
    origin = camera.matrix_world.translation
    through = point_at_distance(camera, px, py, 1.0)
    direction = through - origin
    component = direction[axis]
    if abs(component) < 1e-8:
        raise ValueError(f"Ray is parallel to plane: {px}, {py}, axis={axis}")
    t = (value - origin[axis]) / component
    if t <= 0:
        raise ValueError(f"Plane is behind the eye: {px}, {py}, axis={axis}")
    return origin + t * direction


def image_material(name, image, transparent=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    if transparent:
        transparent_shader = nodes.new("ShaderNodeBsdfTransparent")
        mix = nodes.new("ShaderNodeMixShader")
        links.new(tex.outputs["Alpha"], mix.inputs[0])
        links.new(transparent_shader.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs["Surface"])
        mat.surface_render_method = "DITHERED"
    else:
        links.new(emission.outputs[0], output.inputs["Surface"])
    return mat


def emission_material(name, rgb, strength=1.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    shader = nodes.new("ShaderNodeEmission")
    shader.inputs["Color"].default_value = (*rgb, 1.0)
    shader.inputs["Strength"].default_value = strength
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(shader.outputs[0], output.inputs["Surface"])
    return mat


def mesh_from_projected_quad(name, pixels, world_points, material, coll):
    mesh = bpy.data.meshes.new(name + "_MESH")
    mesh.from_pydata(world_points, [], [(0, 1, 2), (0, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    uv = mesh.uv_layers.new(name="CAMERA_PROJECTED_UV")
    coords = [(px / SIZE[0], 1.0 - py / SIZE[1]) for px, py in pixels]
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv.data[loop_index].uv = coords[vertex_index]
    obj.data.materials.append(material)
    obj["source"] = "Camera-projected concept image; editable 3D face, view-dependent texture"
    obj["sweetspot_only"] = True
    return obj


def line(name, points, material, coll, thickness=.007):
    curve = bpy.data.curves.new(name + "_CURVE", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = thickness
    curve.resolution_u = 2
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for target, xyz in zip(spline.points, points):
        target.co = (*xyz, 1.0)
    obj = bpy.data.objects.new(name, curve)
    coll.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def make_fruit_mesh(camera, image, coll):
    # One baked cut-out is kept as one independent foreground object. Its
    # branch/fruit/juice are NOT falsely represented as separately editable.
    n = 28
    left, top, scale = 301.0, 328.0, .52
    vertices, uvs, faces = [], [], []
    for j in range(n + 1):
        v = j / n
        for i in range(n + 1):
            u = i / n
            px = left + u * SIZE[0] * scale
            py = top + v * SIZE[1] * scale
            fruit_weight = max(0.0, min(1.0, (u - .28) / .55)) * (1.0 - max(0.0, (v - .63) / .30))
            juice_weight = max(0.0, min(1.0, (v - .62) / .28))
            distance = 5.65 - .50 * fruit_weight - .65 * juice_weight
            vertices.append(point_at_distance(camera, px, py, distance))
            uvs.append((u, 1.0 - v))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            faces.append((a, a + n + 1, a + n + 2, a + 1))
    mesh = bpy.data.meshes.new("FRUIT_JUICE_2p5D_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("果枝_果实_果汁_单张素材_2p5D", mesh)
    coll.objects.link(obj)
    uv_layer = mesh.uv_layers.new(name="FOREGROUND_UV")
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            vertex_index = mesh.loops[loop_index].vertex_index
            uv_layer.data[loop_index].uv = uvs[vertex_index]
    obj.data.materials.append(image_material("MAT_FRUIT_CUTOUT_RGBA", image, transparent=True))
    obj["asset_status"] = "Single transparent source; fruit, branches and juice not separately animatable"
    return obj


def set_view_layer_excludes(layer, hidden_collections):
    def walk(node):
        if node.collection.name in hidden_collections:
            node.exclude = True
        for child in node.children:
            walk(child)
    walk(layer.layer_collection)


def render_layer(scene, camera, layer, size, path):
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(path)
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "Medium High Contrast" if False else "Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    for other in scene.view_layers:
        other.use = (other == layer)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED={path}", flush=True)


def main():
    scene = bpy.context.scene
    scene.name = "L屏时空盒_建模与回投"
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    camera.data.lens = 47.0
    camera.data.sensor_width = 36.0
    camera.data.sensor_fit = "HORIZONTAL"
    main_led = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_led = bpy.data.objects["LED_SIDE_2.5x4.5m"]
    led_coll = bpy.data.collections["03_PHYSICAL_LED_PREVIEW"]
    virtual_coll = bpy.data.collections["01_VIRTUAL_CALIBRATION_ROOM"]
    cube_coll = bpy.data.collections["02_CROSS_CORNER_CUBE"]
    led_coll.hide_render = False
    led_coll.hide_viewport = False
    virtual_coll.hide_render = False
    virtual_coll.hide_viewport = False
    cube_coll.hide_render = False
    cube_coll.hide_viewport = False
    for old in bpy.data.collections:
        if old.name.startswith("05_") or old.name.startswith("06_") or old.name.startswith("07_"):
            raise RuntimeError("Please run this builder on the unmodified base scene, not on an existing edit.")

    box = collection("05_可编辑时空盒_四个空间面")
    rails = collection("06_可编辑内框_金属发光线")
    foreground = collection("07_果枝果汁_单层2p5D素材")
    art = bpy.data.images.load(str(ART), check_existing=False)
    art.colorspace_settings.name = "sRGB"
    art.pack()
    fruit = bpy.data.images.load(str(FRUIT), check_existing=False)
    fruit.colorspace_settings.name = "sRGB"
    fruit.pack()

    left_pixels = [(337, 267), (627, 369), (627, 890), (337, 975)]
    right_pixels = [(627, 369), (916, 267), (916, 975), (627, 890)]
    top_pixels = [(337, 267), (627, 171), (916, 267), (627, 369)]
    base_pixels = [(337, 975), (627, 890), (916, 975), (627, 1078)]

    # Two walls meet on an actual 90-degree inside corner at x=-0.9,y=+0.9.
    left_world = [intersect_plane(camera, *p, 1, .90) for p in left_pixels]
    right_world = [intersect_plane(camera, *p, 0, -.90) for p in right_pixels]
    # Independent roof and base surfaces join the walls at their visible edges.
    top_world = [left_world[0], intersect_plane(camera, 627, 171, 2, 4.12),
                 right_world[1], left_world[1]]
    base_world = [left_world[3], left_world[2], right_world[2],
                  intersect_plane(camera, 627, 1078, 2, .36)]

    wall_mat = image_material("MAT_沙地与天空_相机投影参考", art)
    lid_mat = image_material("MAT_金属顶盖_相机投影参考", art)
    plinth_mat = image_material("MAT_金属底座_相机投影参考", art)
    mesh_from_projected_quad("沙地背景_左墙_独立对象", left_pixels, left_world, wall_mat, box)
    mesh_from_projected_quad("沙地背景_右墙_独立对象", right_pixels, right_world, wall_mat, box)
    mesh_from_projected_quad("时空盒_顶部金属盖_独立对象", top_pixels, top_world, lid_mat, box)
    mesh_from_projected_quad("时空盒_底部金属座_独立对象", base_pixels, base_world, plinth_mat, box)

    gold = emission_material("MAT_金边_暖金发光", (1.0, .48, .105), 1.4)
    line("内框_左竖边", [left_world[0], left_world[3]], gold, rails)
    line("内框_右竖边", [right_world[1], right_world[2]], gold, rails)
    line("内框_上沿_左", [left_world[0], left_world[1]], gold, rails)
    line("内框_上沿_右", [right_world[0], right_world[1]], gold, rails)
    line("内框_下沿_左", [left_world[3], left_world[2]], gold, rails)
    line("内框_下沿_右", [right_world[3], right_world[2]], gold, rails)
    # The inner fold stays low contrast: it is a virtual-room depth cue, not
    # a visible seam between the real LED cabinets.
    faint = emission_material("MAT_虚拟内角_暗金", (.15, .083, .027), .45)
    line("虚拟空间内角_非实体屏接缝", [left_world[1], left_world[2]], faint, rails, .003)
    make_fruit_mesh(camera, fruit, foreground)

    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bg.inputs["Strength"].default_value = 0.0

    model_layer = scene.view_layers[0]
    model_layer.name = "01_编辑虚拟盒子"
    playback_layer = scene.view_layers.new("02_检查实体双屏")
    set_view_layer_excludes(model_layer, {virtual_coll.name, cube_coll.name, led_coll.name})
    set_view_layer_excludes(playback_layer,
                            {virtual_coll.name, cube_coll.name,
                             box.name, rails.name, foreground.name})

    target_path = OUT / "01_虚拟空间可编辑模型_甜蜜点.png"
    render_layer(scene, camera, model_layer, SIZE, target_path)
    target = core.image_to_array(bpy.data.images.load(str(target_path), check_existing=False))
    main_quad = core.projected_quad(scene, camera, main_led, SIZE)
    side_quad = core.projected_quad(scene, camera, side_led, SIZE)
    mask = core.inside_convex_quad(*SIZE, main_quad) | core.inside_convex_quad(*SIZE, side_quad)
    outside_lit = int(np.count_nonzero((np.max(target[:, :, :3], axis=2) > .02) & ~mask))
    target[~mask, :3] = 0.0
    target[:, :, 3] = 1.0
    core.save_array(OUT / "02_仅实体LED范围_目标图.png", target, "MAGICBOX_EDITABLE_MASKED")
    main_pixels = core.warp_quad_to_rect(target, main_quad, PANEL)
    side_pixels = core.warp_quad_to_rect(target, side_quad, PANEL)
    main_image = core.save_array(OUT / "03_主屏预畸变_1000x1800.png", main_pixels, "EDITABLE_BOX_MAIN")
    side_image = core.save_array(OUT / "04_侧屏预畸变_1000x1800.png", side_pixels, "EDITABLE_BOX_SIDE")
    core.save_array(OUT / "05_控制器拼屏_2000x1800.png",
                    np.concatenate((main_pixels, side_pixels), axis=1), "EDITABLE_BOX_PACKED")
    main_image.pack()
    side_image.pack()
    core.replace_material(main_led, core.make_emission_material("MAT_双屏回投_MAIN", main_image))
    core.replace_material(side_led, core.make_emission_material("MAT_双屏回投_SIDE", side_image))
    # Sampling the exact shared edge with CLIP can interpolate against black,
    # creating a fake physical seam. Extend the terminal LED texels instead.
    for led in (main_led, side_led):
        for node in led.data.materials[0].node_tree.nodes:
            if node.type == "TEX_IMAGE":
                node.extension = "EXTEND"
    render_layer(scene, camera, playback_layer, SIZE,
                 OUT / "06_Blender实体双屏_回投检查.png")

    # The project opens in the modeling layer, so the selectable geometry is
    # visible first; switching the view-layer dropdown shows the LED playback.
    model_layer.use = True
    playback_layer.use = True
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene["打开后先看"] = "右上角视图层选择 01_编辑虚拟盒子；点击对象可单独选中左右沙地墙、顶盖、底座、金边及前景"
    scene["切换回投"] = "切换视图层到 02_检查实体双屏，即可看到两块真实LED面上的预畸变贴图"
    scene["真实屏幕"] = "2.5m×4.5m + 2.5m×4.5m, 90°, only two vertical LED faces, no top/floor LED"
    scene["制作性质"] = "单视点2.5D/相机投影建模；沙漠细节仍来自概念图纹理，非独立三维地貌"
    scene["待办限制"] = "果枝/果实/果汁仍在一张透明素材中，真正独立动画须分层或重建"
    scene["控制器像素"] = "1000×1800+1000×1800仅为模拟，最终需现场像素图与播放映射"

    readme = bpy.data.texts.new("工程说明_先看这里")
    readme.write("本工程含两个视图层：\n")
    readme.write("01_编辑虚拟盒子：四个空间面、金边和一个果枝果汁前景层可分别选中。\n")
    readme.write("02_检查实体双屏：真实两块竖屏贴有从固定观看点算出的预畸变画面。\n")
    readme.write("顶部、底部和沙地是虚拟空间，并非新增实体LED。\n")
    readme.write("概念图被相机投影到独立几何体；这不是完整可任意换机位的三维沙漠。\n")
    readme.write("果枝、果实、果汁源图仍是一张透明PNG，后续运动制作需要分层。\n")
    readme.write("物理尺寸为两块2.5m×4.5m；像素尺寸暂为模拟。\n")

    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                space = area.spaces.active
                space.shading.type = "MATERIAL"
                space.region_3d.view_perspective = "CAMERA"
                space.region_3d.view_camera_zoom = 0.0
                space.overlay.show_overlays = False

    try:
        if bpy.context.window:
            bpy.context.window.view_layer = model_layer
    except Exception as exc:
        print(f"VIEW_LAYER_SELECT_WARNING={exc}", flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND), compress=False)
    print(f"SAVED_BLEND={BLEND}", flush=True)
    print(f"SWEETSPOT_LIT_OUTSIDE_PHYSICAL_LED={outside_lit}", flush=True)
    print(f"BOX_OBJECTS={[obj.name for obj in box.objects]}", flush=True)


if __name__ == "__main__":
    main()
