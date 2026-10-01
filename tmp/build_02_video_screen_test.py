"""Attach the prewarped 02.m4v panel movies to the existing L LED model."""

from pathlib import Path
import sys

import bpy


root = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
full_frame = "--full-frame-green" in args
round_bottle = "--round-bottle-green" in args
straight_box = "--straight-box" in args
diamond_box = "--diamond-box" in args
if diamond_box:
    out = root / "renders" / "02_m4v_diamond_box_test"
    main_path = out / "01_main_1000x1800.mp4"
    side_path = out / "02_side_1000x1800.mp4"
    blend_out = root / "Lscreen_magicbox_02m4v_DIAMOND_CUBOID_TEST.blend"
elif straight_box:
    out = root / "renders" / "02_m4v_straight_box_test"
    main_path = out / "01_main_1000x1800.mp4"
    side_path = out / "02_side_1000x1800.mp4"
    blend_out = root / "Lscreen_magicbox_02m4v_STRAIGHT_BOX_TEST.blend"
elif round_bottle:
    out = root / "renders" / "02_m4v_green_round_bottle_test"
    main_path = out / "01_main_1000x1800.mp4"
    side_path = out / "02_side_1000x1800.mp4"
    blend_out = root / "Lscreen_magicbox_02m4v_GREEN_ROUND_BOTTLE_TEST.blend"
elif full_frame:
    out = root / "renders" / "02_m4v_full_frame_fill_test"
    main_path = out / "01_main_1000x1800.mp4"
    side_path = out / "02_side_1000x1800.mp4"
    blend_out = root / "Lscreen_magicbox_02m4v_FULL_GREEN_TEST.blend"
else:
    out = root / "renders" / "02_m4v_inverse_projection_test"
    main_path = out / "01_main_prewarped_1000x1800.mp4"
    side_path = out / "02_side_prewarped_1000x1800.mp4"
    blend_out = root / "Lscreen_magicbox_02m4v_INVERSE_PROJECTION_TEST.blend"
for path in (main_path, side_path):
    if not path.is_file():
        raise FileNotFoundError(path)


def assign_movie(obj_name, material_name, movie_path):
    obj = bpy.data.objects[obj_name]
    image = bpy.data.images.load(str(movie_path), check_existing=False)
    image.source = "MOVIE"
    image.filepath = bpy.path.relpath(str(movie_path))
    material = bpy.data.materials.new(material_name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "CLIP"
    tex.image_user.frame_start = 1
    tex.image_user.frame_duration = 360
    tex.image_user.frame_offset = 0
    tex.image_user.use_auto_refresh = True
    tex.image_user.use_cyclic = False
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = 1.0
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(material)
    obj.hide_render = False
    return image


scene = bpy.context.scene
main_image = assign_movie("LED_MAIN_2.5x4.5m", "MAT_02m4v_MAIN_MOVIE", main_path)
side_image = assign_movie("LED_SIDE_2.5x4.5m", "MAT_02m4v_SIDE_MOVIE", side_path)
for collection in bpy.data.collections:
    collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
for layer in scene.view_layers:
    layer.use = layer.name == "02_检查实体双屏"
scene.use_nodes = False
scene.frame_start = 1
scene.frame_end = 360
scene.render.fps = 24
scene.render.fps_base = 1.0
scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 960
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.world.use_nodes = True
background = scene.world.node_tree.nodes.get("Background")
if background:
    background.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    background.inputs["Strength"].default_value = 0.0
scene["视频源"] = str(root / "视频" / "02.m4v")
scene["测试说明"] = "15秒/24fps/360帧；两面1000x1800测试贴图；甜点位6.5米、眼高1.6米；非现场交付规格。"
scene["映射方式"] = (
    "02.m4v绿色保留；金色箱体在甜点位呈菱形透视的长方体，瓶体局部校正圆润；两面贴图按实体屏逆投影。"
    if diamond_box else
    "02.m4v绿色完整留在实体L屏可视区域；金框四边按甜点位保持直线，中央瓶体保持圆润；背景两侧非均匀压缩。"
    if straight_box else
    "02.m4v完整绿色边框保留；背景平滑压缩，中央瓶体按甜点位逆投影校正，保持圆润轮廓。"
    if round_bottle else
    "02.m4v完整帧左右等分映射到L屏；保留全部绿色区域，但观看点画面纵向拉伸。"
    if full_frame else
    "02.m4v作为960x960观看点目标图逆投影；实体屏轮廓外原图内容裁切。"
)
scene["主屏视频"] = str(main_path)
scene["侧屏视频"] = str(side_path)

samples = ((1, 145, 220, 289, 360) if diamond_box else
           (1, 73, 289) if (full_frame or round_bottle or straight_box) else
           (1, 145, 289))
for frame in samples:
    scene.frame_set(frame)
    scene.render.filepath = str(out / f"blender_sweetspot_frame_{frame:03d}.png")
    bpy.ops.render.render(write_still=True)

scene.frame_set(289)
scene.camera = bpy.data.objects["CAM_SCREEN_MODEL_OBLIQUE"]
scene.render.resolution_x = 1200
scene.render.resolution_y = 750
scene.render.filepath = str(out / "blender_oblique_frame_289.png")
bpy.ops.render.render(write_still=True)

scene.frame_set(1)
scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
scene.render.resolution_x = 960
scene.render.resolution_y = 960
scene.render.filepath = str(out / "blender_sweetspot_")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_out), compress=False)
print("VIDEO_BLEND=" + str(blend_out), flush=True)
print("MAIN_MOVIE_SOURCE=" + main_image.filepath, flush=True)
print("SIDE_MOVIE_SOURCE=" + side_image.filepath, flush=True)
