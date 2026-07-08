"""Composite UAV renders over backgrounds in GIMP 3.x.

Rewritten for GIMP 3 GObject Introspection API (pdb global no longer exists).
Tested on GIMP 3.2.x / Python 3.14.

HOW TO RUN:
  1. Open GIMP
  2. Filters > Python-Fu > Console
  3. Paste:
       exec(open(r'C:/Users/tsa3/Desktop/TFG/protonet_uav/scripts/composite_uav_gimp.py').read())

PREREQUISITES:
    Run scripts/download_backgrounds.py first (already done if data/backgrounds/ exists).
"""

# ─── IMPORTS (GIMP 3 uses GObject Introspection — no pdb global) ─────────────
import os
import random

from gi.repository import Gimp, Gio

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TEST_MODE = True  # False = pick a random UAV from the dataset

UAV_IMAGE = (
    r"C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_color_mild_clean/"
    r"enrollment/mq-9_reaper/az000_el-45_noon_clear_enrollment_v00.jpg"
)
UAV_FOLDER = r"C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_color_mild_clean/enrollment"
BG_FOLDER = r"C:/Users/tsa3/Desktop/TFG/protonet_uav/data/backgrounds"
OUT_FOLDER = r"C:/Users/tsa3/Desktop/TFG/protonet_uav/data/composited"

OUTPUT_SIZE = 640
UAV_SCALE = 0.42  # UAV occupies this fraction of the shorter output side
POS_JITTER = 0.15  # max center offset (fraction of OUTPUT_SIZE)

# Sky fuzzy-select threshold (0–255).
# Raise if sky is not fully removed; lower if UAV body gets eaten.
SKY_THRESHOLD = 60

# ─── GIMP 3 CONSTANTS ────────────────────────────────────────────────────────
OP_REPLACE = Gimp.ChannelOps.REPLACE
OP_ADD = Gimp.ChannelOps.ADD
INTERP = Gimp.InterpolationType.CUBIC
RUN_NI = Gimp.RunMode.NONINTERACTIVE


def gfile(path):
    return Gio.File.new_for_path(path)


def load_flat_rgb(path):
    img = Gimp.file_load(RUN_NI, gfile(path))
    if img.get_base_type() != Gimp.ImageBaseType.RGB:
        img.convert_rgb()
    layer = img.flatten()  # flatten() returns the merged layer in GIMP 3
    return img, layer


def export_jpeg(image, out_path, quality=0.92):
    """Save flattened image as JPEG with fallbacks for GIMP 3 API variations."""
    drawable = image.flatten()  # flatten() returns the merged layer in GIMP 3
    out_file = gfile(out_path)
    try:
        # GIMP 3: drawables is a list; quality is 0.0–1.0
        Gimp.file_jpeg_save(RUN_NI, image, [drawable], out_file, quality, 0.0, 1, 0, "", 0, 1, 0, 2)
        return out_path
    except Exception as e:
        print(f"  file_jpeg_save failed ({e}), trying file_overwrite ...")
    try:
        Gimp.file_overwrite(RUN_NI, image, drawable, out_file)
        return out_path
    except Exception as e:
        print(f"  file_overwrite failed ({e}), saving as PNG ...")
        png_path = out_path.replace(".jpg", ".png")
        Gimp.file_png_save(RUN_NI, image, [drawable], gfile(png_path), 0, 9, 1, 1, 1, 1, 1)
        return png_path


def collect_images(folder):
    result = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                result.append(os.path.join(root, f))
    return result


def composite_uav(uav_path, bg_path, out_folder):
    """Composite one UAV image onto one background.

    1. Load UAV image.
    2. Select sky from all 4 corners via fuzzy-select (handles gradient sky).
    3. Invert → UAV selected. Copy it.
    4. Paste onto resized background.
    5. Scale and centre the UAV layer with random jitter.
    6. Flatten and save as JPEG.
    """
    print("UAV:        ", uav_path)
    print("Background: ", bg_path)

    # ── 1. Load UAV ──────────────────────────────────────────────────────────
    uav_img, uav_draw = load_flat_rgb(uav_path)
    W = uav_img.get_width()
    H = uav_img.get_height()

    # ── 2. Select sky via fuzzy-select from all 4 corners ────────────────────
    # Blender Nishita sky is a gradient, so we union-select from every corner.
    corners = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]
    for i, (cx, cy) in enumerate(corners):
        op = OP_REPLACE if i == 0 else OP_ADD
        Gimp.fuzzy_select(
            uav_draw,
            cx,
            cy,
            SKY_THRESHOLD,  # threshold (0-255)
            op,  # REPLACE first corner, ADD the rest
            True,  # antialias
            False,  # feather (done manually below)
            0.0,  # feather radius
            True,  # sample merged
        )

    # Clean up edge:
    #   grow 2px  → fills tiny un-selected sky gaps in fringe
    #   shrink 1px → pulls back so no sky fringe included
    #   feather 0.8px → natural soft edge for compositing
    uav_img.selection_grow(2)
    uav_img.selection_shrink(1)
    uav_img.selection_feather(0.8)

    # Invert: now the UAV (not sky) is selected
    uav_img.selection_invert()

    # ── 3. Copy UAV ───────────────────────────────────────────────────────────
    Gimp.edit_copy(uav_draw)

    # ── 4. Load background and resize to output size ─────────────────────────
    bg_img, _ = load_flat_rgb(bg_path)
    bg_img.scale_full(OUTPUT_SIZE, OUTPUT_SIZE, INTERP)

    # ── 5. Paste UAV as floating selection, then promote to layer ─────────────
    bg_draw = bg_img.flatten()  # get drawable after scale
    floating = Gimp.edit_paste(bg_draw, False)  # False = don't paste-into
    Gimp.floating_sel_to_layer(floating)
    uav_layer = floating  # now a proper layer

    # ── 6. Scale UAV to target fraction of the output frame ──────────────────
    uw = uav_layer.get_width()
    uh = uav_layer.get_height()
    target_px = int(OUTPUT_SIZE * UAV_SCALE)
    factor = target_px / max(uw, uh)
    new_w = max(1, int(uw * factor))
    new_h = max(1, int(uh * factor))
    uav_layer.scale(new_w, new_h, False)

    # ── 7. Centre with random positional jitter ───────────────────────────────
    jx = int((random.random() - 0.5) * POS_JITTER * OUTPUT_SIZE)
    jy = int((random.random() - 0.5) * POS_JITTER * OUTPUT_SIZE)
    uav_layer.set_offsets((OUTPUT_SIZE - new_w) // 2 + jx, (OUTPUT_SIZE - new_h) // 2 + jy)

    # ── 8. Flatten and export ─────────────────────────────────────────────────
    os.makedirs(out_folder, exist_ok=True)
    uav_stem = os.path.splitext(os.path.basename(uav_path))[0]
    bg_cat = os.path.basename(os.path.dirname(bg_path))
    bg_stem = os.path.splitext(os.path.basename(bg_path))[0]
    out_name = "{}__on__{}.jpg".format(uav_stem, bg_cat + "_" + bg_stem)
    out_path = os.path.join(out_folder, out_name)

    saved = export_jpeg(bg_img, out_path)
    print("Saved: ", saved)

    # ── 9. Cleanup ────────────────────────────────────────────────────────────
    uav_img.delete()
    bg_img.delete()
    return saved


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

bg_files = collect_images(BG_FOLDER)
if not bg_files:
    raise RuntimeError(
        "No background images found!\n"
        "Run:  python scripts/download_backgrounds.py\n"
        "Looking in: " + BG_FOLDER
    )

if TEST_MODE:
    uav_path = UAV_IMAGE
else:
    uav_files = collect_images(UAV_FOLDER)
    if not uav_files:
        raise RuntimeError("No UAV images found in: " + UAV_FOLDER)
    uav_path = random.choice(uav_files)

bg_path = random.choice(bg_files)
out_path = composite_uav(uav_path, bg_path, OUT_FOLDER)
Gimp.message("Done!\n\nSaved to:\n" + out_path)
