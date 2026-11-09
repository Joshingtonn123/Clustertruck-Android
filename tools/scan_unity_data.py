#!/usr/bin/env python3
"""Join split Unity WebGL data and inspect UnityWebData entries."""
from pathlib import Path
import mmap
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "Build"
PARTS = sorted(
    BUILD.glob("ClusterTruckWEB.data.part*"),
    key=lambda p: int(p.name.rsplit("part", 1)[1]),
)
TERMS = ["wasm.rip", "notrexed", "rexed", "ported by", "credits", "loading", "splash", "logo", "intro"]
OUT = ROOT / "unity-data-scan-report.txt"
COMBINED = Path("/tmp/ClusterTruckWEB.data")
MAGIC = b"UnityWebData1.0\0"


def add(report, message=""):
    report.append(message)


def search_bytes(data, label, report, max_each=12):
    raw = data if isinstance(data, bytes) else data[:]
    lower = raw.lower()
    for term in TERMS:
        needle = term.encode("utf-8")
        pos = 0
        count = 0
        while count < max_each:
            pos = lower.find(needle, pos)
            if pos < 0:
                break
            left = max(0, pos - 70)
            right = min(len(raw), pos + len(needle) + 100)
            snippet = raw[left:right].decode("utf-8", "replace").replace("\x00", " ")
            add(report, f"MATCH [{label}] term={term!r} offset={pos}: {snippet!r}")
            pos += len(needle)
            count += 1

        for encoding in ("utf-16le", "utf-16be"):
            wide = term.encode(encoding)
            pos = 0
            count = 0
            while count < max_each:
                pos = raw.find(wide, pos)
                if pos < 0:
                    break
                left = max(0, pos - 100)
                right = min(len(raw), pos + len(wide) + 140)
                snippet = raw[left:right].decode(encoding, "replace").replace("\x00", "")
                add(report, f"MATCH [{label}/{encoding}] term={term!r} offset={pos}: {snippet!r}")
                pos += len(wide)
                count += 1


def parse_unity_web_data(data, report):
    if data[:len(MAGIC)] != MAGIC:
        add(report, "UnityWebData header: NOT FOUND.")
        add(report, f"First 32 bytes (hex): {data[:32].hex(' ')}")
        return

    add(report, "UnityWebData header: FOUND.")
    header_size = struct.unpack_from("<I", data, len(MAGIC))[0]
    add(report, f"Declared header size: {header_size}")
    cursor = len(MAGIC) + 4
    count = 0

    while cursor < min(header_size, len(data)):
        if cursor + 12 > header_size:
            add(report, "Entry table ended unexpectedly.")
            break

        offset, size, path_len = struct.unpack_from("<III", data, cursor)
        cursor += 12
        if path_len <= 0 or cursor + path_len > header_size:
            add(report, f"Invalid path length {path_len} at header position {cursor - 4}.")
            break

        path = data[cursor:cursor + path_len].decode("utf-8", "replace").rstrip("\x00")
        cursor += path_len
        count += 1
        add(report, f"ENTRY {count}: offset={offset} size={size} path={path}")

        if offset + size <= len(data) and size:
            entry = bytes(data[offset:offset + size])
            add(report, f"ENTRY FORMAT {path}: {entry[:24].hex(' ')}")
            search_bytes(entry, f"entry:{path}", report, max_each=5)
        else:
            add(report, f"WARNING: entry range outside combined data: {path}")

    add(report, f"Parsed embedded entries: {count}")
    add(report, f"Header table cursor ended at: {cursor}")


def main():
    report = [
        "Clustertruck Android - Unity WebGL data scan",
        "UnityWebData archive parser with per-entry string and format inspection.",
        "String matches are clues only; compressed/serialized assets may not expose readable text.",
        "",
    ]

    if not PARTS:
        add(report, "ERROR: no Build/ClusterTruckWEB.data.part* files found.")
        OUT.write_text("\n".join(report) + "\n", encoding="utf-8")
        return 2

    add(report, f"Found {len(PARTS)} data chunks.")
    total = 0
    with COMBINED.open("wb") as merged:
        for part in PARTS:
            size = part.stat().st_size
            add(report, f"CHUNK: {part.name} size={size}")
            total += size
            with part.open("rb") as src:
                while True:
                    block = src.read(4 * 1024 * 1024)
                    if not block:
                        break
                    merged.write(block)

    add(report, f"Combined size: {total} bytes")
    with COMBINED.open("rb") as f:
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
            add(report, f"First 32 bytes: {data[:32].hex(' ')}")
            parse_unity_web_data(data, report)
            search_bytes(data, "combined-data", report, max_each=8)

    for name in ("ClusterTruckWEB.loader.js", "ClusterTruckWEB.framework.js"):
        path = BUILD / name
        if path.exists():
            search_bytes(path.read_bytes(), name, report, max_each=5)

    OUT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report[:20]))
    print(f"\nFull report written to {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        details = traceback.format_exc()
        OUT.write_text("SCAN ERROR\n" + details, encoding="utf-8")
        print(details)
        sys.exit(1)
