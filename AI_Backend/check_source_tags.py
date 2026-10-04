"""
One-off diagnostic: inspect the ChromaDB metadata to confirm what `source`
label each chunk carries, broken down by the leading filename prefix.

Naming convention used by UMMC guideline PDFs:
    3_<chapter>_..._3rd_Ed.pdf  -> should be source=ADULT
    4_<chapter>_..._3rd_Ed.pdf  -> should be source=PAEDIATRIC
    *renal*.pdf                 -> should be source=RENAL
    *anticoag*.pdf              -> should be source=ANTICOAG

Run this BEFORE the rebuild/re-enrich to confirm the bug, and AFTER to
confirm the fix.

Usage:
    python check_source_tags.py
"""
import os
import re
from collections import defaultdict
from vector_store import get_vector_store


_PAED_PREFIX = re.compile(r'^4[\W_]')
_ADULT_PREFIX = re.compile(r'^3[\W_]')


def classify_prefix(basename: str) -> str:
    """Bucket a filename by its expected source category.

    Handles both naming conventions used in the data folder:
        4_9_Foo.pdf  (underscores)
        4.9 Foo.pdf  (dot + space)
    """
    name = basename.lower()
    if "renal" in name:
        return "renal"
    if "anticoag" in name:
        return "anticoag"
    if _PAED_PREFIX.match(name):
        return "4_xx (paediatric)"
    if _ADULT_PREFIX.match(name):
        return "3_xx (adult)"
    return "other"


def expected_source(prefix: str) -> str:
    return {
        "3_xx (adult)": "ADULT",
        "4_xx (paediatric)": "PAEDIATRIC",
        "renal": "RENAL",
        "anticoag": "ANTICOAG",
    }.get(prefix, "")


def main():
    db = get_vector_store()
    data = db.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    print(f"Total chunks in ChromaDB: {len(metadatas)}")
    print()

    grid = defaultdict(int)
    by_file = defaultdict(lambda: defaultdict(int))

    for meta in metadatas:
        fp = meta.get("file_path") or meta.get("source") or ""
        src = meta.get("source") or "<missing>"
        basename = os.path.basename(fp)
        prefix = classify_prefix(basename)
        grid[(prefix, src)] += 1
        by_file[basename][src] += 1

    # ---- View 1: (prefix, source) grid -----------------------------------
    print("=" * 72)
    print("Chunks grouped by (filename prefix, source label):")
    print("=" * 72)
    wrong_total = 0
    for (prefix, src), count in sorted(grid.items()):
        want = expected_source(prefix)
        if want and src != want:
            flag = f"  <-- WRONG (expected source={want})"
            wrong_total += count
        else:
            flag = ""
        print(f"  {prefix:22s} -> source={src:12s} : {count:6d}{flag}")

    print()
    if wrong_total == 0:
        print("[OK] Every chunk's source tag matches its filename prefix.")
    else:
        print(f"[WARN] {wrong_total} chunks have a source tag that does NOT "
              f"match their filename prefix.")
        print("       This is the bug that causes wrong-population leakage.")
        print("       Fix: 'python build_database.py --reenrich' "
              "(fast, no re-embedding)")
        print("        or: 'python build_database.py --reset' "
              "(full rebuild)")

    # ---- View 2: per-file source label (only files with mixed tags) ------
    mixed = {f: d for f, d in by_file.items() if len(d) > 1}
    if mixed:
        print()
        print("=" * 72)
        print("Files that contain chunks with MIXED source tags:")
        print("=" * 72)
        for fname, src_counts in sorted(mixed.items()):
            print(f"  {fname}")
            for src, c in sorted(src_counts.items()):
                print(f"    source={src:12s} : {c}")


if __name__ == "__main__":
    main()