import bpy
import json
import os


def node_summary(material):
    if not material or not material.use_nodes or not material.node_tree:
        return []
    rows = []
    for node in material.node_tree.nodes:
        row = {"name": node.name, "type": node.bl_idname}
        if node.bl_idname == "ShaderNodeTexImage" and node.image:
            row["image"] = node.image.name
            row["source"] = node.image.source
            row["filepath"] = bpy.path.abspath(node.image.filepath)
            row["packed"] = bool(node.image.packed_file)
            row["frame_duration"] = node.image_user.frame_duration
            row["frame_start"] = node.image_user.frame_start
            row["frame_offset"] = node.image_user.frame_offset
            row["use_auto_refresh"] = node.image_user.use_auto_refresh
            row["use_cyclic"] = node.image_user.use_cyclic
        rows.append(row)
    return rows


scene = bpy.context.scene
payload = {
    "blend": bpy.data.filepath,
    "scene": scene.name,
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
    "fps": scene.render.fps,
    "fps_base": scene.render.fps_base,
    "resolution": [scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage],
    "engine": scene.render.engine,
    "filepath": bpy.path.abspath(scene.render.filepath),
    "file_format": scene.render.image_settings.file_format,
    "ffmpeg_format": scene.render.ffmpeg.format,
    "ffmpeg_codec": scene.render.ffmpeg.codec,
    "camera": scene.camera.name if scene.camera else None,
    "view_layers": [layer.name for layer in scene.view_layers],
    "objects": [],
    "materials": [],
    "images": [],
}

for obj in bpy.data.objects:
    item = {
        "name": obj.name,
        "type": obj.type,
        "hide_render": obj.hide_render,
        "hide_viewport": obj.hide_viewport,
        "location": [round(v, 6) for v in obj.location],
        "rotation_euler": [round(v, 6) for v in obj.rotation_euler],
        "dimensions": [round(v, 6) for v in obj.dimensions],
        "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
    }
    if obj.type == "CAMERA":
        item["camera_data"] = {
            "type": obj.data.type,
            "lens": obj.data.lens,
            "shift_x": obj.data.shift_x,
            "shift_y": obj.data.shift_y,
            "clip_start": obj.data.clip_start,
            "clip_end": obj.data.clip_end,
        }
    payload["objects"].append(item)

for mat in bpy.data.materials:
    payload["materials"].append({
        "name": mat.name,
        "use_nodes": mat.use_nodes,
        "nodes": node_summary(mat),
    })

for img in bpy.data.images:
    payload["images"].append({
        "name": img.name,
        "source": img.source,
        "size": list(img.size),
        "filepath": bpy.path.abspath(img.filepath),
        "packed": bool(img.packed_file),
        "colorspace": img.colorspace_settings.name,
    })

print("BLEND_INSPECT_JSON_BEGIN")
print(json.dumps(payload, ensure_ascii=False, indent=2))
print("BLEND_INSPECT_JSON_END")
