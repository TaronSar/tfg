"""
Render UAV GLB models directly over real backgrounds in Blender.
No segmentation/rembg: model and background are rendered natively in Blender.

Example:
  "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background \
    --python scripts/render_glb_with_backgrounds.py -- \
    --models_root C:/Users/tsa3/Desktop/TFG/protonet_uav/uav_models \
    --before_root C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_before_bg/operational \
    --background_root C:/Users/tsa3/Desktop/TFG/protonet_uav/data/backgrounds \
    --out_root C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_after_bg/operational
"""

import argparse
import math
import os
import random
import re
import subprocess
import sys
import tempfile

import bpy
from mathutils import Euler, Matrix, Vector


IDENTITIES = [
    "Ukraine_pavilion",
    "Ukraine_pavilion_2",
    "Ukraine_PD-2_UAV",
    "Ukraine_poseidon",
]

UAV_BODY_COLORS = [
    (0.13, 0.14, 0.14, 1.0),
    (0.18, 0.20, 0.14, 1.0),
    (0.24, 0.22, 0.16, 1.0),
    (0.15, 0.17, 0.21, 1.0),
]

UAV_ACCENT_COLORS = [
    (0.42, 0.32, 0.18, 1.0),
    (0.38, 0.16, 0.12, 1.0),
    (0.10, 0.22, 0.14, 1.0),
]


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    p = argparse.ArgumentParser(description="Render GLB models over real backgrounds")
    p.add_argument("--models_root", required=True)
    p.add_argument("--before_root", required=True)
    p.add_argument("--background_root", required=True)
    p.add_argument("--out_root", required=True)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--seed", type=int, default=123)
    p.add_argument("--distance", type=float, default=38.0)
    p.add_argument("--focal_mm", type=float, default=200.0)
    p.add_argument("--top_shift", type=float, default=0.22,
                   help="Look-below offset. Larger -> UAV appears higher in frame")
    p.add_argument("--jitter_x", type=float, default=0.09,
                   help="Target jitter in X/Y plane")
    p.add_argument("--jitter_y", type=float, default=0.05,
                   help="Vertical jitter around top placement")
    p.add_argument("--identities", default="all",
                   help="Comma-separated identities or 'all'")
    p.add_argument("--limit", type=int, default=0,
                   help="If >0, render only first N images per identity")
    p.add_argument("--colorize", choices=["none", "mild"], default="mild",
                   help="Apply mild body/accent recoloring similar to color_mild_clean")
    p.add_argument("--degrade", choices=["none", "mild"], default="mild",
                   help="Apply mild jpeg/quality jitter per frame")
    p.add_argument("--uav_scale", type=float, default=0.45,
                   help="Scale factor applied to UAV layer before compositing")
    p.add_argument("--venv_python",
                   default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                        ".venv", "Scripts", "python.exe"),
                   help="Path to venv Python used for PIL compositing step")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        bpy.data.materials.remove(block)


def import_model(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise ValueError(f"Unsupported format: {ext}")

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh objects imported")
    return meshes


def normalize_model(objects):
    bpy.context.view_layer.update()
    all_verts = []
    for obj in objects:
        for corner in obj.bound_box:
            all_verts.append(obj.matrix_world @ Vector(corner))

    xs = [v.x for v in all_verts]
    ys = [v.y for v in all_verts]
    zs = [v.z for v in all_verts]

    center = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2))
    max_dim = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    scale = 1.0 / max_dim if max_dim > 0 else 1.0

    transform = Matrix.Diagonal((scale, scale, scale, 1.0)) @ Matrix.Translation(-center)
    for obj in objects:
        obj.matrix_world = transform @ obj.matrix_world

    bpy.context.view_layer.update()


def setup_renderer(width, height, samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 95

    scene.cycles.samples = samples
    scene.cycles.use_denoising = True

    # Keep output close to source texture brightness while preserving UAV contrast.
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    try:
        scene.view_settings.look = "None"
    except Exception:
        pass
    scene.view_settings.exposure = 0.1
    scene.view_settings.gamma = 1.0

    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    try:
        scene.cycles.device = "GPU"
    except Exception:
        scene.cycles.device = "CPU"

    # Render UAV with transparent background; PIL will composite over real BG.
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    # Neutral grey ambient so dark PBR materials stay visible in the transparent pass.
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    wnodes = scene.world.node_tree.nodes
    wlinks = scene.world.node_tree.links
    bg_node = wnodes.get("Background")
    out_node = wnodes.get("World Output")
    if bg_node is None:
        bg_node = wnodes.new("ShaderNodeBackground")
    if out_node is None:
        out_node = wnodes.new("ShaderNodeOutputWorld")
    bg_node.inputs["Color"].default_value = (0.55, 0.57, 0.60, 1.0)
    bg_node.inputs["Strength"].default_value = 0.6
    try:
        wlinks.new(bg_node.outputs["Background"], out_node.inputs["Surface"])
    except Exception:
        pass


def add_camera(focal_mm):
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.data.lens = focal_mm
    bpy.context.scene.camera = cam
    return cam


def add_sun():
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
    sun = bpy.context.active_object
    sun.data.energy = 3.8
    sun.rotation_euler = Euler((math.radians(40), 0.0, math.radians(35)), "XYZ")


def add_fill_lights():
    # Soft frontal fill.
    bpy.ops.object.light_add(type="AREA", location=(8, -6, 6))
    key = bpy.context.active_object
    key.data.energy = 900.0
    key.data.size = 8.0
    key.rotation_euler = Euler((math.radians(55), 0.0, math.radians(35)), "XYZ")

    # Opposite-side fill to avoid near-black silhouettes.
    bpy.ops.object.light_add(type="AREA", location=(-7, 7, 5))
    fill = bpy.context.active_object
    fill.data.energy = 640.0
    fill.data.size = 7.0
    fill.rotation_euler = Euler((math.radians(60), 0.0, math.radians(-145)), "XYZ")

    # Back rim to separate dark UAV parts from dark terrain in backgrounds.
    bpy.ops.object.light_add(type="AREA", location=(0, 10, 8))
    rim = bpy.context.active_object
    rim.data.energy = 450.0
    rim.data.size = 9.0
    rim.rotation_euler = Euler((math.radians(65), 0.0, math.radians(180)), "XYZ")


def position_camera(cam, azimuth_deg, elevation_deg, distance, target_offset=(0.0, 0.0, 0.0)):
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)

    x = distance * math.cos(el) * math.cos(az)
    y = distance * math.cos(el) * math.sin(az)
    z = distance * math.sin(el)
    cam.location = Vector((x, y, z))

    target = Vector(target_offset)
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def parse_pose_from_name(filename):
    m = re.search(r"az(-?\d+(?:\.\d+)?)_el(-?\d+(?:\.\d+)?)", filename)
    if not m:
        raise ValueError(f"Cannot parse az/el from: {filename}")
    return float(m.group(1)), float(m.group(2))


def composite_over_bg(uav_png, bg_path, out_jpg, width, height, quality, seed, uav_scale, venv_python):
    """Call the venv Python PIL compositor to blend UAV PNG over background."""
    helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_composite_uav_over_bg.py")
    subprocess.run(
        [venv_python, helper, uav_png, bg_path, out_jpg,
         str(width), str(height), str(quality), str(seed), str(uav_scale)],
        check=True,
    )


def make_colored_material(name, color, roughness=0.72):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def apply_uav_color_variant(objects):
    body = random.choice(UAV_BODY_COLORS)
    accent = random.choice(UAV_ACCENT_COLORS)
    body_mat = make_colored_material(f"body_{random.randint(0, 999999)}", body)
    accent_mat = make_colored_material(f"accent_{random.randint(0, 999999)}", accent)

    for idx, obj in enumerate(objects):
        if obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(accent_mat if idx % 5 == 0 else body_mat)


def get_backgrounds(background_root):
    files = []
    for root, _dirs, names in os.walk(background_root):
        for n in names:
            if n.lower().endswith((".jpg", ".jpeg", ".png")):
                files.append(os.path.join(root, n))
    files.sort()
    return files


def render_identity(identity, glb_path, before_dir, out_dir, backgrounds, cfg):
    clear_scene()
    meshes = import_model(glb_path)
    normalize_model(meshes)

    setup_renderer(cfg.width, cfg.height, cfg.samples)
    cam = add_camera(cfg.focal_mm)
    add_sun()
    add_fill_lights()

    os.makedirs(out_dir, exist_ok=True)

    src_images = [n for n in os.listdir(before_dir) if n.lower().endswith((".jpg", ".jpeg", ".png"))]
    src_images.sort()
    if len(src_images) != 30:
        raise RuntimeError(f"{identity}: expected 30 source images, found {len(src_images)}")

    if cfg.limit > 0:
        src_images = src_images[: cfg.limit]

    tmp_dir = tempfile.mkdtemp(prefix="uav_render_")

    for i, src_name in enumerate(src_images):
        az, el = parse_pose_from_name(src_name)

        tx = random.uniform(-cfg.jitter_x, cfg.jitter_x)
        ty = random.uniform(-cfg.jitter_x, cfg.jitter_x)
        tz = -cfg.top_shift + random.uniform(-cfg.jitter_y, cfg.jitter_y)
        position_camera(cam, az, el, cfg.distance, target_offset=(tx, ty, tz))

        # Apply a fresh color variant every frame so UAV color is not constant.
        if cfg.colorize == "mild":
            apply_uav_color_variant(meshes)

        if cfg.degrade == "mild":
            cam.data.dof.use_dof = True
            cam.data.dof.focus_distance = cfg.distance * random.uniform(0.95, 1.08)
            cam.data.dof.aperture_fstop = random.uniform(14.0, 20.0)
            quality = 95
        else:
            cam.data.dof.use_dof = False
            quality = 95

        # Render UAV as transparent PNG.
        stem = os.path.splitext(src_name)[0]
        tmp_png = os.path.join(tmp_dir, stem + ".png")
        bpy.context.scene.render.filepath = tmp_png
        bpy.ops.render.render(write_still=True)

        # Composite PNG over real background using PIL (venv Python).
        bg_path = backgrounds[i]
        out_path = os.path.join(out_dir, stem + ".jpg")
        composite_over_bg(
            tmp_png,
            bg_path,
            out_path,
            cfg.width,
            cfg.height,
            quality,
            seed=cfg.seed + i,
            uav_scale=cfg.uav_scale,
            venv_python=cfg.venv_python,
        )

        # Clean up temp PNG immediately.
        try:
            os.remove(tmp_png)
        except OSError:
            pass

        print(f"[{identity}] {i+1:02d}/30 -> {src_name} <- {os.path.basename(bg_path)}")


def main():
    cfg = parse_args()
    random.seed(cfg.seed)

    backgrounds = get_backgrounds(cfg.background_root)
    if len(backgrounds) != 30:
        raise RuntimeError(f"Expected exactly 30 backgrounds, found {len(backgrounds)}")

    identities = list(IDENTITIES)
    if cfg.identities.strip().lower() != "all":
        requested = [x.strip() for x in cfg.identities.split(",") if x.strip()]
        identities = [x for x in identities if x in requested]
        if not identities:
            raise RuntimeError("No valid identities selected with --identities")

    for identity in identities:
        glb_path = os.path.join(cfg.models_root, identity, f"{identity}.glb")
        before_dir = os.path.join(cfg.before_root, identity)
        out_dir = os.path.join(cfg.out_root, identity)

        if not os.path.exists(glb_path):
            raise RuntimeError(f"Missing GLB: {glb_path}")
        if not os.path.isdir(before_dir):
            raise RuntimeError(f"Missing source folder: {before_dir}")

        render_identity(identity, glb_path, before_dir, out_dir, backgrounds, cfg)

    print("Done rendering all identities.")


if __name__ == "__main__":
    main()
