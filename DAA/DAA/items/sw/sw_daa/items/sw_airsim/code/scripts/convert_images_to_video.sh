#!/bin/bash

# Convert PNG images from AirSim recordings to MP4 videos
# Usage: ./convert_images_to_video.sh [path_to_records_or_code] [output_videos_path]

# If first argument is not defined, use ./records by default.
INPUT_PATH="${1:-./records}"
# If path exists and is a directory, and the last part of the path is "records", use it directly. Otherwise,
# append "records" to the path.
if [ -d "$INPUT_PATH" ] && [ "$(basename "$INPUT_PATH")" = "records" ]; then
    RECORDS_DIR="$INPUT_PATH"
else
    RECORDS_DIR="$INPUT_PATH/records"
fi

# Second argument is output directory for videos, default to ./video_records
OUTPUT_DIR="${2:-./video_records}"
# If path does not exist or is not a directory, raise an error.
if [ ! -d "$RECORDS_DIR" ]; then
    echo "Error: Records folder not found: $RECORDS_DIR"
    exit 1
fi

# If ffmpeg does not exists in path, it prints an error and exits.
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffmpeg is not installed."
    echo "Install it with: sudo apt update && sudo apt install -y ffmpeg"
    exit 1
fi

# Creates output directory if it does not exist.
mkdir -p "$OUTPUT_DIR"
# If output directory is not writable, raise an error.
if [ ! -w "$OUTPUT_DIR" ]; then
    echo "Error: No write permissions for $OUTPUT_DIR"
    exit 1
fi

# Search for all recording folders (e.g., 2026-05-08-09-54-42)
for recording_dir in "$RECORDS_DIR"/*/; do
    # If the directory contains an "images" folder
    if [ -d "${recording_dir}images" ]; then
        # Stores directory name
        recording_name=$(basename "$recording_dir")
        echo "Converting recording: $recording_name"
        
        # Count images to verify they exist. If no PNG images are found, print an error and skip to the next recording.
        image_count=$(ls -1 "${recording_dir}images"/*.png 2>/dev/null | wc -l)
        if [ $image_count -eq 0 ]; then
            echo "Error: No PNG images found in ${recording_dir}images"
            continue
        fi
        
        echo "Images found: $image_count"
        
        # Create MP4 video with ffmpeg in writable output folder
        output_video="${OUTPUT_DIR}/${recording_name}_video.mp4"
        
        echo "Generating video: $output_video"

        # 30 fps in output video, uploads PNGs in natural order, uses libx264 codec, yuv420p pixel format for compatibility,
        # crf 23 for good quality with reasonable file size, overwrites output if it already exists, and only shows errors in logs.
        ffmpeg -framerate 30 \
               -pattern_type glob -i "${recording_dir}images/*.png" \
               -c:v libx264 \
               -pix_fmt yuv420p \
               -crf 23 \
               "$output_video" \
               -y -loglevel error
        
        # Check if video was created successfully
        if [ -f "$output_video" ]; then
            echo "Video created successfully"
            ls -lh "$output_video"
        else
            echo "Error creating video"
            echo "Debugging: check if there are valid PNGs in ${recording_dir}images"
        fi
    fi
done

echo "Conversion completed."
