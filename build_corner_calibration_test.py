import bpy
import math
import os
import shutil
import subprocess
from mathutils import Matrix, Vector


# =============================================================================
# L-shaped naked-eye 3D calibration test
# Physical LED: main 3.0 x 4.5 m, side 2.0 x 4.5 m, 90 degree outer corner.
# Coordinate system:
#   main LED: Y=0, X=-3..0, outward normal -Y
#   side LED: X=0, Y=0..2, outward normal +X
#   shared corner edge: (0,0,0)..(0,0,4.5)
# =============================================================================

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT_DIR, "renders", "corner_calibration")
os.makedirs(OUT_DIR, exist_ok=True)

BLEND_PATH = os.path.join(ROOT_DIR, "L_LED_corner_calibration_v1.blend")
REPORT_PATH = os.path.join(OUT_DIR, "projection_validation.txt")

MAIN_W = 3.0
SIDE_W = 2.0
SCREEN_H = 4.5

# Provisional exhibition sweet spot: 6.5 m from the corner in plan,
# 30 degrees toward the side screen from the main-screen normal, eye height 1.6 m.
EYE = Vector((3.25, -5.6291651246, 1.60))

FPS = 24
FRAME_START = 1
FRAME_END = 72
FRAME_CROSS = 43
CUBE_START = (-1.60, 0.70, 2.15)
CUBE_END = (-0.30, 2.00, 2.15)
PREVIEW_TARGET = (-1.05, 0.72, 2.25)

# Diagnostic render sizes. They preserve the exact physical ratios:
# main 2:3, side 4:9, unfolded one-controller canvas 10:9.
MAIN_RES = (600, 900)
SIDE_RES = (400, 900)
PACKED_RES = (1000, 900)
PREVIEW_RES = (960, 540)

MAIN_VIDEO = os.path.join(OUT_DIR, "01_main_panel_600x900.mp4")
SIDE_VIDEO = os.path.join(OUT_DIR, "02_side_panel_400x900.mp4")
PREVIEW_VIDEO = os.path.join(OUT_DIR, "04_sweet_spot_reprojection_preview_960x540.mp4")
MAIN_STILL = os.path.join(OUT_DIR, "01_main_panel_crossing_frame.png")
SIDE_STILL = os.path.join(OUT_DIR, "02_side_panel_crossing_frame.png")
PREVIEW_STILL = os.path.join(OUT_DIR, "04_sweet_spot_crossing_frame.png")
PACKED_VIDEO = os.path.join(OUT_DIR, "03_one_controller_packed_1000x900.mp4")
PACKED_STILL = os.path.join(OUT_DIR, "03_one_controller_crossing_frame.png")

FFMPEG_EXE = shutil.which("ffmpeg") or os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    "Microsoft",
    "WinGet",
    "Packages",
    "Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe",
    "ffmpeg-8.1.1-essentials_build",
    "bin",
    "ffmpeg.exe",
)


def clear_file():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.images,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def ratio_label(width, height):
    width_mm = int(round(width * 1000.0))
    height_mm = int(round(height * 1000.0))
    divisor = math.gcd(width_mm, height_mm)
    return f"{width_mm // divisor}:{height_mm // divisor}"


def make_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def move_to_collection(obj, coll):
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    coll.objects.link(obj)


def make_principled_material(name, color, emission=None, strength=0.0, roughness=0.55):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        emission_input = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emission_input:
            emission_input.default_value = (*emission, 1.0)
        strength_input = bsdf.inputs.get("Emission Strength")
        if strength_input:
            strength_input.default_value = strength
    return mat


def make_movie_material(name, movie_path):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for node in list(nodes):
        nodes.remove(node)

    out = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    tex = nodes.new("ShaderNodeTexImage")
    image = bpy.data.images.load(movie_path, check_existing=False)
    image.source = "MOVIE"
    tex.image = image
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    tex.image_user.frame_start = FRAME_START
    tex.image_user.frame_duration = FRAME_END - FRAME_START + 1
    tex.image_user.frame_offset = 0
    tex.image_user.use_auto_refresh = True
    emission.inputs["Strength"].default_value = 1.0
    links.new(tex.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def add_box(name, size, location, material, coll, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        mod = obj.modifiers.new(name="Calibration bevel", type="BEVEL")
        mod.width = bevel
        mod.segments = 3
    obj.data.materials.append(material)
    move_to_collection(obj, coll)
    return obj


def add_screen_quad(name, vertices, material, coll, role):
    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UVMap")
    # Vertex order is left-to-right and bottom-to-top as seen from the sweet spot.
    uvs = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    for loop_index, uv in zip(mesh.polygons[0].loop_indices, uvs):
        uv_layer.data[loop_index].uv = uv
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    obj.data.materials.append(material)
    obj["content_role"] = role
    obj["has_frame"] = False
    obj["has_border"] = False
    return obj


def add_camera_with_basis(name, location, right, up, back, coll):
    data = bpy.data.cameras.new(f"{name}_DATA")
    data.sensor_width = 36.0
    data.sensor_fit = "HORIZONTAL"
    data.clip_start = 0.05
    data.clip_end = 100.0
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    basis = Matrix((Vector(right), Vector(up), Vector(back))).transposed().to_4x4()
    obj.matrix_world = Matrix.Translation(Vector(location)) @ basis
    return obj


def add_look_camera(name, location, target, lens, coll):
    data = bpy.data.cameras.new(f"{name}_DATA")
    data.lens = lens
    data.sensor_width = 36.0
    data.clip_start = 0.05
    data.clip_end = 100.0
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = location
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


def add_grid_line(name, size, location, material, coll):
    return add_box(name, size, location, material, coll, bevel=0.0)


def set_linear_animation(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    action = obj.animation_data.action
    if hasattr(action, "fcurves"):
        fcurves = action.fcurves
    else:
        strip = action.layers[0].strips[0]
        channelbag = strip.channelbag(action.slots[0])
        fcurves = channelbag.fcurves
    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"


def configure_off_axis(cam, distance, panel_width, center_x, center_y):
    # Blender horizontal sensor fit: shift_x and shift_y are both normalized
    # against the horizontal image-plane width.
    cam.data.lens = cam.data.sensor_width * distance / panel_width
    cam.data.shift_x = center_x / panel_width
    cam.data.shift_y = center_y / panel_width
    cam["eye_world_m"] = tuple(round(v, 6) for v in EYE)
    cam["screen_plane_distance_m"] = distance
    cam["off_axis_center_x_m"] = center_x
    cam["off_axis_center_y_m"] = center_y
    cam["projection_method"] = "single-eye generalized perspective / off-axis frustum"


def local_bounds(cam, world_corners):
    inv = cam.matrix_world.inverted()
    points = [inv @ Vector(p) for p in world_corners]
    return {
        "left": min(p.x for p in points),
        "right": max(p.x for p in points),
        "bottom": min(p.y for p in points),
        "top": max(p.y for p in points),
        "distance": sum(-p.z for p in points) / len(points),
    }


def rendered_frame_bounds(scene, cam, distance):
    points = []
    for p in cam.data.view_frame(scene=scene):
        scale = distance / (-p.z)
        points.append(p * scale)
    return {
        "left": min(p.x for p in points),
        "right": max(p.x for p in points),
        "bottom": min(p.y for p in points),
        "top": max(p.y for p in points),
        "distance": distance,
    }


def bounds_error(a, b):
    keys = ("left", "right", "bottom", "top", "distance")
    return max(abs(a[k] - b[k]) for k in keys)


def setup_render_common(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.use_file_extension = True


def set_resolution(scene, size):
    scene.render.resolution_x = size[0]
    scene.render.resolution_y = size[1]
    scene.render.resolution_percentage = 100


def render_video(scene, camera, size, filepath):
    scene.camera = camera
    set_resolution(scene, size)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    frame_dir = os.path.splitext(filepath)[0] + "_frames"
    os.makedirs(frame_dir, exist_ok=True)
    scene.render.filepath = os.path.join(frame_dir, "frame_")
    bpy.ops.render.render(animation=True)
    if not os.path.isfile(FFMPEG_EXE):
        raise RuntimeError(f"FFmpeg not found: {FFMPEG_EXE}")
    frame_pattern = os.path.join(frame_dir, "frame_%04d.png")
    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-framerate",
            str(FPS),
            "-start_number",
            str(FRAME_START),
            "-i",
            frame_pattern,
            "-frames:v",
            str(FRAME_END - FRAME_START + 1),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            filepath,
        ],
        check=True,
    )


def render_still(scene, camera, size, filepath, frame):
    scene.camera = camera
    set_resolution(scene, size)
    scene.frame_set(frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)


def pack_controller_canvas():
    if not os.path.isfile(FFMPEG_EXE):
        raise RuntimeError(f"FFmpeg not found: {FFMPEG_EXE}")
    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-i",
            MAIN_VIDEO,
            "-i",
            SIDE_VIDEO,
            "-filter_complex",
            "[0:v][1:v]hstack=inputs=2[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-crf",
            "18",
            "-preset",
            "medium",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            PACKED_VIDEO,
        ],
        check=True,
    )
    subprocess.run(
        [
            FFMPEG_EXE,
            "-y",
            "-i",
            MAIN_STILL,
            "-i",
            SIDE_STILL,
            "-filter_complex",
            "[0:v][1:v]hstack=inputs=2[v]",
            "-map",
            "[v]",
            "-frames:v",
            "1",
            "-update",
            "1",
            PACKED_STILL,
        ],
        check=True,
    )


def main():
    clear_file()
    scene = bpy.context.scene
    scene.name = "L_CORNER_CALIBRATION"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    scene.unit_settings.scale_length = 1.0
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    setup_render_common(scene)

    scene["test_name"] = "Grid room + cube crossing the 90-degree corner"
    scene["physical_main_screen"] = f"{MAIN_W:.1f}m x {SCREEN_H:.1f}m; {ratio_label(MAIN_W, SCREEN_H)}"
    scene["physical_side_screen"] = f"{SIDE_W:.1f}m x {SCREEN_H:.1f}m; {ratio_label(SIDE_W, SCREEN_H)}"
    scene["unfolded_physical_canvas"] = f"{MAIN_W + SIDE_W:.1f}m x {SCREEN_H:.1f}m; {ratio_label(MAIN_W + SIDE_W, SCREEN_H)}"
    scene["diagnostic_packed_canvas"] = (
        f"{PACKED_RES[0]} x {PACKED_RES[1]}; main {MAIN_RES[0]}px + side {SIDE_RES[0]}px"
    )
    plan_radius = math.hypot(EYE.x, EYE.y)
    view_azimuth = math.degrees(math.atan2(EYE.x, -EYE.y))
    scene["provisional_sweet_spot"] = (
        f"({EYE.x:.6f}, {EYE.y:.6f}, {EYE.z:.2f})m; "
        f"plan radius {plan_radius:.3f}m; {view_azimuth:.3f}deg toward side from main normal"
    )
    scene["important"] = "Do not resize/crop individual panel renders; replace packing resolution only after supplier pixel map arrives"

    virtual_coll = make_collection("01_VIRTUAL_CALIBRATION_ROOM")
    cube_coll = make_collection("02_CROSS_CORNER_CUBE")
    screen_coll = make_collection("03_PHYSICAL_LED_PREVIEW")
    camera_coll = make_collection("04_PROJECTION_CAMERAS")

    mat_room = make_principled_material(
        "MAT_ROOM_DARK", (0.004, 0.008, 0.015), emission=(0.005, 0.012, 0.025), strength=0.65, roughness=0.9
    )
    mat_grid_minor = make_principled_material(
        "MAT_GRID_MINOR_CYAN", (0.0, 0.18, 0.23), emission=(0.0, 0.85, 1.0), strength=3.0, roughness=0.35
    )
    mat_grid_major = make_principled_material(
        "MAT_GRID_MAJOR_WHITE", (0.35, 0.55, 0.58), emission=(0.55, 0.95, 1.0), strength=4.0, roughness=0.3
    )
    mat_seam_plane = make_principled_material(
        "MAT_SEAM_REFERENCE_MAGENTA", (0.28, 0.0, 0.16), emission=(1.0, 0.0, 0.42), strength=5.0, roughness=0.25
    )
    mat_cube = make_principled_material(
        "MAT_CUBE_ORANGE", (0.9, 0.12, 0.01), emission=(1.0, 0.09, 0.005), strength=2.1, roughness=0.22
    )
    mat_cube_edge = make_principled_material(
        "MAT_CUBE_EDGE_WHITE", (0.8, 0.9, 1.0), emission=(1.0, 1.0, 1.0), strength=5.0, roughness=0.2
    )
    mat_screen_placeholder = make_principled_material(
        "MAT_SCREEN_PLACEHOLDER", (0.01, 0.03, 0.08), emission=(0.02, 0.08, 0.22), strength=0.5, roughness=0.9
    )

    # Oversized room surfaces ensure every off-axis ray is filled behind both screens.
    add_box("ROOM_FLOOR", (14.0, 16.0, 0.03), (-5.0, 6.0, -0.025), mat_room, virtual_coll)
    add_box("ROOM_CEILING", (14.0, 16.0, 0.03), (-5.0, 6.0, 4.525), mat_room, virtual_coll)
    add_box("ROOM_BACK", (18.0, 0.03, 4.6), (-5.0, 8.0, 2.25), mat_room, virtual_coll)
    add_box("ROOM_LEFT", (0.03, 18.0, 4.6), (-6.0, 6.0, 2.25), mat_room, virtual_coll)

    # Floor and ceiling grids (0.5 m minor, 1.0 m major).
    for i in range(-18, 1):
        x = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_FLOOR_X_{i:+03d}", (width, 16.0, 0.012), (x, 6.0, 0.004), mat, virtual_coll)
        add_grid_line(f"GRID_CEILING_X_{i:+03d}", (width, 16.0, 0.012), (x, 6.0, 4.496), mat, virtual_coll)
    for i in range(0, 29):
        y = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_FLOOR_Y_{i:02d}", (14.0, width, 0.012), (-5.0, y, 0.004), mat, virtual_coll)
        add_grid_line(f"GRID_CEILING_Y_{i:02d}", (14.0, width, 0.012), (-5.0, y, 4.496), mat, virtual_coll)

    # Back-wall grid at Y=7.98 m.
    for i in range(-18, 5):
        x = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_BACK_VERTICAL_{i:+03d}", (width, 0.012, 4.5), (x, 7.978, 2.25), mat, virtual_coll)
    for i in range(0, 10):
        z = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_BACK_HORIZONTAL_{i:02d}", (18.0, 0.012, width), (-5.0, 7.978, z), mat, virtual_coll)

    # Left-wall grid at X=-5.978 m.
    for i in range(0, 29):
        y = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_LEFT_VERTICAL_{i:02d}", (0.012, width, 4.5), (-5.978, y, 2.25), mat, virtual_coll)
    for i in range(0, 10):
        z = i * 0.5
        major = (i % 2 == 0)
        width = 0.028 if major else 0.014
        mat = mat_grid_major if major else mat_grid_minor
        add_grid_line(f"GRID_LEFT_HORIZONTAL_{i:02d}", (0.012, 16.0, width), (-5.978, 6.0, z), mat, virtual_coll)

    # Magenta floor line is the vertical viewing plane passing through eye and corner.
    # Points on this plane project to the physical shared edge.
    seam_length = 6.0
    seam_dir = Vector((-EYE.x, -EYE.y, 0.0)).normalized()
    seam_center = seam_dir * (seam_length / 2.0)
    seam_ref = add_box(
        "SWEET_SPOT_TO_CORNER_PLANE_FLOOR_TRACE",
        (0.035, seam_length, 0.02),
        (seam_center.x, seam_center.y, 0.018),
        mat_seam_plane,
        virtual_coll,
    )
    seam_ref.rotation_euler[2] = math.atan2(-seam_dir.x, seam_dir.y)

    # Animated cube: crosses the viewing plane near frame 43 and therefore moves
    # continuously from one LED face to the other in the correctly reprojected output.
    cube = add_box("CALIBRATION_CUBE_SOLID", (0.82, 0.82, 0.82), CUBE_START, mat_cube, cube_coll, bevel=0.07)
    cube["animation_role"] = "crosses the 90-degree screen seam"
    cube["crossing_frame"] = FRAME_CROSS
    cube.location = CUBE_START
    cube.rotation_euler = (math.radians(10), math.radians(-12), math.radians(0))
    cube.keyframe_insert(data_path="location", frame=FRAME_START)
    cube.keyframe_insert(data_path="rotation_euler", frame=FRAME_START)
    cube.location = CUBE_END
    cube.rotation_euler = (math.radians(190), math.radians(348), math.radians(360))
    cube.keyframe_insert(data_path="location", frame=FRAME_END)
    cube.keyframe_insert(data_path="rotation_euler", frame=FRAME_END)
    set_linear_animation(cube)

    frame_cube = add_box("CALIBRATION_CUBE_WIREFRAME", (0.86, 0.86, 0.86), CUBE_START, mat_cube_edge, cube_coll)
    wire = frame_cube.modifiers.new(name="White edge cage", type="WIREFRAME")
    wire.thickness = 0.022
    wire.use_replace = True
    frame_cube.parent = cube
    frame_cube.matrix_parent_inverse = cube.matrix_world.inverted()

    # Physical LED quads. Kept invisible during projection renders, then receive
    # the rendered panel movies for a sweet-spot reprojection verification.
    main_screen = add_screen_quad(
        f"LED_MAIN_{MAIN_W:.1f}x{SCREEN_H:.1f}m",
        [(-MAIN_W, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, SCREEN_H), (-MAIN_W, 0.0, SCREEN_H)],
        mat_screen_placeholder,
        screen_coll,
        "main active LED surface; UV left edge to shared corner",
    )
    side_screen = add_screen_quad(
        f"LED_SIDE_{SIDE_W:.1f}x{SCREEN_H:.1f}m",
        [(0.0, 0.0, 0.0), (0.0, SIDE_W, 0.0), (0.0, SIDE_W, SCREEN_H), (0.0, 0.0, SCREEN_H)],
        mat_screen_placeholder,
        screen_coll,
        "side active LED surface; UV shared corner to outer edge",
    )
    main_screen["physical_size_m"] = f"{MAIN_W:.1f} x {SCREEN_H:.1f}"
    main_screen["panel_render_px"] = f"{MAIN_RES[0]} x {MAIN_RES[1]}"
    side_screen["physical_size_m"] = f"{SIDE_W:.1f} x {SCREEN_H:.1f}"
    side_screen["panel_render_px"] = f"{SIDE_RES[0]} x {SIDE_RES[1]}"

    # Main camera: local right +X, local up +Z, local backward -Y.
    main_cam = add_camera_with_basis(
        "CAM_OFFAXIS_MAIN",
        EYE,
        right=(1, 0, 0),
        up=(0, 0, 1),
        back=(0, -1, 0),
        coll=camera_coll,
    )
    main_distance = -EYE.y
    main_center_x = ((-MAIN_W - EYE.x) + (0.0 - EYE.x)) / 2.0
    vertical_center = ((0.0 - EYE.z) + (SCREEN_H - EYE.z)) / 2.0
    configure_off_axis(main_cam, main_distance, MAIN_W, main_center_x, vertical_center)
    main_cam["panel"] = f"main {MAIN_W:.1f} x {SCREEN_H:.1f}m"
    main_cam["expected_render"] = f"{MAIN_RES[0]} x {MAIN_RES[1]}"

    # Side camera: local right +Y, local up +Z, local backward +X.
    side_cam = add_camera_with_basis(
        "CAM_OFFAXIS_SIDE",
        EYE,
        right=(0, 1, 0),
        up=(0, 0, 1),
        back=(1, 0, 0),
        coll=camera_coll,
    )
    side_distance = EYE.x
    side_center_x = ((0.0 - EYE.y) + (SIDE_W - EYE.y)) / 2.0
    configure_off_axis(side_cam, side_distance, SIDE_W, side_center_x, vertical_center)
    side_cam["panel"] = f"side {SIDE_W:.1f} x {SCREEN_H:.1f}m"
    side_cam["expected_render"] = f"{SIDE_RES[0]} x {SIDE_RES[1]}"

    preview_cam = add_look_camera(
        "CAM_SWEET_SPOT_PREVIEW",
        EYE,
        target=PREVIEW_TARGET,
        lens=24.0,
        coll=camera_coll,
    )
    preview_cam["role"] = "normal camera placed at the same sweet spot to verify reprojected LED playback"

    # Validate that each Blender render frame lands on its physical LED rectangle.
    main_corners = [(-MAIN_W, 0, 0), (0, 0, 0), (0, 0, SCREEN_H), (-MAIN_W, 0, SCREEN_H)]
    side_corners = [(0, 0, 0), (0, SIDE_W, 0), (0, SIDE_W, SCREEN_H), (0, 0, SCREEN_H)]
    set_resolution(scene, MAIN_RES)
    main_target = local_bounds(main_cam, main_corners)
    main_frame = rendered_frame_bounds(scene, main_cam, main_distance)
    main_error = bounds_error(main_target, main_frame)
    set_resolution(scene, SIDE_RES)
    side_target = local_bounds(side_cam, side_corners)
    side_frame = rendered_frame_bounds(scene, side_cam, side_distance)
    side_error = bounds_error(side_target, side_frame)

    main_cam["max_projection_error_m"] = main_error
    side_cam["max_projection_error_m"] = side_error
    scene["projection_validation"] = f"main error={main_error:.10f}m; side error={side_error:.10f}m"

    report = [
        "L-SHAPED LED CORNER CALIBRATION / PROJECTION VALIDATION",
        "========================================================",
        f"Sweet spot E = ({EYE.x:.6f}, {EYE.y:.6f}, {EYE.z:.6f}) m",
        f"Main LED = {MAIN_W:.3f} x {SCREEN_H:.3f} m; output {MAIN_RES[0]} x {MAIN_RES[1]}",
        f"Side LED = {SIDE_W:.3f} x {SCREEN_H:.3f} m; output {SIDE_RES[0]} x {SIDE_RES[1]}",
        f"Packed canvas = {PACKED_RES[0]} x {PACKED_RES[1]} (main left, side right)",
        "",
        f"Main camera: lens={main_cam.data.lens:.6f} mm shift_x={main_cam.data.shift_x:.9f} shift_y={main_cam.data.shift_y:.9f}",
        f"Main target bounds={main_target}",
        f"Main rendered bounds={main_frame}",
        f"Main max error={main_error:.12f} m",
        "",
        f"Side camera: lens={side_cam.data.lens:.6f} mm shift_x={side_cam.data.shift_x:.9f} shift_y={side_cam.data.shift_y:.9f}",
        f"Side target bounds={side_target}",
        f"Side rendered bounds={side_frame}",
        f"Side max error={side_error:.12f} m",
        "",
        "PASS" if max(main_error, side_error) < 1e-6 else "CHECK REQUIRED",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
    text_block = bpy.data.texts.new("PROJECTION_VALIDATION.txt")
    text_block.write("\n".join(report))

    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.001, 0.002, 0.005, 1.0)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.02

    # Phase A: render independent panel diagnostics from the same physical eye.
    screen_coll.hide_render = True
    virtual_coll.hide_render = False
    cube_coll.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    print("CALIBRATION_PHASE=MAIN_PANEL_VIDEO", flush=True)
    render_video(scene, main_cam, MAIN_RES, MAIN_VIDEO)
    render_still(scene, main_cam, MAIN_RES, MAIN_STILL, FRAME_CROSS)

    print("CALIBRATION_PHASE=SIDE_PANEL_VIDEO", flush=True)
    render_video(scene, side_cam, SIDE_RES, SIDE_VIDEO)
    render_still(scene, side_cam, SIDE_RES, SIDE_STILL, FRAME_CROSS)

    print("CALIBRATION_PHASE=ONE_CONTROLLER_PACKING", flush=True)
    pack_controller_canvas()

    # Phase B: assign the generated movies to the exact physical LED faces.
    main_movie_mat = make_movie_material("MAT_MAIN_PANEL_MOVIE", MAIN_VIDEO)
    side_movie_mat = make_movie_material("MAT_SIDE_PANEL_MOVIE", SIDE_VIDEO)
    main_screen.data.materials.clear()
    side_screen.data.materials.clear()
    main_screen.data.materials.append(main_movie_mat)
    side_screen.data.materials.append(side_movie_mat)

    # Only the LED planes are rendered now. This proves the content aligns when
    # observed from the same sweet spot, instead of showing the virtual room directly.
    screen_coll.hide_render = False
    virtual_coll.hide_render = True
    cube_coll.hide_render = True

    print("CALIBRATION_PHASE=SWEET_SPOT_REPROJECTION_PREVIEW", flush=True)
    render_video(scene, preview_cam, PREVIEW_RES, PREVIEW_VIDEO)
    render_still(scene, preview_cam, PREVIEW_RES, PREVIEW_STILL, FRAME_CROSS)

    scene.camera = preview_cam
    set_resolution(scene, PREVIEW_RES)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = PREVIEW_STILL
    scene.frame_set(FRAME_CROSS)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)

    print(f"SAVED_BLEND={BLEND_PATH}", flush=True)
    print(f"VALIDATION_REPORT={REPORT_PATH}", flush=True)
    print(f"MAIN_VIDEO={MAIN_VIDEO}", flush=True)
    print(f"SIDE_VIDEO={SIDE_VIDEO}", flush=True)
    print(f"PACKED_VIDEO={PACKED_VIDEO}", flush=True)
    print(f"PREVIEW_VIDEO={PREVIEW_VIDEO}", flush=True)


if __name__ == "__main__":
    main()
