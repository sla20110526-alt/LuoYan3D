import bpy
import os
import sys


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_l_screen_booth import (
    add_camera,
    add_screen_quad,
    clear_file,
    collection,
    make_material,
)


MAIN_W = 3.0
SIDE_W = 2.0
SCREEN_H = 4.5

BLEND_PATH = os.path.join(SCRIPT_DIR, "L_LED_screen_only_checked_v6.blend")
RENDER_DIR = os.path.join(SCRIPT_DIR, "renders")
RENDER_PATH = os.path.join(RENDER_DIR, "L_LED_screen_only_preview_v6.png")
os.makedirs(RENDER_DIR, exist_ok=True)


def main():
    clear_file()
    scene = bpy.context.scene
    scene.name = "L_LED_SCREEN_ONLY"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    scene["contents"] = "Two LED active surfaces only; no exhibition model, floor, frame, seam, top, or enclosure"
    scene["main_led"] = "3.0m x 4.5m; aspect 2:3"
    scene["side_led"] = "2.0m x 4.5m; aspect 4:9"
    scene["corner"] = "90 degrees; exact shared edge from (0,0,0) to (0,0,4.5)"
    scene["bottom_elevation"] = "Z=0.0m"
    scene["cross_screen_source"] = "1:1 AI master; reproject without stretching"

    led_collection = collection("LED_SCREEN_ONLY")
    utility_collection = collection("CAMERAS_ONLY")

    screen_mat = make_material(
        "MAT_LED_CHECK_BLUE",
        (0.004, 0.035, 0.22),
        roughness=0.82,
        emission=(0.008, 0.10, 0.72),
        strength=0.85,
    )

    main_led = add_screen_quad(
        "LED_MAIN_ACTIVE_3.0x4.5m_RATIO_2x3",
        [
            (-MAIN_W, 0.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, SCREEN_H),
            (-MAIN_W, 0.0, SCREEN_H),
        ],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        screen_mat,
        led_collection,
        MAIN_W,
        SCREEN_H,
        "2:3",
    )
    side_led = add_screen_quad(
        "LED_SIDE_ACTIVE_2.0x4.5m_RATIO_4x9",
        [
            (0.0, 0.0, 0.0),
            (0.0, SIDE_W, 0.0),
            (0.0, SIDE_W, SCREEN_H),
            (0.0, 0.0, SCREEN_H),
        ],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        screen_mat,
        led_collection,
        SIDE_W,
        SCREEN_H,
        "4:9",
    )

    for obj in (main_led, side_led):
        obj["has_border"] = False
        obj["has_frame"] = False
        obj["bottom_z_m"] = 0.0
        obj["top_z_m"] = 4.5
        obj["uv_orientation"] = "U horizontal from corner/outward mapping; V bottom-to-top"

    camera = add_camera(
        "CAM_Check_Perspective",
        (5.25, -8.60, 3.20),
        (-0.85, 0.52, 2.25),
        48.0,
        utility_collection,
    )
    scene.camera = camera

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.009, 0.016, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.16

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = RENDER_PATH
    scene.view_settings.look = "AgX - Medium High Contrast"

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"Saved: {BLEND_PATH}")
    print(f"Rendered: {RENDER_PATH}")


if __name__ == "__main__":
    main()
