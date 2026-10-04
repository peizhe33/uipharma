"""
RxNorm API client for SmartPharma.
Fallback layer when a drug is not found in the local drug_database.

API Documentation: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
- Free to use, no API key required
- Rate limit: ~20 requests/second (generous for our use case)

Usage:
    from rxnorm_client import lookup_drug
    result = lookup_drug("Augmentin")
    # Returns: {"generic_name": "amoxicillin / clavulanate", "ingredients": [...], ...}
    # Returns: None if not found
"""

import requests
from typing import Optional, Dict, List
from functools import lru_cache

# =========================
# Configuration
# =========================
RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
RXCLASS_BASE = "https://rxnav.nlm.nih.gov/REST/rxclass"
TIMEOUT = 10  # seconds — fail fast if API is slow

# =========================
# ATC class code to simple drug class mapping
# ATC Level 1 codes: https://www.whocc.no/atc_ddd_index/
# =========================
ATC_TO_CLASS = {
    "J01": "antibiotic",
    "J02": "antifungal",
    "J04": "antimycobacterial",
    "J05": "antiviral",
    "N02": "analgesic/antipyretic",
    "M01": "NSAID (anti-inflammatory/analgesic)",
    "B01": "anticoagulant",
    "A02B": "proton pump inhibitor",
    "A03F": "antiemetic",
    "A04A": "antiemetic",
    "R03": "bronchodilator",
    "H02": "corticosteroid",
    "R05C": "mucolytic",
    "C02": "antihypertensive",
    "C03": "diuretic",
    "C07": "beta-blocker",
    "C08": "calcium channel blocker",
    "C09": "ACE inhibitor/ARB",
    "C10": "lipid-lowering agent",
    "A10": "antidiabetic",
    "R06": "antihistamine",
}


# =========================
# API Helper Functions
# =========================

def _safe_get(url: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to RxNorm API with error handling."""
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[RxNorm API] Request failed: {e}")
    return None


def _find_rxcui(drug_name: str) -> Optional[str]:
    """
    Step 1: Find the RxNorm Concept ID (RXCUI) for a drug name.
    Searches brand names, generic names, and ingredients.
    """
    data = _safe_get(f"{RXNORM_BASE}/drugs.json", {"name": drug_name})
    if not data:
        return None

    # Navigate the response to find the first valid RXCUI
    drug_group = data.get("drugGroup", {})
    concept_groups = drug_group.get("conceptGroup", [])

    for group in concept_groups:
        properties_list = group.get("conceptProperties", [])
        if properties_list:
            # Return the first RXCUI found
            return properties_list[0].get("rxcui")

    return None


def _get_ingredients(rxcui: str) -> List[str]:
    """
    Step 2: Get the active ingredients for a given RXCUI.
    Uses the 'related' endpoint with tty=IN (Ingredient).
    """
    data = _safe_get(
        f"{RXNORM_BASE}/rxcui/{rxcui}/related.json",
        {"tty": "IN+MIN"}  # IN = single ingredient, MIN = multi-ingredient
    )
    if not data:
        return []

    ingredients = []
    related_group = data.get("relatedGroup", {})
    concept_groups = related_group.get("conceptGroup", [])

    for group in concept_groups:
        properties_list = group.get("conceptProperties", [])
        for prop in properties_list:
            name = prop.get("name", "").lower()
            if name and name not in ingredients:
                ingredients.append(name)

    return ingredients


def _get_generic_name(rxcui: str) -> Optional[str]:
    """
    Get the generic (nonproprietary) name for an RXCUI.
    Uses the related endpoint with tty=IN to get ingredient name.
    """
    data = _safe_get(
        f"{RXNORM_BASE}/rxcui/{rxcui}/related.json",
        {"tty": "IN"}
    )
    if not data:
        return None

    related_group = data.get("relatedGroup", {})
    concept_groups = related_group.get("conceptGroup", [])

    for group in concept_groups:
        properties_list = group.get("conceptProperties", [])
        if properties_list:
            return properties_list[0].get("name", "").lower()

    return None


def _get_drug_class(drug_name: str) -> Optional[str]:
    """
    Step 3: Get the pharmacological class using RxClass API.
    Uses ATC classification (WHO standard).
    """
    data = _safe_get(
        f"{RXCLASS_BASE}/class/byDrugName.json",
        {
            "drugName": drug_name,
            "relaSource": "ATC",
            "rela": "may_treat"
        }
    )

    # Try ATC "has_ingredient" relation as fallback
    if not data or not data.get("rxclassDrugInfoList"):
        data = _safe_get(
            f"{RXCLASS_BASE}/class/byDrugName.json",
            {
                "drugName": drug_name,
                "relaSource": "ATC",
            }
        )

    if not data:
        return None

    info_list = data.get("rxclassDrugInfoList", {})
    drug_infos = info_list.get("rxclassDrugInfo", [])

    for info in drug_infos:
        class_info = info.get("rxclassMinConceptItem", {})
        class_id = class_info.get("classId", "")

        # Match ATC code prefix to our simple class mapping
        for atc_prefix, drug_class in ATC_TO_CLASS.items():
            if class_id.startswith(atc_prefix):
                return drug_class

    return None


# =========================
# Main Public Function (cached)
# =========================

@lru_cache(maxsize=256)
def lookup_drug(drug_name: str) -> Optional[Dict]:
    """
    Look up a drug in the RxNorm API.
    Returns a dict with generic_name, ingredients, and drug_class.
    Returns None if not found.

    Results are cached in memory — same drug name won't hit the API twice.

    Example:
        >>> lookup_drug("Augmentin")
        {
            "generic_name": "amoxicillin",
            "ingredients": ["amoxicillin", "clavulanate"],
            "drug_class": "antibiotic",
            "source": "rxnorm"
        }
    """
    print(f"[RxNorm API] Looking up: '{drug_name}'")

    # Step 1: Find RXCUI
    rxcui = _find_rxcui(drug_name)
    if not rxcui:
        print(f"[RxNorm API] No RXCUI found for '{drug_name}'")
        return None

    print(f"[RxNorm API] Found RXCUI: {rxcui}")

    # Step 2: Get generic name
    generic_name = _get_generic_name(rxcui)

    # Step 3: Get ingredients
    ingredients = _get_ingredients(rxcui)

    # Step 4: Get drug class
    # Try with generic name first (more reliable), then original name
    drug_class = None
    if generic_name:
        drug_class = _get_drug_class(generic_name)
    if not drug_class:
        drug_class = _get_drug_class(drug_name)

    result = {
        "generic_name": generic_name or drug_name.lower(),
        "ingredients": ingredients if ingredients else [generic_name or drug_name.lower()],
        "drug_class": drug_class or "unknown",
        "source": "rxnorm"
    }

    print(f"[RxNorm API] Result: {result}")
    return result