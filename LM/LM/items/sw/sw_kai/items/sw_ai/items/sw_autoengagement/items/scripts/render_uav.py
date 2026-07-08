"""Render synthetic UAV datasets in Blender.

Renders a .glb/.gltf UAV model from many angles, distances, and sky conditions,
producing two datasets:
    - operational/  : small UAV (~60-120px) against sky  → goes in data/train or data/val
  - enrollment/   : large UAV filling frame             → goes in enrollment/<model_name>

RUN FROM COMMAND LINE (no GUI, fastest):
    blender --background --python scripts/render_uav.py -- \
        --model /path/to/mq1_predator.glb \
        --name mq1_predator \
        --output /path/to/data/train/

RUN FROM BLENDER GUI:
    1. Open Blender → Scripting workspace
    2. Paste this script
    3. Edit the FALLBACK CONFIG block below
    4. Click Run Script

REQUIREMENTS:
    - Blender 3.x or 4.x
    - Model must be .glb or .gltf (download from Sketchfab)

OUTPUT STRUCTURE:
    <output>/
        operational/
            mq1_predator/
                az000_el-20_noon_far.jpg
                az030_el000_overcast_far.jpg
                ...
        enrollment/
            mq1_predator/
                az000_el000_noon_close.jpg
                ...
"""

import math
import os
import random
import sys

import bpy
from mathutils import Euler, Matrix, Vector

# ─── FALLBACK CONFIG (used when running from GUI, not CLI) ──────────────────
FALLBACK = dict(
    model="/path/to/your_uav.glb",  # ← edit this
    name="my_uav",  # ← edit this (folder name = identity name)
    output="/path/to/data/train/",  # ← edit this
    width=640,
    height=640,
    samples=32,  # cycles samples (lower = faster, 16-64 is fine)
)

# ─── CAMERA ORBIT SETTINGS ──────────────────────────────────────────────────
# Azimuth: horizontal rotation around UAV (0=front, 90=right, 180=rear, 270=left)
AZIMUTHS_DEG = list(
    range(0, 360, 45)
)  # 8-way coverage: enough silhouette variety without huge datasets

# Elevation: camera angle relative to the UAV center.
# Use only negative values: below-UAV oblique belly views, no parallel/above views.
ELEVATIONS_DEG = [-65, -45, -25, -10]  # underside through shallow side views

# ─── RENDER MODES ───────────────────────────────────────────────────────────
# "operational" → small UAV, simulates 50-100m distance, goes in train/val
# "enrollment"  → large UAV, simulates close client photo, goes in enrollment/
MODES = {
    "operational": {
        "distance_mult": 32.0,  # closer than the older 38.0 preset to reduce tiny detections
        "focal_mm": 200,  # telephoto lens (like a ground observer's camera)
        "target_px": 90,  # approximate rendered UAV size in pixels (informational)
        "distance_jitter": (1.10, 1.35),
        "focal_jitter": (0.95, 1.0),
    },
    "enrollment": {
        "distance_mult": 2.5,  # camera close → large, detailed UAV
        "focal_mm": 85,  # standard lens
        "target_px": 350,  # UAV fills much of the frame
        "distance_jitter": (0.90, 1.35),
        "focal_jitter": (0.85, 1.20),
    },
}

# ─── SKY / BACKGROUND CONFIGS ───────────────────────────────────────────────
# Mix of realistic sky and flat-color overcast
# Each dict: type="sky" uses Blender's Nishita sky (physically based)
#            type="color" uses flat background color
SKIES = [
    {"type": "sky", "sun_elev": 60, "sun_rot": 0.2, "name": "noon_clear"},
    {"type": "sky", "sun_elev": 25, "sun_rot": 1.0, "name": "morning"},
    {"type": "sky", "sun_elev": 10, "sun_rot": 2.5, "name": "dusk"},
    {"type": "color", "color": (0.80, 0.82, 0.85), "name": "overcast"},
    {"type": "color", "color": (0.92, 0.94, 0.97), "name": "white_hazy"},
]

# High-contrast but plausible body colors. Chosen to avoid sky-like pale gray/blue.
UAV_BODY_COLORS = [
    (0.10, 0.11, 0.10, 1.0),  # charcoal
    (0.16, 0.19, 0.12, 1.0),  # olive drab
    (0.24, 0.22, 0.15, 1.0),  # dark sand/khaki
    (0.18, 0.16, 0.13, 1.0),  # dark tan
    (0.12, 0.15, 0.18, 1.0),  # dark blue-gray
    (0.20, 0.11, 0.09, 1.0),  # muted rust/brown
]

UAV_ACCENT_COLORS = [
    (0.55, 0.45, 0.22, 1.0),  # muted yellow/tan
    (0.42, 0.12, 0.08, 1.0),  # dull red-brown
    (0.08, 0.22, 0.12, 1.0),  # dark green
    (0.06, 0.08, 0.10, 1.0),  # near black
]


# ─── PARSE CLI ARGS ─────────────────────────────────────────────────────────
def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        return FALLBACK  # running from GUI

    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=640)
    p.add_argument("--samples", type=int, default=32)
    p.add_argument(
        "--azimuths", type=int, default=8, help="Number of horizontal angles (evenly spaced 0-360)"
    )
    p.add_argument(
        "--elevations",
        type=float,
        nargs="+",
        default=None,
        help=(
            "Camera elevation angles in degrees. Default covers underside through "
            "shallow side views."
        ),
    )
    p.add_argument(
        "--realistic",
        action="store_true",
        help="Randomize camera roll, distance, lens, aim, exposure, and lighting per render.",
    )
    p.add_argument(
        "--colorize",
        choices=["none", "operational", "all"],
        default="operational",
        help=(
            "Override UAV materials with contrast-preserving colors. Default: "
            "operational renders only."
        ),
    )
    p.add_argument(
        "--variants",
        type=int,
        default=1,
        help="Number of randomized renders per pose/sky when --realistic is set.",
    )
    p.add_argument(
        "--sky_count",
        type=int,
        default=3,
        help="Use only the first N sky presets. Useful for quick realistic dataset passes.",
    )
    p.add_argument(
        "--skip_enrollment",
        action="store_true",
        help="Only render operational (far) images, skip enrollment",
    )
    p.add_argument(
        "--operational_distance_mult",
        type=float,
        default=None,
        help="Override operational camera distance multiplier for demo or ablation renders.",
    )
    p.add_argument(
        "--operational_focal_mm",
        type=float,
        default=None,
        help="Override operational focal length for demo or ablation renders.",
    )
    p.add_argument(
        "--operational_distance_jitter",
        type=float,
        nargs=2,
        default=None,
        metavar=("MIN", "MAX"),
        help="Override operational distance jitter multipliers.",
    )
    p.add_argument(
        "--operational_focal_jitter",
        type=float,
        nargs=2,
        default=None,
        metavar=("MIN", "MAX"),
        help="Override operational focal length jitter multipliers.",
    )
    args = p.parse_args(argv)
    cfg = vars(args)
    global AZIMUTHS_DEG, ELEVATIONS_DEG
    step = 360.0 / max(1, cfg["azimuths"])
    AZIMUTHS_DEG = [round(i * step, 3) for i in range(max(1, cfg["azimuths"]))]
    if cfg["elevations"] is not None:
        ELEVATIONS_DEG = cfg["elevations"]
    return cfg


# ─── SCENE SETUP ────────────────────────────────────────────────────────────
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)
    for block in list(bpy.data.materials):
        bpy.data.materials.remove(block)


def import_model(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.import_scene.obj(filepath=path)
    else:
        raise ValueError(f"Unsupported format: {ext}. Use .glb, .gltf, .fbx, or .obj")

    imported = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not imported:
        raise RuntimeError("No mesh objects found after import.")
    return imported


def normalize_model(objects):
    """Center model at origin and scale so its longest axis = 1.0 Blender unit."""
    bpy.context.view_layer.update()

    # Compute world bounding box across all mesh objects. Use bound_box corners
    # instead of local vertices so parented/multi-object GLBs stay centered.
    all_verts = []
    for obj in objects:
        for corner in obj.bound_box:
            all_verts.append(obj.matrix_world @ Vector(corner))

    if not all_verts:
        return

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
    center_str = tuple(round(v, 4) for v in center)
    print(f"Normalized model: center={center_str} max_dim={max_dim:.4f} scale={scale:.4f}")


def setup_renderer(cfg):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = cfg.get("samples", 32)
    scene.cycles.use_denoising = True
    # Use GPU if available
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.get_devices()
    for device in prefs.devices:
        device.use = True
    try:
        scene.cycles.device = "GPU"
    except Exception:
        scene.cycles.device = "CPU"
    scene.render.resolution_x = cfg.get("width", 640)
    scene.render.resolution_y = cfg.get("height", 640)
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 95


def add_camera(focal_mm=85):
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.data.lens = focal_mm
    bpy.context.scene.camera = cam
    return cam


def add_sun_light(elevation_deg=45, rotation_deg=0, strength=3.0):
    # Remove existing lights
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj)
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
    sun = bpy.context.active_object
    sun.data.energy = strength
    sun.rotation_euler = Euler(
        (math.radians(90 - elevation_deg), 0, math.radians(rotation_deg)), "XYZ"
    )
    return sun


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


def apply_uav_color_variant(objects, mode_name, colorize):
    if colorize == "none" or (colorize == "operational" and mode_name != "operational"):
        return

    body = random.choice(UAV_BODY_COLORS)
    accent = random.choice(UAV_ACCENT_COLORS)
    body_mat = make_colored_material(f"runtime_body_{mode_name}_{random.randint(0, 999999)}", body)
    accent_mat = make_colored_material(
        f"runtime_accent_{mode_name}_{random.randint(0, 999999)}", accent
    )

    for idx, obj in enumerate(objects):
        if obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(accent_mat if idx % 5 == 0 else body_mat)


def set_if_supported(obj, attr, value):
    if hasattr(obj, attr):
        try:
            setattr(obj, attr, value)
        except Exception:
            pass


def set_supported_sky_type(sky_node):
    candidates = [
        "NISHITA",
        "MULTIPLE_SCATTERING",
        "SINGLE_SCATTERING",
        "PREETHAM",
        "HOSEK_WILKIE",
    ]
    try:
        enum_items = sky_node.bl_rna.properties["sky_type"].enum_items
        supported = {item.identifier for item in enum_items}
    except Exception:
        supported = set(candidates)

    for sky_type in candidates:
        if sky_type not in supported:
            continue
        try:
            sky_node.sky_type = sky_type
            return sky_type
        except TypeError:
            continue

    raise RuntimeError(f"No supported sky type found. Available: {sorted(supported)}")


def set_sky_background(sky_cfg):
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputWorld")
    out.location = (400, 0)

    if sky_cfg["type"] == "sky":
        bg = nodes.new("ShaderNodeBackground")
        bg.location = (200, 0)
        sky = nodes.new("ShaderNodeTexSky")
        sky.location = (0, 0)
        set_supported_sky_type(sky)
        set_if_supported(sky, "sun_elevation", math.radians(sky_cfg.get("sun_elev", 45)))
        set_if_supported(sky, "sun_rotation", sky_cfg.get("sun_rot", 0.0))
        set_if_supported(sky, "altitude", 500)
        set_if_supported(sky, "air_density", 1.0)
        set_if_supported(sky, "dust_density", 0.5)
        bg.inputs["Strength"].default_value = 1.0
        links.new(sky.outputs["Color"], bg.inputs["Color"])
        links.new(bg.outputs["Background"], out.inputs["Surface"])
        # Add matching sun light
        add_sun_light(
            elevation_deg=sky_cfg.get("sun_elev", 45),
            rotation_deg=math.degrees(sky_cfg.get("sun_rot", 0)),
        )

    elif sky_cfg["type"] == "color":
        bg = nodes.new("ShaderNodeBackground")
        bg.location = (200, 0)
        c = sky_cfg["color"]
        bg.inputs["Color"].default_value = (*c, 1.0)
        bg.inputs["Strength"].default_value = 1.5
        links.new(bg.outputs["Background"], out.inputs["Surface"])
        add_sun_light(elevation_deg=40, strength=2.0)


def position_camera(cam, azimuth_deg, elevation_deg, distance, target_offset=None, roll_deg=0.0):
    """Place camera on a sphere around the origin.

    azimuth=0, elevation=0 → camera looking horizontally at the UAV front.
    elevation > 0 → camera above, looking down.
    elevation < 0 → camera below, looking up (belly shot, like ground observer).
    """
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)

    x = distance * math.cos(el) * math.cos(az)
    y = distance * math.cos(el) * math.sin(az)
    z = distance * math.sin(el)

    cam.location = Vector((x, y, z))

    target = Vector((0, 0, 0)) if target_offset is None else Vector(target_offset)
    direction = target - cam.location
    rot = direction.to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()
    if roll_deg:
        cam.rotation_euler.rotate_axis("Z", math.radians(roll_deg))


def random_render_params(realistic, mode_cfg):
    if not realistic:
        return {
            "distance": mode_cfg["distance_mult"],
            "focal_mm": mode_cfg["focal_mm"],
            "target_offset": (0, 0, 0),
            "roll_deg": 0.0,
            "exposure": 0.0,
            "gamma": 1.0,
            "sun_strength": 1.0,
        }

    distance_lo, distance_hi = mode_cfg.get("distance_jitter", (0.78, 1.35))
    focal_lo, focal_hi = mode_cfg.get("focal_jitter", (0.82, 1.22))

    return {
        "distance": mode_cfg["distance_mult"] * random.uniform(distance_lo, distance_hi),
        "focal_mm": mode_cfg["focal_mm"] * random.uniform(focal_lo, focal_hi),
        "target_offset": (
            random.uniform(-0.08, 0.08),
            random.uniform(-0.08, 0.08),
            random.uniform(-0.05, 0.05),
        ),
        "roll_deg": random.uniform(-32.0, 32.0),
        "exposure": random.uniform(-0.45, 0.35),
        "gamma": random.uniform(0.88, 1.12),
        "sun_strength": random.uniform(0.80, 1.35),
    }


# ─── RENDER LOOP ─────────────────────────────────────────────────────────────
def render_dataset(cfg):
    model_path = cfg["model"]
    model_name = cfg["name"]
    out_root = cfg["output"]
    skip_enroll = cfg.get("skip_enrollment", False)
    modes = {name: values.copy() for name, values in MODES.items()}
    if cfg.get("operational_distance_mult") is not None:
        modes["operational"]["distance_mult"] = float(cfg["operational_distance_mult"])
    if cfg.get("operational_focal_mm") is not None:
        modes["operational"]["focal_mm"] = float(cfg["operational_focal_mm"])
    if cfg.get("operational_distance_jitter") is not None:
        modes["operational"]["distance_jitter"] = tuple(
            float(v) for v in cfg["operational_distance_jitter"]
        )
    if cfg.get("operational_focal_jitter") is not None:
        modes["operational"]["focal_jitter"] = tuple(
            float(v) for v in cfg["operational_focal_jitter"]
        )

    # Output directories
    op_dir = os.path.join(out_root, "operational", model_name)
    en_dir = os.path.join(os.path.dirname(out_root.rstrip("/")), "enrollment", model_name)
    os.makedirs(op_dir, exist_ok=True)
    if not skip_enroll:
        os.makedirs(en_dir, exist_ok=True)

    # Scene setup
    clear_scene()
    objects = import_model(model_path)
    normalize_model(objects)  # model is now 1 unit long, centered at origin
    setup_renderer(cfg)
    cam = add_camera()

    skies = SKIES[: max(1, int(cfg["sky_count"]))] if cfg.get("sky_count") else SKIES
    variants = max(1, int(cfg.get("variants", 1))) if cfg.get("realistic", False) else 1
    total = (
        len(AZIMUTHS_DEG)
        * len(ELEVATIONS_DEG)
        * len(skies)
        * variants
        * (1 + (0 if skip_enroll else 1))
    )
    done = 0

    for sky in skies:
        set_sky_background(sky)
        base_light_energy = {
            obj.name: obj.data.energy
            for obj in bpy.data.objects
            if obj.type == "LIGHT" and hasattr(obj.data, "energy")
        }

        for mode_name, mode_cfg in modes.items():
            if mode_name == "enrollment" and skip_enroll:
                continue

            out_dir = op_dir if mode_name == "operational" else en_dir

            for az in AZIMUTHS_DEG:
                for el in ELEVATIONS_DEG:
                    for variant in range(variants):
                        suffix = (
                            f"_v{variant:02d}"
                            if cfg.get("realistic", False) or variants > 1
                            else ""
                        )
                        az_str = f"az{int(round(az)):03d}"
                        el_str = f"el{int(round(el)):+03d}"
                        filename = f"{az_str}_{el_str}_{sky['name']}_{mode_name}{suffix}.jpg"
                        filepath = os.path.join(out_dir, filename)

                        if os.path.exists(filepath):
                            done += 1
                            continue  # resume-safe: skip already rendered

                        params = random_render_params(cfg.get("realistic", False), mode_cfg)
                        cam.data.lens = params["focal_mm"]
                        bpy.context.scene.view_settings.exposure = params["exposure"]
                        bpy.context.scene.view_settings.gamma = params["gamma"]
                        for obj in bpy.data.objects:
                            if obj.type == "LIGHT" and hasattr(obj.data, "energy"):
                                obj.data.energy = (
                                    base_light_energy.get(obj.name, obj.data.energy)
                                    * params["sun_strength"]
                                )
                        apply_uav_color_variant(
                            objects, mode_name, cfg.get("colorize", "operational")
                        )
                        position_camera(
                            cam,
                            az,
                            el,
                            params["distance"],
                            params["target_offset"],
                            params["roll_deg"],
                        )
                        bpy.context.scene.render.filepath = filepath
                        bpy.ops.render.render(write_still=True)

                        done += 1
                        print(f"[{done}/{total}] {filename}")

    print("\nDone. Renders saved to:")
    print(f"  operational → {op_dir}")
    if not skip_enroll:
        print(f"  enrollment  → {en_dir}")
    print("\nNext steps:")
    print("  1. Run: python scripts/audit_dataset.py --data_root data/ --show_sizes")
    print("  2. If audit passes: python -m src.train --data_root data/ ...")


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = parse_args()
    render_dataset(cfg)
