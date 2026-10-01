"""Render the first corrected bottle-frame maps on the physical Blender L model."""

from pathlib import Path
import sys
import bpy

root = Path(__file__).resolve().parents[1]
straight_box = "--straight-box" in sys.argv
out = root / "renders" / ("02_m4v_straight_box_test" if straight_box else
                          "02_m4v_green_round_bottle_test")

for side, obj_name in (("main", "LED_MAIN_2.5x4.5m"), ("side", "LED_SIDE_2.5x4.5m")):
    path = out / f"{side}_frame_289.png"
    image = bpy.data.images.load(str(path), check_existing=False)
    mat = bpy.data.materials.new(f"MAT_ROUND_BOTTLE_{side.upper()}_STILL")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    emission = nodes.new("ShaderNodeEmission")
    output = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(tex.outputs["Color"], emission.inputs["Color"])
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj = bpy.data.objects[obj_name]
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    obj.hide_render = False

scene = bpy.context.scene
for collection in bpy.data.collections:
    collection.hide_render = collection.name != "03_PHYSICAL_LED_PREVIEW"
for layer in scene.view_layers:
    layer.use = layer.name == "02_检查实体双屏"
scene.use_nodes = False
scene.camera = bpy.data.objects["CAM_SWEET_SPOT_PREVIEW"]
scene.render.resolution_x = 960
scene.render.resolution_y = 960
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(out / ("blender_straight_box_frame_289.png" if straight_box else
                                  "blender_round_bottle_frame_289.png"))
scene.view_settings.view_transform = "Standard"
scene.world.use_nodes = True
background = scene.world.node_tree.nodes.get("Background")
if background:
    background.inputs["Color"].default_value = (0, 0, 0, 1)
    background.inputs["Strength"].default_value = 0
bpy.ops.render.render(write_still=True)
