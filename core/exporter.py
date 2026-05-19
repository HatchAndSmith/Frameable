from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import tifffile


def export_tiff(image_bgr: np.ndarray, output_dir: Path,
                source_name: str, timestamp: float,
                keywords: Optional[list[str]] = None,
                crop_angle: float = 0.0,
                write_xmp: bool = False,
                write_angle: bool = False) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(source_name).stem
    total_sec = int(timestamp)
    mins = total_sec // 60
    secs = total_sec % 60
    ms = int((timestamp - total_sec) * 1000)
    ts_str = f"{mins:02d}m{secs:02d}s{ms:03d}ms"
    filename = f"{stem}_{ts_str}.tif"
    out_path = output_dir / filename

    # Ensure unique filename
    counter = 1
    while out_path.exists():
        out_path = output_dir / f"{stem}_{ts_str}_{counter}.tif"
        counter += 1

    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    # Scale 8-bit to 16-bit for maximum headroom
    image_16 = (image_rgb.astype(np.uint16) * 257)
    tifffile.imwrite(str(out_path), image_16, photometric="rgb", compression="deflate")

    if write_xmp:
        from core import xmp_writer
        xmp_writer.write(
            out_path,
            keywords=keywords or [],
            crop_angle=crop_angle,
            include_angle=write_angle,
        )

    return out_path
