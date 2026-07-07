/**
 * UAV Background Compositor
 * =========================
 * Photoshop ExtendScript (JSX) — compatible with Photoshop CC 2019+
 *
 * Opens a rendered UAV image, isolates the UAV using AI Select Subject,
 * and composites it onto a randomly chosen real-world background image.
 *
 * HOW TO RUN:
 *   Photoshop → File → Scripts → Browse → select this .jsx file
 *   OR: File → Scripts → Script Events Manager for automation
 *
 * PREREQUISITES:
 *   1. Run scripts/download_backgrounds.py first to populate data/backgrounds/
 *   2. Photoshop CC 2019 or later (for Select Subject AI)
 *
 * CONFIG: Edit the paths in the CONFIG block below before running.
 */

// ─── CONFIG ──────────────────────────────────────────────────────────────────
var CONFIG = {
    // Folder containing rendered UAV images (any subdirectory works)
    uavFolder: "C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_color_mild_clean/enrollment",

    // Folder with real-world backgrounds (subfolders: forest, beach, clouds, ...)
    bgFolder: "C:/Users/tsa3/Desktop/TFG/protonet_uav/data/backgrounds",

    // Output folder for composited results
    outFolder: "C:/Users/tsa3/Desktop/TFG/protonet_uav/data/composited",

    // If true, pick a specific UAV image; if false, pick randomly
    testMode: true,
    testImage: "C:/Users/tsa3/Desktop/TFG/protonet_uav/data/uav_dataset_color_mild_clean/enrollment/mq-9_reaper/az000_el-45_noon_clear_enrollment_v00.jpg",

    // Output size
    outputWidth:  640,
    outputHeight: 640,

    // UAV scale on the background (fraction of background shorter side)
    // 0.35 = UAV occupies ~35% of the frame width — realistic overhead appearance
    uavScale: 0.40,

    // Random position jitter as fraction of background size (keeps UAV roughly centred)
    positionJitter: 0.15,

    // Shadow/blend settings
    blendMode: BlendMode.NORMAL,
    uavOpacity: 100,  // percent; lower for haze effect

    // Add a subtle drop shadow to ground the UAV
    addShadow: true,
    shadowOpacity: 60,
    shadowDistance: 8,
    shadowAngle: 130,
    shadowBlur: 12,
};
// ─────────────────────────────────────────────────────────────────────────────


// ─── UTILITIES ────────────────────────────────────────────────────────────────

/** Collect all jpg/png files recursively under a Folder */
function collectImages(folder) {
    var f = (folder instanceof Folder) ? folder : new Folder(folder);
    var results = [];
    var items = f.getFiles();
    for (var i = 0; i < items.length; i++) {
        var item = items[i];
        if (item instanceof Folder) {
            var sub = collectImages(item);
            for (var j = 0; j < sub.length; j++) results.push(sub[j]);
        } else if (item instanceof File) {
            var name = item.name.toLowerCase();
            if (name.match(/\.(jpg|jpeg|png|tif|tiff|bmp)$/)) {
                results.push(item);
            }
        }
    }
    return results;
}

/** Pick a random element from an array */
function randomPick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

/** Ensure a folder exists, create it if not */
function ensureFolder(path) {
    var f = new Folder(path);
    if (!f.exists) f.create();
    return f;
}

/** Run Select Subject via Action Manager (works CC 2019+) */
function runSelectSubject() {
    var idSelectSubject = stringIDToTypeID("selectSubject");
    var desc = new ActionDescriptor();
    desc.putBoolean(stringIDToTypeID("includeBackground"), false);
    executeAction(idSelectSubject, desc, DialogModes.NO);
}

/** Refine edge / Select and Mask to clean up fringe pixels */
function refineSelection() {
    // Expand by 1px, then contract by 2px to tighten around UAV edges
    // This removes sky fringe without losing detail
    var idIntersect = charIDToTypeID("Intr");
    
    // Contract selection by 1px to remove sky fringe
    try {
        var idContract = charIDToTypeID("Cntrc");
        var contractDesc = new ActionDescriptor();
        contractDesc.putUnitDouble(charIDToTypeID("By  "), charIDToTypeID("#Pxl"), 1);
        contractDesc.putBoolean(stringIDToTypeID("applyEffectAtCanvasBounds"), false);
        executeAction(idContract, contractDesc, DialogModes.NO);
    } catch(e) {}

    // Feather by 0.5px for a natural edge
    try {
        var idFeather = charIDToTypeID("Fthr");
        var featherDesc = new ActionDescriptor();
        featherDesc.putUnitDouble(charIDToTypeID("Rds "), charIDToTypeID("#Pxl"), 0.5);
        executeAction(idFeather, featherDesc, DialogModes.NO);
    } catch(e) {}
}

/** Add a drop shadow layer style to the active layer */
function addDropShadow(opacity, angle, distance, blur) {
    var idsetd = charIDToTypeID("setd");
    var desc = new ActionDescriptor();
    var idnull = charIDToTypeID("null");
    var ref = new ActionReference();
    ref.putProperty(charIDToTypeID("Prpr"), charIDToTypeID("Lefx"));
    ref.putEnumerated(charIDToTypeID("Lyr "), charIDToTypeID("Ordn"), charIDToTypeID("Trgt"));
    desc.putReference(idnull, ref);
    var fxDesc = new ActionDescriptor();
    var shadowDesc = new ActionDescriptor();
    shadowDesc.putBoolean(charIDToTypeID("enab"), true);
    shadowDesc.putUnitDouble(charIDToTypeID("Opct"), charIDToTypeID("#Prc"), opacity);
    shadowDesc.putUnitDouble(charIDToTypeID("lagl"), charIDToTypeID("#Ang"), angle);
    shadowDesc.putUnitDouble(charIDToTypeID("Dstn"), charIDToTypeID("#Pxl"), distance);
    shadowDesc.putUnitDouble(charIDToTypeID("blur"), charIDToTypeID("#Pxl"), blur);
    shadowDesc.putBoolean(charIDToTypeID("uglg"), true);
    fxDesc.putObject(charIDToTypeID("DrSh"), charIDToTypeID("DrSh"), shadowDesc);
    desc.putObject(charIDToTypeID("T   "), charIDToTypeID("Lefx"), fxDesc);
    executeAction(idsetd, desc, DialogModes.NO);
}

// ─── MAIN ────────────────────────────────────────────────────────────────────

function main() {

    // ── 1. Collect background images ──────────────────────────────────────────
    var bgFiles = collectImages(new Folder(CONFIG.bgFolder));
    if (bgFiles.length === 0) {
        alert("No background images found in:\n" + CONFIG.bgFolder +
              "\n\nRun scripts/download_backgrounds.py first.");
        return;
    }

    // ── 2. Pick the UAV source image ──────────────────────────────────────────
    var uavFile;
    if (CONFIG.testMode) {
        uavFile = new File(CONFIG.testImage);
        if (!uavFile.exists) {
            alert("Test UAV image not found:\n" + CONFIG.testImage);
            return;
        }
    } else {
        var uavFiles = collectImages(new Folder(CONFIG.uavFolder));
        if (uavFiles.length === 0) {
            alert("No UAV images found in:\n" + CONFIG.uavFolder);
            return;
        }
        uavFile = randomPick(uavFiles);
    }

    var bgFile = randomPick(bgFiles);
    $.writeln("UAV:        " + uavFile.fsName);
    $.writeln("Background: " + bgFile.fsName);

    // ── 3. Open UAV image ────────────────────────────────────────────────────
    var uavDoc = open(uavFile);

    // Flatten and convert to RGB (in case it was indexed or CMYK)
    uavDoc.flatten();
    uavDoc.changeMode(ChangeMode.RGB);

    // ── 4. Select Subject (AI) ───────────────────────────────────────────────
    uavDoc.activeLayer = uavDoc.layers[0];
    try {
        runSelectSubject();
    } catch(e) {
        alert("Select Subject failed — requires Photoshop CC 2019+.\nError: " + e.message);
        uavDoc.close(SaveOptions.DONOTSAVECHANGES);
        return;
    }

    // Refine edge (tighten, small feather)
    refineSelection();

    // ── 5. Copy UAV region to clipboard ──────────────────────────────────────
    // Selection from selectSubject = the UAV. Copy it.
    uavDoc.selection.copy(true);   // true = copy merged (flattened look)

    // ── 6. Open background ───────────────────────────────────────────────────
    var bgDoc = open(bgFile);
    bgDoc.flatten();
    bgDoc.changeMode(ChangeMode.RGB);

    // Resize background to output size
    bgDoc.resizeImage(
        UnitValue(CONFIG.outputWidth,  "px"),
        UnitValue(CONFIG.outputHeight, "px"),
        72, ResampleMethod.BICUBICSHARPER
    );

    // ── 7. Paste UAV onto background ─────────────────────────────────────────
    app.activeDocument = bgDoc;
    var uavLayer = bgDoc.paste();  // returns the new layer
    uavLayer.name = "UAV";

    // ── 8. Scale UAV to target size ───────────────────────────────────────────
    var targetPx = Math.min(CONFIG.outputWidth, CONFIG.outputHeight) * CONFIG.uavScale;

    // Compute current UAV bounding box
    var bounds = uavLayer.bounds;  // [left, top, right, bottom] as UnitValues
    var curW = bounds[2].value - bounds[0].value;
    var curH = bounds[3].value - bounds[1].value;
    var curMax = Math.max(curW, curH);
    var scalePct = (targetPx / curMax) * 100;

    uavLayer.resize(scalePct, scalePct, AnchorPosition.MIDDLECENTER);

    // ── 9. Randomise position (centered with jitter) ─────────────────────────
    var jitterX = (Math.random() - 0.5) * CONFIG.positionJitter * CONFIG.outputWidth;
    var jitterY = (Math.random() - 0.5) * CONFIG.positionJitter * CONFIG.outputHeight;

    // Re-read bounds after resize
    bounds = uavLayer.bounds;
    var cx = (bounds[0].value + bounds[2].value) / 2;
    var cy = (bounds[1].value + bounds[3].value) / 2;
    var targetCX = CONFIG.outputWidth  / 2 + jitterX;
    var targetCY = CONFIG.outputHeight / 2 + jitterY;

    uavLayer.translate(
        UnitValue(targetCX - cx, "px"),
        UnitValue(targetCY - cy, "px")
    );

    // ── 10. Blend / opacity ──────────────────────────────────────────────────
    uavLayer.blendMode = CONFIG.blendMode;
    uavLayer.opacity   = CONFIG.uavOpacity;

    // ── 11. Drop shadow ──────────────────────────────────────────────────────
    if (CONFIG.addShadow) {
        app.activeDocument = bgDoc;
        bgDoc.activeLayer = uavLayer;
        addDropShadow(
            CONFIG.shadowOpacity,
            CONFIG.shadowAngle,
            CONFIG.shadowDistance,
            CONFIG.shadowBlur
        );
    }

    // ── 12. Flatten & save ───────────────────────────────────────────────────
    ensureFolder(CONFIG.outFolder);

    var uavName  = decodeURI(uavFile.name).replace(/\.[^.]+$/, "");
    var bgName   = decodeURI(bgFile.parent.name) + "_" +
                   decodeURI(bgFile.name).replace(/\.[^.]+$/, "");
    var outName  = uavName + "__on__" + bgName + ".jpg";
    var outFile  = new File(CONFIG.outFolder + "/" + outName);

    bgDoc.flatten();

    var jpgOpts = new JPEGSaveOptions();
    jpgOpts.quality = 11;  // 0-12; 11 = high quality
    bgDoc.saveAs(outFile, jpgOpts, true, Extension.LOWERCASE);

    $.writeln("Saved: " + outFile.fsName);
    alert("Done!\n\nComposited image saved to:\n" + outFile.fsName);

    // Close source docs without saving
    bgDoc.close(SaveOptions.DONOTSAVECHANGES);
    uavDoc.close(SaveOptions.DONOTSAVECHANGES);
}

// ─── ENTRY POINT ─────────────────────────────────────────────────────────────
try {
    main();
} catch (err) {
    alert("Script error:\n" + err.message + "\n(line " + err.line + ")");
}
