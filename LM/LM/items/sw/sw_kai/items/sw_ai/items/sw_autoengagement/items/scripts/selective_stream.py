import os
import io
from remotezip import RemoteZip
from PIL import Image

# Complete list of all 12 flight sorties from Science Data Bank
urls = [
    "https://download.scidb.cn/download?fileId=9282ae0baf2816c72bfff8164d735c83&path=/V4/Fixed-wing-UAV-A.zip&fileName=Fixed-wing-UAV-A.zip",
    "https://download.scidb.cn/download?fileId=540ca62c76a19725f728dc1c3caf2fa6&path=/V4/Fixed-wing-UAV-A'.zip&fileName=Fixed-wing-UAV-A'.zip",
    "https://download.scidb.cn/download?fileId=3e4f6ea1c00086277d3cfa3394760c10&path=/V4/Fixed-wing-UAV-B.zip&fileName=Fixed-wing-UAV-B.zip",
    "https://download.scidb.cn/download?fileId=4d9c87d634036c1025626187a9cd39b4&path=/V4/Fixed-wing-UAV-B'.zip&fileName=Fixed-wing-UAV-B'.zip",
    "https://download.scidb.cn/download?fileId=d83105594fcda6c1289736dd9c1399be&path=/V4/Fixed-wing-UAV-C.zip&fileName=Fixed-wing-UAV-C.zip",
    "https://download.scidb.cn/download?fileId=2ee85e05571f3a3b8a36ad5ce334816c&path=/V4/Fixed-wing-UAV-C'.zip&fileName=Fixed-wing-UAV-C'.zip",
    "https://download.scidb.cn/download?fileId=8ab3c0618dbc1a8593b6b9a877984fb8&path=/V4/Fixed-wing-UAV-D.zip&fileName=Fixed-wing-UAV-D.zip",
    "https://download.scidb.cn/download?fileId=b3c7263efcd06b0b59f05bf20e5cdd94&path=/V4/Fixed-wing-UAV-D'.zip&fileName=Fixed-wing-UAV-D'.zip",
    "https://download.scidb.cn/download?fileId=7d4017b5b04aff2862959726bab02a50&path=/V4/Fixed-wing-UAV-E.zip&fileName=Fixed-wing-UAV-E.zip",
    "https://download.scidb.cn/download?fileId=5045a615b5ca84d3d834c1f4174c644f&path=/V4/Fixed-wing-UAV-E'.zip&fileName=Fixed-wing-UAV-E'.zip",
    "https://download.scidb.cn/download?fileId=685fe3af3ddacffa08eaee41b5665ffd&path=/V4/Fixed-wing-UAV-F.zip&fileName=Fixed-wing-UAV-F.zip",
    "https://download.scidb.cn/download?fileId=9439953f6b87ee79261c614f42f033ef&path=/V4/Fixed-wing-UAV-F'.zip&fileName=Fixed-wing-UAV-F'.zip"
]

OUTPUT_DIR = "./data/Bottom-Up_Zoom_Imgs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("[*] Starting self-verifying spaced-interval extraction...")

for url in urls:
    archive_name = url.split("fileName=")[-1]
    print(f"\n[+] Connecting to remote archive: {archive_name}")
    
    try:
        with RemoteZip(url) as rz:
            all_files = rz.namelist()
            
            # 1. Gather all files matching our exact folder target layout path criteria
            target_files = [
                f for f in all_files 
                if "bottom_up" in f.lower() and "zoom_imgs" in f.lower() and not f.endswith('/')
            ]
            
            if not target_files:
                print(f"    [-] No matching paths found. Skipping {archive_name}.")
                continue
            
            # Sort chronologically to maintain standard spatial positioning layouts
            target_files.sort()
            
            # 2. Build prioritized list using 10-step stride intervals
            strided_candidates = target_files[::10]
            
            # Build secondary backup list with all other images to fulfill the quota if corruption happens
            backup_candidates = [f for f in target_files if f not in strided_candidates]
            
            # Total search execution list: strided items first, backups second
            search_queue = strided_candidates + backup_candidates
            
            print(f"    [i] Found {len(target_files)} total assets. Stride candidates: {len(strided_candidates)}")
            print(f"    [*] Scanning for 20 clean, uncorrupted images...")
            
            uncorrupted_count = 0
            
            for file_info in search_queue:
                if uncorrupted_count >= 20:
                    break  # Quota filled successfully for this folder, advance to next zip
                
                try:
                    # Stream the precise file bytes from the remote zip directly into RAM buffer
                    img_bytes = rz.read(file_info)
                    
                    # Pass bytes into memory stream and verify file health via Pillow
                    with Image.open(io.BytesIO(img_bytes)) as img:
                        img.verify()  # Throws exception immediately if image header or payload is corrupted
                    
                    # If verification passes, manually map and write bytes to preserve folder paths
                    target_path = os.path.join(OUTPUT_DIR, file_info)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    with open(target_path, 'wb') as f_out:
                        f_out.write(img_bytes)
                        
                    uncorrupted_count += 1
                    print(f"        [{uncorrupted_count}/20] Validated & Extracted: {os.path.basename(file_info)}")
                    
                except (IOError, SyntaxError, Exception) as img_err:
                    # Gracefully catches broken zips, invalid headers, or truncated data streams
                    print(f"        [!] Skipped Corrupted Image: {os.path.basename(file_info)}")
                    continue
                    
            if uncorrupted_count < 20:
                print(f"    [!] Warning: Only found {uncorrupted_count} uncorrupted files in this folder archive.")
                
    except Exception as e:
        print(f"    [-] Network error reading zip archive context {archive_name}. Reason: {e}")

print("\n[+] Clean selective downsampling execution finalized.")