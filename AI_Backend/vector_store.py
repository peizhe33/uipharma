from langchain_chroma import Chroma
from embedding import get_embedding_function
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma")

def get_vector_store():
    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=get_embedding_function()
    )

def build_or_load_store():
    """Load Chroma and wrap it so app.py can use .texts and .search()"""
    db = get_vector_store()
    return ChromaWrapper(db)

def adjust_retrieval_distance(raw_distance: float, metadata: dict, expected: dict) -> float:
    """
    Adjust raw vector distance using clinical metadata.

    Lower distance = better.
    Therefore:
    - subtract for good matches
    - add for bad matches
    """

    adjusted = raw_distance

    chapter = str(metadata.get("chapter", "")).lower()
    condition = str(metadata.get("condition", "")).lower()
    section_type = str(metadata.get("section_type", "")).lower()
    severity = str(metadata.get("severity", "")).lower()
    route = str(metadata.get("route", "")).lower()
    drug_names = str(metadata.get("drug_names", "")).lower()

    expected_chapter = str(expected.get("chapter", "")).lower()
    expected_condition = str(expected.get("condition", "")).lower()
    expected_section = str(expected.get("section_type", "")).lower()
    expected_severity = str(expected.get("severity", "")).lower()
    expected_route = str(expected.get("route", "")).lower()
    expected_drugs = [str(d).lower() for d in expected.get("drug_names", [])]

    # 1. Chapter match
    if expected_chapter:
        if chapter == expected_chapter:
            adjusted -= 6
        elif chapter:
            adjusted += 8

    # 2. Condition match
    if expected_condition:
        if condition == expected_condition:
            adjusted -= 10
        elif condition == "unknown" or condition == "":
            adjusted += 3
        else:
            adjusted += 6

    # 3. Section type match
    if expected_section:
        if section_type == expected_section:
            adjusted -= 3
        elif section_type:
            adjusted += 2

    # 4. Severity match
    if expected_severity:
        if expected_severity in severity:
            adjusted -= 3
        elif severity not in ["", "unknown"]:
            adjusted += 2

    # 5. Route match
    if expected_route:
        if route == expected_route or route == "mixed":
            adjusted -= 2
        elif route not in ["", "unknown"]:
            adjusted += 2

    # 6. Drug match: useful, but must not dominate diagnosis
    for drug in expected_drugs:
        if drug and drug in drug_names:
            adjusted -= 1

    return adjusted

def build_chroma_filter(where: dict | None):
    """
    Convert simple metadata filters into Chroma-compatible filters.

    Input:
        {
            "chapter": "Skin and Soft Tissue Infections",
            "condition": "cellulitis/ssti",
            "section_type": "treatment",
        }

    Output:
        {
            "$and": [
                {"chapter": {"$eq": "Skin and Soft Tissue Infections"}},
                {"condition": {"$eq": "cellulitis/ssti"}},
                {"section_type": {"$eq": "treatment"}},
            ]
        }
    """
    if not where:
        return None

    conditions = []

    for key, value in where.items():
        if value is None or value == "":
            continue

        # If user already passed advanced Chroma filter, keep it
        if key.startswith("$"):
            return where

        conditions.append({key: {"$eq": value}})

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}

class ChromaWrapper:
    def __init__(self, db):
        self._db = db
        # This lets app.py do len(STORE.texts) without crashing
        self.texts = db.get()["documents"] or []

    def search(
        self,
        query: str,
        k: int = 5,
        where: dict | None = None,
        expected: dict | None = None,
        fetch_k: int | None = None,
    ):
        """
        Search Chroma, then optionally rerank results using clinical metadata.

        k = final number of results returned
        fetch_k = number of raw vector results to retrieve before metadata reranking
        expected = expected clinical metadata, e.g.
            {
                "chapter": "Skin and Soft Tissue Infections",
                "condition": "cellulitis/ssti",
                "section_type": "treatment",
                "severity": "mild_or_low",
                "route": "PO",
                "drug_names": ["cloxacillin", "cefalexin"]
            }
        """

        fetch_k = fetch_k or max(k * 4, 20)

        chroma_filter = build_chroma_filter(where)

        if chroma_filter:
            results = self._db.similarity_search_with_score(
                query,
                k=fetch_k,
                filter=chroma_filter
            )
        else:
            results = self._db.similarity_search_with_score(
                query,
                k=fetch_k
            )

        items = []

        for doc, score in results:
            raw_distance = float(score)
            metadata = doc.metadata or {}

            adjusted_distance = raw_distance

            if expected:
                adjusted_distance = adjust_retrieval_distance(
                    raw_distance=raw_distance,
                    metadata=metadata,
                    expected=expected
                )

            items.append({
                "text": doc.page_content,
                "meta": metadata,
                "distance": raw_distance,
                "adjusted_distance": adjusted_distance,
            })

        # Lower distance is better
        items = sorted(items, key=lambda x: x["adjusted_distance"])

        # Keep only final top k
        items = items[:k]

        # Reassign rank after reranking
        for idx, item in enumerate(items, start=1):
            item["rank"] = idx

        return items