"""Download category-specific real-world backgrounds from internet search.

Primary source: Flickr public feed tag search (no API key).
Fallback source: Wikimedia Commons search.

Run:
  python scripts/download_backgrounds.py --count 10 --replace
"""

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
FLICKR_FEED = "https://www.flickr.com/services/feeds/photos_public.gne"
HEADERS = {"User-Agent": "uav-background-downloader/1.1 (research; no-api-key mode)"}

CATEGORY_QUERIES = {
    "beach": ["beach,coast,shore,landscape", "tropical,beach,sea", "coastline,beach"],
    "forest": ["forest,trees,landscape", "rainforest,canopy", "pine,forest,nature"],
    "clouds": ["clouds,sky,landscape", "cloudscape,sky", "cumulus,sky"],
    "countryside": ["countryside,fields,landscape", "rural,farmland", "rolling,hills,landscape"],
    "desert": ["desert,dunes,landscape", "arid,desert", "sahara,dunes"],
    "urban": ["city,skyline,landscape", "urban,cityscape", "downtown,city,skyline"],
}

CATEGORY_INCLUDE = {
    "beach": {"beach", "coast", "shore", "sea", "ocean", "coastline", "sand"},
    "forest": {"forest", "rainforest", "woods", "woodland", "trees", "canopy", "pine"},
    "clouds": {"cloud", "clouds", "cloudscape", "sky", "cumulus", "stratus", "cirrus"},
    "countryside": {"countryside", "rural", "farm", "farmland", "field", "fields", "hills"},
    "desert": {"desert", "dune", "dunes", "sahara", "arid", "wadi", "sand"},
    "urban": {"city", "urban", "cityscape", "skyline", "downtown", "street", "buildings"},
}

GLOBAL_EXCLUDE = {
    "cat",
    "cats",
    "kitten",
    "dog",
    "dogs",
    "puppy",
    "bird",
    "birds",
    "eagle",
    "pigeon",
    "animal",
    "animals",
    "insect",
    "insects",
    "butterfly",
    "moth",
    "damselfly",
    "dragonfly",
    "flower",
    "flowers",
    "portrait",
    "selfie",
    "person",
    "people",
    "face",
    "wedding",
    "food",
    "car",
    "cars",
    "toy",
    "logo",
    "poster",
    "drawing",
    "illustration",
    "artwork",
    "statue",
    "airplane",
    "drone",
    "uav",
}


def request_json(url: str, retries: int = 5) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise


def build_flickr_variants(media_url: str) -> list[str]:
    """Flickr feed gives `_m` size URL. Try larger variants first."""
    variants = []
    if "_m." in media_url:
        variants.append(media_url.replace("_m.", "_b."))
        variants.append(media_url.replace("_m.", "_c."))
        variants.append(media_url.replace("_m.", "_z."))
        variants.append(media_url)
    else:
        variants.append(media_url)
    return variants


def flickr_search_files(tags: str) -> list[dict]:
    params = {
        "format": "json",
        "nojsoncallback": "1",
        "lang": "en-us",
        "tagmode": "any",
        "tags": tags,
    }
    url = f"{FLICKR_FEED}?{urllib.parse.urlencode(params)}"
    data = request_json(url)

    items = []
    for it in data.get("items", []):
        media = it.get("media", {})
        media_url = media.get("m")
        if not media_url:
            continue
        items.append(
            {
                "title": it.get("title", "untitled"),
                "meta": (it.get("title", "") + " " + it.get("tags", "")).lower(),
                "urls": build_flickr_variants(media_url),
            }
        )
    return items


def commons_search_files(query: str, max_results: int = 40) -> list[dict]:
    """Fallback search in Wikimedia Commons File namespace."""
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": str(max_results),
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": "1920",
        "format": "json",
    }
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    data = request_json(url)

    out = []
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        title = page.get("title", "")
        info = (page.get("imageinfo") or [{}])[0]
        img_url = info.get("thumburl") or info.get("url")
        mime = (info.get("mime") or "").lower()
        if not img_url or not mime.startswith("image/"):
            continue
        if mime in {"image/svg+xml", "image/gif"}:
            continue
        out.append({"title": title, "meta": title.lower(), "urls": [img_url]})
    return out


def is_relevant(category: str, meta_text: str) -> bool:
    tokens = set(meta_text.replace("_", " ").replace("-", " ").split())
    include = CATEGORY_INCLUDE[category]

    # Reject obvious unrelated content.
    if tokens.intersection(GLOBAL_EXCLUDE):
        return False

    # Require at least one category-defining keyword.
    return bool(tokens.intersection(include))


def is_safe_background(meta_text: str) -> bool:
    """Relaxed filter for top-up: reject obvious non-background content only."""
    tokens = set(meta_text.replace("_", " ").replace("-", " ").split())
    return not bool(tokens.intersection(GLOBAL_EXCLUDE))


def download_binary(url: str, out_path: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = resp.read()
        if len(data) < 20_000:
            return False
        out_path.write_bytes(data)
        return True
    except Exception:
        return False


def clean_existing_images(folder: Path):
    for file in folder.glob("*.*"):
        if file.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            file.unlink(missing_ok=True)


def download_backgrounds(out_root: str, count_per_category: int, replace: bool = False):
    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    total_downloaded = 0
    total_failed = 0

    for category, queries in CATEGORY_QUERIES.items():
        category_dir = out_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        if replace:
            clean_existing_images(category_dir)

        print(f"\n[{category}] Searching internet images by category tags...")

        candidates = []
        seen_url = set()

        # Primary source: Flickr tag search (category-specific)
        for tags in queries:
            found = flickr_search_files(tags)
            print(f"  Flickr tags '{tags}' -> {len(found)} candidates")
            for item in found:
                key = item["urls"][0]
                if key not in seen_url:
                    seen_url.add(key)
                    candidates.append(item)

        # Fallback source: Wikimedia category query if the raw pool is tiny.
        if len(candidates) < count_per_category:
            for tags in queries:
                query = tags.replace(",", " ")
                found = commons_search_files(query, max_results=30)
                print(f"  Commons query '{query}' -> {len(found)} candidates")
                for item in found:
                    key = item["urls"][0]
                    if key not in seen_url:
                        seen_url.add(key)
                        candidates.append(item)

        filtered_candidates = [c for c in candidates if is_relevant(category, c.get("meta", ""))]

        # If strict filter leaves too few, supplement from Wikimedia and filter again.
        if len(filtered_candidates) < count_per_category:
            needed = count_per_category - len(filtered_candidates)
            for tags in queries:
                query = tags.replace(",", " ")
                found = commons_search_files(query, max_results=50)
                for item in found:
                    key = item["urls"][0]
                    if key in seen_url:
                        continue
                    seen_url.add(key)
                    if is_relevant(category, item.get("meta", "")):
                        filtered_candidates.append(item)
                        if len(filtered_candidates) >= count_per_category:
                            break
                if len(filtered_candidates) >= count_per_category:
                    break
            if needed > 0:
                print("  Added Wikimedia fallback candidates to fill shortage.")

        print(f"  Relevant candidates after filtering: {len(filtered_candidates)}")

        downloaded = 0
        for item in filtered_candidates:
            if downloaded >= count_per_category:
                break

            # Try URL variants (for Flickr: large then medium)
            ext = ".jpg"
            for url in item["urls"]:
                suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
                if suffix in {".jpg", ".jpeg", ".png"}:
                    ext = ".jpg" if suffix == ".jpeg" else suffix
                dest = category_dir / f"{category}_{downloaded + 1:03d}{ext}"
                if download_binary(url, dest):
                    downloaded += 1
                    total_downloaded += 1
                    print(
                        f"  [{downloaded:02d}/{count_per_category}] {dest.name} <- {item['title']}"
                    )
                    break
            time.sleep(0.15)

        # Final top-up pass: if still short, accept broader but safe candidates.
        if downloaded < count_per_category:
            topup_candidates = []
            for tags in queries:
                query = tags.replace(",", " ")
                for item in commons_search_files(query + " landscape", max_results=80):
                    key = item["urls"][0]
                    if key in seen_url:
                        continue
                    seen_url.add(key)
                    if is_safe_background(item.get("meta", "")):
                        topup_candidates.append(item)

            for item in topup_candidates:
                if downloaded >= count_per_category:
                    break
                ext = ".jpg"
                for url in item["urls"]:
                    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
                    if suffix in {".jpg", ".jpeg", ".png"}:
                        ext = ".jpg" if suffix == ".jpeg" else suffix
                    dest = category_dir / f"{category}_{downloaded + 1:03d}{ext}"
                    if download_binary(url, dest):
                        downloaded += 1
                        total_downloaded += 1
                        print(
                            f"  [{downloaded:02d}/{count_per_category}] {dest.name}"
                            f" <- {item['title']} (top-up)"
                        )
                        break
                time.sleep(0.15)

        if downloaded < count_per_category:
            missing = count_per_category - downloaded
            total_failed += missing
            print(f"  Only downloaded {downloaded}/{count_per_category} for '{category}'.")

    print(f"\nDone. Downloaded: {total_downloaded}, failed: {total_failed}")
    print(f"Saved to: {out_dir.resolve()}")
    return total_downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download category-specific real-world backgrounds"
    )
    parser.add_argument("--out", default="data/backgrounds", help="Output root folder")
    parser.add_argument("--count", type=int, default=10, help="Images per category")
    parser.add_argument(
        "--replace", action="store_true", help="Delete old images in each category first"
    )
    args = parser.parse_args()

    n = download_backgrounds(args.out, count_per_category=max(1, args.count), replace=args.replace)
    if n == 0:
        print("\nNo images were downloaded. Try running again in a few minutes.")
