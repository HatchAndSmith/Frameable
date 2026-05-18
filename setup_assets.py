"""
Run this once after cloning to download font files and regenerate icons.

  python setup_assets.py

Requires: pip install pillow
"""

import sys
import urllib.request
from pathlib import Path

FONTS = {
    "IBMPlexMono-Regular.ttf": (
        "https://cdn.jsdelivr.net/npm/@ibm/plex/IBM-Plex-Mono/fonts/complete/ttf/"
        "IBMPlexMono-Regular.ttf"
    ),
    "IBMPlexMono-Medium.ttf": (
        "https://cdn.jsdelivr.net/npm/@ibm/plex/IBM-Plex-Mono/fonts/complete/ttf/"
        "IBMPlexMono-Medium.ttf"
    ),
}


def download_fonts():
    dest = Path("assets/fonts")
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in FONTS.items():
        out = dest / name
        if out.exists():
            print(f"  {name} already present, skipping.")
            continue
        print(f"  Downloading {name}...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, out)
            print(f"{out.stat().st_size // 1024} KB")
        except Exception as e:
            print(f"FAILED ({e})")
            print(f"  Download manually from: {url}")


def generate_icons():
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  Pillow not installed — run: pip install pillow")
        return

    BG     = (28,  28,  28,  255)
    ORANGE = (232, 96,  28,  255)
    SURFACE= (42,  42,  42,  255)

    def make(size):
        img = Image.new("RGBA", (size, size), BG)
        d   = ImageDraw.Draw(img)
        m   = max(1, int(size * 0.14))
        lw  = max(1, size // 80)
        bl  = max(2, int(size * 0.13))
        bw  = max(1, size // 42)

        d.rectangle([m, m, size-m-1, size-m-1], outline=ORANGE, width=lw)
        for (cx, cy), (dx, dy) in zip(
            [(m,m),(size-m-1,m),(m,size-m-1),(size-m-1,size-m-1)],
            [(1,1),(-1,1),(1,-1),(-1,-1)]
        ):
            d.line([(cx, cy), (cx+dx*bl, cy)], fill=ORANGE, width=bw)
            d.line([(cx, cy), (cx, cy+dy*bl)], fill=ORANGE, width=bw)

        pad  = int(size * 0.30)
        cell = max(1, (size - 2*pad) // 3)
        gap  = max(1, size // 256)
        for r in range(3):
            for c in range(3):
                x0 = pad + c*cell + gap
                y0 = pad + r*cell + gap
                x1 = x0 + max(1, cell - gap*2 - 1)
                y1 = y0 + max(1, cell - gap*2 - 1)
                d.rectangle([x0, y0, x1, y1],
                             fill=ORANGE if (r == 1 and c == 1) else SURFACE)
        return img

    Path("assets").mkdir(exist_ok=True)
    make(1024).save("assets/icon.png")
    print("  assets/icon.png written")

    sizes  = [16, 32, 48, 64, 128, 256]
    frames = [make(s).convert("RGBA") for s in sizes]
    frames[0].save("assets/icon.ico", format="ICO",
                   sizes=[(s,s) for s in sizes], append_images=frames[1:])
    print("  assets/icon.ico written")

    # ICNS requires macOS iconutil — create the iconset folder for the user
    iconset = Path("assets/icon.iconset")
    iconset.mkdir(exist_ok=True)
    spec = [
        (16,"icon_16x16"), (32,"icon_16x16@2x"),
        (32,"icon_32x32"), (64,"icon_32x32@2x"),
        (128,"icon_128x128"), (256,"icon_128x128@2x"),
        (256,"icon_256x256"), (512,"icon_256x256@2x"),
        (512,"icon_512x512"), (1024,"icon_512x512@2x"),
    ]
    for sz, nm in spec:
        make(sz).save(iconset / f"{nm}.png")
    print("  assets/icon.iconset/ written")
    print("  On Mac, run:  iconutil -c icns assets/icon.iconset -o assets/icon.icns")


if __name__ == "__main__":
    print("Downloading fonts...")
    download_fonts()
    print("Generating icons...")
    generate_icons()
    print("Done.")
