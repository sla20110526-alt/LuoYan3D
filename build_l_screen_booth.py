import bpy
import math
import os
from mathutils import Vector


# -----------------------------------------------------------------------------
# Project constants (meters)
# -----------------------------------------------------------------------------
MAIN_W = 3.0
SIDE_W = 2.0
SCREEN_H = 4.5
SCREEN_THICKNESS = 0.12
CORNER_ANGLE = 90.0

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(ROOT_DIR, "L_screen_booth_3m_2m_4p5m.blend")
RENDER_DIR = os.path.join(ROOT_DIR, "renders")
os.makedirs(RENDER_DIR, exist_ok=True)


def clear_file():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def move_to_collection(obj, coll):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)


def make_material(name, base, metallic=0.0, roughness=0.45, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emission_input:
            emission_input.default_value = (*emission, 1.0)
        strength_input = bsdf.inputs.get("Emission Strength")
        if strength_input:
            strength_input.default_value = strength
    return mat


def add_box(name, size, location, material, coll, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new(name="Edge softening", type="BEVEL")
        mod.width = bevel
        mod.segments = 3
    obj.data.materials.append(material)
    move_to_collection(obj, coll)
    return obj


def add_cylinder(name, radius, depth, location, material, coll, vertices=64, bevel=0.02):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if bevel > 0:
        mod = obj.modifiers.new(name="Edge softening", type="BEVEL")
        mod.width = bevel
        mod.segments = 3
    obj.data.materials.append(material)
    move_to_collection(obj, coll)
    return obj


def add_screen_quad(name, vertices, uvs, material, coll, width, height, aspect):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for loop, uv in zip(mesh.polygons[0].loop_indices, uvs):
        uv_layer.data[loop].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(material)
    obj["physical_width_m"] = width
    obj["physical_height_m"] = height
    obj["aspect_ratio"] = aspect
    obj["content_role"] = "LED video surface"
    return obj


def add_curve_line(name, points, material, coll, bevel=0.012, cyclic=False):
    curve = bpy.data.curves.new(name=f"{name}_CURVE", type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for p, co in zip(spline.points, points):
        p.co = (*co, 1.0)
    spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    coll.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def add_text(name, body, location, rotation, size, material, coll, extrude=0.003):
    curve = bpy.data.curves.new(name=f"{name}_CURVE", type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = extrude * 0.25
    obj = bpy.data.objects.new(name, curve)
    coll.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    obj.data.materials.append(material)
    return obj


def add_camera(name, location, target, lens, coll):
    data = bpy.data.cameras.new(name=f"{name}_DATA")
    data.lens = lens
    data.sensor_width = 36.0
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name, location, target, energy, size, color, coll):
    data = bpy.data.lights.new(name=f"{name}_DATA", type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def main():
    clear_file()
    scene = bpy.context.scene
    scene.name = "L_SCREEN_STAGE"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0

    scene["screen_configuration"] = "L-shaped floor-standing LED, two vertical faces only"
    scene["main_screen"] = "3.0m x 4.5m (2:3)"
    scene["side_screen"] = "2.0m x 4.5m (4:9)"
    scene["corner_angle_deg"] = CORNER_ANGLE
    scene["ai_cross_screen_master"] = "1:1 source; crop/reproject into physical 10:9 unfolded LED"
    scene["estimated_sweet_spot"] = "6.5m from corner, eye height 1.6m, 30deg toward side from main normal"

    screens = collection("01_LED_SCREENS")
    booth = collection("02_BOOTH_STRUCTURE")
    props = collection("03_DISPLAY_PROPS")
    guides = collection("04_GUIDES_VIEWPORT_ONLY")
    cameras = collection("05_CAMERAS_LIGHTS")
    guides.hide_render = True

    # Materials: screen color is intentionally different from the green reference booth.
    mat_screen = make_material(
        "MAT_LED_TEST_BLUE",
        (0.018, 0.18, 0.42),
        roughness=0.25,
        emission=(0.02, 0.28, 0.78),
        strength=1.8,
    )
    mat_frame = make_material("MAT_FRAME_DEEP_GREEN", (0.015, 0.13, 0.10), metallic=0.05, roughness=0.32)
    mat_trim = make_material("MAT_TRIM_WARM_GOLD", (0.72, 0.48, 0.18), metallic=0.55, roughness=0.24)
    mat_cream = make_material("MAT_BOOTH_CREAM", (0.78, 0.69, 0.51), roughness=0.52)
    mat_floor = make_material("MAT_FLOOR", (0.10, 0.11, 0.13), metallic=0.05, roughness=0.5)
    mat_white = make_material("MAT_GUIDE_WHITE", (0.92, 0.95, 1.0), roughness=0.3, emission=(0.8, 0.9, 1.0), strength=0.5)
    mat_orange = make_material("MAT_VIEW_GUIDE_ORANGE", (1.0, 0.18, 0.03), roughness=0.3, emission=(1.0, 0.06, 0.01), strength=1.0)
    mat_product = make_material("MAT_PRODUCT_ORANGE", (0.95, 0.24, 0.025), roughness=0.3)
    mat_cap = make_material("MAT_PRODUCT_CAP", (0.08, 0.18, 0.08), metallic=0.1, roughness=0.3)

    # Ground and raised booth floor.
    add_box("Exhibition_Hall_Floor", (18.0, 18.0, 0.10), (0.0, 0.0, -0.06), mat_floor, booth, bevel=0.0)
    add_box("Booth_Raised_Floor", (4.6, 4.1, 0.12), (-0.55, 0.75, 0.06), mat_cream, booth, bevel=0.06)

    # Screen backing is deliberately slightly larger; LED active areas remain exact.
    add_box(
        "MAIN_LED_Back_Frame",
        (MAIN_W + 0.14, SCREEN_THICKNESS, SCREEN_H + 0.14),
        (-MAIN_W / 2, 0.0, SCREEN_H / 2),
        mat_frame,
        screens,
        bevel=0.035,
    )
    add_box(
        "SIDE_LED_Back_Frame",
        (SCREEN_THICKNESS, SIDE_W + 0.14, SCREEN_H + 0.14),
        (0.0, SIDE_W / 2, SCREEN_H / 2),
        mat_frame,
        screens,
        bevel=0.035,
    )

    main_screen = add_screen_quad(
        "LED_MAIN_3.0x4.5m_RATIO_2x3",
        [
            (-MAIN_W, -0.071, 0.0),
            (0.0, -0.071, 0.0),
            (0.0, -0.071, SCREEN_H),
            (-MAIN_W, -0.071, SCREEN_H),
        ],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        mat_screen,
        screens,
        MAIN_W,
        SCREEN_H,
        "2:3",
    )
    side_screen = add_screen_quad(
        "LED_SIDE_2.0x4.5m_RATIO_4x9",
        [
            (0.071, 0.0, 0.0),
            (0.071, SIDE_W, 0.0),
            (0.071, SIDE_W, SCREEN_H),
            (0.071, 0.0, SCREEN_H),
        ],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        mat_screen,
        screens,
        SIDE_W,
        SCREEN_H,
        "4:9",
    )
    main_screen["uv_orientation"] = "U left-to-right, V bottom-to-top"
    side_screen["uv_orientation"] = "U corner-to-side-end, V bottom-to-top"

    # Gold corner strip makes the physical seam obvious without covering active pixels.
    add_box("L_Corner_Trim", (0.035, 0.035, SCREEN_H + 0.12), (0.018, -0.018, SCREEN_H / 2), mat_trim, screens, bevel=0.008)

    # Non-LED booth canopy/frame, echoing the uploaded booth rendering.
    add_box("NON_LED_Main_Top_Beam", (3.35, 0.38, 0.22), (-1.55, 0.14, 4.68), mat_frame, booth, bevel=0.035)
    add_box("NON_LED_Side_Top_Beam", (0.38, 2.35, 0.22), (-0.14, 1.05, 4.68), mat_frame, booth, bevel=0.035)
    add_box("NON_LED_Main_End_Post", (0.22, 0.32, 4.72), (-3.17, 0.11, 2.36), mat_frame, booth, bevel=0.025)
    add_box("NON_LED_Side_End_Post", (0.32, 0.22, 4.72), (-0.11, 2.17, 2.36), mat_frame, booth, bevel=0.025)

    # Tiered product stage, simplified from the red-box portion of the reference image.
    add_box("Product_Stage_Lower", (3.30, 1.42, 0.38), (-1.30, -0.72, 0.19), mat_trim, props, bevel=0.13)
    add_box("Product_Stage_Upper", (2.85, 1.16, 0.36), (-1.22, -0.71, 0.50), mat_cream, props, bevel=0.10)
    add_cylinder("Product_Round_Plinth", 0.62, 0.16, (-0.67, -0.78, 0.78), mat_trim, props, bevel=0.035)

    # Simple pack and bottle establish scale; both are easy to delete later.
    add_box("Placeholder_Product_Pack", (0.82, 0.16, 0.82), (-1.38, -0.94, 1.23), mat_cream, props, bevel=0.035)
    add_cylinder("Placeholder_Bottle_Body", 0.16, 0.72, (-0.48, -0.92, 1.22), mat_product, props, vertices=48, bevel=0.025)
    add_cylinder("Placeholder_Bottle_Shoulder", 0.12, 0.16, (-0.48, -0.92, 1.66), mat_product, props, vertices=48, bevel=0.02)
    add_cylinder("Placeholder_Bottle_Cap", 0.09, 0.12, (-0.48, -0.92, 1.80), mat_cap, props, vertices=48, bevel=0.015)

    # Cabinet grid references at 0.5m intervals (viewport only).
    grid_offset_main = -0.078
    for i in range(1, 6):
        x = -MAIN_W + i * 0.5
        add_curve_line(f"GUIDE_Main_Grid_V_{i}", [(x, grid_offset_main, 0.0), (x, grid_offset_main, SCREEN_H)], mat_white, guides, bevel=0.003)
    for i in range(1, 9):
        z = i * 0.5
        add_curve_line(f"GUIDE_Main_Grid_H_{i}", [(-MAIN_W, grid_offset_main, z), (0.0, grid_offset_main, z)], mat_white, guides, bevel=0.003)
    grid_offset_side = 0.078
    for i in range(1, 4):
        y = i * 0.5
        add_curve_line(f"GUIDE_Side_Grid_V_{i}", [(grid_offset_side, y, 0.0), (grid_offset_side, y, SCREEN_H)], mat_white, guides, bevel=0.003)
    for i in range(1, 9):
        z = i * 0.5
        add_curve_line(f"GUIDE_Side_Grid_H_{i}", [(grid_offset_side, 0.0, z), (grid_offset_side, SIDE_W, z)], mat_white, guides, bevel=0.003)

    # Screen labels and physical-dimension guides (viewport only).
    add_text(
        "GUIDE_Label_Main",
        "MAIN LED  3.0m x 4.5m  |  2:3",
        (-1.50, -0.095, 2.30),
        (math.radians(90), 0.0, 0.0),
        0.24,
        mat_white,
        guides,
    )
    add_text(
        "GUIDE_Label_Side",
        "SIDE LED  2.0m x 4.5m  |  4:9",
        (0.095, 1.00, 2.30),
        (math.radians(90), 0.0, math.radians(90)),
        0.20,
        mat_white,
        guides,
    )

    # Estimated standing-view sweet spot: 6.5m radius, 30 degrees toward the side.
    sweet_radius = 6.5
    sweet_x = sweet_radius * math.sin(math.radians(30.0))
    sweet_y = -sweet_radius * math.cos(math.radians(30.0))
    eye_z = 1.60
    add_cylinder("GUIDE_Sweet_Spot_Floor_Marker", 0.25, 0.025, (sweet_x, sweet_y, 0.025), mat_orange, guides, vertices=48, bevel=0.008)
    add_curve_line(
        "GUIDE_View_Line_To_Corner",
        [(sweet_x, sweet_y, eye_z), (0.0, 0.0, 2.25)],
        mat_orange,
        guides,
        bevel=0.012,
    )
    add_text(
        "GUIDE_Sweet_Spot_Label",
        "SWEET SPOT ~6.5m / EYE 1.6m",
        (sweet_x, sweet_y - 0.35, 0.15),
        (0.0, 0.0, 0.0),
        0.22,
        mat_orange,
        guides,
    )

    # Cameras: physical sweet spot and a slightly raised client-preview camera.
    cam_sweet = add_camera(
        "CAM_SweetSpot_6p5m",
        (sweet_x, sweet_y, eye_z),
        (-0.72, 0.35, 2.25),
        32.0,
        cameras,
    )
    cam_sweet["purpose"] = "Estimated live-view anamorphic reference camera"
    cam_sweet["distance_to_corner_m"] = sweet_radius
    cam_sweet["eye_height_m"] = eye_z

    cam_preview = add_camera(
        "CAM_Client_Preview",
        (5.90, -9.40, 3.00),
        (-0.82, 0.32, 2.15),
        43.0,
        cameras,
    )
    cam_preview["purpose"] = "Presentation preview camera"
    scene.camera = cam_preview

    add_area_light("LIGHT_Key", (3.5, -4.0, 8.0), (-0.8, 0.3, 2.0), 1300.0, 4.0, (1.0, 0.83, 0.70), cameras)
    add_area_light("LIGHT_Fill", (-4.0, -2.0, 5.5), (-1.0, 0.2, 2.0), 900.0, 5.0, (0.60, 0.76, 1.0), cameras)
    add_area_light("LIGHT_Rim", (2.5, 4.0, 6.5), (-0.2, 0.8, 2.3), 1100.0, 3.0, (0.45, 0.65, 1.0), cameras)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.018, 0.025, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.32

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = os.path.join(RENDER_DIR, "L_screen_booth_preview.png")
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "AgX - Medium High Contrast"

    # Color-management-safe compositor vignette is avoided; keep the file editable.
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"Saved: {BLEND_PATH}")
    print(f"Rendered: {scene.render.filepath}")


if __name__ == "__main__":
    main()
