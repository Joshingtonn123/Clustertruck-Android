#!/usr/bin/env python3
"""Join split Unity WebGL data and search for embedded branding strings. Diagnostic build with UnityWebData entry parsing."""
from pathlib import Path
import mmap
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "Build"
PARTS = sorted(BUILD.glob("ClusterTruckWEB.data.part*"),
               key=lambda p: int(p.name.rsplit("part", 1)[1]))
TERMS = [
    "wasm.rip", "wasm", "notrexed", "rexed",
    "ported by", "port by", "ported", "credits",
]
OUT = ROOT / "unity-data-scan-report.txt"
COMBINED = Path("/tmp/ClusterTruckWEB.data")

def add(report, message=""):
    report.append(message)

def search_bytes(data, label, report):
    # mmap objects are not case-foldable; make a bytes view for scanning.
    raw = data if isinstance(data, bytes) else data[:]
    lower = raw.lower()
    for term in TERMS:
        needle = term.encode("utf-8")
        pos = 0
        count = 0
        while count < 25:
            pos = lower.find(needle, pos)
            if pos < 0:
                break
            left, right = max(0, pos - 70), min(len(raw), pos + len(needle) + 100)
            snippet = raw[left:right].decode("utf-8", "replace").replace("\\x00", " ")
            add(report, f"MATCH [{label}] term={term!r} offset={pos}: {snippet!r}")
            pos += len(needle)
            count += 1
        for encoding in ("utf-16le", "utf-16be"):
            wide = term.encode(encoding)
            pos = 0
            count = 0
            while count < 25:
                pos = raw.find(wide, pos)
                if pos < 0:
                    break
                left, right = max(0, pos - 100), min(len(raw), pos + len(wide) + 140)
                snippet = raw[left:right].decode(encoding, "replace").replace("\\x00", "")
                add(report, f"MATCH [{label}/{encoding}] term={term!r} offset={pos}: {snippet!r}")
                pos += len(wide)
                count += 1

def parse_unity_web_data(data, report):
    magic = b"UnityWebData1.0\\0"
    if data[:len(magic)] != magic:
        add(report, "UnityWebData header: not found at byte 0.")
        add(report, f"First 32 bytes (hex): {data[:32].hex(' ')}")
        return
    add(report, "UnityWebData header: FOUND.")
    header_size = struct.unpack_from("<I", data, len(magic))[0]
    add(report, f"Declared header size: {header_size}")
    cursor = len(magic) + 4
    count = 0
    while cursor < min(header_size, len(data)):
        # UnityWebData entries are: offset, size, path byte-length, path bytes.
        if cursor + 12 > header_size:
            add(report, "Entry table ended unexpectedly.")
            break
        offset, size, path_len = struct.unpack_from("<III", data, cursor)
        cursor += 12
        if path_len <= 0 or cursor + path_len > header_size:
            add(report, f"Invalid path length {path_len} at header position {cursor - 4}.")
            break
        path = data[cursor:cursor + path_len].decode("utf-8", "replace")
        cursor += path_len
        count += 1
        add(report, f"ENTRY {count}: offset={offset} size={size} path={path}")
        if offset + size <= len(data) and size:
            entry = data[offset:offset + size]
            search_bytes(entry, f"entry:{path}", report)
            # List recognizable formats at the start of each entry.
            add(report, f"ENTRY FORMAT {path}: {entry[:16].hex(' ')}")
        else:
            add(report, f"WARNING: entry range outside combined data: {path}")
    add(report, f"Parsed embedded entries: {count}")

def main():
    report = [
        "Clustertruck Android - Unity WebGL data scan",
        "This report searches raw and directly indexed UnityWebData content.",
        "A no-match result does NOT rule out compressed/serialized Unity assets.",
        "",
    ]
    if not PARTS:
        add(report, "ERROR: no Build/ClusterTruckWEB.data.part* files found.")
        OUT.write_text("\\n".join(report), encoding="utf-8")
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
            search_bytes(data, "combined-data", report)
            parse_unity_web_data(data, report)
    # Also inspect the readable Unity WebGL loader/framework files.
    for name in ("ClusterTruckWEB.loader.js", "ClusterTruckWEB.framework.js"):
        path = BUILD / name
        if path.exists():
            raw = path.read_bytes()
            search_bytes(raw, name, report)
    OUT.write_text("\\n".join(report) + "\\n", encoding="utf-8")
    print("\\n".join(report[:12]))
    print(f"\\nFull report written to {OUT}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        details = traceback.format_exc()
        OUT.write_text("SCAN ERROR\\n" + details, encoding="utf-8")
        print(details)
        sys.exit(0)
