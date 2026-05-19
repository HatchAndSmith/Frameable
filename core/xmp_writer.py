from pathlib import Path


def write(tiff_path: Path, keywords: list[str],
          crop_angle: float = 0.0, include_angle: bool = False) -> Path:
    """Write an XMP sidecar file next to tiff_path and return its path."""
    xmp_path = tiff_path.with_suffix(".xmp")

    kw_items = "\n".join(
        f"          <rdf:li>{_esc(k)}</rdf:li>" for k in sorted(set(keywords))
    )
    angle_xml = ""
    if include_angle and abs(crop_angle) >= 0.2:
        angle_xml = f"\n      <crs:CropAngle>{-crop_angle:.2f}</crs:CropAngle>"

    crs_ns = ' xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"' if angle_xml else ""

    xmp = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f'    <rdf:Description rdf:about=""\n'
        f'      xmlns:dc="http://purl.org/dc/elements/1.1/"{crs_ns}>\n'
        f'      <dc:subject>\n'
        f'        <rdf:Bag>\n'
        f'{kw_items}\n'
        f'        </rdf:Bag>\n'
        f'      </dc:subject>{angle_xml}\n'
        f'    </rdf:Description>\n'
        f'  </rdf:RDF>\n'
        f'</x:xmpmeta>\n'
        f'<?xpacket end="w"?>'
    )

    xmp_path.write_text(xmp, encoding="utf-8")
    return xmp_path


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
