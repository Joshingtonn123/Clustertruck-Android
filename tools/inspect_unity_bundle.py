#!/usr/bin/env python3
"""Inspect the UnityFS bundle inside ClusterTruckWEB.data and export likely loading-screen images."""
from pathlib import Path
import re
import struct
import traceback

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "Build"
PARTS = sorted(BUILD.glob("ClusterTruckWEB.data.part*"),
               key=lambda p: int(p.name.rsplit("part", 1)[1]))
REPORT = ROOT / "unity-assets-report.txt"
OUT_DIR = ROOT / "unity-assets"
MAGIC = b"UnityWebData1.0\0"
CANDIDATE = re.compile(r"(logo|load|splash|intro|title|background|start|wasm|notrexed|credit)", re.I)


def main():
    lines = ["Clustertruck Unity asset inventory", ""]
    if not PARTS:
        lines.append("ERROR: Unity data chunks not found.")
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 2

    combined = Path("/tmp/ClusterTruckWEB.data")
    with combined.open("wb") as dst:
        for part in PARTS:
            with part.open("rb") as src:
                while True:
                    block = src.read(4 * 1024 * 1024)
                    if not block:
                        break
                    dst.write(block)

    with combined.open("rb") as f:
        if f.read(len(MAGIC)) != MAGIC:
            raise RuntimeError("UnityWebData header missing")
        header_size = struct.unpack("<I", f.read(4))[0]
        entries = []
        cursor = len(MAGIC) + 4
        f.seek(cursor)
        while f.tell() < header_size:
            offset, size, path_len = struct.unpack("<III", f.read(12))
            path = f.read(path_len).decode("utf-8", "replace").rstrip("\0")
            entries.append((offset, size, path))

    bundle_entry = next((e for e in entries if e[2] == "data.unity3d"), None)
    if not bundle_entry:
        raise RuntimeError("data.unity3d entry not found in UnityWebData")
    offset, size, _ = bundle_entry
    bundle_path = Path("/tmp/clustertruck-data.unity3d")
    with combined.open("rb") as src, bundle_path.open("wb") as dst:
        src.seek(offset)
        remaining = size
        while remaining:
            block = src.read(min(4 * 1024 * 1024, remaining))
            if not block:
                raise RuntimeError("Unexpected end of data.unity3d")
            dst.write(block)
            remaining -= len(block)

    lines.append(f"UnityFS bundle extracted: {size} bytes")
    try:
        import UnityPy
    except Exception:
        lines.append("ERROR: UnityPy import failed:")
        lines.append(traceback.format_exc())
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    OUT_DIR.mkdir(exist_ok=True)
    env = UnityPy.load(str(bundle_path))
    objects = list(env.objects)
    lines.append(f"UnityPy objects discovered: {len(objects)}")
    type_counts = {}
    exported = 0
    text_count = 0

    for obj in objects:
        type_name = getattr(obj.type, "name", str(obj.type))
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
        try:
            data = obj.read()
            name = str(getattr(data, "m_Name", "") or "")
            if type_name in ("Texture2D", "Sprite", "VideoClip", "TextAsset", "MovieTexture"):
                lines.append(f"OBJECT type={type_name} path_id={obj.path_id} name={name!r}")

            if type_name == "TextAsset":
                script = getattr(data, "script", b"")
                if isinstance(script, bytes):
                    decoded = script.decode("utf-8", "replace")
                else:
                    decoded = str(script)
                if decoded.strip():
                    text_count += 1
                    if CANDIDATE.search(name) or CANDIDATE.search(decoded):
                        lines.append(f"TEXT ASSET {name!r}: {decoded[:1500]!r}")

            if type_name in ("Texture2D", "Sprite") and CANDIDATE.search(name):
                image = getattr(data, "image", None)
                if image is not None:
                    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)[:80] or "unnamed"
                    target = OUT_DIR / f"{type_name}_{obj.path_id}_{safe}.png"
                    image.save(target)
                    exported += 1
                    lines.append(f"EXPORTED IMAGE {target.name} size={target.stat().st_size}")
        except Exception as exc:
            lines.append(f"READ ERROR type={type_name} path_id={obj.path_id}: {type(exc).__name__}: {exc}")

    lines.append("")
    lines.append("OBJECT TYPE COUNTS:")
    for type_name, count in sorted(type_counts.items()):
        lines.append(f"{type_name}: {count}")
    lines.append(f"TextAsset objects read: {text_count}")
    lines.append(f"Candidate images exported: {exported}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:35]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        REPORT.write_text("ASSET INSPECTION ERROR\n" + traceback.format_exc(), encoding="utf-8")
        print(traceback.format_exc())
        raise
