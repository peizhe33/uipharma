"""
Runtime diagnostic that mimics app.py's Phase 3 retrieval for Case R20
(adult, 63yo, severe pyelonephritis) and shows:

  1. Source-tag distribution in ChromaDB (same as check_source_tags.py)
  2. What the raw vector search returns for the diagnosis query
  3. Which of those chunks would PASS the age-based source filter
  4. Whether ANY paediatric (4_xx) chunk survives the filter
  5. Same for the per-drug query (nitrofurantoin)

Run this AFTER rebuilding the DB. If step 4 or step 5 shows a 4_xx chunk
surviving the filter, the bug is in the filter logic, NOT the data.
If they show no 4_xx survivors, the bug is somewhere downstream
(reference assembly, caching, etc.).

Usage:
    python debug_retrieval.py
"""
import os
import re
from collections import defaultdict
from vector_store import get_vector_store
from config import allowed_sources_for_age


_PAED_PREFIX = re.compile(r'^4[\W_]')
_ADULT_PREFIX = re.compile(r'^3[\W_]')

# Mimic Case R20
PATIENT_AGE = 63
DIAGNOSIS = "Severe pyelonephritis"
DRUG_NAME = "nitrofurantoin"
TOP_K = 5


def basename_of(meta: dict) -> str:
    fp = meta.get("file_path") or meta.get("source") or ""
    return os.path.basename(fp)


def is_paediatric_file(basename: str) -> bool:
    """Match both '4_9_Foo.pdf' and '4.9 Foo.pdf' style names."""
    return bool(_PAED_PREFIX.match(basename.lower()))


def is_adult_file(basename: str) -> bool:
    """Match both '3_9_Foo.pdf' and '3.9 Foo.pdf' style names."""
    return bool(_ADULT_PREFIX.match(basename.lower()))


def print_chunks(title: str, items, max_show: int = 12):
    print(f"\n--- {title} ({len(items)} results) ---")
    for i, item in enumerate(items[:max_show], 1):
        meta = item.get("meta", {})
        basename = basename_of(meta)
        src = meta.get("source", "<missing>")
        page = meta.get("page", "?")
        dist = item.get("adjusted_distance", item.get("distance", "?"))
        flag = ""
        if is_paediatric_file(basename) and PATIENT_AGE > 18:
            flag = "  <-- PAEDIATRIC FILE LEAKING INTO ADULT QUERY"
        print(f"  [{i}] source={src:11s} | file={basename} | "
              f"pg={page} | dist={dist}{flag}")
    if len(items) > max_show:
        print(f"  ... and {len(items) - max_show} more")


def main():
    db = get_vector_store()
    allowed = allowed_sources_for_age(PATIENT_AGE)
    print("=" * 75)
    print(f"DIAGNOSTIC: Case R20 retrieval simulation")
    print("=" * 75)
    print(f"Patient age           : {PATIENT_AGE}")
    print(f"Allowed sources       : {sorted(allowed)}")
    print(f"Diagnosis query       : '{DIAGNOSIS}'")
    print(f"Per-drug query        : '{DRUG_NAME}'")
    print(f"TOP_K                 : {TOP_K}")

    # -----------------------------------------------------------------
    # STEP 1: source-tag distribution
    # -----------------------------------------------------------------
    print()
    print("=" * 75)
    print("STEP 1: Source-tag distribution in ChromaDB")
    print("=" * 75)
    data = db.get(include=["metadatas"])
    by_prefix_src = defaultdict(int)
    for meta in (data.get("metadatas") or []):
        basename = basename_of(meta)
        src = meta.get("source", "<missing>")
        if is_paediatric_file(basename):
            prefix = "4_xx (paed)"
        elif is_adult_file(basename):
            prefix = "3_xx (adult)"
        elif "anticoag" in basename.lower():
            prefix = "anticoag"
        elif "renal" in basename.lower():
            prefix = "renal"
        else:
            prefix = "other"
        by_prefix_src[(prefix, src)] += 1

    bad = 0
    for (prefix, src), count in sorted(by_prefix_src.items()):
        expected = {
            "3_xx (adult)": "ADULT",
            "4_xx (paed)": "PAEDIATRIC",
            "anticoag": "ANTICOAG",
            "renal": "RENAL",
        }.get(prefix)
        flag = ""
        if expected and src != expected:
            flag = f"  <-- MISTAGGED (should be {expected})"
            bad += count
        print(f"  {prefix:14s} source={src:11s} : {count:5d}{flag}")

    if bad == 0:
        print("\n  [OK] All chunks correctly tagged. "
              "Source filter SHOULD prevent paediatric leakage.")
    else:
        print(f"\n  [FAIL] {bad} chunks have stale tags. "
              "Run 'python build_database.py --reset' then re-run this.")
        return

    # -----------------------------------------------------------------
    # STEP 2: raw diagnosis search (no filter)
    # -----------------------------------------------------------------
    print()
    print("=" * 75)
    print("STEP 2: Raw diagnosis search BEFORE age-source filter")
    print("=" * 75)
    expected_meta = {
        "chapter": "Urology Infections",
        "condition": "pyelonephritis/urosepsis",
        "section_type": "treatment",
        "severity": "severe_or_high",
        "route": "",
        "drug_names": [DRUG_NAME],
    }
    diag_raw = db.similarity_search_with_score(DIAGNOSIS, k=20)
    diag_raw_items = []
    for doc, score in diag_raw:
        diag_raw_items.append({
            "text": doc.page_content,
            "meta": doc.metadata or {},
            "distance": round(float(score), 3),
            "adjusted_distance": round(float(score), 3),
        })
    print_chunks("Raw vector hits (no filter)", diag_raw_items, max_show=15)

    # -----------------------------------------------------------------
    # STEP 3: apply age-source filter (what app.py does)
    # -----------------------------------------------------------------
    print()
    print("=" * 75)
    print("STEP 3: After age-based source filter (allowed = "
          f"{sorted(allowed)})")
    print("=" * 75)
    filtered = [
        item for item in diag_raw_items
        if item.get("meta", {}).get("source") in allowed
    ]
    print_chunks("Filter survivors", filtered, max_show=15)
    leakers = [
        item for item in filtered
        if is_paediatric_file(basename_of(item["meta"]))
    ]
    if leakers:
        print(f"\n  [FAIL] {len(leakers)} paediatric chunk(s) survived the "
              "filter. Check meta['source'] values printed above.")
        for item in leakers:
            print(f"    file={basename_of(item['meta'])} "
                  f"source={item['meta'].get('source')!r}")
    else:
        print("\n  [OK] No paediatric chunks survived the filter.")

    # -----------------------------------------------------------------
    # STEP 4: per-drug search for nitrofurantoin
    # -----------------------------------------------------------------
    print()
    print("=" * 75)
    print(f"STEP 4: Per-drug search for '{DRUG_NAME}' after filter")
    print("=" * 75)
    drug_raw = db.similarity_search_with_score(DRUG_NAME, k=10)
    drug_items = []
    for doc, score in drug_raw:
        drug_items.append({
            "text": doc.page_content,
            "meta": doc.metadata or {},
            "distance": round(float(score), 3),
        })
    drug_filtered = [
        item for item in drug_items
        if item.get("meta", {}).get("source") in allowed
    ]
    print_chunks("Per-drug filter survivors", drug_filtered, max_show=15)
    drug_leakers = [
        item for item in drug_filtered
        if is_paediatric_file(basename_of(item["meta"]))
    ]
    if drug_leakers:
        print(f"\n  [FAIL] {len(drug_leakers)} paediatric chunk(s) survived "
              "the per-drug filter.")
    else:
        print("\n  [OK] No paediatric chunks survived the per-drug filter.")

    print()
    print("=" * 75)
    print("VERDICT")
    print("=" * 75)
    if not leakers and not drug_leakers:
        print("  Filtering works correctly at the retrieval layer.")
        print("  If 4.9 still appears in the Flask output, the leakage is")
        print("  happening DOWNSTREAM of retrieval (e.g. stale Flask process,")
        print("  references built from a path I haven't found yet).")
        print("  Next step: restart Flask, then check the DEBUG logs at")
        print("  request time for 'Retrieved N documents' and the source tag")
        print("  of each retrieved item.")
    else:
        print("  Filter is letting paediatric content through. The bug is")
        print("  EITHER in the source tagging (run check_source_tags.py)")
        print("  OR in the filter logic itself.")


if __name__ == "__main__":
    main()