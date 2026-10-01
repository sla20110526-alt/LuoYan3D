"""Make the tested LED composite immediately visible on opening in Blender."""

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Lscreen_magicbox_fruit_inverse_projection_VIEW_READY.blend"


def main():
    scene = bpy.context.scene
    camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
    main_led = bpy.data.objects["LED_MAIN_2.5x4.5m"]
    side_led = bpy.data.objects["LED_SIDE_2.5x4.5m"]

    scene.camera = camera
    scene.render.resolution_x = 1254
    scene.render.resolution_y = 1254
    scene.render.resolution_percentage = 100

    # The calibration room and cube are useful construction aids but must not
    # cover the textured LED surfaces when this file is opened for review.
    for collection in bpy.data.collections:
        visible = collection.name in {"03_PHYSICAL_LED_PREVIEW", "04_PROJECTION_CAMERAS"}
        collection.hide_viewport = not visible
        collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
    for obj in (main_led, side_led):
        obj.hide_viewport = False
        obj.hide_render = False
        obj.hide_set(False)

    packed = []
    for obj in (main_led, side_led):
        for material in obj.data.materials:
            if material is None or not material.use_nodes:
                continue
            for node in material.node_tree.nodes:
                if node.type != "TEX_IMAGE" or node.image is None:
                    continue
                image = node.image
                if image.packed_file is None:
                    image.pack()
                packed.append((obj.name, image.name, image.packed_file is not None))

    # Every saved 3D View area opens in camera view with textures visible.
    # MATERIAL preview avoids the blank gray SOLID viewport that confused the
    # previous handoff, while the F12 render remains the definitive validation.
    view_count = 0
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.shading.type = "MATERIAL"
            space.region_3d.view_perspective = "CAMERA"
            space.region_3d.view_camera_zoom = 0.0
            space.overlay.show_overlays = False
            view_count += 1

    layout = bpy.data.workspaces.get("Layout")
    if layout is not None and bpy.context.window is not None:
        bpy.context.window.workspace = layout

    scene["OPEN_THIS_FILE"] = "Two LED panels are textured. Layout viewport is Material Preview in the 45-degree sweet-spot camera."
    scene["PACKED_TEXTURES"] = "Both prewarped LED panel PNGs are embedded in this .blend file."
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT), compress=False)
    print(f"VIEW_READY_BLEND={OUTPUT}")
    print(f"VIEW_3D_AREAS_UPDATED={view_count}")
    print(f"PACKED_PANEL_IMAGES={packed}")


if __name__ == "__main__":
    main()
