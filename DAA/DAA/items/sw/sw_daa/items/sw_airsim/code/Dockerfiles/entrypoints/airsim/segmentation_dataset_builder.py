#!/usr/bin/env python3
from __future__ import annotations
import datetime
import json
import os
import re
import time

import airsim
import cv2
import numpy as np
from loguru import logger


class SegmentationDatasetBuilder:

    # SegmentationDatasetBuilder::_init_ initializes parameters, output paths and API client.
    def __init__(self):
        # AirSim capture settings
        self.vehicle_name = os.environ.get("AIRSIM_VEHICLE_NAME", "PX4")
        self.camera_name = os.environ.get("AIRSIM_CAMERA_NAME", "camera_forward")
        self.camera_name_d = os.environ.get("AIRSIM_CAMERA_NAME_D", "camera_forward_d")

        # Minimum area in pixels for an annotation to be included
        self.min_area_px = int(os.environ.get("MIN_AREA_PX", "5"))
        # Maximum saving rate in Hz (0 for no limit) - 1 frame per second - avoid generating too much data
        self.save_rate_hz = float(os.environ.get("SAVE_RATE_HZ", "1.0"))
        self.min_dt = (1.0 / self.save_rate_hz) if self.save_rate_hz > 0 else 0.0

        # Input categories for the model
        self.categories = [
            {"id": 1, "name": "airborne", "supercategory": "object"},
            {"id": 2, "name": "helicopter", "supercategory": "object"},
            {"id": 3, "name": "bird", "supercategory": "object"},
            {"id": 4, "name": "drone", "supercategory": "object"},
            {"id": 5, "name": "flock", "supercategory": "object"},
            {"id": 6, "name": "ufo", "supercategory": "object"},
            {"id": 7, "name": "airplane", "supercategory": "object"},
        ]

        # Obtain world name 
        world_name = os.environ.get("WORLD_NAME", "unknown_world") or "unknown_world"
        now = datetime.datetime.now()

        # Create folder in synthetic_data, with image folder and JSON file
        output_root = os.environ.get("OUTPUT_ROOT", "/root/synthetic_data")
        self.world_name = world_name
        self.sim_dir = output_root
        self.images_dir = os.path.join(self.sim_dir, "images")
        self.segmentation_dir = os.path.join(self.sim_dir, "segmentation")
        self.depth_dir = os.path.join(self.sim_dir, "depth")
        self.bbox_dir = os.path.join(self.sim_dir, "bbox")
        self.store_bbox = os.environ.get("STORE_BBOX", "false").strip().lower() in ("1", "true", "yes")
        self.json_flush_every_n_frames = 100         # Every 100 saved frames, persist buffer to current JSON.
        self.json_frames_per_file = 10000            # Every 10000 saved frames, a new JSON chunk file is created. 
        self.json_chunk_index = 1                    # N JSONs counter
        self.frames_in_current_json = 0              # Frames in current JSON counter
        self.frames_since_last_flush = 0             # Frames since last flush to disk counter
        self.current_json_path = self._build_json_chunk_path(self.json_chunk_index)
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.segmentation_dir, exist_ok=True)
        os.makedirs(self.depth_dir, exist_ok=True)
        if self.store_bbox:
            os.makedirs(self.bbox_dir, exist_ok=True)

        # Load color table used to decode segmentation BGR -> ID
        self.color_to_id = self._load_colors_table()

        # Initialize API client with retry logic (wait for AirSim to be ready)
        self.client = None
        max_retries = 60
        for attempt in range(max_retries):
            try:
                logger.info("GOING TO CONNECT TO AIRSIM API...")
                self.client = airsim.MultirotorClient()
                self.client.confirmConnection()
                logger.info(f"bbox_seg: AirSim connection established on attempt {attempt + 1}")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.info(f"bbox_seg: Waiting for AirSim... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    raise RuntimeError(f"Failed to connect to AirSim after {max_retries} attempts: {e}")

        # Read dynamic objects IDs configuration and map them to categories
        self.dynamic_ids_path = os.environ.get("DYNAMIC_IDS_PATH", "/root/settings/assets/dynamics_ids.json")
        self.dynamic_objects, self.target_ids = self._load_dynamic_ids_config(self.dynamic_ids_path)
        self.id_to_category = self._build_id_to_category_map(self.dynamic_objects)

        # Assign segmentation IDs from JSON configuration.
        try:
            for dynamic_obj in self.dynamic_objects:
                name = dynamic_obj["name"]
                seg_id = dynamic_obj["id"]
                success = self.client.simSetSegmentationObjectID(name, seg_id, False)
                logger.info(f"dynamic_ids: Object {name} now has color ID {seg_id}")
                logger.info(f"dynamic_ids: Operation successful: {success}")
        except Exception as e:
            logger.error(f"dynamic_ids: Error assigning segmentation IDs: {e}")
            exit(1)

        logger.info("dynamic_ids: All objects assigned successfully")

        # Attributes initialization
        self.next_image_id = 1
        self.next_ann_id = 1
        # General info for JSON
        self.dataset_info = {
            "description": "Synthetic data with AirSim",
            "version": "1.0",
            "year": now.year,
            "date_created": now.strftime("%d/%m/%Y"),
        }

        # Buffer to store dataset in memory before flushing to JSON file
        self.dataset_buffer = {
            "info": self.dataset_info,
            "images": [],
            "annotations": [],
            "categories": self.categories,
        }
        # Initialize first output JSON chunk with empty arrays (images, annotations) and info.
        self._initialize_output_json(self.current_json_path)

        # Info logs
        logger.info(f"bbox_seg: reading bgr+seg+depth from AirSim API camera='{self.camera_name}' vehicle='{self.vehicle_name}'")
        logger.info(f"bbox_seg: reading bgr+seg+depth from AirSim API camera_d='{self.camera_name_d}' vehicle='{self.vehicle_name}'")
        logger.info(f"bbox_seg: loaded dynamic IDs from {self.dynamic_ids_path}")
        logger.info(f"bbox_seg: target IDs={self.target_ids}")
        logger.info(f"bbox_seg: loaded colors_table entries={len(self.color_to_id)}")
        logger.info(f"bbox_seg: store_bbox={self.store_bbox}")
        logger.info(f"bbox_seg: writing dataset chunks to {self.sim_dir} "
              f"(flush every {self.json_flush_every_n_frames} frames, "
              f"new JSON every {self.json_frames_per_file} saved frames)")


    # SegmentationDatasetBuilder::_build_id_to_category_map builds a mapping from segmentation IDs to category IDs based on dynamic object names and category names.
    def _build_id_to_category_map(self, dynamic_objects: list) -> dict:
        # Some variations in object names to map
        alias_to_category = {
            "aircraft": "airplane",
            "plane": "airplane",
        }
        id_to_category = {}

        for dynamic_obj in dynamic_objects:
            object_name = re.sub(r"[^a-z]+", "", dynamic_obj["name"].lower())
            category_id = None

            for category in self.categories:
                category_name = category["name"]
                normalized_category_name = re.sub(r"[^a-z]+", "", category_name.lower())

                # For all the dynamic objects and all the categories, both current dynamic object and category names are normalized
                # If current dynamic object name is included in current category, category ID is assigned
                if normalized_category_name in object_name:
                    category_id = int(category["id"])
                    break

                # Or if the alias assigned to the dynamic object name is included in the category name, also is assigned
                for alias, alias_category_name in alias_to_category.items():
                    if alias_category_name == category_name and alias in object_name:
                        category_id = int(category["id"])
                        break

                if category_id is not None:
                    break

            if category_id is None:
                raise ValueError(
                    f"Unable to infer category for object '{dynamic_obj['name']}' with segmentation ID {dynamic_obj['id']}"
                )

            id_to_category[int(dynamic_obj["id"])] = category_id

        return id_to_category

    # SegmentationDatasetBuilder::_load_dynamic_ids_config reads dynamic object names and segmentation IDs from JSON.
    def _load_dynamic_ids_config(self, config_path: str) -> tuple[list[dict], list[int]]:
        if not os.path.isfile(config_path):
            raise FileNotFoundError(
                f"dynamic IDs config not found at {config_path}. "
                "Please create settings/algorithms/assets/dynamics_ids.json in the selected simulation."
            )

        # Opens and reads JSON file
        with open(config_path, "r") as f:
            raw = json.load(f)

        if isinstance(raw, dict) and "objects" in raw:
            entries = raw["objects"]
        else:
            raise ValueError(
                f"Unsupported dynamic IDs format in {config_path}. "
                "Use a list, an 'objects' key, or a name->id dictionary."
            )

        dynamic_objects = []
        for idx, entry in enumerate(entries):
            # Shall be a dictionary with name and ID
            if not isinstance(entry, dict):
                raise ValueError(f"Invalid entry #{idx} in {config_path}: expected object, got {type(entry).__name__}")

            if "name" not in entry or "id" not in entry:
                raise ValueError(f"Invalid entry #{idx} in {config_path}: each entry must contain 'name' and 'id'")

            # Stores name and ID
            name = str(entry["name"]).strip()
            seg_id = int(entry["id"])
            if not name:
                raise ValueError(f"Invalid entry #{idx} in {config_path}: 'name' cannot be empty")

            dynamic_objects.append({"name": name, "id": seg_id})

        if not dynamic_objects:
            raise ValueError(f"No dynamic objects found in {config_path}")

        # The target IDs are all the segmentation IDs found in the JSON file
        target_ids = sorted({obj["id"] for obj in dynamic_objects})
        logger.info(f"dynamic_ids: loaded {len(dynamic_objects)} object mappings from {config_path}")
        return dynamic_objects, target_ids

    # SegmentationDatasetBuilder::_build_json_chunk_path returns the path for a chunked JSON output file.
    def _build_json_chunk_path(self, chunk_index: int) -> str:
        if chunk_index <= 1:
            return os.path.join(self.sim_dir, f"synthetic_data_{self.world_name}.json")
        return os.path.join(self.sim_dir, f"synthetic_data_{self.world_name}_{chunk_index}.json")

    # SegmentationDatasetBuilder::_initialize_output_json creates an output JSON file with empty arrays.
    def _initialize_output_json(self, output_path: str):
        output = {
            "info": self.dataset_info,
            "images": [],
            "annotations": [],
            "categories": self.categories,
        }
        with open(output_path, "w") as f:
            json.dump(output, f, indent=4)

    # SegmentationDatasetBuilder::_flush_dataset_buffer appends RAM buffer to current JSON.
    def _flush_dataset_buffer(self):
        if not self.dataset_buffer["images"] and not self.dataset_buffer["annotations"]:
            return

        # If JSON exists, loads it. Otherwise, creates it.
        if os.path.isfile(self.current_json_path):
            with open(self.current_json_path, "r") as f:
                output = json.load(f)
        else:
            output = {
                "info": self.dataset_info,
                "images": [],
                "annotations": [],
                "categories": self.categories,
            }

        output["images"].extend(self.dataset_buffer["images"])
        output["annotations"].extend(self.dataset_buffer["annotations"])

        with open(self.current_json_path, "w") as f:
            json.dump(output, f, indent=4)

        self.dataset_buffer["images"].clear()
        self.dataset_buffer["annotations"].clear()
        self.frames_since_last_flush = 0

    # SegmentationDatasetBuilder::_rotate_json_file switches to the next JSON chunk.
    def _rotate_json_file(self):
        self.json_chunk_index += 1
        self.frames_in_current_json = 0
        self.current_json_path = self._build_json_chunk_path(self.json_chunk_index)
        self._initialize_output_json(self.current_json_path)

    # SegmentationDatasetBuilder::_load_colors_table loads colors_table.json as { (r,g,b): id }
    def _load_colors_table(self) -> dict[tuple[int, int, int], int]:
        table_path = "/root/colors_table.json"
        # If file does not exist, raise an error
        if not os.path.isfile(table_path):
            raise FileNotFoundError(f"colors_table.json not found at {table_path}")

        # Stores file as a dictionary
        with open(table_path, "r") as f:
            raw = json.load(f)

        logger.info(f"bbox_seg: colors_table.json raw entries: {len(raw)}")

        # Creates output dictionary from color map to ID.
        # Store BGR tuples to be robust to channel order at runtime.
        color_to_id = {}
        for sid_str, bgr in raw.items():
            # If entry has not the right format, skip it
            if not isinstance(bgr, list) or len(bgr) != 3:
                logger.warning(f"bbox_seg: WARNING - Invalid format for ID {sid_str}: {bgr}")
                continue
            sid = int(sid_str)
            b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
            color_to_id[(b, g, r)] = sid

        logger.info(f"bbox_seg: colors table loaded from {table_path}")
        logger.info(f"bbox_seg: converted to {len(color_to_id)} (B,G,R)->ID mappings")
        
        # For debugging, uncomment
        # Print first 10 mappings for verification
        logger.debug(f"bbox_seg: sample mappings (first 10):")
        for i, ((b, g, r), sid) in enumerate(color_to_id.items()):
            if i >= 10:
                break
            logger.debug(f"  BGR({b:3d}, {g:3d}, {r:3d}) -> ID {sid}")
        
        return color_to_id

    # SegmentationDatasetBuilder::_get_id_for_color converts a 3-channel color to its corresponding segmentation ID
    def _get_id_for_color(self, color: list[int]) -> int | None:
        # If no 3-channel color is provided, returns None
        if color is None or len(color) != 3:
            return None
        # BGR
        b = int(color[0])
        g = int(color[1])
        r = int(color[2])

        return self.color_to_id.get((b, g, r), None)

    # SegmentationDatasetBuilder::_seg_to_id_matrix converts the segmentation image to a 2D matrix of IDs
    def _seg_to_id_matrix(self, seg_img: np.ndarray | None) -> np.ndarray | None:
        # If no segmentation image is provided, returns None
        if seg_img is None:
            return None

        # Indexed segmentation image to 2D matrix of IDs
        if seg_img.ndim == 2:
            logger.info("bbox_seg: segmentation is mono8 (indexed)")
            return seg_img.astype(np.int32)

        # 3-channel image: decode each BGR color using colors_table.json
        if seg_img.ndim == 3 and seg_img.shape[2] == 3:
            h, w = seg_img.shape[:2]
            # Creates matrix to store resulting segmentation IDs
            seg_ids = np.zeros((h, w), dtype=np.int32)

            # Build mapping only for colors present in this frame
            flat_bgr = seg_img.reshape(-1, 3)
            unique_colors = np.unique(flat_bgr, axis=0)

            # Print all unique BGR colors found with their IDs
            # The two commented prints -> print unique_colors and BGR to corresponding ID. Useful for debbuging segmentation color issues.
            # Change table of colors in consequence (as the one given by AirSim differs from the reals one)
            logger.debug(f"bbox_seg: Found {len(unique_colors)} unique BGR colors in segmentation image:")
            for bgr in unique_colors:
                sid = self._get_id_for_color(bgr)
                # Skip pure black (background)
                if not np.array_equal(bgr, [0, 0, 0]):
                    id_str = f"ID {sid}" if sid is not None else "ID None"
                    logger.debug(f"  BGR({int(bgr[0]):3d}, {int(bgr[1]):3d}, {int(bgr[2]):3d}) -> {id_str}")

            for bgr in unique_colors:
                # For each unique BGR color, obtains the corresponding segmentation ID
                sid = self._get_id_for_color(bgr)
                if sid is None:
                    continue
                # If it exists, it creates a mask for all pixels with this BGR color
                mask = (seg_img[:, :, 0] == bgr[0]) & (seg_img[:, :, 1] == bgr[1]) & (seg_img[:, :, 2] == bgr[2])
                # Stores ID in the matrix
                seg_ids[mask] = sid

            return seg_ids

        return None

    # SegmentationDatasetBuilder::_capture_pair captures a synchronized tuple (Scene + Segmentation + Depth) from AirSim API
    def _capture_pair(self) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        # Requested the three images from AirSim API
        responses = self.client.simGetImages([
            airsim.ImageRequest(self.camera_name, airsim.ImageType.Scene, False, False),
            airsim.ImageRequest(self.camera_name, airsim.ImageType.Segmentation, False, False),
            airsim.ImageRequest(self.camera_name_d, airsim.ImageType.DepthPerspective, True, False)
        ], vehicle_name=self.vehicle_name)

        # No all the images have been received
        if responses is None or len(responses) < 3:
            return None, None, None

        # Stores them 
        scene = responses[0]
        seg = responses[1]
        depth = responses[2]
        # Invalid images have width or height equal to 0
        if scene.width == 0 or scene.height == 0 or seg.width == 0 or seg.height == 0 or depth.width == 0 or depth.height == 0:
            return None, None, None

        # Stores images as numpy arrays.
        try:
            bgr = np.frombuffer(scene.image_data_uint8, dtype=np.uint8).reshape(scene.height, scene.width, 3)
            seg_img = np.frombuffer(seg.image_data_uint8, dtype=np.uint8).reshape(seg.height, seg.width, 3)
            depth_m = np.array(depth.image_data_float, dtype=np.float32).reshape(depth.height, depth.width)
            return bgr, seg_img, depth_m
        except Exception as e:
            logger.error(f"bbox_seg: Error converting image data: {e}")
            return None, None, None


    # SegmentationDatasetBuilder::_process_frame processes one frame from AirSim API.
    def _process_frame(self) -> float:
        frame_start = time.perf_counter()
    

        # Captures from API
        bgr, seg, depth_m = self._capture_pair()
        if bgr is None or seg is None or depth_m is None:
            return time.perf_counter() - frame_start

        # Stores height and width of segmentation and BGR images, and calculates the scaling factors between them
        seg_h, seg_w = seg.shape[0], seg.shape[1]
        bgr_h, bgr_w = bgr.shape[0], bgr.shape[1]
        scale_x = float(bgr_w) / float(seg_w)
        scale_y = float(bgr_h) / float(seg_h)

        # Converts segmentation image to 2D matrix of IDs.
        seg_ids = self._seg_to_id_matrix(seg)
        if seg_ids is None:
            return time.perf_counter() - frame_start

        # --- Step 1: compute all annotations in memory for this frame ---
        frame_anns = []
        for object_id in self.target_ids:
            # Create a mask for the current ID (mask is 1 where the segmentation ID matches the current object_id)
            mask = seg_ids == int(object_id)
            # Obtains coords of the mask. If there are no pixels with the current ID, skip to the next ID
            ys, xs = np.where(mask)
            if ys.size == 0:
                continue

            # For computing the bounding box
            x_min = int(xs.min())
            x_max = int(xs.max())
            y_min = int(ys.min())
            y_max = int(ys.max())
            width = int(x_max - x_min + 1)
            height = int(y_max - y_min + 1)
            area = float(width * height)

            # If area of the bbox is smaller than the minimum area, skip to the next ID
            if area < self.min_area_px:
                logger.info(f"bbox_seg: Object ID {object_id} area={area:.1f} < min_area_px={self.min_area_px}, skipped")
                continue

            # Convert results from segmentation coordinates to BGR coordinates.
            x_min_bgr = float(x_min) * scale_x
            y_min_bgr = float(y_min) * scale_y
            width_bgr = float(width) * scale_x
            height_bgr = float(height) * scale_y
            area_bgr = float(area) * scale_x * scale_y

            frame_anns.append({
                "category_id": int(self.id_to_category.get(int(object_id), 1)),
                "iscrowd": 0,
                "bbox": [x_min_bgr, y_min_bgr, width_bgr, height_bgr],
                "area": area_bgr,
            })

        # If no objects were detected in this frame, skip saving entirely
        if not frame_anns:
            return time.perf_counter() - frame_start

        # --- Step 2: assign IDs and file paths ---
        image_id = self.next_image_id
        self.next_image_id += 1
        image_file = f"{image_id}.png"
        image_rel_path = f"images/{image_file}"
        image_abs_path = os.path.join(self.images_dir, image_file)
        seg_abs_path = os.path.join(self.segmentation_dir, image_file)
        depth_abs_path = os.path.join(self.depth_dir, image_file)
        bbox_abs_path = os.path.join(self.bbox_dir, image_file) if self.store_bbox else None

        # --- Step 3: save images (for dataset consumers), segmentation and depth images to disk ---
        cv2.imwrite(image_abs_path, bgr)
        cv2.imwrite(seg_abs_path, seg)

        # Save depth in millimeters as uint16 PNG (0 means invalid/non-finite).
        depth_mm = np.where(np.isfinite(depth_m), depth_m * 1000.0, 0.0)
        depth_mm = np.clip(depth_mm, 0.0, 65535.0).astype(np.uint16)
        cv2.imwrite(depth_abs_path, depth_mm)

        # --- Step 4: save bbox overlay image to disk (optional) ---
        if self.store_bbox:
            bgr_bbox = bgr.copy()
            for ann in frame_anns:
                bx, by, bw, bh = ann["bbox"]
                x1 = int(round(bx))
                y1 = int(round(by))
                x2 = int(round(bx + bw))
                y2 = int(round(by + bh))
                cv2.rectangle(bgr_bbox, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = str(ann["category_id"])
                cv2.putText(bgr_bbox, label, (x1, max(y1 - 4, 0)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.imwrite(bbox_abs_path, bgr_bbox)

        # --- Step 5: update dataset in memory and write JSON ---
        self.dataset_buffer["images"].append({
            "id": image_id,
            "width": bgr_w,
            "height": bgr_h,
            "file_name": image_rel_path,
            "date_captured": datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        })
        for ann in frame_anns:
            ann_out = {
                "id": self.next_ann_id,
                "category_id": ann["category_id"],
                "iscrowd": ann["iscrowd"],
                "image_id": image_id,
                "area": ann["area"],
                "bbox": ann["bbox"],
            }
            self.dataset_buffer["annotations"].append(ann_out)
            self.next_ann_id += 1

        # Persist periodically and rotate file every N saved frames.
        self.frames_in_current_json += 1
        self.frames_since_last_flush += 1

        should_rotate = self.frames_in_current_json >= self.json_frames_per_file
        should_flush = self.frames_since_last_flush >= self.json_flush_every_n_frames or should_rotate

        if should_flush:
            self._flush_dataset_buffer()
        if should_rotate:
            self._rotate_json_file()
        return time.perf_counter() - frame_start

    # SegmentationDatasetBuilder::run starts the main loop to capture frames from AirSim API and process them.
    def run(self):
        logger.info("bbox_seg: starting AirSim API capture loop")
        try:
            while True:
                elapsed_time_frame = self._process_frame()
                if self.min_dt > 0.0:
                    sleep_time = self.min_dt - elapsed_time_frame
                    if sleep_time > 0.0:
                        time.sleep(sleep_time)
        finally:
            self._flush_dataset_buffer()


# __main__ initializes the ROS node, creates an instance of the class and starts the ROS loop
if __name__ == "__main__":
    builder = SegmentationDatasetBuilder()
    builder.run()
