#!/usr/bin/env python3
"""Static compliance checks for the iMessage sticker pack project."""

from __future__ import annotations

import json
import plistlib
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STICKER_CATALOG = ROOT / "StickerPackExtension" / "Stickers.xcstickers"
STICKER_PACK = STICKER_CATALOG / "Sticker Pack.stickerpack"
ICON_SET = STICKER_CATALOG / "iMessage App Icon.stickersiconset"
PBXPROJ = ROOT / "Haha Scale.xcodeproj" / "project.pbxproj"
HOST_PLIST = ROOT / "Haha Scale" / "Info.plist"
EXTENSION_PLIST = ROOT / "StickerPackExtension" / "Info.plist"


class ValidationError(Exception):
    pass


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_plist(path: Path):
    return plistlib.loads(path.read_bytes())


def parse_png(path: Path) -> dict[str, int | bool]:
    with path.open("rb") as f:
        signature = f.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValidationError(f"{path}: invalid PNG signature")

        width = height = color_type = None
        has_trns = False

        while True:
            length_raw = f.read(4)
            if len(length_raw) != 4:
                break
            length = struct.unpack(">I", length_raw)[0]
            chunk_type = f.read(4)
            chunk_data = f.read(length)
            crc = f.read(4)
            if len(chunk_type) != 4 or len(chunk_data) != length or len(crc) != 4:
                raise ValidationError(f"{path}: malformed PNG chunk stream")

            if chunk_type == b"IHDR":
                width, height, _, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk_data)
            elif chunk_type == b"tRNS":
                has_trns = True
            elif chunk_type == b"IEND":
                break

        if width is None or height is None or color_type is None:
            raise ValidationError(f"{path}: missing IHDR")

        return {
            "width": width,
            "height": height,
            "color_type": color_type,
            "has_trns": has_trns,
        }


def parse_size_points(size: str) -> tuple[int, int]:
    raw_w, raw_h = size.split("x", maxsplit=1)
    return int(raw_w), int(raw_h)


def parse_scale(scale: str) -> int:
    return int(scale.rstrip("x"))


def validate_parseable_files(errors: list[str]) -> None:
    for path in ROOT.rglob("*.json"):
        try:
            load_json(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Invalid JSON {path.relative_to(ROOT)}: {exc}")

    for path in ROOT.rglob("*.plist"):
        try:
            load_plist(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Invalid plist {path.relative_to(ROOT)}: {exc}")


def validate_project_settings(errors: list[str]) -> None:
    host_info = load_plist(HOST_PLIST)
    ext_info = load_plist(EXTENSION_PLIST)
    pbxproj_text = PBXPROJ.read_text(encoding="utf-8")

    required_caps = host_info.get("UIRequiredDeviceCapabilities", [])
    if isinstance(required_caps, list) and "armv7" in required_caps:
        errors.append("Host Info.plist still contains deprecated UIRequiredDeviceCapabilities armv7")

    if host_info.get("CFBundleVersion") != "$(CURRENT_PROJECT_VERSION)":
        errors.append("Host CFBundleVersion must be $(CURRENT_PROJECT_VERSION)")

    if ext_info.get("CFBundleVersion") != "$(CURRENT_PROJECT_VERSION)":
        errors.append("Extension CFBundleVersion must be $(CURRENT_PROJECT_VERSION)")

    if '"iPhone Developer"' in pbxproj_text:
        errors.append('project.pbxproj still contains legacy signing identity "iPhone Developer"')

    marketing_versions = {v.strip() for v in re.findall(r"MARKETING_VERSION = ([^;]+);", pbxproj_text)}
    if len(marketing_versions) != 1:
        errors.append(f"Inconsistent MARKETING_VERSION values: {sorted(marketing_versions)}")
    elif marketing_versions != {"1.3.0"}:
        errors.append(f"Unexpected MARKETING_VERSION: {sorted(marketing_versions)}")

    project_versions = {v.strip() for v in re.findall(r"CURRENT_PROJECT_VERSION = ([^;]+);", pbxproj_text)}
    if len(project_versions) != 1:
        errors.append(f"Inconsistent CURRENT_PROJECT_VERSION values: {sorted(project_versions)}")
    elif project_versions != {"2"}:
        errors.append(f"Unexpected CURRENT_PROJECT_VERSION: {sorted(project_versions)}")


def validate_sticker_assets(errors: list[str]) -> None:
    pack_contents = load_json(STICKER_PACK / "Contents.json")
    stickers = pack_contents.get("stickers", [])

    for sticker_ref in stickers:
        sticker_folder = sticker_ref.get("filename")
        if not sticker_folder:
            errors.append("Sticker pack Contents.json has sticker entry without filename")
            continue

        sticker_dir = STICKER_PACK / sticker_folder
        if not sticker_dir.exists():
            errors.append(f"Missing sticker directory: {sticker_dir.relative_to(ROOT)}")
            continue

        contents_path = sticker_dir / "Contents.json"
        if not contents_path.exists():
            errors.append(f"Missing sticker Contents.json: {contents_path.relative_to(ROOT)}")
            continue

        sticker_meta = load_json(contents_path)
        png_name = sticker_meta.get("properties", {}).get("filename")
        if not png_name:
            errors.append(f"{contents_path.relative_to(ROOT)} missing properties.filename")
            continue

        png_path = sticker_dir / png_name
        if not png_path.exists():
            errors.append(f"Missing sticker PNG: {png_path.relative_to(ROOT)}")
            continue

        png = parse_png(png_path)
        if (png["width"], png["height"]) != (300, 300):
            errors.append(
                f"{png_path.relative_to(ROOT)} must be 300x300, got {png['width']}x{png['height']}"
            )

        file_size = png_path.stat().st_size
        if file_size >= 500 * 1024:
            errors.append(f"{png_path.relative_to(ROOT)} is {file_size} bytes; must be < 500KB")


def validate_icon_assets(errors: list[str]) -> None:
    icon_contents = load_json(ICON_SET / "Contents.json")
    images = icon_contents.get("images", [])

    for image in images:
        filename = image.get("filename")
        if not filename:
            continue

        path = ICON_SET / filename
        if not path.exists():
            errors.append(f"Missing icon PNG: {path.relative_to(ROOT)}")
            continue

        png = parse_png(path)
        size = image.get("size")
        scale = image.get("scale")
        if size and scale:
            points_w, points_h = parse_size_points(size)
            factor = parse_scale(scale)
            expected_w, expected_h = points_w * factor, points_h * factor
            if (png["width"], png["height"]) != (expected_w, expected_h):
                errors.append(
                    f"{path.relative_to(ROOT)} size mismatch: expected {expected_w}x{expected_h}, "
                    f"got {png['width']}x{png['height']}"
                )

        if filename == "main-1024.png":
            if png["color_type"] in {4, 6}:
                errors.append("main-1024.png must not include alpha channel")
            if png["has_trns"]:
                errors.append("main-1024.png must not include tRNS transparency")


def main() -> int:
    errors: list[str] = []

    validate_parseable_files(errors)
    validate_project_settings(errors)
    validate_sticker_assets(errors)
    validate_icon_assets(errors)

    if errors:
        print("Validation failed:")
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}")
        return 1

    print("Validation passed: project configuration and sticker/icon assets are compliant.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
