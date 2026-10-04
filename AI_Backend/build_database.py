import argparse
import os
import re
import shutil
from typing import List

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from embedding import get_embedding_function
from langchain_chroma import Chroma


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma")
DATA_PATH = os.path.join(BASE_DIR, "data")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe the entire ChromaDB and rebuild from scratch (slow - "
             "re-embeds every chunk with PubMedBERT).",
    )
    parser.add_argument(
        "--reenrich", action="store_true",
        help="Re-tag metadata on existing chunks WITHOUT re-embedding. "
             "Use this when enrich_metadata logic has changed (e.g. new "
             "source label like PAEDIATRIC was added) but the underlying "
             "PDFs and text chunks are unchanged. Much faster than --reset.",
    )
    args = parser.parse_args()

    if args.reset:
        print("[INFO] Clearing database (full rebuild)")
        clear_database()

    if args.reenrich:
        # Re-tag metadata on existing chunks without re-embedding. This is
        # the fast path when enrich_metadata logic changes (e.g. new source
        # label, new condition keyword) but the underlying text is the same.
        reenrich_existing_chunks()
        return

    documents = load_documents()
    chunks = split_documents(documents)
    add_to_chroma(chunks)


def load_documents():
    document_loader = PyPDFDirectoryLoader(DATA_PATH)
    return document_loader.load()


def split_documents(documents: List[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=200,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)


# ============================================================
# Metadata enrichment helpers
# ============================================================

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def contains_any(text: str, terms: List[str]) -> bool:
    text = norm(text)
    return any(term.lower() in text for term in terms)


def infer_source_label(filename: str) -> str:
    """
    Tag each chunk by the population/section it belongs to.

    UMMC guideline files follow the naming convention:
      - 3<sep><chapter>...3rd_Ed.pdf  -> ADULT chapter
      - 4<sep><chapter>...3rd_Ed.pdf  -> PAEDIATRIC chapter
    where <sep> can be any of: underscore, dot, dash, space. Real-world
    file copies use a mix of conventions, e.g.
      4_9_Urology_Infections_2024_3rd_Ed.pdf  (underscore)
      4.9 Urology Infections_2024_3rd Ed.pdf  (dot + space)
    The regex below matches the digit followed by any non-word char or
    underscore so both styles work without renaming files.

    Renal-dose tables and the anticoagulant quick guide get their own
    labels so they can be retrieved for any patient regardless of age.
    """
    f = filename.lower()

    # Renal-dose and anticoagulant tables are age-agnostic - tag them first
    # so they don't get swallowed by the 3/4 prefix rules below.
    if "renal dose" in f or "renal" in f:
        return "RENAL"

    if "anticoagulant" in f or "anticoag" in f:
        return "ANTICOAG"

    # Paediatric chapters: filename starts with "4" followed by any
    # separator (underscore, dot, dash, whitespace) - covers
    # 4_xx_Foo.pdf, 4.xx Foo.pdf, 4-xx-Foo.pdf, "4 xx Foo.pdf".
    # OR explicitly mentions paediatric/neonatal/NICU in the filename.
    if (
        re.match(r'^4[\W_]', f)
        or "paediatric" in f
        or "pediatric" in f
        or "nicu" in f
        or "neonatal" in f
    ):
        return "PAEDIATRIC"

    # Default = adult antimicrobial chapter (3_xx or 3.xx files, plus any
    # filename that doesn't match a more specific rule above).
    return "ADULT"


def infer_chapter(filename: str) -> str:
    f = filename.lower()

    chapter_map = {
        "bone and joint": "Bone and Joint Infections",
        "skin and soft tissue": "Skin and Soft Tissue Infections",
        "genital": "Genital and Sexually Transmitted Infections",
        "sexually transmitted": "Genital and Sexually Transmitted Infections",
        "obstetrics": "Obstetrics and Gynaecology Infections",
        "gynaecology": "Obstetrics and Gynaecology Infections",
        "hiv": "HIV Related Opportunistic Infections",
        "tropical": "Tropical Infections",
        "surgical related": "Surgical Related Infections",
        "surgical site": "Surgical Site Infection",
        "cardiovascular": "Cardiovascular System Infections",
        "central nervous": "Central Nervous System Infections",
        "cns": "Central Nervous System Infections",
        "ophthalmology": "Ophthalmology Infections",
        "ear": "Ear, Nose, and Throat Infections",
        "nose": "Ear, Nose, and Throat Infections",
        "throat": "Ear, Nose, and Throat Infections",
        "ent": "Ear, Nose, and Throat Infections",
        "febrile neutropenia": "Febrile Neutropenia",
        "gastrointestinal": "Gastrointestinal Infections",
        "respiratory": "Respiratory Tract Infections",
        "urology": "Urology Infections",
        "renal": "Renal Dose",
        "anticoagulant": "Anticoagulant",
    }

    for key, chapter in chapter_map.items():
        if key in f:
            return chapter

    return "unknown"

def has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) is not None

def infer_condition(text: str, filename: str) -> str:
    t = norm(text)
    f = filename.lower()
    if "skin and soft tissue" in f:
        if "diabetic foot" in t:
            return "diabetic foot infection"
        if "necrotising" in t or "necrotizing" in t:
            return "necrotising infection"
        if "bite" in t or "animal bite" in t or "human bite" in t:
            return "bite wound infection"
        if "abscess" in t or "carbuncle" in t or "furuncle" in t:
            return "abscess/carbuncle/furuncle"
        return "cellulitis/ssti"

    if "urology" in f:
        if "pyelonephritis" in t or "urosepsis" in t:
            return "pyelonephritis/urosepsis"
        if "cystitis" in t:
            return "cystitis"
        if has_word(t, "uti") or "urinary tract infection" in t:
            return "urinary tract infection"

    if "respiratory" in f:
        if "community-acquired pneumonia" in t or "community acquired pneumonia" in t or has_word(t, "cap"):
            return "community-acquired pneumonia"
        if "hospital-acquired pneumonia" in t or "ventilator-associated pneumonia" in t or has_word(t, "hap") or has_word(t, "vap"):
            return "hospital-acquired pneumonia/ventilator-associated pneumonia"
    
    if (
        "community-acquired pneumonia" in t
        or "community acquired pneumonia" in t
        or has_word(t, "cap")
    ):
        return "community-acquired pneumonia"

    if (
        "hospital-acquired pneumonia" in t
        or "ventilator-associated pneumonia" in t
        or has_word(t, "hap")
        or has_word(t, "vap")
    ):

        return "hospital-acquired pneumonia/ventilator-associated pneumonia"

    if "lung abscess" in t:
        return "lung abscess"

    if "bronchiectasis" in t:
        return "bronchiectasis"

    if "copd" in t or "chronic obstructive pulmonary disease" in t:
        return "acute exacerbation of copd"

    # SSTI
    if contains_any(t, [
        "cellulitis",
        "skin and soft tissue infection",
        "skin and soft tissue infections",
        "ssti",
        "generalised/moderate",
    ]) or "skin and soft tissue" in f:
        return "cellulitis/ssti"

    if contains_any(t, [
        "abscess",
        "carbuncle",
        "furuncle",
    ]):
        return "abscess/carbuncle/furuncle"

    if "diabetic foot" in t:
        return "diabetic foot infection"

    if "necrotising" in t or "necrotizing" in t:
        return "necrotising infection"

    if "bite" in t or "animal bite" in t or "human bite" in t:
        return "bite wound infection"

    # Urology
    if contains_any(t, [
        "pyelonephritis",
        "urosepsis",
    ]):
        return "pyelonephritis/urosepsis"

    if "cystitis" in t:
        return "cystitis"

    if "urinary tract infection" in t or "uti" in t:
        return "urinary tract infection"

    # CNS
    if "meningitis" in t:
        return "meningitis"

    if "encephalitis" in t:
        return "encephalitis"

    # GI
    if "cholangitis" in t:
        return "cholangitis"

    if "cholecystitis" in t:
        return "cholecystitis"

    if "diverticulitis" in t:
        return "diverticulitis"

    if "peritonitis" in t:
        return "peritonitis"

    if "gastroenteritis" in t or "diarrhoea" in t or "diarrhea" in t:
        return "gastroenteritis/diarrhoea"

    # Febrile neutropenia
    if "febrile neutropenia" in t or "neutropenic fever" in t:
        return "febrile neutropenia"

    return "unknown"


def infer_section_type(text: str) -> str:
    t = norm(text)

    treatment_markers = [
        "suggested treatment",
        "preferred",
        "alternative",
        "empirical",
        "antibiotic",
        "antimicrobial",
    ]

    dose_markers = [
        " mg ",
        " po ",
        " iv ",
        " q6h",
        " q8h",
        " q12h",
        " q24h",
    ]

    if contains_any(t, treatment_markers) or contains_any(t, dose_markers):
        return "treatment"

    if contains_any(t, [
        "curb-65",
        "crb 65",
        "crb-65",
        "severity assessment",
        "risk stratification",
        "scoring",
    ]):
        return "severity"

    if contains_any(t, [
        "diagnosis",
        "diagnostic",
        "clinical criteria",
        "imaging",
        "chest x-ray",
        "cxr",
        "culture",
        "investigation",
        "definition",
    ]):
        return "diagnosis_or_investigation"

    if contains_any(t, [
        "renal dose",
        "creatinine clearance",
        "egfr",
        "renal impairment",
    ]):
        return "renal"

    if contains_any(t, [
        "allergy",
        "hypersensitivity",
        "anaphylaxis",
        "urticaria",
        "dress",
        "sjs",
        "ten",
    ]):
        return "allergy"

    return "general"


def infer_severity(text: str) -> str:
    t = norm(text)
    levels = []

    if contains_any(t, [
        "low severity",
        "mild",
        "outpatient",
        "curb-65 = 0-1",
        "crb 65 = 0",
        "community-onset; mild",
        "mild cellulitis",
        "mild infection",
        "mild to moderate",
        "mild-moderate",
        "non-purulent",
        "uncomplicated",
        "localised",
        "localized",
        "first line oral",
        "oral therapy",
        "500 mg po",
        "500mg po",
        "po q6h",
        "po q8h",
        "po q12h",
        "duration: 5",
        "duration: 7",
        "5-7 days",
        "5 - 7 days",
        "3-5 days",
        "3 - 5 days",
        "short course",
    ]):
        levels.append("mild_or_low")

    if contains_any(t, [
        "moderate",
        "generalised",
        "generalized",
        "inpatient",
        "curb 65 = 2",
        "curb > 2",
        "crb 65 = 1",
        "crb 65 = 1 - 2",
        "moderate cellulitis",
        "moderate infection",
        "systemic",
        "hospitalised",
        "hospitalized",
        "iv q8h",
        "iv q6h",
        "1 g iv",
        "1g iv",
        "2 g iv",
        "2g iv",
        "cefazolin",
        "de-escalat",
    ]):
        levels.append("moderate")

    if contains_any(t, [
        "severe",
        "high severity",
        "icu",
        "sepsis",
        "urosepsis",
        "necrotising",
        "necrotizing",
        "severe cellulitis",
        "severe infection",
        "life-threatening",
        "bacteraemia",
        "bacteremia",
        "shock",
        "intensive care",
        "vancomycin",
        "piperacillin",
        "meropenem",
        "10-14 days",
        "10 - 14 days",
        "14 days",
    ]):
        levels.append("severe_or_high")

    if not levels:
        return "unknown"

    # Chroma metadata should be scalar, so store as string.
    return "_and_".join(sorted(set(levels)))


def infer_route(text: str) -> str:
    t = norm(text)
    routes = []

    if re.search(r"\bpo\b", t) or " oral " in f" {t} ":
        routes.append("PO")

    if re.search(r"\biv\b", t) or " intravenous " in f" {t} ":
        routes.append("IV")

    if not routes:
        return "unknown"

    if len(routes) > 1:
        return "mixed"

    return routes[0]


def extract_drug_names(text: str) -> str:
    """
    Store as semicolon-separated string because Chroma metadata should be simple scalar values.
    Add more drugs later as your database grows.
    """
    t = norm(text)

    known_drugs = [
        "amoxicillin",
        "co-amoxiclav",
        "amoxiclav",
        "amoxicillin clavulanate",
        "cloxacillin",
        "flucloxacillin",
        "cefalexin",
        "cephalexin",
        "ceftriaxone",
        "cefuroxime",
        "cefazolin",
        "ceftazidime",
        "cefepime",
        "piperacillin/tazobactam",
        "piperacillin-tazobactam",
        "azithromycin",
        "clarithromycin",
        "erythromycin",
        "doxycycline",
        "clindamycin",
        "metronidazole",
        "ciprofloxacin",
        "levofloxacin",
        "moxifloxacin",
        "gentamicin",
        "amikacin",
        "vancomycin",
        "meropenem",
        "imipenem",
        "ertapenem",
        "trimethoprim",
        "co-trimoxazole",
        "sulfamethoxazole",
        "nitrofurantoin",
        "fosfomycin",
        "paracetamol",
    ]

    found = []

    for drug in known_drugs:
        if drug in t:
            normalized = normalize_drug_alias(drug)
            found.append(normalized)

    found = sorted(set(found))
    return ";".join(found) if found else "unknown"


def normalize_drug_alias(drug: str) -> str:
    d = drug.lower().strip()

    aliases = {
        "cephalexin": "cefalexin",
        "amoxiclav": "co-amoxiclav",
        "amoxicillin clavulanate": "co-amoxiclav",
        "piperacillin-tazobactam": "piperacillin/tazobactam",
    }

    return aliases.get(d, d)


def infer_clinical_context(text: str) -> str:
    t = norm(text)
    contexts = []

    if contains_any(t, ["uncomplicated", "mild", "outpatient"]):
        contexts.append("uncomplicated_or_outpatient")

    if contains_any(t, ["inpatient", "moderate", "generalised", "generalized"]):
        contexts.append("inpatient_or_moderate")

    if contains_any(t, ["severe", "icu", "sepsis", "urosepsis"]):
        contexts.append("severe_or_sepsis")

    if contains_any(t, ["anaerobic", "polymicrobial", "contaminated wound"]):
        contexts.append("anaerobic_or_polymicrobial")

    if contains_any(t, ["bite", "animal bite", "human bite"]):
        contexts.append("bite_wound")

    if contains_any(t, ["diabetic foot"]):
        contexts.append("diabetic_foot")

    if contains_any(t, ["necrotising", "necrotizing"]):
        contexts.append("necrotising")

    if contains_any(t, ["penicillin allergy", "cephalosporin allergy", "anaphylaxis", "urticaria"]):
        contexts.append("allergy_note")

    if not contexts:
        return "general"

    return ";".join(sorted(set(contexts)))


def enrich_metadata(chunk: Document) -> Document:
    """
    Add clinical retrieval metadata to each chunk.
    These fields are for filtering/retrieval only.
    They should not be treated as final clinical decisions.
    """
    original_path = chunk.metadata.get("file_path") or chunk.metadata.get("source", "")
    filename = os.path.basename(original_path)
    text = chunk.page_content or ""

    chunk.metadata["source"] = infer_source_label(filename)
    chunk.metadata["chapter"] = infer_chapter(filename)
    chunk.metadata["condition"] = infer_condition(text, filename)
    chunk.metadata["section_type"] = infer_section_type(text)
    chunk.metadata["severity"] = infer_severity(text)
    chunk.metadata["route"] = infer_route(text)
    chunk.metadata["drug_names"] = extract_drug_names(text)
    chunk.metadata["clinical_context"] = infer_clinical_context(text)

    return chunk


# ============================================================
# Existing ID and source handling
# ============================================================

def calculate_chunk_ids(chunks):
    """
    Generate unique IDs for each chunk.
    Format: filename:page_number:chunk_index

    Important:
    - PyPDFDirectoryLoader stores the original file path in metadata["source"].
    - We preserve it as metadata["file_path"] before enrich_metadata
      overwrites `source` with the population/section label
      (ADULT / PAEDIATRIC / RENAL / ANTICOAG).
    """
    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source", "")
        page = chunk.metadata.get("page", "")
        current_page_id = f"{source}:{page}"

        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        chunk.metadata["file_path"] = source
        chunk.metadata["id"] = chunk_id

    return chunks


def add_to_chroma(chunks: List[Document]):
    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embedding_function()
    )

    chunks_with_ids = calculate_chunk_ids(chunks)

    # Add clinical metadata
    chunks_with_ids = [enrich_metadata(chunk) for chunk in chunks_with_ids]

    existing_items = db.get(include=[])
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB: {len(existing_ids)}")

    new_chunks = []
    for chunk in chunks_with_ids:
        if chunk.metadata["id"] not in existing_ids:
            new_chunks.append(chunk)

    if new_chunks:
        print(f"[INFO] Adding new documents: {len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, ids=new_chunk_ids)
    else:
        print("[OK] No new documents to add")

    print("[OK] Database build complete")


def reenrich_existing_chunks():
    """
    Re-tag metadata on every existing chunk in ChromaDB WITHOUT re-embedding.

    Why this exists:
      The original add_to_chroma() flow is incremental - it only enriches
      and adds NEW chunks (those whose IDs are not yet in the collection).
      If enrich_metadata() logic changes after the database is built (e.g.
      a new source label like PAEDIATRIC is added, or a new condition
      keyword is recognised), existing chunks keep their OLD metadata and
      retrieval filters silently use stale tags.

      This function fixes that without paying the cost of re-embedding
      every chunk. It iterates over the existing collection, re-runs the
      enrichers against each chunk's stored text and file_path, and
      updates only the metadata in-place via the underlying chromadb
      collection's update() API.

    What it does NOT touch:
      - The embedding vectors themselves (those are derived from text and
        the PubMedBERT model, neither of which changed).
      - The chunk IDs (text hasn't changed, so the IDs are still valid).
      - The text content of each chunk.
    """
    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embedding_function(),
    )

    existing = db.get(include=["metadatas", "documents"])
    ids = existing.get("ids") or []
    metadatas = existing.get("metadatas") or []
    documents = existing.get("documents") or []

    if not ids:
        print("[WARN] ChromaDB is empty - nothing to re-enrich. "
              "Run 'python build_database.py' first to populate it.")
        return

    print(f"[INFO] Re-enriching metadata on {len(ids)} existing chunks...")

    updated_ids = []
    updated_metas = []
    unchanged = 0

    for chunk_id, meta, text in zip(ids, metadatas, documents):
        old_meta = dict(meta) if meta else {}
        file_path = old_meta.get("file_path") or old_meta.get("source") or ""
        filename = os.path.basename(file_path)

        new_meta = dict(old_meta)
        new_meta["source"] = infer_source_label(filename)
        new_meta["chapter"] = infer_chapter(filename)
        new_meta["condition"] = infer_condition(text or "", filename)
        new_meta["section_type"] = infer_section_type(text or "")
        new_meta["severity"] = infer_severity(text or "")
        new_meta["route"] = infer_route(text or "")
        new_meta["drug_names"] = extract_drug_names(text or "")
        new_meta["clinical_context"] = infer_clinical_context(text or "")

        # Only push an update if anything actually changed - avoids
        # unnecessary writes when nothing in enrich_metadata moved.
        changed_keys = [
            k for k in (
                "source", "chapter", "condition", "section_type",
                "severity", "route", "drug_names", "clinical_context",
            ) if old_meta.get(k) != new_meta.get(k)
        ]
        if changed_keys:
            updated_ids.append(chunk_id)
            updated_metas.append(new_meta)
        else:
            unchanged += 1

    if not updated_ids:
        print(f"[OK] Nothing to update - all {len(ids)} chunks already "
              f"have current metadata.")
        return

    # Batch the update through the underlying chromadb collection. The
    # langchain Chroma wrapper does not expose a metadata-only update,
    # but the underlying ._collection.update() accepts ids+metadatas
    # without requiring embeddings (Chroma will keep the existing ones).
    BATCH = 500
    for i in range(0, len(updated_ids), BATCH):
        batch_ids = updated_ids[i:i + BATCH]
        batch_metas = updated_metas[i:i + BATCH]
        db._collection.update(ids=batch_ids, metadatas=batch_metas)
        print(f"[INFO]   Updated batch {i // BATCH + 1} "
              f"({len(batch_ids)} chunks)")

    print(f"[OK] Re-enrichment complete: "
          f"{len(updated_ids)} updated, {unchanged} unchanged.")


def clear_database():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)


if __name__ == "__main__":
    main()