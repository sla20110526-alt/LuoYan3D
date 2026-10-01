import bpy
import math
import os
import sys
from mathutils import Vector

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_l_screen_booth import (
    add_area_light,
    add_box,
    add_camera,
    add_curve_line,
    add_cylinder,
    add_screen_quad,
    add_text,
    clear_file,
    collection,
    make_material,
)


# Exact user-confirmed LED dimensions (meters)
MAIN_W = 3.0
SIDE_W = 2.0
SCREEN_H = 4.5

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BLEND_PATH = os.path.join(ROOT_DIR, "full_exhibition_booth_direct_floor_v5.blend")
RENDER_DIR = os.path.join(ROOT_DIR, "renders")
RENDER_PATH = os.path.join(RENDER_DIR, "full_exhibition_booth_direct_floor_preview_v5.png")
os.makedirs(RENDER_DIR, exist_ok=True)


def make_wood_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.42

    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = 7.0
    tex.inputs["Detail"].default_value = 2.5
    tex.inputs["Roughness"].default_value = 0.62
    tex.inputs["Distortion"].default_value = 0.08

    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.35, 7.5, 1.0)
    coord = nodes.new("ShaderNodeTexCoord")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.13, 0.055, 0.018, 1.0)
    ramp.color_ramp.elements[1].color = (0.62, 0.29, 0.07, 1.0)
    ramp.color_ramp.elements.new(0.58).color = (0.31, 0.12, 0.028, 1.0)

    links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def add_open_screen_body(name, bounds, omitted_face, material, coll):
    """Thin screen shell without a polygon on the active display side."""
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    verts = [
        (min_x, min_y, min_z), (max_x, min_y, min_z),
        (max_x, max_y, min_z), (min_x, max_y, min_z),
        (min_x, min_y, max_z), (max_x, min_y, max_z),
        (max_x, max_y, max_z), (min_x, max_y, max_z),
    ]
    face_map = {
        "bottom": (0, 3, 2, 1),
        "top": (4, 5, 6, 7),
        "min_y": (0, 1, 5, 4),
        "max_y": (3, 7, 6, 2),
        "min_x": (0, 4, 7, 3),
        "max_x": (1, 2, 6, 5),
    }
    faces = [face for key, face in face_map.items() if key != omitted_face]
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def add_branded_text(name, body, location, rotation, size, material, coll, font):
    obj = add_text(name, body, location, rotation, size, material, coll, extrude=0.004)
    if font is not None:
        obj.data.font = font
    return obj


def add_column(name, x, y, height, green, cream, coll):
    add_box(f"{name}_Core", (0.34, 0.34, height), (x, y, height / 2), green, coll, bevel=0.025)
    add_box(f"{name}_Front_Inlay", (0.17, 0.025, height - 0.34), (x, y - 0.183, height / 2), cream, coll, bevel=0.01)
    add_box(f"{name}_Side_Inlay", (0.025, 0.17, height - 0.34), (x + 0.183, y, height / 2), cream, coll, bevel=0.01)
    add_box(f"{name}_Base", (0.48, 0.48, 0.16), (x, y, 0.08), green, coll, bevel=0.025)
    add_box(f"{name}_Capital", (0.48, 0.48, 0.16), (x, y, height - 0.08), green, coll, bevel=0.025)


def add_counter(name, location, size, cream, green, gold, coll, sign_side="front"):
    x, y, z = location
    sx, sy, sz = size
    add_box(f"{name}_Body", size, location, cream, coll, bevel=0.065)
    add_box(f"{name}_Top", (sx + 0.08, sy + 0.08, 0.08), (x, y, z + sz / 2 + 0.04), gold, coll, bevel=0.035)
    if sign_side == "front":
        add_box(f"{name}_LogoPanel", (sx * 0.66, 0.025, sz * 0.50), (x, y - sy / 2 - 0.014, z), green, coll, bevel=0.025)
    else:
        add_box(f"{name}_LogoPanel", (0.025, sy * 0.66, sz * 0.50), (x + sx / 2 + 0.014, y, z), green, coll, bevel=0.025)


def add_chair(name, location, rotation_z, green, cream, coll):
    x, y, z = location
    angle = math.radians(rotation_z)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(x, y, z))
    root = bpy.context.object
    root.name = name
    root.rotation_euler.z = angle
    for old in list(root.users_collection):
        old.objects.unlink(root)
    coll.objects.link(root)

    parts = []
    parts.append(add_box(f"{name}_Seat", (0.55, 0.55, 0.12), (x, y, z + 0.47), green, coll, bevel=0.08))
    parts.append(add_box(f"{name}_Back", (0.55, 0.12, 0.62), (x, y + 0.22, z + 0.82), green, coll, bevel=0.10))
    parts.append(add_box(f"{name}_Cushion", (0.45, 0.45, 0.08), (x, y - 0.01, z + 0.56), cream, coll, bevel=0.06))
    for lx in (-0.20, 0.20):
        for ly in (-0.20, 0.20):
            parts.append(add_cylinder(f"{name}_Leg_{lx}_{ly}", 0.025, 0.45, (x + lx, y + ly, z + 0.225), green, coll, vertices=16, bevel=0.006))
    for part in parts:
        part.parent = root
        # Convert existing world transform to parent-local before rotating as a group.
        part.matrix_parent_inverse = root.matrix_world.inverted()
    return root


def add_bottle(name, location, orange, cap, coll, scale=1.0):
    x, y, z = location
    body = add_cylinder(f"{name}_Body", 0.055 * scale, 0.22 * scale, (x, y, z + 0.11 * scale), orange, coll, vertices=20, bevel=0.008)
    shoulder = add_cylinder(f"{name}_Shoulder", 0.043 * scale, 0.045 * scale, (x, y, z + 0.2425 * scale), orange, coll, vertices=20, bevel=0.006)
    lid = add_cylinder(f"{name}_Cap", 0.038 * scale, 0.045 * scale, (x, y, z + 0.2875 * scale), cap, coll, vertices=20, bevel=0.005)
    return (body, shoulder, lid)


def add_right_shelf_wall(green, cream, gold, orange, cap, structure, products):
    # Continuation of the right-side booth wall behind the 2 m LED face.
    add_box("Right_Retail_Backwall", (0.14, 3.05, 3.62), (-0.13, 3.72, 1.81), green, structure, bevel=0.025)
    add_box("Right_Retail_Cream_Inset", (0.035, 2.78, 2.66), (-0.215, 3.72, 2.01), cream, structure, bevel=0.015)
    add_box("Right_Retail_Base_Cabinet", (0.62, 3.02, 0.68), (0.08, 3.72, 0.34), cream, structure, bevel=0.035)

    for idx, z in enumerate((0.80, 1.30, 1.80, 2.30, 2.80)):
        add_box(f"Right_Shelf_{idx+1}", (0.62, 2.82, 0.07), (0.08, 3.72, z), gold, structure, bevel=0.012)
    for idx, y in enumerate((2.30, 3.01, 3.72, 4.43, 5.14)):
        add_box(f"Right_Shelf_Divider_{idx+1}", (0.60, 0.055, 2.05), (0.08, y, 1.78), green, structure, bevel=0.008)

    # Products belong on the retail shelving only; no arbitrary props are placed in front of the LED.
    count = 0
    for row_z in (0.84, 1.34, 1.84, 2.34):
        for y in (2.48, 2.82, 3.16, 3.50, 3.84, 4.18, 4.52, 4.86):
            count += 1
            add_bottle(f"RightShelf_Product_{count:02d}", (0.42, y, row_z), orange, cap, products, scale=0.82)


def add_back_retail_wall(green, cream, gold, orange, cap, structure, products):
    # PDF pages 2/8 show two product walls separated by a cream art wall.
    add_box("Back_Retail_Header", (8.20, 0.16, 0.70), (-4.30, 5.58, 3.72), green, structure, bevel=0.025)
    add_box("Back_Central_ArtWall", (1.90, 0.15, 3.10), (-4.25, 5.56, 1.55), cream, structure, bevel=0.025)

    shelf_specs = (
        ("Back_Left", -6.82, 3.05),
        ("Back_Right", -1.62, 3.15),
    )
    count = 0
    for shelf_name, cx, width in shelf_specs:
        add_box(f"{shelf_name}_Backwall", (width, 0.14, 3.30), (cx, 5.55, 1.65), green, structure, bevel=0.025)
        add_box(f"{shelf_name}_GraphicPanel", (width - 0.16, 0.035, 0.74), (cx, 5.455, 2.93), cream, structure, bevel=0.015)
        add_box(f"{shelf_name}_BaseCabinet", (width - 0.12, 0.58, 0.66), (cx, 5.28, 0.33), cream, structure, bevel=0.025)
        for idx, z in enumerate((0.80, 1.28, 1.76, 2.24)):
            add_box(f"{shelf_name}_Shelf_{idx+1}", (width - 0.18, 0.58, 0.065), (cx, 5.28, z), gold, structure, bevel=0.010)
        for x in (cx - width * 0.33, cx, cx + width * 0.33):
            add_box(f"{shelf_name}_Divider_{x:.2f}", (0.045, 0.56, 1.88), (x, 5.28, 1.63), green, structure, bevel=0.006)
        start_x = cx - width / 2 + 0.22
        end_x = cx + width / 2 - 0.22
        positions = 7
        for row_z in (0.84, 1.32, 1.80, 2.28):
            for j in range(positions):
                x = start_x + (end_x - start_x) * j / (positions - 1)
                count += 1
                add_bottle(f"BackShelf_Product_{count:02d}", (x, 4.98, row_z), orange, cap, products, scale=0.76)

    # Three abstract art panels visible on the central cream wall.
    art_colors = (
        make_material("MAT_Art_BlackGold", (0.12, 0.075, 0.028), metallic=0.32, roughness=0.36),
        make_material("MAT_Art_PaleGold", (0.70, 0.55, 0.24), metallic=0.12, roughness=0.48),
        make_material("MAT_Art_Cream", (0.68, 0.64, 0.52), metallic=0.05, roughness=0.52),
    )
    for i, (x, mat) in enumerate(zip((-4.82, -4.25, -3.68), art_colors), start=1):
        add_box(f"Back_Art_Panel_{i}", (0.46, 0.045, 0.92), (x, 5.455, 1.98), mat, structure, bevel=0.018)


def add_hall(hall, lights, dark, charcoal, floor_mat, white_emit):
    # Top surface is exactly Z=0, matching the LED bottom edge.
    add_box("Hall_Floor", (24.0, 18.0, 0.12), (-2.0, 2.0, -0.06), floor_mat, hall, bevel=0.0)
    add_box("Hall_Back_Wall", (24.0, 0.20, 8.0), (-2.0, 8.5, 4.0), dark, hall, bevel=0.0)
    add_box("Hall_Left_Wall", (0.20, 18.0, 8.0), (-14.0, 2.0, 4.0), dark, hall, bevel=0.0)
    add_box("Hall_Ceiling", (24.0, 18.0, 0.18), (-2.0, 2.0, 8.0), charcoal, hall, bevel=0.0)

    # Exhibition-hall beam grid and luminous strips visible in the supplied rendering.
    for i, y in enumerate((-4.0, -1.5, 1.0, 3.5, 6.0)):
        add_box(f"Hall_Truss_X_{i+1}", (23.0, 0.16, 0.20), (-2.0, y, 7.55), dark, hall, bevel=0.015)
    for i, x in enumerate((-11.0, -7.5, -4.0, -0.5, 3.0, 6.5)):
        add_box(f"Hall_Truss_Y_{i+1}", (0.16, 17.0, 0.20), (x, 2.0, 7.54), dark, hall, bevel=0.015)
    for i, x in enumerate((-10.0, -6.5, -3.0, 0.5, 4.0, 7.0)):
        for j, y in enumerate((-2.7, 0.0, 2.7, 5.4)):
            add_box(f"Hall_LightStrip_{i+1}_{j+1}", (2.05, 0.045, 0.035), (x, y, 7.40), white_emit, lights, bevel=0.012)


def main():
    clear_file()
    scene = bpy.context.scene
    scene.name = "FULL_EXHIBITION_BOOTH"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    scene["reconstruction_basis"] = "Single supplied perspective image; visible structure reconstructed, occluded rear structure inferred"
    scene["exact_led_dimensions"] = "Main 3.0x4.5m; Side 2.0x4.5m; 90-degree corner"
    scene["led_border"] = "None - two flush active faces meet directly at the corner"
    scene["top_led"] = "No top LED"
    scene["screen_top_alignment"] = "LED top edge and booth upper edge are both Z=4.5m"
    scene["screen_enclosure"] = "Right-front closed 3.0m x 2.0m block; two exterior faces are LED; top/rear/interior faces are non-LED"
    scene["screen_floor_contact"] = "Both LED faces extend directly to hall floor Z=0; no plinth, apron, or perimeter trim outside them"
    scene["future_ai_master"] = "1:1"

    led = collection("01_LED_EXACT_NO_BORDER")
    booth = collection("02_BOOTH_ARCHITECTURE")
    furniture = collection("03_COUNTERS_AND_FURNITURE")
    products = collection("04_RETAIL_SHELF_PRODUCTS")
    signage = collection("05_SIGNAGE")
    guides = collection("06_DIMENSION_GUIDES")
    hall = collection("07_EXHIBITION_HALL")
    lights = collection("08_CAMERAS_AND_LIGHTS")
    guides.hide_render = True

    # Core palette sampled conceptually from the supplied booth rendering.
    mat_green = make_material("MAT_Brand_Deep_Green", (0.004, 0.070, 0.038), metallic=0.02, roughness=0.40)
    mat_green_2 = make_material("MAT_Brand_Green_Accent", (0.010, 0.17, 0.080), metallic=0.02, roughness=0.36)
    mat_cream = make_material("MAT_Warm_Cream", (0.78, 0.69, 0.51), roughness=0.48)
    mat_gold = make_material("MAT_Sand_Gold", (0.58, 0.37, 0.12), metallic=0.22, roughness=0.34)
    mat_white = make_material("MAT_Display_White", (0.94, 0.91, 0.84), roughness=0.32)
    mat_mirror = make_material("MAT_Display_Mirror", (0.30, 0.36, 0.34), metallic=0.86, roughness=0.12)
    mat_screen = make_material(
        "MAT_LED_Solid_Blue",
        (0.006, 0.045, 0.24),
        roughness=0.80,
        emission=(0.008, 0.10, 0.72),
        strength=0.72,
    )
    mat_orange = make_material("MAT_Product_Orange", (0.92, 0.20, 0.018), roughness=0.32)
    mat_cap = make_material("MAT_Product_Cap", (0.025, 0.18, 0.09), metallic=0.05, roughness=0.30)
    mat_text = make_material("MAT_Signage_Light", (0.96, 0.86, 0.63), roughness=0.30, emission=(0.85, 0.70, 0.40), strength=0.35)
    mat_white_emit = make_material("MAT_Hall_Light", (0.92, 0.95, 1.0), roughness=0.20, emission=(1.0, 1.0, 1.0), strength=8.0)
    mat_hall_dark = make_material("MAT_Hall_Dark", (0.018, 0.022, 0.028), metallic=0.08, roughness=0.54)
    mat_hall_charcoal = make_material("MAT_Hall_Charcoal", (0.035, 0.040, 0.048), metallic=0.10, roughness=0.56)
    mat_hall_floor = make_material("MAT_Hall_Floor", (0.19, 0.20, 0.21), metallic=0.0, roughness=0.44)
    mat_wood = make_wood_material("MAT_Booth_Wood_Floor")
    mat_guide = make_material("MAT_Guide_Orange", (1.0, 0.12, 0.015), roughness=0.25, emission=(1.0, 0.06, 0.01), strength=1.0)

    # Whole hall first, then the booth footprint.
    add_hall(hall, lights, mat_hall_dark, mat_hall_charcoal, mat_hall_floor, mat_white_emit)
    # Irregular booth floor: it stops at the two exterior LED planes.
    # There is no wood/white apron in front of the main LED or outside the side LED.
    add_box("Booth_Wood_Platform_Left", (5.925, 5.755, 0.14), (-5.9625, 2.8775, 0.07), mat_wood, booth, bevel=0.035)
    add_box("Booth_Wood_Platform_Rear", (3.00, 3.755, 0.14), (-1.50, 3.8775, 0.07), mat_wood, booth, bevel=0.025)
    add_box("Booth_Wood_Platform_Front_Left", (5.925, 1.00, 0.14), (-5.9625, -0.50, 0.07), mat_wood, booth, bevel=0.035)
    add_box("Booth_Wood_Platform_Right_Rear", (0.525, 3.755, 0.14), (0.2625, 3.8775, 0.07), mat_wood, booth, bevel=0.025)
    add_box("Booth_Perimeter_Trim_Front_Left", (5.925, 0.08, 0.18), (-5.9625, -1.015, 0.10), mat_green, booth, bevel=0.018)
    add_box("Booth_Perimeter_Trim_Right_Rear", (0.08, 3.755, 0.18), (0.545, 3.8775, 0.10), mat_green, booth, bevel=0.018)

    # ------------------------------------------------------------------
    # Exact flush L screen: no frame, no corner strip, no top LED.
    # Screen thickness extends inward only; the outward faces remain flush.
    # ------------------------------------------------------------------
    add_open_screen_body("LED_MAIN_SolidBody_NoFrame", (-MAIN_W, 0.0, 0.0, 0.06, 0.0, SCREEN_H), "min_y", mat_screen, led)
    add_open_screen_body("LED_SIDE_SolidBody_NoFrame", (-0.06, 0.0, 0.0, SIDE_W, 0.0, SCREEN_H), "max_x", mat_screen, led)
    main_led = add_screen_quad(
        "LED_MAIN_ACTIVE_3.0x4.5m_2x3",
        [(-MAIN_W, 0.0, 0), (0, 0.0, 0), (0, 0.0, SCREEN_H), (-MAIN_W, 0.0, SCREEN_H)],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        mat_screen,
        led,
        MAIN_W,
        SCREEN_H,
        "2:3",
    )
    side_led = add_screen_quad(
        "LED_SIDE_ACTIVE_2.0x4.5m_4x9",
        [(0.0, 0, 0), (0.0, SIDE_W, 0), (0.0, SIDE_W, SCREEN_H), (0.0, 0, SCREEN_H)],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        mat_screen,
        led,
        SIDE_W,
        SCREEN_H,
        "4:9",
    )
    main_led["future_content"] = "Cross-screen master 1:1, mapped without stretching"
    side_led["future_content"] = "Cross-screen master 1:1, mapped without stretching"

    # Open hospitality zone and non-LED perimeter lightbox structure.
    # PDF pages 3/4/7 confirm that the roof is open; there is no solid canopy slab.
    add_box("Front_Fascia_Green", (5.45, 0.52, 0.82), (-5.75, 0.02, 4.09), mat_green, booth, bevel=0.035)
    add_box("Front_Fascia_Cream_Panel", (3.65, 0.035, 0.54), (-5.40, -0.258, 4.09), mat_cream, booth, bevel=0.018)
    add_box("Front_Fascia_Logo_Panel", (1.22, 0.038, 0.54), (-7.90, -0.260, 4.09), mat_green_2, booth, bevel=0.018)
    add_box("Left_Fascia_Green", (0.52, 5.15, 0.82), (-8.46, 2.47, 4.09), mat_green, booth, bevel=0.035)
    add_box("Rear_Fascia_Green", (8.55, 0.52, 0.82), (-4.25, 5.55, 4.09), mat_green, booth, bevel=0.035)
    add_box("Rear_Fascia_Cream_Left", (2.80, 0.035, 0.54), (-6.75, 5.265, 4.09), mat_cream, booth, bevel=0.018)
    add_box("Rear_Fascia_Logo_Panel", (1.45, 0.038, 0.54), (-4.25, 5.263, 4.09), mat_green_2, booth, bevel=0.018)
    add_box("Rear_Fascia_Cream_Right", (2.80, 0.035, 0.54), (-1.75, 5.265, 4.09), mat_cream, booth, bevel=0.018)
    add_box("Right_Fascia_Green", (0.52, 3.50, 0.82), (-0.02, 3.72, 4.09), mat_green, booth, bevel=0.035)
    add_box("Right_Fascia_Cream_Panel", (0.035, 2.35, 0.54), (0.268, 3.72, 4.09), mat_cream, booth, bevel=0.018)

    add_column("Column_Front_Left", -7.55, 0.24, 4.02, mat_green, mat_cream, booth)
    add_column("Column_Front_Right", -3.35, 0.24, 4.02, mat_green, mat_cream, booth)
    add_column("Column_Rear_Left", -7.55, 5.28, 4.02, mat_green, mat_cream, booth)
    add_column("Column_Right_Front", -0.25, 2.35, 4.02, mat_green, mat_cream, booth)
    add_column("Column_Right_Rear", -0.25, 5.28, 4.02, mat_green, mat_cream, booth)

    # The top view shows a closed 3m x 2m screen enclosure at the booth's right-front corner.
    # Only its front and right exterior faces are LED; the top is explicitly non-LED.
    add_box("LED_Enclosure_Interior_Left_Wall", (0.10, 2.00, 4.50), (-2.95, 1.00, 2.25), mat_green, booth, bevel=0.0)
    add_box("LED_Enclosure_Interior_Back_Wall", (3.00, 0.10, 4.50), (-1.50, 1.95, 2.25), mat_green, booth, bevel=0.0)
    add_screen_quad(
        "LED_Enclosure_Top_NON_LED",
        [(-3.0, 0.0, 4.5), (0.0, 0.0, 4.5), (0.0, 2.0, 4.5), (-3.0, 2.0, 4.5)],
        [(0, 0), (1, 0), (1, 1), (0, 1)],
        mat_green,
        booth,
        3.0,
        2.0,
        "NON-LED TOP",
    )

    # Back and right retail/display walls.
    add_right_shelf_wall(mat_green, mat_cream, mat_gold, mat_orange, mat_cap, booth, products)
    add_back_retail_wall(mat_green, mat_cream, mat_gold, mat_orange, mat_cap, booth, products)

    # Reception counters and hospitality furniture visible across the left side.
    add_counter("Front_Left_Reception", (-8.02, -0.56, 0.62), (1.20, 0.70, 1.10), mat_cream, mat_green, mat_gold, furniture)
    add_counter("Front_Middle_Reception", (-3.78, -0.56, 0.62), (1.28, 0.72, 1.10), mat_cream, mat_green, mat_gold, furniture)
    add_counter("Right_Side_Reception", (0.53, 2.48, 0.62), (0.72, 1.10, 1.10), mat_cream, mat_green, mat_gold, furniture, sign_side="side")
    add_counter("Interior_Service_Counter", (-6.18, 3.70, 0.58), (2.15, 0.72, 1.00), mat_cream, mat_green, mat_gold, furniture)

    add_cylinder("Hospitality_Table_Top", 0.58, 0.08, (-5.68, 2.33, 0.76), mat_cream, furniture, vertices=64, bevel=0.025)
    add_cylinder("Hospitality_Table_Base", 0.10, 0.72, (-5.68, 2.33, 0.37), mat_green, furniture, vertices=32, bevel=0.012)
    add_cylinder("Hospitality_Table_Foot", 0.34, 0.06, (-5.68, 2.33, 0.06), mat_green, furniture, vertices=48, bevel=0.015)
    add_chair("Chair_Left", (-6.72, 2.32, 0.0), -90, mat_green, mat_cream, furniture)
    add_chair("Chair_Right", (-4.68, 2.32, 0.0), 90, mat_green, mat_cream, furniture)
    add_chair("Chair_Back", (-5.68, 3.30, 0.0), 180, mat_green, mat_cream, furniture)

    # Additional negotiation groups visible in the top/inside views (PDF pages 7-9).
    table_centers = (
        (-7.10, 3.62),
        (-5.18, 4.15),
        (-2.72, 4.20),
        (-2.30, 2.70),
        (-6.78, 1.55),
    )
    for idx, (tx, ty) in enumerate(table_centers, start=1):
        add_cylinder(f"Table_{idx}_Top", 0.44, 0.07, (tx, ty, 0.75), mat_white, furniture, vertices=48, bevel=0.022)
        add_cylinder(f"Table_{idx}_Stem", 0.075, 0.70, (tx, ty, 0.38), mat_green, furniture, vertices=24, bevel=0.008)
        add_cylinder(f"Table_{idx}_Foot", 0.25, 0.05, (tx, ty, 0.045), mat_green, furniture, vertices=36, bevel=0.012)
        for chair_idx, (dx, dy, rz) in enumerate(((0.0, -0.72, 0), (0.72, 0.0, 90), (0.0, 0.72, 180), (-0.72, 0.0, -90)), start=1):
            add_chair(f"Table_{idx}_Chair_{chair_idx}", (tx + dx, ty + dy, 0.0), rz, mat_green, mat_cream, furniture)

    # Central organic product island reconstructed from the close view on PDF page 8.
    island_x, island_y = -4.32, 1.45
    for i, (dx, dy, sx, sy) in enumerate(((-0.72, 0.00, 1.42, 0.92), (0.05, 0.04, 1.70, 1.02), (0.78, -0.02, 1.25, 0.82)), start=1):
        base = add_cylinder(f"Central_Island_Base_{i}", 0.58, 0.12, (island_x + dx, island_y + dy, 0.13), mat_white, furniture, vertices=64, bevel=0.035)
        base.scale.x = sx
        base.scale.y = sy
    for i, (dx, dy, h, color) in enumerate(((-0.65, -0.04, 0.55, mat_green), (-0.25, 0.08, 0.78, mat_cream), (0.20, -0.02, 0.48, mat_green), (0.52, 0.06, 0.92, mat_cream), (0.83, -0.05, 0.62, mat_green)), start=1):
        add_box(f"Central_Island_Plinth_{i}", (0.33, 0.34, h), (island_x + dx, island_y + dy, 0.23 + h / 2), color, furniture, bevel=0.035)
    # Mirrored mountain/wave fins and planting details.
    for i, dx in enumerate((-0.78, -0.52, -0.26, 0.00, 0.26, 0.52, 0.78), start=1):
        height = 0.42 + 0.38 * (1.0 - abs(dx) / 0.9)
        add_box(f"Central_Island_MirrorFin_{i}", (0.035, 0.12, height), (island_x + dx, island_y + 0.28, 0.28 + height / 2), mat_mirror, furniture, bevel=0.008)
    for i, angle in enumerate(range(0, 360, 36), start=1):
        a = math.radians(angle)
        px = island_x + math.cos(a) * 0.85
        py = island_y + math.sin(a) * 0.32
        add_curve_line(f"Central_Island_Plant_{i}", [(px, py, 0.24), (px + math.cos(a) * 0.10, py + math.sin(a) * 0.08, 0.74)], mat_green_2, furniture, bevel=0.018)

    # Utility equipment visible behind the screen block in the interior perspective.
    add_box("Utility_Refrigerator", (0.72, 0.66, 1.86), (-0.68, 3.55, 0.93), mat_white, furniture, bevel=0.035)
    add_box("Utility_Refrigerator_DoorLine", (0.56, 0.018, 0.025), (-0.68, 3.211, 0.98), mat_hall_dark, furniture, bevel=0.003)
    add_cylinder("Utility_Water_Dispenser_Bottle", 0.14, 0.34, (-1.18, 3.38, 1.32), mat_screen, furniture, vertices=32, bevel=0.020)
    add_box("Utility_Water_Dispenser", (0.42, 0.42, 1.12), (-1.18, 3.38, 0.58), mat_white, furniture, bevel=0.030)

    # Architectural spotlights under the non-LED fascia and over product walls.
    spotlight_positions = (
        (-7.20, 0.36, 3.86), (-5.80, 0.36, 3.86), (-4.35, 0.36, 3.86),
        (-7.40, 5.12, 3.54), (-5.85, 5.12, 3.54), (-4.30, 5.12, 3.54), (-2.75, 5.12, 3.54), (-1.20, 5.12, 3.54),
        (-0.34, 2.55, 3.75), (-0.34, 3.55, 3.75), (-0.34, 4.55, 3.75),
    )
    for i, pos in enumerate(spotlight_positions, start=1):
        lamp = add_cylinder(f"Booth_Spotlight_{i}", 0.075, 0.20, pos, mat_hall_dark, booth, vertices=24, bevel=0.012)
        lamp.rotation_euler.x = math.radians(72)

    # Signage based on the visible booth graphics, separate from the blank LED surfaces.
    font = None
    for font_path in ("C:\\Windows\\Fonts\\msyh.ttc", "C:\\Windows\\Fonts\\msyhbd.ttc"):
        if os.path.exists(font_path):
            font = bpy.data.fonts.load(font_path)
            break
    add_branded_text(
        "Sign_Front_Slogan",
        "沙棘之恋   健康相伴",
        (-5.40, -0.283, 4.09),
        (math.radians(90), 0, 0),
        0.28,
        mat_green,
        signage,
        font,
    )
    add_branded_text(
        "Sign_Front_Logo",
        "沙棘之恋",
        (-7.90, -0.285, 4.09),
        (math.radians(90), 0, 0),
        0.22,
        mat_text,
        signage,
        font,
    )
    for name, x in (("Sign_Counter_Left", -8.02), ("Sign_Counter_Middle", -3.78)):
        add_branded_text(name, "沙棘之恋", (x, -0.926, 0.62), (math.radians(90), 0, 0), 0.15, mat_text, signage, font)
    add_branded_text(
        "Sign_Back_Header",
        "活力无限",
        (-2.42, 5.105, 2.98),
        (math.radians(90), 0, 0),
        0.25,
        mat_green,
        signage,
        font,
    )

    # Exact-dimension helpers kept in viewport only.
    add_curve_line("GUIDE_Main_Width", [(-3.0, -0.18, -0.16), (0.0, -0.18, -0.16)], mat_guide, guides, bevel=0.012)
    add_curve_line("GUIDE_Side_Width", [(0.18, 0.0, -0.16), (0.18, 2.0, -0.16)], mat_guide, guides, bevel=0.012)
    add_curve_line("GUIDE_Height", [(-3.18, -0.18, 0.0), (-3.18, -0.18, 4.5)], mat_guide, guides, bevel=0.012)
    add_branded_text("GUIDE_Main_Text", "3.0m", (-1.5, -0.20, -0.28), (math.radians(90), 0, 0), 0.20, mat_guide, guides, font)
    add_branded_text("GUIDE_Side_Text", "2.0m", (0.20, 1.0, -0.28), (math.radians(90), 0, math.radians(90)), 0.20, mat_guide, guides, font)
    add_branded_text("GUIDE_Height_Text", "4.5m", (-3.28, -0.20, 2.25), (math.radians(90), 0, math.radians(90)), 0.20, mat_guide, guides, font)

    # Cameras: client overview and the estimated live sweet spot.
    cam_overview = add_camera("CAM_Overview_Matched", (8.4, -13.4, 5.1), (-3.35, 2.00, 2.45), 48.0, lights)
    cam_overview["purpose"] = "Wide overview approximating the supplied rendering"
    cam_sweet = add_camera("CAM_SweetSpot_6p5m", (3.25, -5.6292, 1.60), (-0.70, 0.35, 2.25), 32.0, lights)
    cam_sweet["purpose"] = "Estimated standing audience anamorphic reference"
    cam_front = add_camera("CAM_Front_Elevation", (-4.25, -14.8, 3.35), (-4.25, 2.05, 2.35), 53.0, lights)
    cam_front["purpose"] = "Front elevation based on PDF page 2"
    cam_interior = add_camera("CAM_Interior", (-4.35, -0.58, 2.25), (-4.25, 5.10, 1.55), 28.0, lights)
    cam_interior["purpose"] = "Interior layout based on PDF pages 8-9"
    cam_top = add_camera("CAM_Top_Layout", (-4.25, 2.35, 7.15), (-4.25, 2.35, 0.0), 50.0, lights)
    cam_top.data.type = "ORTHO"
    cam_top.data.ortho_scale = 9.2
    cam_top["purpose"] = "Top layout based on PDF page 7"
    cam_top_oblique = add_camera("CAM_Top_Oblique_Reference", (7.0, -9.0, 7.0), (-4.10, 2.35, 1.0), 48.0, lights)
    cam_top_oblique["purpose"] = "Oblique top view showing the right-front LED enclosure"
    scene.camera = cam_overview

    add_area_light("LIGHT_Booth_Key", (3.6, -4.5, 7.3), (-2.2, 1.7, 2.2), 2200.0, 5.5, (1.0, 0.84, 0.68), lights)
    add_area_light("LIGHT_Booth_Fill", (-7.2, -2.2, 6.1), (-3.7, 2.3, 2.0), 1700.0, 6.0, (0.57, 0.73, 1.0), lights)
    add_area_light("LIGHT_Booth_Rim", (3.2, 6.0, 6.8), (-1.0, 2.2, 2.2), 1900.0, 4.5, (0.52, 0.74, 1.0), lights)
    add_area_light("LIGHT_Interior", (-5.5, 2.4, 3.8), (-5.5, 2.4, 0.0), 650.0, 3.2, (1.0, 0.82, 0.58), lights)

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.006, 0.008, 0.012, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.20

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    preview_jobs = (
        (cam_overview, RENDER_PATH),
        (cam_front, os.path.join(RENDER_DIR, "full_exhibition_booth_front_v5.png")),
        (cam_interior, os.path.join(RENDER_DIR, "full_exhibition_booth_interior_v5.png")),
        (cam_top, os.path.join(RENDER_DIR, "full_exhibition_booth_top_v5.png")),
        (cam_top_oblique, os.path.join(RENDER_DIR, "full_exhibition_booth_top_oblique_v5.png")),
    )
    for camera, path in preview_jobs:
        scene.camera = camera
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
    scene.camera = cam_overview
    scene.render.filepath = RENDER_PATH
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print(f"Saved: {BLEND_PATH}")
    print(f"Rendered: {RENDER_PATH}")


if __name__ == "__main__":
    main()
