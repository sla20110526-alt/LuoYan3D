import bpy
import math
import os
import shutil
import subprocess
from mathutils import Vector


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT_DIR, "renders", "gpt_image_reference")
os.makedirs(OUT_DIR, exist_ok=True)

MAIN_PANEL = os.path.join(OUT_DIR, "01_main_panel_virtual_space_1000x1800.png")
SIDE_PANEL = os.path.join(OUT_DIR, "02_side_panel_virtual_space_1000x1800.png")
PACKED_CANVAS = os.path.join(OUT_DIR, "03_unfolded_L_canvas_2000x1800.png")
SWEET_VIEW = os.path.join(OUT_DIR, "04_Lscreen_45deg_virtual_space_base_1536x1536.png")
BLEND_PATH = os.path.join(ROOT_DIR, "Lscreen_45deg_virtual_space_base.blend")

EYE = Vector((6.5 / math.sqrt(2.0), -6.5 / math.sqrt(2.0), 1.60))
TARGET = Vector((-0.625, 0.625, 2.25))


def set_principled(mat, base, emission, strength, roughness=0.8):
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if emission_input:
        emission_input.default_value = (*emission, 1.0)
    strength_input = bsdf.inputs.get("Emission Strength")
    if strength_input:
        strength_input.default_value = strength


def new_principled(name, base, emission, strength, roughness=0.8):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    set_principled(mat, base, emission, strength, roughness)
    return mat


def replace_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def make_image_material(name, image_path):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for node in list(nodes):
        nodes.remove(node)
    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    texture = nodes.new("ShaderNodeTexImage")
    image = bpy.data.images.load(image_path, check_existing=False)
    texture.image = image
    texture.interpolation = "Linear"
    texture.extension = "EXTEND"
    emission.inputs["Strength"].default_value = 1.0
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def set_render(scene, camera, width, height, filepath):
    scene.camera = camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.filepath = filepath
    scene.view_settings.look = "AgX - Medium High Contrast"
    bpy.ops.render.render(write_still=True)


def pack_panels():
    ffmpeg = shutil.which("ffmpeg") or os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft",
        "WinGet",
        "Packages",
        "Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe",
        "ffmpeg-8.1.1-essentials_build",
        "bin",
        "ffmpeg.exe",
    )
    if not os.path.isfile(ffmpeg):
        raise RuntimeError(f"FFmpeg not found: {ffmpeg}")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            MAIN_PANEL,
            "-i",
            SIDE_PANEL,
            "-filter_complex",
            "[0:v][1:v]hstack=inputs=2[v]",
            "-map",
            "[v]",
            "-frames:v",
            "1",
            "-update",
            "1",
            PACKED_CANVAS,
        ],
        check=True,
    )


def main():
    scene = bpy.context.scene
    scene.frame_set(1)

    virtual = bpy.data.collections["01_VIRTUAL_CALIBRATION_ROOM"]
    cube = bpy.data.collections["02_CROSS_CORNER_CUBE"]
    screens = bpy.data.collections["03_PHYSICAL_LED_PREVIEW"]

    # Render a clean brand-colored room. Minor half-meter lines are hidden so
    # the reference gives GPT Image geometry without forcing a dense grid style.
    virtual.hide_render = False
    cube.hide_render = True
    screens.hide_render = True

    floor_mat = new_principled(
        "MAT_REF_FLOOR_GREEN",
        (0.006, 0.050, 0.032),
        (0.008, 0.075, 0.045),
        0.75,
        0.92,
    )
    wall_mat = new_principled(
        "MAT_REF_WALL_GREEN",
        (0.004, 0.075, 0.048),
        (0.006, 0.105, 0.063),
        0.82,
        0.88,
    )
    ceiling_mat = new_principled(
        "MAT_REF_CEILING_GREEN",
        (0.003, 0.038, 0.027),
        (0.004, 0.055, 0.038),
        0.62,
        0.95,
    )
    gold_mat = bpy.data.materials["MAT_GRID_MAJOR_WHITE"]
    set_principled(
        gold_mat,
        (0.48, 0.245, 0.035),
        (1.0, 0.43, 0.055),
        2.4,
        0.30,
    )

    replace_material(bpy.data.objects["ROOM_FLOOR"], floor_mat)
    replace_material(bpy.data.objects["ROOM_CEILING"], ceiling_mat)
    replace_material(bpy.data.objects["ROOM_BACK"], wall_mat)
    replace_material(bpy.data.objects["ROOM_LEFT"], wall_mat)

    for obj in virtual.objects:
        material_name = obj.data.materials[0].name if hasattr(obj.data, "materials") and obj.data.materials else ""
        if material_name == "MAT_GRID_MINOR_CYAN":
            obj.hide_render = True
        elif material_name == "MAT_GRID_MAJOR_WHITE":
            obj.hide_render = False
        if obj.name == "SWEET_SPOT_TO_CORNER_PLANE_FLOOR_TRACE":
            obj.hide_render = True

    world = scene.world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.003, 0.002, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.02

    main_cam = bpy.data.objects["CAM_OFFAXIS_MAIN"]
    side_cam = bpy.data.objects["CAM_OFFAXIS_SIDE"]
    main_screen = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_screen = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    print("REFERENCE_PHASE=MAIN_PANEL", flush=True)
    set_render(scene, main_cam, 1000, 1800, MAIN_PANEL)
    print("REFERENCE_PHASE=SIDE_PANEL", flush=True)
    set_render(scene, side_cam, 1000, 1800, SIDE_PANEL)
    pack_panels()

    main_mat = make_image_material("MAT_REF_MAIN_PANEL", MAIN_PANEL)
    side_mat = make_image_material("MAT_REF_SIDE_PANEL", SIDE_PANEL)
    replace_material(main_screen, main_mat)
    replace_material(side_screen, side_mat)

    virtual.hide_render = True
    cube.hide_render = True
    screens.hide_render = False

    preview_cam = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    preview_cam.location = EYE
    preview_cam.data.lens = 47.0
    preview_cam.data.sensor_width = 36.0
    preview_cam.data.sensor_fit = "HORIZONTAL"
    look_at(preview_cam, TARGET)
    preview_cam["reference_role"] = "45-degree bisector geometry guide for GPT Image"

    print("REFERENCE_PHASE=SWEET_VIEW", flush=True)
    set_render(scene, preview_cam, 1536, 1536, SWEET_VIEW)

    scene["reference_image"] = "Clean 45-degree L-screen virtual room base for GPT Image"
    scene["screen_configuration"] = "2.5m x 4.5m + 2.5m x 4.5m, 90 degrees, frameless"
    scene["sweet_spot"] = "45-degree bisector, plan radius 6.5m, eye height 1.6m"
    scene["reference_excludes"] = "product, branch, fruit, liquid, text, logo, physical border, top LED"
    scene.camera = preview_cam
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    print(f"SAVED_BLEND={BLEND_PATH}", flush=True)
    print(f"SWEET_VIEW={SWEET_VIEW}", flush=True)
    print(f"PACKED_CANVAS={PACKED_CANVAS}", flush=True)


if __name__ == "__main__":
    main()
