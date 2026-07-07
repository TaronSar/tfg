import cv2

import argparse
from pathlib import Path

def extract_frames(video_path: Path, output_folder: Path, every_sec: float,
                   max_frames: int | None = None, image_ext: str = "jpg",
                   overwrite: bool = False) -> list[Path]:
    if not video_path.exists():
        raise SystemExit(f"Video file not found: {video_path}")

    output_folder.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for old_frame in output_folder.glob(f"frame_*.{image_ext}"):
            old_frame.unlink()
    existing_indices = []
    for frame in output_folder.glob(f"frame_*.{image_ext}"):
        try:
            existing_indices.append(int(frame.stem.removeprefix("frame_")))
        except ValueError:
            continue
    start_index = max(existing_indices, default=-1) + 1

    cap = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
    if not cap.isOpened():
        cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"OpenCV could not decode video file: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, int(round(fps * every_sec)))
    saved_paths = []
    frame_idx = 0
    saved_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % frame_interval == 0:
            output_path = output_folder / f"frame_{start_index + saved_count:05d}.{image_ext}"
            cv2.imwrite(str(output_path), frame)
            saved_paths.append(output_path)
            saved_count += 1
            if max_frames is not None and saved_count >= max_frames:
                break

        frame_idx += 1

    cap.release()
    print(f"video={video_path}")
    print(f"fps={fps:.2f}")
    print(f"every_sec={every_sec}")
    print(f"frame_interval={frame_interval}")
    print(f"start_index={start_index}")
    print(f"saved={len(saved_paths)}")
    print(f"output={output_folder}")
    return saved_paths

def main():
    parser = argparse.ArgumentParser(description="Extract preview frames from a video.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--every_sec", type=float, default=0.5,
                        help="Save one frame every N seconds.")
    parser.add_argument("--max_frames", type=int, default=40)
    parser.add_argument("--image_ext", choices=["jpg", "png"], default="jpg")
    parser.add_argument("--overwrite", action="store_true",
                        help="Delete existing frame_*.jpg/png files before extracting.")
    args = parser.parse_args()

    extract_frames(
        video_path=Path(args.video),
        output_folder=Path(args.output),
        every_sec=args.every_sec,
        max_frames=args.max_frames,
        image_ext=args.image_ext,
        overwrite=args.overwrite,
    )

if __name__ == "__main__":
    main()
