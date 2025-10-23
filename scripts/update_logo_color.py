import argparse
from pathlib import Path


def replace_in_text_file(file_path: Path, old: str, new: str) -> bool:
    if not file_path.exists():
        return False
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Not a text file
        return False

    if old in text:
        updated = text.replace(old, new)
        file_path.write_text(updated, encoding="utf-8")
        return True
    # Also try case-insensitive variant by normalizing both
    lower_old = old.lower()
    lower_text = text.lower()
    if lower_old in lower_text:
        # Do a manual case-insensitive replace preserving original casing where possible
        # Simple approach: rebuild by scanning
        result_chars = []
        i = 0
        n = len(text)
        m = len(old)
        while i < n:
            if i + m <= n and text[i:i+m].lower() == lower_old:
                result_chars.append(new)
                i += m
            else:
                result_chars.append(text[i])
                i += 1
        file_path.write_text("".join(result_chars), encoding="utf-8")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Replace a hex color in logo/icon SVG files.")
    parser.add_argument("--src", required=True, help="Source hex color (e.g. #2d3748f2)")
    parser.add_argument("--dst", required=True, help="Destination hex color (e.g. #f9f9f9f2)")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]), help="Project root path")
    args = parser.parse_args()

    root = Path(args.root)
    targets = [
        root / "static" / "icons" / "logo.svg",
        root / "static" / "icons" / "icon.svg",
    ]

    any_changed = False
    for path in targets:
        changed = replace_in_text_file(path, args.src, args.dst)
        any_changed = any_changed or changed

    # Optionally try to update manifest icons or other SVGs if present
    # but keep scope narrow to avoid unintended changes.

    if not any_changed:
        # Not an error; just inform via exit code 0
        print("No occurrences found in target SVG files.")
    else:
        print("Color replaced where found.")


if __name__ == "__main__":
    main()
















