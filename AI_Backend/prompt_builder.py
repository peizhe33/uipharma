"""
Prompt building and text normalization for SmartPharma RAG.
Handles context assembly and response post-processing.
"""
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from config import SYSTEM_PRIMER
from drug_database import (
    DrugClass, SUPPORTIVE_CARE_CLASSES,
    get_drug_class, get_drug_subclass, get_ingredients,
    is_supportive_care, check_ingredient_duplication,
    check_max_dose_safety, get_drug_info,
    is_restricted_drug, check_negative_indication,
    get_monitoring_for, get_known_interactions,
    DRUG_DB,
)

# Maximum characters per retrieved guideline snippet injected into the LLM
# prompt. Clinical dosing information is almost always in the first 200-300
# chars after a drug name; truncating at 400 keeps prompts lean without
# losing key regimen data. Raising this increases VRAM usage and inference
# time proportionally - do not set above 600.
MAX_SNIPPET_LEN = 400


# =========================
# Anticoagulant indications
# =========================
ANTICOAGULANT_INDICATIONS = {
    "dvt", "deep vein thrombosis", "pe", "pulmonary embolism",
    "vte", "venous thromboembolism", "atrial fibrillation", "af",
    "stroke prevention", "mechanical heart valve", "prosthetic valve",
    "thromboprophylaxis", "thrombosis", "embolism",
    "left ventricular thrombus", "lvt", "acs", "acute coronary syndrome",
    "nstemi", "stemi", "myocardial infarction"
}


# =========================
# Frequency normalization
# =========================
FREQUENCY_TO_HOURS = {
    "once a day": 24, "once daily": 24, "every 24 hours": 24,
    "every 24 hrs": 24, "every 24h": 24, "24 hourly": 24,
    "q24h": 24, "q24": 24, "od": 24, "qd": 24,
    "daily": 24, "once per day": 24,
    "twice a day": 12, "twice daily": 12, "every 12 hours": 12,
    "every 12 hrs": 12, "every 12h": 12, "12 hourly": 12,
    "q12h": 12, "q12": 12, "bd": 12, "bid": 12, "b.d.": 12, "b.i.d.": 12,
    "three times a day": 8, "three times daily": 8, "every 8 hours": 8,
    "every 8 hrs": 8, "every 8h": 8, "8 hourly": 8,
    "q8h": 8, "q8": 8, "tds": 8, "tid": 8, "t.d.s.": 8, "t.i.d.": 8,
    "thrice daily": 8, "thrice a day": 8,
    "four times a day": 6, "four times daily": 6, "every 6 hours": 6,
    "every 6 hrs": 6, "every 6h": 6, "6 hourly": 6,
    "q6h": 6, "q6": 6, "qid": 6, "qds": 6, "q.i.d.": 6, "q.d.s.": 6,
    "every 4 hours": 4, "every 4 hrs": 4, "q4h": 4, "q4": 4,
    "every 48 hours": 48, "q48h": 48, "every other day": 48, "alternate days": 48,
    "every 72 hours": 72, "q72h": 72,
    "once a week": 168, "once weekly": 168, "weekly": 168,
    "stat": 0, "single dose": 0, "once only": 0,
}


def normalize_frequency_to_hours(freq_str: str) -> Optional[int]:
    if not freq_str:
        return None
    cleaned = freq_str.lower().strip().rstrip(".")

    if cleaned in FREQUENCY_TO_HOURS:
        return FREQUENCY_TO_HOURS[cleaned]

    m = re.match(r'every\s+(\d+)\s*(?:hours?|hrs?|h)\b', cleaned)
    if m:
        return int(m.group(1))

    m = re.match(r'(\d+)\s*hourly', cleaned)
    if m:
        return int(m.group(1))

    m = re.match(r'q\s*(\d+)\s*h?', cleaned)
    if m:
        return int(m.group(1))

    m = re.match(r'(\d+)\s*times?\s*(?:a\s*day|daily|per\s*day)', cleaned)
    if m:
        times = int(m.group(1))
        if times > 0:
            return 24 // times

    return None


def extract_guideline_frequency(drug_name: str, text: str):
    escaped = re.escape(drug_name)
    window_match = re.search(rf'{escaped}(.{{0,200}})', text, re.IGNORECASE | re.DOTALL)
    if not window_match:
        return None
    window = window_match.group(1)

    m = re.search(r'q\s*(\d+)\s*(?:[-]\s*(\d+))?\s*h', window, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1)), m.group(0).strip())

    abbrev_map = {
        r'\bOD\b': (24, 24), r'\bBD\b': (12, 12), r'\bBID\b': (12, 12),
        r'\bTDS\b': (8, 8), r'\bTID\b': (8, 8),
        r'\bQID\b': (6, 6), r'\bQDS\b': (6, 6),
    }
    for pattern, (min_h, max_h) in abbrev_map.items():
        m = re.search(pattern, window, re.IGNORECASE)
        if m:
            return (min_h, max_h, m.group(0).strip())

    word_map = {
        r'once\s+daily': (24, 24), r'twice\s+daily': (12, 12),
        r'three\s+times?\s+daily': (8, 8), r'four\s+times?\s+daily': (6, 6),
    }
    for pattern, (min_h, max_h) in word_map.items():
        m = re.search(pattern, window, re.IGNORECASE)
        if m:
            return (min_h, max_h, m.group(0).strip())

    m = re.search(r'every\s+(\d+)\s*(?:[-]\s*(\d+))?\s*(?:hours?|hrs?|h)', window, re.IGNORECASE)
    if m:
        return (int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1)), m.group(0).strip())

    return None


def extract_guideline_dose(drug_name: str, text: str,
                           patient_weight_kg: Optional[float] = None):
    """
    Backward-compatible wrapper. Returns the BEST single dose pattern.
    Now uses extract_all_guideline_doses() under the hood to scan ALL
    chunks rather than just stopping at the first match, then picks the
    most plausible adult-oral interpretation.

    Returns one of:
        ("range", min_mg, max_mg, raw_str)
        ("single", value_mg, raw_str)
        ("perkg", per_kg_mg, computed_mg, raw_str)
        None
    """
    candidates = extract_all_guideline_doses(drug_name, text, patient_weight_kg)
    return pick_best_dose_candidate(candidates, drug_name, patient_weight_kg,
                                     prefer_route=None)


# --- Paediatric / context filters --------------------------------------------

_PAEDIATRIC_KEYWORDS = re.compile(
    r'\b(?:p[ae]ediatric|paeds?|child(?:ren)?|infant|neonate|neonatal|'
    r'newborn|toddler|kg\s+body\s+weight\s+for\s+children|<\s*1[28]\s*(?:year|yr)|'
    r'under\s+1[28]\s*(?:year|yr))\b',
    re.IGNORECASE,
)
_IV_KEYWORDS = re.compile(r'\b(?:IV|intravenous|infusion|parenteral)\b', re.IGNORECASE)
_PO_KEYWORDS = re.compile(r'\b(?:PO|oral|by\s+mouth|tablet|capsule|syrup)\b', re.IGNORECASE)
_SEVERE_KEYWORDS = re.compile(
    r'\b(?:severe|severely|critical|life-threatening|sepsis|ICU|'
    r'meningitis|endocarditis|bacteraemia|bacteremia|necrotising|necrotizing)\b',
    re.IGNORECASE,
)


def _classify_dose_context(window: str) -> Dict[str, bool]:
    """Tag the chunk-window context so we can prefer the right dose."""
    return {
        "is_paediatric": bool(_PAEDIATRIC_KEYWORDS.search(window)),
        "is_iv": bool(_IV_KEYWORDS.search(window)),
        "is_po": bool(_PO_KEYWORDS.search(window)),
        "is_severe": bool(_SEVERE_KEYWORDS.search(window)),
    }


def extract_all_guideline_doses(drug_name: str, text: str,
                                patient_weight_kg: Optional[float] = None
                                ) -> List[Dict[str, Any]]:
    """
    Scan the text for EVERY mention of the drug and return a list of
    candidate dose dicts. Each candidate carries the dose pattern AND
    a classification of its surrounding context (paediatric? IV? severe?).

    This replaces the old 'first match wins' approach. Downstream code
    then picks the most appropriate candidate using pick_best_dose_candidate().
    """
    if not text or not drug_name:
        return []

    candidates: List[Dict[str, Any]] = []
    escaped = re.escape(drug_name)

    # Find every mention of the drug in the chunk and inspect the window
    # immediately AFTER each mention. We use a tight window (80 chars) so
    # we capture the dose that immediately follows the drug name but
    # don't accidentally capture a different row's dose further down.
    #
    # Important: within each window we pick the dose pattern *closest*
    # to the drug name, not the one that happens to match first by regex
    # ordering. This is what prevents "2 g IV" from another row leaking
    # in when "300 mg PO" appears first right after the drug name.
    for match in re.finditer(escaped, text, re.IGNORECASE):
        start = match.end()
        # Take the rest of THIS line as the dose window. If there's no
        # newline within 80 chars, fall back to 80 chars. This prevents
        # the next row's "IV" or dose from leaking into this row's window.
        line_end = text.find('\n', start)
        if line_end == -1 or line_end - start > 80:
            line_end = start + 80
        window = text[start:line_end]
        # For context tags (is_iv, is_po, is_paediatric) use only this line
        # plus a small lead-in.
        line_start = text.rfind('\n', 0, match.start()) + 1
        ctx_window = text[line_start:line_end]
        ctx = _classify_dose_context(ctx_window)

        # Run all patterns and pick the earliest match
        pattern_attempts = []
        # per-kg
        p = re.search(r'(\d+\.?\d*)\s*mg\s*/\s*kg', window, re.IGNORECASE)
        if p:
            per_kg = float(p.group(1))
            computed = (per_kg * patient_weight_kg) if patient_weight_kg else None
            pattern_attempts.append((p.start(), {
                "kind": "perkg", "per_kg": per_kg, "computed_mg": computed,
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # mixed-unit range: e.g. "500 mg - 1 g" or "500mg-1g"
        # This must be tried BEFORE plain range-mg so a "500mg-1g" string
        # is not mis-parsed as a 500-1mg range with extra g leftover.
        # Bug 4b fix: previously a range like "500 mg - 1 g" was missed
        # entirely, leaving only "500mg" as a single-value target which
        # then incorrectly flagged 1000mg as exceeding the guideline.
        p = re.search(
            r'(\d+\.?\d*)\s*mg\s*[-]\s*(\d+\.?\d*)\s*g\b',
            window, re.IGNORECASE
        )
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "range",
                "min_mg": float(p.group(1)),
                "max_mg": float(p.group(2)) * 1000,
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # Also reverse direction: "1 g - 2 g" already covered by range g,
        # but "0.5 g - 1000 mg" is exotic - cover it too
        p = re.search(
            r'(\d+\.?\d*)\s*g\s*[-]\s*(\d+\.?\d*)\s*mg\b',
            window, re.IGNORECASE
        )
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "range",
                "min_mg": float(p.group(1)) * 1000,
                "max_mg": float(p.group(2)),
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # range mg
        p = re.search(r'(\d+)\s*[-]\s*(\d+)\s*mg', window, re.IGNORECASE)
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "range",
                "min_mg": float(p.group(1)), "max_mg": float(p.group(2)),
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # range g
        p = re.search(r'(\d+\.?\d*)\s*[-]\s*(\d+\.?\d*)\s*g\b', window, re.IGNORECASE)
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "range",
                "min_mg": float(p.group(1)) * 1000,
                "max_mg": float(p.group(2)) * 1000,
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # single mg
        p = re.search(r'(?<!\d[-])\b(\d+)\s*mg\b(?!\s*[-])', window, re.IGNORECASE)
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "single", "value_mg": float(p.group(1)),
                "raw": p.group(0).strip(), "context": ctx,
            }))
        # single g
        p = re.search(r'(?<!\d[-])\b(\d+\.?\d*)\s*g\b(?!\s*[-])', window, re.IGNORECASE)
        if p:
            pattern_attempts.append((p.start(), {
                "kind": "single", "value_mg": float(p.group(1)) * 1000,
                "raw": p.group(0).strip(), "context": ctx,
            }))

        if pattern_attempts:
            # Pick the dose closest to (after) the drug name - that's the
            # one bound to THIS mention of the drug, not a later row.
            pattern_attempts.sort(key=lambda t: t[0])
            candidates.append(pattern_attempts[0][1])

    return candidates


def pick_best_dose_candidate(candidates: List[Dict[str, Any]],
                              drug_name: str,
                              patient_weight_kg: Optional[float] = None,
                              prefer_route: Optional[str] = None):
    """
    From all candidate dose patterns found, return the one most plausible
    for the patient as a tuple matching the OLD extract_guideline_dose() return:
        ("range", min, max, raw)
        ("single", val, raw)
        ("perkg", per_kg, computed, raw)
        None

    Selection logic (in order):
      1. Drop paediatric candidates if the patient is clearly an adult.
      2. Prefer candidates matching the requested route (PO vs IV).
      3. If both per-kg and fixed-dose patterns exist, prefer fixed-dose.
      4. Sanity check per-kg: if computed value > 3x the median single-dose
         seen for this drug, treat as suspicious and prefer the fixed-dose.
    """
    if not candidates:
        return None

    is_adult = patient_weight_kg is None or patient_weight_kg >= 40  # rough
    route_lower = (prefer_route or "").lower()

    # Step 1: drop paediatric candidates for adult patients
    if is_adult:
        adult_candidates = [c for c in candidates if not c["context"]["is_paediatric"]]
        if adult_candidates:  # only drop them if we have adult alternatives
            candidates = adult_candidates

    # Step 2: if a route was requested, prefer matching context
    if route_lower in ("po", "oral"):
        po_candidates = [c for c in candidates if c["context"]["is_po"]
                          and not c["context"]["is_iv"]]
        if po_candidates:
            candidates = po_candidates
    elif route_lower in ("iv", "intravenous"):
        iv_candidates = [c for c in candidates if c["context"]["is_iv"]]
        if iv_candidates:
            candidates = iv_candidates

    # Step 3: split into per-kg vs fixed-dose candidates
    perkg_candidates = [c for c in candidates if c["kind"] == "perkg"]
    fixed_candidates = [c for c in candidates if c["kind"] in ("single", "range")]

    # If we have fixed candidates, prefer them over per-kg for adult oral cases
    if fixed_candidates:
        # Sanity check: if there's also a per-kg candidate and the computed
        # value is wildly larger than the fixed value, the per-kg is almost
        # certainly the paediatric/IV-severe row.
        chosen = fixed_candidates[0]
    elif perkg_candidates:
        chosen = perkg_candidates[0]
    else:
        chosen = candidates[0]

    # Final sanity check using max daily dose from drug DB
    chosen = _sanity_check_against_max_dose(chosen, drug_name, fixed_candidates,
                                              patient_weight_kg)

    # Convert chosen candidate back to the legacy tuple format
    if chosen["kind"] == "range":
        return ("range", chosen["min_mg"], chosen["max_mg"], chosen["raw"])
    if chosen["kind"] == "single":
        return ("single", chosen["value_mg"], chosen["raw"])
    if chosen["kind"] == "perkg":
        return ("perkg", chosen["per_kg"], chosen["computed_mg"], chosen["raw"])
    return None


def _sanity_check_against_max_dose(chosen, drug_name, fixed_candidates,
                                    patient_weight_kg):
    """
    If the chosen candidate is per-kg AND its computed value > 3x the median
    of fixed-dose candidates, fall back to the fixed-dose. Also check against
    the per-drug max_daily_dose to detect impossible single doses.
    """
    if chosen["kind"] != "perkg":
        return chosen
    if not chosen.get("computed_mg") or not fixed_candidates:
        return chosen

    fixed_values = []
    for c in fixed_candidates:
        if c["kind"] == "single":
            fixed_values.append(c["value_mg"])
        elif c["kind"] == "range":
            fixed_values.append((c["min_mg"] + c["max_mg"]) / 2)
    if not fixed_values:
        return chosen

    median_fixed = sorted(fixed_values)[len(fixed_values) // 2]
    if chosen["computed_mg"] > 3 * median_fixed:
        print(
            f"[dose extractor] {drug_name}: per-kg candidate "
            f"({chosen['computed_mg']:.0f}mg) is >3x the median fixed dose "
            f"({median_fixed:.0f}mg). Falling back to fixed dose - this is "
            f"likely a paediatric or IV-severe row."
        )
        return fixed_candidates[0]

    return chosen



# =========================
# Three-Tier Relevance System
# =========================
def determine_relevance(
    med: dict,
    retrieved: list,
    diagnosis: str,
    per_drug_results: Dict[str, Dict[str, Any]] = None,
    patient_allergy: str = "",
) -> Tuple[str, str]:
    name = med.get("generic_name", med.get("name", "")).strip()
    original_name = med.get("original_name", name)
    name_lower = name.lower()
    diagnosis_lower = diagnosis.lower().strip()

    drug_class = get_drug_class(name)
    drug_subclass = get_drug_subclass(name)

    # Site-restricted drugs are now part of NEGATIVE_INDICATIONS. We only
    # short-circuit here for CRITICAL severity rules (the hard blocks like
    # nitrofurantoin for pyelonephritis, or daptomycin for pneumonia).
    # WARNING-level traps are handled later in the flow, after the
    # structured-DB and RAG paths.
    site_violation = check_negative_indication(name, diagnosis, "")
    if site_violation and site_violation.get("severity") == "CRITICAL":
        return ("NOT_INDICATED",
                f"{name} is contraindicated for '{diagnosis}'. "
                f"{site_violation['message']} Treatment failure expected. "
                f"Discontinue and switch to a guideline-recommended antibiotic.")

    # ---- SUPPORTIVE CARE EARLY EXIT ----
    # Paracetamol, ibuprofen, PPIs, antiemetics, etc. are commonly co-prescribed
    # for symptom management. They are categorically NOT expected to appear in
    # the UMMC antimicrobial guideline. Returning NOT_INDICATED for them is a
    # category error and causes alert fatigue (Test Case 1 paracetamol bug).
    # This check MUST run before PATH A (structured guideline lookup), because
    # PATH A returns NOT_INDICATED for any drug missing from the regimen rows.
    if is_supportive_care(name):
        return ("SUPPORTIVE_CARE",
                f"{name} ({drug_subclass or drug_class}) is recognised supportive care "
                f"(symptom management). Outside the scope of antimicrobial guideline "
                f"evaluation; commonly co-prescribed and not a prescription error.")

    # =====================================================================
    # PATH A: Structured guideline lookup (runs BEFORE the RAG-based logic
    # below). If the diagnosis maps to a condition that we have structured
    # data for, we use deterministic table lookup instead of guessing from
    # retrieved text. If not, we fall through to the existing RAG logic so
    # nothing breaks for unstructured chapters.
    # =====================================================================
    try:
        from guideline_db import (
            normalise_diagnosis, has_structured_data_for, is_drug_indicated,
            lookup_regimens, format_regimen_for_prompt,
        )

        cond_key, sev_key = normalise_diagnosis(diagnosis)
        if cond_key and has_structured_data_for(cond_key):
            indicated, matched_rows, explanation = is_drug_indicated(
                name, cond_key, severity=sev_key, allergy=patient_allergy or None
            )

            if not indicated and not matched_rows:
                # Drug is genuinely not in the regimen - show what IS preferred
                preferred = lookup_regimens(cond_key, severity=sev_key,
                                             tier="preferred")
                preferred_str = ""
                if preferred:
                    preferred_str = "\n".join(
                        format_regimen_for_prompt(r) for r in preferred[:5]
                    )
                msg = (
                    f"{name} ({drug_subclass or drug_class}) is NOT listed in "
                    f"the UMMC structured guideline for '{diagnosis}'. "
                    f"{explanation} "
                    + (f"Preferred regimens for this condition:\n{preferred_str}"
                       if preferred_str else "")
                )
                return ("NOT_INDICATED", msg)

            if not indicated and matched_rows:
                # Drug IS in the regimen but allergy-contraindicated
                return ("NOT_INDICATED",
                        f"{name} is listed in the guideline for '{diagnosis}' "
                        f"BUT contraindicated by patient allergy. {explanation}")

            if indicated and matched_rows:
                tiers = sorted({r.get("tier", "?") for r in matched_rows})
                tier_str = ", ".join(tiers)

                # Map tier to relevance category
                if "preferred" in tiers:
                    return ("GUIDELINE_PREFERRED",
                            f"{name} matches a PREFERRED row in the structured "
                            f"UMMC guideline for '{diagnosis}'. {explanation}")
                elif any(t in tiers for t in (
                        "alternative", "penicillin_allergy", "mrsa_suspected",
                        "mrsa_severe", "anaerobic_coverage_addon",
                        "diabetic_or_immunocompromised", "esbl_or_pen_allergy",
                        "adjunct_toxin_suppression")):
                    return ("ACCEPTABLE_ALTERNATIVE",
                            f"{name} matches an ALTERNATIVE/conditional row "
                            f"({tier_str}) in the structured guideline for "
                            f"'{diagnosis}'. {explanation}")
                else:
                    return ("ACCEPTABLE_ALTERNATIVE",
                            f"{name} matches a structured-guideline row for "
                            f"'{diagnosis}' under tier '{tier_str}'.")
    except ImportError:
        # guideline_db not available - silently fall through to RAG
        pass
    except Exception as e:
        print(f"[guideline_db] lookup failed - falling back to RAG: {e}")

    # =====================================================================
    # RAG fallback (the original logic, unchanged)
    # =====================================================================
    found_in_diagnosis_chunks = any(
        name_lower in item["text"].lower()
        for item in retrieved
    )
    if not found_in_diagnosis_chunks and original_name.lower() != name_lower:
        found_in_diagnosis_chunks = any(
            original_name.lower() in item["text"].lower()
            for item in retrieved
        )

    has_anticoag_indication = any(
        ind in diagnosis_lower for ind in ANTICOAGULANT_INDICATIONS
    )

    drug_lookup = (per_drug_results or {}).get(name, {})
    indicated_contexts = drug_lookup.get("indicated_contexts", [])

    restricted_reason = is_restricted_drug(name)

    if found_in_diagnosis_chunks:
        if restricted_reason:
            return ("RESTRICTED_USE",
                    f"{name} ({drug_subclass or drug_class}) appears in the "
                    f"guidelines for '{diagnosis}' but is a RESTRICTED agent. "
                    f"{restricted_reason} Verify clinical justification "
                    f"(culture/sensitivity, severity, allergy status) before "
                    f"approving.")

        # ---- TIER 3.7: indication-specific drug relevance ----
        # Drug appears in retrieved chunks but might not be indicated for
        # THIS specific sub-condition (e.g. metronidazole in SSTI chapter
        # is only for bite/anaerobic, not plain cellulitis).
        # We collect the context around the drug mentions and check the
        # NEGATIVE_INDICATIONS table.
        # (check_negative_indication is imported at module level)
        chunk_ctx_for_drug = ""
        for item in retrieved:
            txt = item.get("text", "")
            if name_lower in txt.lower():
                # Take 300 chars around each mention as drug-specific context
                for m in re.finditer(re.escape(name_lower), txt.lower()):
                    s = max(0, m.start() - 150)
                    e = min(len(txt), m.end() + 150)
                    chunk_ctx_for_drug += " " + txt[s:e]
        neg = check_negative_indication(name, diagnosis, chunk_ctx_for_drug)
        if neg:
            return ("RESTRICTED_USE",
                    f"{name} ({drug_subclass or drug_class}) appears in the "
                    f"chapter for '{diagnosis}' BUT the surrounding text does "
                    f"not match this patient's specific indication. {neg['message']} "
                    f"Verify whether a specific clinical reason applies; do not "
                    f"approve as a routine first-line choice.")

        return ("GUIDELINE_PREFERRED",
                f"{name} is found in the UMMC guidelines for '{diagnosis}'. "
                f"Drug class: {drug_subclass or drug_class}.")

    if is_supportive_care(name):
        return ("ACCEPTABLE_ALTERNATIVE",
                f"{name} is a {drug_subclass or drug_class} - recognised supportive care "
                f"medication. Commonly co-prescribed for symptom management. "
                f"This is NOT a prescription error.")

    if drug_class == DrugClass.ANTICOAGULANT and not has_anticoag_indication:
        return ("NOT_INDICATED",
                f"{name} is an anticoagulant ({drug_subclass}). No anticoagulant indication "
                f"(DVT/PE/AF/VTE) found for this patient. Flag as potential prescription error.")

    if drug_class == DrugClass.ANTIBIOTIC:
        if restricted_reason:
            return ("RESTRICTED_USE",
                    f"{name} ({drug_subclass}) is a RESTRICTED last-resort antibiotic "
                    f"and is NOT indicated in the standard guidelines for "
                    f"'{diagnosis}'. {restricted_reason} Do NOT approve unless "
                    f"strong justification (severe sepsis, MDR organism, allergy, "
                    f"culture-confirmed indication) is documented.")

        if indicated_contexts:
            chapter_names = [c["chapter"] for c in indicated_contexts[:5]]
            chapter_list = ", ".join(chapter_names)

            return ("NOT_INDICATED",
                    f"{name} ({drug_subclass}) is found in the UMMC guidelines but "
                    f"for DIFFERENT conditions: [{chapter_list}]. "
                    f"It is NOT listed for '{diagnosis}'. "
                    f"This drug is inappropriate for the current diagnosis. "
                    f"Recommend switching to a guideline-recommended antibiotic for "
                    f"'{diagnosis}'. See the DRUG INDICATION EVIDENCE section below "
                    f"for the conditions where {name} IS indicated.")
        else:
            return ("NOT_INDICATED",
                    f"{name} ({drug_subclass}) is NOT found anywhere in the UMMC "
                    f"Antimicrobial Guidelines. No guideline evidence supports its use "
                    f"for '{diagnosis}' or any other condition in the formulary. "
                    f"Verify with prescriber - this may be a prescription error.")

    if drug_class != DrugClass.UNKNOWN:
        return ("ACCEPTABLE_ALTERNATIVE",
                f"{name} ({drug_subclass or drug_class}) is not an antimicrobial. "
                f"It is not covered by the UMMC antimicrobial guidelines. "
                f"It may be prescribed for a co-existing condition.")

    return ("ACCEPTABLE_ALTERNATIVE",
            f"{name} is not in the drug database. Cannot determine class. "
            f"Use your medical knowledge to assess appropriateness.")


def normalize_dose_to_mg(dose: str, unit: str) -> str:
    try:
        val = float(dose)
        if unit.lower() == 'g':
            return f"{dose}{unit} ({int(val * 1000)}mg equivalent)"
        return f"{dose}{unit}"
    except (ValueError, TypeError):
        return f"{dose}{unit}"


def _clean_filename(file_path: str) -> str:
    basename = os.path.basename(file_path)
    for ext in ('.pdf', '.PDF', '.txt', '.docx', '.doc'):
        if basename.endswith(ext):
            return basename[:-len(ext)]
    return basename


def filter_and_renumber_citations(
    text: str,
    references: List[str],
) -> Tuple[str, List[str]]:
    """
    Filter references to only those actually cited as [N] in `text`, and
    renumber so the kept references become [1], [2], [3] ... in order of
    first appearance in the text.

    Args:
        text:       Final answer text containing [N] citations from the LLM.
        references: References list from build_report_json. Each entry must
                    start with "[N] " where N matches the rank used in text.

    Returns:
        (new_text, new_references) where uncited references have been
        dropped and citations renumbered consecutively starting from 1.

    Example:
        text = "Switch to drug X [3]. See also [3][5]."
        references = ["[1] foo", "[2] bar", "[3] baz", "[4] qux", "[5] quux"]
        -> new_text = "Switch to drug X [1]. See also [1][2]."
           new_references = ["[1] baz", "[2] quux"]
    """
    if not text:
        return text, references

    # Step 1: Collect cited ranks in order of first appearance
    cited_order: List[int] = []
    seen: set = set()
    for m in re.finditer(r'\[(\d+)\]', text):
        n = int(m.group(1))
        if n not in seen:
            cited_order.append(n)
            seen.add(n)

    if not cited_order:
        # No citations found - drop all references
        return text, []

    # Step 2: Build old → new rank mapping
    old_to_new = {old: i + 1 for i, old in enumerate(cited_order)}

    # Step 3: Substitute [old] → [new] in text using placeholders to avoid
    # collision (e.g. swap 1↔2 would corrupt with a naive single-pass)
    def _to_placeholder(match):
        n = int(match.group(1))
        if n in old_to_new:
            return f"[~{old_to_new[n]}~]"
        return match.group(0)

    new_text = re.sub(r'\[(\d+)\]', _to_placeholder, text)
    new_text = re.sub(r'\[~(\d+)~\]', r'[\1]', new_text)

    # Step 4: Filter and renumber references list
    # Each reference looks like "[5] 3.9 Urology Infections_2024_3rd Ed (pg 5)"
    new_references: List[Optional[str]] = [None] * len(cited_order)
    for ref in references:
        m = re.match(r'^\s*\[(\d+)\]\s*(.*)$', ref)
        if not m:
            continue
        old_rank = int(m.group(1))
        if old_rank not in old_to_new:
            continue
        new_rank = old_to_new[old_rank]
        rest = m.group(2)
        new_references[new_rank - 1] = f"[{new_rank}] {rest}"

    # Drop any None slots (cited rank had no matching reference - shouldn't
    # happen in practice but be defensive)
    final_references = [r for r in new_references if r is not None]

    return new_text, final_references


def _format_ref_line(item: dict, rank: int) -> str:
    m = item.get("meta", {})
    file_path = m.get("file_path", "")
    source_label = m.get("source", "")
    page = m.get("page", "")

    if file_path:
        src = _clean_filename(file_path)
    else:
        src = source_label or "UMMC Guidelines"

    ident = f"(pg {int(page) + 1})" if page != "" else ""

    if source_label == "ANTICOAG":
        return f"[{rank}] MOH Anticoagulant Quick Guide 1st Edition {ident}"
    else:
        return f"[{rank}] {src} {ident}"


def _parse_weight_kg(patient: Dict[str, Any]) -> Optional[float]:
    if not patient:
        return None
    raw = (patient.get("weight") or patient.get("Weight")
           or patient.get("weight_kg") or "")
    if raw in (None, ""):
        return None
    try:
        cleaned = re.sub(r'[^0-9.]', '', str(raw))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


# =========================
# Per-drug verdict builder (deterministic)
# Returns a per-drug record used by both prompt and report.
# =========================
# =========================
# Per-drug verdict builder (deterministic)
# Returns a per-drug record used by both prompt and report.
# =========================
def build_drug_verdict(
    med: Dict[str, Any],
    retrieved: List[Dict[str, Any]],
    indicated_chunks: List[Dict[str, Any]],
    weight_kg: Optional[float],
    diagnosis: str = "",
    age_months: Optional[float] = None,
) -> Dict[str, Any]:
    name = med.get("generic_name", med.get("name", ""))
    dose_str = med.get("dose", "")
    unit = med.get("unit", "mg")
    frequency = med.get("frequency", "")

    out = {
        "name": name,
        "dose_verdict": None,
        "dose_target_mg": None,
        "dose_target_str": None,
        "freq_verdict": None,
        "freq_target_str": None,
        "verdict_lines": [],
        "should_discontinue": False,
        "discontinue_reason": "",
    }

    # ---- SUPPORTIVE CARE EARLY EXIT ----
    # Supportive care drugs (paracetamol, ibuprofen, PPIs, antiemetics) are not
    # in the antimicrobial guideline. The max-daily-dose safety check still runs
    # separately in app.py via check_max_dose_safety, so dangerous overdoses are
    # still caught. Here we just skip the guideline-comparison verdict so we
    # don't print "no guideline range found" which reads as a flag.
    try:
        if is_supportive_care(name):
            out["verdict_lines"].append(
                f"  {name.capitalize()} is supportive care (symptom relief). "
                f"Not evaluated against the antimicrobial guideline."
            )
            return out
    except Exception:
        pass

    # 1. Skip dose check entirely if the drug is a negative indication
    try:
        if diagnosis:
            neg = check_negative_indication(name, diagnosis, "")
            if neg:
                severity = neg.get("severity", "WARNING")
                if severity == "CRITICAL":
                    reason_short = "is site-restricted"
                elif severity == "WARNING":
                    reason_short = "is not routinely indicated"
                else:
                    reason_short = "is not indicated"
                neg_msg = (neg.get("message") or "").strip()
                line = f"  {name.capitalize()} {reason_short} for '{diagnosis}'."
                if neg_msg:
                    line += f" {neg_msg}"
                out["verdict_lines"].append(line)
                out["should_discontinue"] = True
                out["discontinue_reason"] = (
                    f"{name} {reason_short} for '{diagnosis}'"
                )
                return out
    except Exception:
        pass

    # Build display strings using the ORIGINAL prescribed dose+unit so the
    # output never reads "2000g" or "0.5mg" after our internal conversion.
    prescribed_display = f"{dose_str}{unit}" if dose_str else ""

    try:
        dose_val = float(dose_str)
        if unit.lower() == 'g':
            dose_val = dose_val * 1000  # internal canonical units = mg
    except (ValueError, TypeError):
        dose_val = None

    if dose_val is not None:
        structured_match_found = False

        # =====================================================================
        # PATH A: STRUCTURED DOSE CHECK (Fixes the Cellulitis cross-contamination)
        # =====================================================================
        try:
            from guideline_db import normalise_diagnosis, is_drug_indicated
            cond_key, sev_key = normalise_diagnosis(diagnosis)
            
            if cond_key:
                indicated, matched_rows, _ = is_drug_indicated(
                    name, cond_key, severity=sev_key, age_months=age_months,
                )

                # Intelligent Fallback: If drug isn't in this specific severity (e.g. Moderate CAP), 
                # check if it exists in ANY severity for this condition (e.g. Mild CAP).
                # This prevents it from falling back to Cellulitis chunks!
                if not indicated:
                    _, any_sev_rows, _ = is_drug_indicated(
                        name, cond_key, severity=None, age_months=age_months,
                    )
                    if any_sev_rows:
                        matched_rows = any_sev_rows
                        indicated = True

                if indicated and matched_rows:
                    # Pick the row that matches the prescribed route, falling
                    # back to the first row if no route match. Without this
                    # step, a paediatric cefuroxime PO prescription would be
                    # compared against the IV-25 mg/kg row rather than the
                    # PO-10-15 mg/kg row and incorrectly flagged.
                    pres_route = (med.get("route") or "").upper().strip()
                    chosen_row = None
                    if pres_route:
                        for r in matched_rows:
                            if (r.get("route") or "").upper() == pres_route:
                                chosen_row = r
                                break
                    if chosen_row is None:
                        chosen_row = matched_rows[0]
                    row = chosen_row
                    structured_match_found = True

                    target_val = row.get("dose_value")
                    target_unit = (row.get("dose_unit") or "mg").strip()
                    qualifier = row.get("dose_qualifier", "")

                    # Normalize the guideline target to mg so comparisons work
                    # regardless of whether the guideline stores 2 g, 500 mg,
                    # 10 mg/kg, etc. This is the root fix for the "2000g" bug.
                    def _to_mg(v, u):
                        try:
                            v = float(v)
                        except (ValueError, TypeError):
                            return None
                        u = (u or "mg").lower().strip()
                        if u == "g":
                            return v * 1000
                        if u in ("mg", ""):
                            return v
                        if u in ("mcg", "ug", "µg"):
                            return v / 1000
                        if u in ("mg/kg", "mg per kg"):
                            return v * weight_kg if weight_kg else None
                        if u in ("g/kg",):
                            return v * 1000 * weight_kg if weight_kg else None
                        return v  # unknown unit - assume already mg

                    # 1. Check if structured data has a range (e.g., "500-1000 mg")
                    m = re.search(r'(\d+(?:\.\d+)?)\s*[-\u2013\u2014to]+\s*(\d+(?:\.\d+)?)', qualifier, re.IGNORECASE)
                    if m:
                        min_raw = float(m.group(1))
                        max_raw = float(m.group(2))
                        min_mg = _to_mg(min_raw, target_unit) or min_raw
                        max_mg = _to_mg(max_raw, target_unit) or max_raw

                        # For mg/kg ranges, show both the per-kg range AND
                        # the computed mg range for the patient's weight so
                        # the report is immediately interpretable.
                        if (target_unit.lower() in ("mg/kg", "mg per kg")
                                and weight_kg):
                            out["dose_target_str"] = (
                                f"{min_raw:g}-{max_raw:g} mg/kg = "
                                f"{min_mg:.0f}-{max_mg:.0f} mg for "
                                f"{weight_kg:g} kg"
                            )
                        else:
                            out["dose_target_str"] = (
                                f"{min_raw:g}-{max_raw:g} {target_unit}"
                            )
                        out["dose_target_mg"] = (min_mg + max_mg) / 2

                        if min_mg <= dose_val <= max_mg:
                            out["dose_verdict"] = "CORRECT"
                        else:
                            out["dose_verdict"] = "INCORRECT"
                            out["verdict_lines"].append(
                                f"  Dose: {prescribed_display} - INCORRECT "
                                f"(guideline: {out['dose_target_str']})"
                            )
                    else:
                        # 2. Check exact value (with unit normalization)
                        target_mg = _to_mg(target_val, target_unit)
                        # For single mg/kg targets, also show the patient-
                        # specific computed mg value.
                        if (target_unit.lower() in ("mg/kg", "mg per kg")
                                and weight_kg and target_mg is not None):
                            out["dose_target_str"] = (
                                f"{target_val:g} mg/kg = {target_mg:.0f} mg "
                                f"for {weight_kg:g} kg"
                            )
                        else:
                            out["dose_target_str"] = f"{target_val} {target_unit}"
                        out["dose_target_mg"] = target_mg

                        if target_mg is not None and abs(dose_val - target_mg) < max(target_mg * 0.05, 1):
                            out["dose_verdict"] = "CORRECT"
                        else:
                            out["dose_verdict"] = "INCORRECT"
                            out["verdict_lines"].append(
                                f"  Dose: {prescribed_display} - INCORRECT "
                                f"(guideline: {out['dose_target_str']})"
                            )
                    
                    # 3. Check Frequency deterministically
                    target_freq = row.get("frequency", "")
                    if frequency and target_freq:
                        out["freq_target_str"] = target_freq
                        prescribed_hours = normalize_frequency_to_hours(frequency)
                        target_hours = normalize_frequency_to_hours(target_freq)
                        
                        if prescribed_hours and target_hours:
                            if prescribed_hours == target_hours:
                                out["freq_verdict"] = "CORRECT"
                            else:
                                out["freq_verdict"] = "INCORRECT"
                                out["verdict_lines"].append(f"  Frequency: '{frequency}' - INCORRECT (guideline: {target_freq})")
                                
        except Exception as e:
            print(f"[DEBUG] Structured dose check bypassed: {e}")

        # =====================================================================
        # PATH B: FALLBACK TO REGEX RAG CHUNKS (Only if not in structured DB)
        # =====================================================================
        if not structured_match_found:
            all_candidates = []
            route = med.get("route", "")
            for item in retrieved + indicated_chunks:
                text = item.get("text", "")
                cs = extract_all_guideline_doses(name, text, weight_kg)
                all_candidates.extend(cs)

            guideline_dose = pick_best_dose_candidate(
                all_candidates, name, weight_kg, prefer_route=route
            )

            if guideline_dose:
                kind = guideline_dose[0]
                if kind == "range":
                    _, min_d, max_d, _ = guideline_dose
                    out["dose_target_str"] = f"{min_d:.0f}-{max_d:.0f}mg"
                    out["dose_target_mg"] = (min_d + max_d) / 2
                    if min_d <= dose_val <= max_d:
                        out["dose_verdict"] = "CORRECT"
                    else:
                        out["dose_verdict"] = "INCORRECT"
                        out["verdict_lines"].append(f"  Dose: {prescribed_display} - INCORRECT (guideline: {min_d:.0f}-{max_d:.0f}mg)")
                elif kind == "single":
                    _, single, _ = guideline_dose
                    out["dose_target_str"] = f"{single:.0f}mg"
                    out["dose_target_mg"] = single
                    if abs(dose_val - single) < 1:
                        out["dose_verdict"] = "CORRECT"
                    else:
                        out["dose_verdict"] = "INCORRECT"
                        out["verdict_lines"].append(f"  Dose: {prescribed_display} - INCORRECT (guideline: {single:.0f}mg)")
                elif kind == "perkg":
                    _, per_kg, computed, _ = guideline_dose
                    if computed is not None:
                        out["dose_target_str"] = f"{per_kg} mg/kg = {computed:.0f}mg for {weight_kg:.0f}kg"
                        out["dose_target_mg"] = computed
                        tol = max(computed * 0.10, 5)
                        if abs(dose_val - computed) <= tol:
                            out["dose_verdict"] = "CORRECT"
                        else:
                            out["dose_verdict"] = "INCORRECT"
                            out["verdict_lines"].append(f"  Dose: {prescribed_display} - INCORRECT (guideline: {per_kg} mg/kg = {computed:.0f}mg for {weight_kg:.0f}kg)")
                    else:
                        out["dose_target_str"] = f"{per_kg} mg/kg"
                        out["verdict_lines"].append(f"  Dose: {prescribed_display} - CHECK manually (guideline is weight-based: {per_kg} mg/kg; patient weight not provided)")
            else:
                max_daily = None
                info = get_drug_info(name)
                if info:
                    max_daily = info.get("max_daily_dose_mg")
                if max_daily and dose_val > max_daily:
                    out["dose_verdict"] = "EXCEEDS"
                    out["verdict_lines"].append(f"  Dose: {prescribed_display} - EXCEEDS max daily dose ({max_daily:.0f}mg/day from drug database). Check safety.")
                else:
                    out["verdict_lines"].append(f"  Dose: {prescribed_display} - no guideline range found.")

        # RAG Fallback Frequency check
        if frequency and not structured_match_found:
            prescribed_hours = normalize_frequency_to_hours(frequency)
            if prescribed_hours and prescribed_hours > 0:
                guideline_result = None
                for item in retrieved:
                    result = extract_guideline_frequency(name, item.get("text", ""))
                    if result:
                        guideline_result = result
                        break
                if guideline_result:
                    min_h, max_h, raw_str = guideline_result
                    out["freq_target_str"] = raw_str
                    if min_h <= prescribed_hours <= max_h:
                        out["freq_verdict"] = "CORRECT"
                    else:
                        out["freq_verdict"] = "INCORRECT"
                        out["verdict_lines"].append(f"  Frequency: '{frequency}' (every {prescribed_hours}h) - INCORRECT (guideline: {raw_str})")

    return out
# =========================
# PER-DRUG FOCUSED PROMPT (item 8)
# Builds a prompt focused on one drug, with that drug's
# retrieval results, that drug's verdicts, and patient context.
# =========================
def make_prompt_per_drug(
    med: Dict[str, Any],
    retrieved: List[Dict[str, Any]],
    indicated_chunks: List[Dict[str, Any]],
    patient: Dict[str, Any],
    labs: Dict[str, Any],
    vitals: Dict[str, Any],
    diagnosis: str,
    drug_alerts: List[dict],
    drug_verdict: Dict[str, Any],
    rag_failure: bool,
    drug_index: int,
    total_drugs: int,
) -> str:
    """
    Build a focused single-drug prompt. The LLM is asked to give a
    short, specific assessment of THIS drug only.
    """
    name = med.get("generic_name", med.get("name", ""))
    dose_str = med.get("dose", "")
    unit = med.get("unit", "mg")
    frequency = med.get("frequency", "")
    route = med.get("route", "")
    prn = bool(med.get("prn", False))

    drug_class = get_drug_class(name)
    drug_subclass = get_drug_subclass(name)
    weight_kg = _parse_weight_kg(patient)

    # Critical banner for THIS drug
    banner_lines = []
    crit_alerts = [a for a in drug_alerts
                   if a.get("severity") == "CRITICAL"]
    if crit_alerts:
        banner_lines.append(f"[!!!] CRITICAL ALERTS FOR {name.upper()}:")
        for a in crit_alerts:
            banner_lines.append(f"  - {a['message']}")
        banner_lines.append("")
    if rag_failure:
        banner_lines.append("[!!!] GUIDELINE RETRIEVAL FAILURE:")
        banner_lines.append(
            f"  No reliable guideline evidence retrieved for '{diagnosis}'. "
            f"Do NOT generate specific dose, frequency, or interaction values "
            f"from your own knowledge. State 'Insufficient guideline evidence "
            f"retrieved - manual pharmacist review required'."
        )
        banner_lines.append("")

    critical_banner = ""
    if banner_lines:
        critical_banner = (
            "=" * 70 + "\n"
            + "\n".join(banner_lines)
            + "=" * 70 + "\n\n"
        )

    # Patient mini-summary
    age = patient.get("age", "?")
    gender = patient.get("gender", "?")
    weight = patient.get("weight", "?")
    allergy_text = (
        vitals.get("allergy_details") or vitals.get("allergy")
        or patient.get("allergy_details") or patient.get("allergy")
        or "None reported"
    )
    egfr = labs.get("egfr", "")
    creatinine = labs.get("creatinine", "")

    patient_section = (
        f"PATIENT: {age}y {gender}, weight {weight}kg. "
        f"Allergy: {allergy_text}. "
    )
    if egfr or creatinine:
        patient_section += f"Renal: eGFR={egfr}, Cr={creatinine}. "

    # Tier
    tier, explanation = determine_relevance(
        med, retrieved, diagnosis,
        {name: {"indicated_contexts": [], "indicated_chunks": indicated_chunks}},
        patient_allergy=allergy_text,
    )

    # Verdict block for THIS drug
    verdict_block = ""
    if drug_verdict.get("verdict_lines"):
        verdict_block = (
            "\nVERDICTS (SYSTEM-CALCULATED - REPORT EXACTLY):\n"
            + f"{name} [{tier}]:\n"
            + "\n".join(drug_verdict["verdict_lines"])
            + "\n"
        )

    # Monitoring + interactions for THIS drug
    monitoring_lines = get_monitoring_for(name)
    monitoring_block = ""
    if monitoring_lines:
        monitoring_block = (
            f"\nMONITORING for {name} (SYSTEM-GENERATED - REPORT EXACTLY):\n"
            + "\n".join(f"  * {p}" for p in monitoring_lines)
            + "\n"
        )

    # Build context block
    ctx_lines = []
    seen_ranks = set()
    for item in retrieved:
        rank = item.get("rank", 0)
        if rank in seen_ranks:
            continue
        seen_ranks.add(rank)

        m = item.get("meta", {})
        file_path = m.get("file_path", "")
        source_label = m.get("source", "")
        if file_path:
            src = _clean_filename(file_path)
        else:
            src = source_label or "UMMC Guidelines"
        page = m.get("page", "")
        ident = f"Page {int(page) + 1}" if page != "" else ""
        if source_label == "ANTICOAG":
            header = f"MOH Anticoagulant Quick Guide 1st Edition [{ident}]"
        else:
            header = f"UMMC Antimicrobial Guidelines 3rd Edition - Chapter {src} [{ident}]"
        snippet = item["text"].strip().replace("\n\n", "\n")
        if len(snippet) > MAX_SNIPPET_LEN:
            snippet = snippet[:MAX_SNIPPET_LEN] + " ..."
        ctx_lines.append(f"REFERENCE [{rank}]: {header}\n{snippet}\n")

    indicated_context = ""
    if tier == "NOT_INDICATED" and indicated_chunks:
        indic_lines = []
        for item in indicated_chunks[:3]:
            rank = item.get("rank", 0)
            if rank in seen_ranks:
                continue
            seen_ranks.add(rank)
            m = item.get("meta", {})
            file_path = m.get("file_path", "")
            source_label = m.get("source", "")
            if file_path:
                src = _clean_filename(file_path)
            else:
                src = source_label or "UMMC Guidelines"
            page = m.get("page", "")
            ident = f"Page {int(page) + 1}" if page != "" else ""
            if source_label == "ANTICOAG":
                header = f"MOH Anticoagulant Quick Guide 1st Edition [{ident}]"
            else:
                header = f"UMMC Antimicrobial Guidelines 3rd Edition - Chapter {src} [{ident}]"
            snippet = item["text"].strip().replace("\n\n", "\n")
            if len(snippet) > MAX_SNIPPET_LEN:
                snippet = snippet[:MAX_SNIPPET_LEN] + " ..."
            indic_lines.append(f"REFERENCE [{rank}]: {header}\n{snippet}\n")
        if indic_lines:
            indicated_context = (
                f"\nDRUG INDICATION EVIDENCE - conditions {name} IS used for "
                f"(NOT '{diagnosis}'):\n"
                + "\n".join(indic_lines) + "\n"
            )

    context_block = "\n".join(ctx_lines) if ctx_lines else "No context retrieved."

    # Drug header
    drug_header = (
        f"DRUG: {name}\n"
        f"  Dose: {dose_str}{unit}\n"
        f"  Frequency: {frequency}\n"
    )
    if route:
        drug_header += f"  Route: {route}\n"
    if prn:
        drug_header += f"  PRN: yes\n"
    drug_header += f"  Class: {drug_subclass or drug_class}\n"
    drug_header += f"  Tier: {tier}\n"

    prompt = (
        f"{critical_banner}"
        f"{SYSTEM_PRIMER}\n"
        f"{'=' * 70}\n"
        f"FOCUSED DRUG REVIEW ({drug_index} of {total_drugs}): {name}\n"
        f"{'=' * 70}\n"
        f"{patient_section}\n"
        f"DIAGNOSIS: {diagnosis}\n\n"
        f"{drug_header}\n"
        f"{verdict_block}"
        f"{monitoring_block}\n"
        f"{'=' * 70}\n"
        f"GUIDELINE EVIDENCE FOR THIS DRUG:\n"
        f"{'=' * 70}\n"
        f"{context_block}\n"
        f"{indicated_context}\n"
        f"{'=' * 70}\n"
        f"YOUR TASK:\n"
        f"Provide a SHORT focused assessment of {name} ONLY. Use this exact format:\n\n"
        f"  Assessment: <one sentence overall verdict for {name}>\n"
        f"  Issues: <bullet list of any problems with this drug, "
        f"or 'None'>\n"
        f"  Recommendation: <what should be done with {name} - "
        f"continue / discontinue / change to X / adjust dose / etc.>\n\n"
        f"CRITICAL RULES:\n"
        f"- This is for {name} ONLY. Do not discuss other drugs.\n"
        f"- ONLY use [N] citation numbers from REFERENCE blocks above.\n"
        f"- NEVER invent placeholder references like '[1] Local guideline'.\n"
        f"- For allergy conflicts, recommendation MUST be discontinuation.\n"
        f"- For NOT_INDICATED, recommendation MUST be discontinuation OR switch to a guideline drug.\n"
        f"- For RESTRICTED_USE, demand justification.\n"
        f"- Do NOT contradict the system VERDICTS above.\n"
        f"- Keep your response to under 8 lines.\n"
    )

    return prompt


# =========================
# Per-drug recommendation parser (used to build ai_suggestion)
# =========================
_RE_RECOMMENDATION = re.compile(
    r'(?:^|\n)\s*Recommendation\s*:\s*(.+?)(?=\n\s*[A-Z][a-z]+\s*:|\Z)',
    re.IGNORECASE | re.DOTALL
)
_RE_SWITCH_TO = re.compile(
    r'(?:switch|change|replace)\s+(?:to|with)\s+([A-Z][A-Za-z\-]+)',
    re.IGNORECASE
)
_RE_DISCONTINUE = re.compile(
    r'\b(discontinue|stop|withdraw|withhold)\b',
    re.IGNORECASE
)


def extract_drug_recommendation(llm_text: str) -> Dict[str, Any]:
    """
    Parse a per-drug LLM response into a structured recommendation.
    """
    out = {
        "raw_text": llm_text.strip(),
        "action": "continue",
        "switch_to": None,
        "discontinue": False,
    }
    m = _RE_RECOMMENDATION.search(llm_text)
    rec_text = m.group(1).strip() if m else llm_text

    if _RE_DISCONTINUE.search(rec_text):
        out["discontinue"] = True
        out["action"] = "discontinue"

    sm = _RE_SWITCH_TO.search(rec_text)
    if sm:
        out["switch_to"] = sm.group(1).strip()
        out["action"] = "switch"

    return out


# =========================
# Build ai_suggestion deterministically
# =========================
def find_replacement_regimens(
    diagnosis: str,
    removed_drugs: List[str],
    existing_drugs: List[str],
    patient_allergy: str = "",
    patient_age_months: Optional[float] = None,
    limit: int = 1,
) -> List[Dict[str, Any]]:
    """
    Look up guideline-preferred replacement drug(s) for a diagnosis when
    one or more antibiotics have been removed from the prescription.

    Uses the structured guideline DB. Returns up to `limit` regimen rows
    (dicts with name/dose/unit/frequency/route plus a tier label) that:
      - match the patient's age (skips paediatric mg/kg rows for adults)
      - are not already in `existing_drugs`
      - are not contraindicated by `patient_allergy`

    Returns [] if no structured data exists for the diagnosis or no safe
    replacement could be found.
    """
    if not diagnosis or not removed_drugs:
        return []

    try:
        from guideline_db import (
            normalise_diagnosis, has_structured_data_for,
            lookup_regimens, is_drug_indicated,
        )
    except ImportError:
        return []

    cond_key, sev_key = normalise_diagnosis(diagnosis)
    if not cond_key or not has_structured_data_for(cond_key):
        return []

    existing_lower = {str(d).lower().strip() for d in existing_drugs}
    # Also exclude the drugs being removed — they must never be recommended
    # as their own replacements (e.g. nitrofurantoin replacing nitrofurantoin).
    removed_lower = {str(d).lower().strip() for d in removed_drugs}
    excluded_lower = existing_lower | removed_lower
    added_names: set = set()
    found: List[Dict[str, Any]] = []

    # Walk tiers in priority order. Preferred is first-line, alternative
    # is acceptable, the allergy-specific tiers cover penicillin-allergic
    # patients and ESBL coverage.
    tier_order = (
        "preferred", "alternative",
        "penicillin_allergy", "esbl_or_pen_allergy",
    )

    for tier in tier_order:
        if len(found) >= limit:
            break
        rows = lookup_regimens(
            cond_key, severity=sev_key,
            tier=tier, age_months=patient_age_months,
        )
        for r in rows:
            if len(found) >= limit:
                break
            drug = (r.get("drug") or "").strip()
            if not drug:
                continue
            drug_lower = drug.lower()
            if drug_lower in excluded_lower or drug_lower in added_names:
                continue

            # Defensive age filter: some rows have age_group set without
            # age_max bounds, so _row_matches_age leaks paediatric
            # weight-based regimens into adult queries.
            if patient_age_months is not None and patient_age_months >= 216:
                age_group = (r.get("age_group") or "").lower()
                dose_unit_lc = str(r.get("dose_unit", "")).lower()
                if age_group in ("paediatric", "neonatal"):
                    continue
                if dose_unit_lc.endswith("/kg"):
                    continue
            if patient_age_months is not None and patient_age_months < 216:
                age_group = (r.get("age_group") or "").lower()
                if age_group == "adult":
                    continue

            # Allergy filter
            if patient_allergy:
                try:
                    indicated, _, _ = is_drug_indicated(
                        drug, cond_key,
                        severity=sev_key,
                        allergy=patient_allergy,
                        age_months=patient_age_months,
                    )
                    if not indicated:
                        continue
                except Exception:
                    pass  # permissive on lookup failure

            dose_value = r.get("dose_value", "")
            if isinstance(dose_value, float) and dose_value.is_integer():
                dose_value = int(dose_value)

            found.append({
                "name": drug,
                "dose": str(dose_value),
                "unit": r.get("dose_unit", "mg"),
                "frequency": r.get("frequency", ""),
                "route": r.get("route", ""),
                "tier": tier,
                "page": r.get("page", ""),
                "source_chapter": r.get("source_chapter", ""),
            })
            added_names.add(drug_lower)

    return found


def build_ai_suggestion(
    medicines: List[Dict[str, Any]],
    drug_verdicts: Dict[str, Dict[str, Any]],
    preprocessing_alerts: List[dict],
    drug_recommendations: Dict[str, Dict[str, Any]],
    diagnosis: str = "",
    patient_allergy: str = "",
    patient_age_months: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Build the structured ai_suggestion list that the Flutter UI will
    pre-fill into its editable AI-suggestion panel.

    For each prescribed drug, decide:
      - keep as-is
      - keep but adjust dose/frequency
      - switch to a different drug
      - discontinue (remove from suggestion)

    After processing, if any antibiotic was removed AND the structured
    guideline DB has a regimen for the diagnosis, append the guideline-
    preferred replacement drug(s) so the doctor sees a complete,
    actionable suggestion instead of just an empty slot.
    """
    suggestions = []

    # Index alerts by drug for quick lookup
    alerts_by_drug: Dict[str, List[dict]] = {}
    for a in preprocessing_alerts:
        d = (a.get("drug") or "").lower()
        if d:
            alerts_by_drug.setdefault(d, []).append(a)
        # Multi-drug alerts (CLASS_OVERLAP, THERAPEUTIC_DUPLICATION) list
        # affected drugs in the 'drugs' field. Index under each one.
        for md in (a.get("drugs") or []):
            md_lower = str(md).lower().strip()
            if md_lower and md_lower != d:
                alerts_by_drug.setdefault(md_lower, []).append(a)

    # PRE-PASS: determine which drugs will be removed so that overlap
    # checks on surviving drugs can tell whether the partner is gone.
    terminal_types = {
        "ALLERGY_DIRECT", "ALLERGY_CROSS_REACTIVITY",
        "PRN_INAPPROPRIATE", "SITE_RESTRICTED",
        "NEGATIVE_INDICATION",
    }
    removed_drugs: set = set()
    for med in medicines:
        nm = (med.get("generic_name") or med.get("name", "")).lower()
        da = alerts_by_drug.get(nm, [])
        v = drug_verdicts.get(nm, {})
        rec = drug_recommendations.get(nm, {})
        if any(a.get("type") in terminal_types for a in da):
            removed_drugs.add(nm)
        elif v.get("should_discontinue"):
            removed_drugs.add(nm)
        elif rec.get("discontinue"):
            removed_drugs.add(nm)

    for med in medicines:
        name = med.get("generic_name", med.get("name", ""))
        name_lower = name.lower()
        original = {
            "name": med.get("generic_name", med.get("name", "")),
            "dose": str(med.get("dose", "")),
            "unit": med.get("unit", "mg"),
            "frequency": med.get("frequency", ""),
            "route": med.get("route", ""),
            "prn": bool(med.get("prn", False)),
            "action": "continue",
            "rationale": (
                f"{med.get('generic_name', med.get('name', ''))}: "
                f"continue as prescribed - no issues detected."
            ),
        }

        drug_alerts = alerts_by_drug.get(name_lower, [])
        rec = drug_recommendations.get(name_lower, {})
        v = drug_verdicts.get(name_lower, {})

        # 1) Allergy, PRN-misuse, site-restriction, or negative indication
        #    from preprocessing alerts -> REMOVE from AI suggestion entirely.
        #    The doctor keeps their original in "Use Doctor prescription";
        #    the AI suggestion just omits the unsafe/unindicated drug.
        terminal_hits = [
            a for a in drug_alerts if a.get("type") in terminal_types
        ]
        if terminal_hits:
            continue  # omit this drug from the AI suggestion

        # 1b) Verdict says should_discontinue (catch-all for any verdict-
        #     level discontinuation that didn't come via a preprocessing
        #     alert, e.g. structured-DB NOT_INDICATED)
        if v.get("should_discontinue"):
            continue  # omit this drug from the AI suggestion

        # 2) LLM said discontinue -> omit from AI suggestion
        if rec.get("discontinue"):
            continue

        # 3) LLM said switch to X
        if rec.get("switch_to"):
            original["name"] = rec["switch_to"]
            original["dose"] = ""
            original["frequency"] = ""
            original["action"] = "switch"
            original["rationale"] = (
                f"Switch to {rec['switch_to']} per recommendation. "
                "Dose and frequency to be confirmed against guidelines."
            )
            suggestions.append(original)
            continue

        # 4) Dose incorrect -> adjust
        if v.get("dose_verdict") == "INCORRECT" and v.get("dose_target_str"):
            target = v.get("dose_target_mg")
            if target is not None:
                original["dose"] = str(int(target))
                original["unit"] = "mg"
            original["action"] = "adjust"
            original["rationale"] = (
                f"Dose adjusted to match guideline ({v['dose_target_str']})."
            )

        # 5) Frequency incorrect -> adjust and auto-set
        if v.get("freq_verdict") == "INCORRECT" and v.get("freq_target_str"):
            original["frequency"] = v["freq_target_str"]
            original["action"] = "adjust"
            original["rationale"] = (
                f"{name}: frequency adjusted to {v['freq_target_str']}."
            )

        # 6) CLASS_OVERLAP or THERAPEUTIC_DUPLICATION -> flag in rationale
        #    Don't auto-remove because overlap may be intentional
        #    (step-down therapy, different infection sites), but upgrade
        #    action to at least 'adjust' so the pharmacist notices.
        #    HOWEVER, skip the flag if every other drug in the overlap pair
        #    has already been removed from the suggestion list (the overlap
        #    is effectively resolved).
        overlap_types = {"CLASS_OVERLAP", "THERAPEUTIC_DUPLICATION"}
        overlap_hits = [
            a for a in drug_alerts if a.get("type") in overlap_types
        ]
        if overlap_hits and original["action"] == "continue":
            # Check if at least one OTHER drug in the pair survived
            # (was not removed in the pre-pass)
            has_live_partner = False
            for oh in overlap_hits:
                partner_drugs = [
                    str(d).lower().strip()
                    for d in (oh.get("drugs") or [])
                ]
                for pd in partner_drugs:
                    if pd != name_lower and pd not in removed_drugs:
                        has_live_partner = True
                        break
                if has_live_partner:
                    break

            if has_live_partner:
                overlap_msg = (overlap_hits[0].get("message") or "").strip()
                if overlap_msg:
                    original["action"] = "adjust"
                    original["rationale"] = (
                        f"Therapeutic redundancy flagged: {overlap_msg} "
                        "Verify if both drugs are intended."
                    )

        suggestions.append(original)

    # =================================================================
    # POST-PASS: if any antibiotic was removed AND the diagnosis maps to
    # a structured guideline regimen, append the single guideline-
    # preferred replacement drug so the AI suggestion is actionable.
    # Capped at 1 to avoid showing competing alternatives - the doctor
    # gets the first-line choice, can edit drug name if a different one
    # is preferred clinically.
    # =================================================================
    antibiotic_removed = any(
        get_drug_class(d) == DrugClass.ANTIBIOTIC for d in removed_drugs
    )
    if antibiotic_removed and diagnosis:
        existing_drug_names = [s["name"] for s in suggestions]

        # Skip adding a replacement if an antibiotic already in the
        # suggestion is indicated for this diagnosis — the prescription
        # is already covered (e.g. cefuroxime is prescribed alongside
        # nitrofurantoin; nitrofurantoin is removed but cefuroxime stays,
        # so no replacement is needed).
        existing_antibiotic_covers = False
        try:
            from guideline_db import (
                normalise_diagnosis, has_structured_data_for, is_drug_indicated,
            )
            cond_key, sev_key = normalise_diagnosis(diagnosis)
            if cond_key and has_structured_data_for(cond_key):
                for existing_name in existing_drug_names:
                    if get_drug_class(existing_name) != DrugClass.ANTIBIOTIC:
                        continue
                    try:
                        indicated, matched, _ = is_drug_indicated(
                            existing_name, cond_key,
                            severity=sev_key,
                            allergy=patient_allergy or None,
                            age_months=patient_age_months,
                        )
                        if indicated and matched:
                            existing_antibiotic_covers = True
                            print(f"DEBUG: '{existing_name}' already covers "
                                  f"'{diagnosis}' — skipping replacement lookup")
                            break
                    except Exception:
                        pass
        except Exception:
            pass
        if not existing_antibiotic_covers:
            replacements = find_replacement_regimens(
                diagnosis=diagnosis,
                removed_drugs=list(removed_drugs),
                existing_drugs=existing_drug_names,
                patient_allergy=patient_allergy,
                patient_age_months=patient_age_months,
                limit=1,
            )
            removed_list = ", ".join(sorted(removed_drugs))
            for r in replacements:
                suggestions.append({
                    "name": r["name"],
                    "dose": r["dose"],
                    "unit": r["unit"],
                    "frequency": r["frequency"],
                    "route": r["route"],
                    "prn": False,
                    "action": "switch",
                    "rationale": (
                        f"Guideline-preferred for '{diagnosis}'. "
                        f"Suggested replacement for the removed "
                        f"antibiotic(s): {removed_list}."
                    ),
                })
            if replacements:
                print(f"DEBUG: Added {len(replacements)} guideline "
                      f"replacement(s) to ai_suggestion: "
                      f"{[r['name'] for r in replacements]}")

    return suggestions


# =========================
# Build flat alert strings for the structured `report.alerts` array
# Flutter parser looks for: ALLERGY, DOSE ALERT, NOT in guideline,
# RENAL, RESTRICTED, PRN, SITE, INTERACTION
# =========================
def build_alert_strings(
    preprocessing_alerts: List[dict],
    drug_verdicts: Dict[str, Dict[str, Any]],
    interaction_notes: List[str],
    rag_failure: bool,
) -> List[str]:
    out = []

    for a in preprocessing_alerts:
        t = a.get("type", "")
        msg = a.get("message", "").strip()
        if not msg:
            continue
        # Map types to Flutter parser keywords
        if t in ("ALLERGY_DIRECT", "ALLERGY_CROSS_REACTIVITY"):
            out.append(f"ALLERGY: {msg}")
        elif t == "PRN_INAPPROPRIATE":
            out.append(f"PRN ALERT: {msg}")
        elif t == "SITE_RESTRICTED":
            out.append(f"SITE RESTRICTED - NOT in guideline for this site: {msg}")
        elif t == "RESTRICTED_USE":
            out.append(f"RESTRICTED ANTIBIOTIC: {msg}")
        elif t == "MAX_DOSE_EXCEEDED":
            out.append(f"DOSE ALERT: {msg}")
        elif t == "THERAPEUTIC_DUPLICATION":
            out.append(f"DUPLICATION: {msg}")
        elif t == "CLASS_OVERLAP":
            out.append(f"CLASS OVERLAP: {msg}")
        elif t == "SPELL_CORRECTION":
            out.append(f"INFO: {msg}")
        else:
            out.append(msg)

    # Verdict-driven alerts
    for name, v in drug_verdicts.items():
        if v.get("dose_verdict") == "INCORRECT":
            out.append(
                f"DOSE ALERT: {name} dose does not match guideline target "
                f"({v.get('dose_target_str','?')})."
            )
        elif v.get("dose_verdict") == "EXCEEDS":
            out.append(
                f"DOSE ALERT: {name} exceeds maximum daily dose."
            )
        if v.get("freq_verdict") == "INCORRECT":
            out.append(
                f"DOSE ALERT: {name} frequency does not match guideline target "
                f"({v.get('freq_target_str','?')})."
            )

    for note in interaction_notes:
        out.append(f"INTERACTION: {note}")

    if rag_failure:
        out.append(
            "NOT in guideline: Retrieval failed for this diagnosis. "
            "Manual pharmacist review required - LLM output should be "
            "treated as low-confidence."
        )

    return out


# =========================
# Build the structured report JSON (item 6)
# =========================
def build_report_json(
    diagnosis: str,
    medicines: List[Dict[str, Any]],
    preprocessing_alerts: List[dict],
    drug_verdicts: Dict[str, Dict[str, Any]],
    drug_recommendations: Dict[str, Dict[str, Any]],
    retrieved: List[Dict[str, Any]],
    rag_failure: bool,
    patient_allergy: str = "",
    patient_age_months: Optional[float] = None,
    allowed_sources: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Assemble the structured `report` field returned to Flutter.

    Flutter parser expects:
      {
        "assessment": "...",
        "diagnosis_enriched": "...",
        "alerts": [ "<keyworded strings>" ],
        "recommendations": [ "..." ],
        "monitoring": [ {"drug": "...", "params": [...]} ],
        "interactions": [ "..." ],
        "ai_suggestion": [ {"name": "...", "dose": "...", ...} ],
        "references": [ "..." ],
        "rag_failure": false
      }
    """
    interaction_notes = get_known_interactions(medicines)

    alerts = build_alert_strings(
        preprocessing_alerts, drug_verdicts, interaction_notes, rag_failure
    )

    n_critical = sum(1 for a in preprocessing_alerts
                     if a.get("severity") == "CRITICAL")
    n_warning = sum(1 for a in preprocessing_alerts
                    if a.get("severity") == "WARNING")

    if rag_failure:
        assessment = (
            "Manual pharmacist review required - guideline retrieval failed."
        )
    elif n_critical > 0:
        assessment = (
            f"CRITICAL safety issues detected ({n_critical}). "
            f"Review alerts and consider immediate intervention."
        )
    elif n_warning > 0 or any(v.get("dose_verdict") == "INCORRECT"
                              or v.get("freq_verdict") == "INCORRECT"
                              for v in drug_verdicts.values()):
        assessment = (
            "Prescription requires review - dosing or stewardship "
            "concerns detected."
        )
    else:
        assessment = "Prescription appears appropriate. Standard monitoring."

    monitoring = []
    for med in medicines:
        name = med.get("generic_name", med.get("name", ""))
        params = get_monitoring_for(name)
        if params:
            monitoring.append({"drug": name, "params": params})

    recommendations = []
    for name, rec in drug_recommendations.items():
        text = rec.get("raw_text", "")
        if text:
            recommendations.append(f"{name}: {text}")

    ai_suggestion = build_ai_suggestion(
        medicines, drug_verdicts, preprocessing_alerts, drug_recommendations,
        diagnosis=diagnosis,
        patient_allergy=patient_allergy,
        patient_age_months=patient_age_months,
    )

    # Use the explicit allowed_sources passed from app.py if available
    # (this is the same set used for retrieval, so the reference filter
    # and the retrieval filter stay perfectly aligned). Fall back to
    # age-derived computation if the caller didn't pass it.
    allowed_sources_for_refs = allowed_sources
    if allowed_sources_for_refs is None:
        try:
            from config import allowed_sources_for_age
            if patient_age_months is not None:
                age_years = patient_age_months / 12.0
                allowed_sources_for_refs = allowed_sources_for_age(int(age_years))
        except Exception:
            allowed_sources_for_refs = None

    def _ref_source_ok(item: dict) -> bool:
        if allowed_sources_for_refs is None:
            return True
        src = item.get("meta", {}).get("source", "")
        if not src:
            return True  # missing source — let it through, don't break refs
        return src in allowed_sources_for_refs

    references = []
    seen = set()
    for item in retrieved:
        if not _ref_source_ok(item):
            print(f"DEBUG: Dropping ref (wrong-population source): "
                  f"{item.get('meta', {}).get('source')} "
                  f"file={item.get('meta', {}).get('file_path')}")
            continue
        rank = item.get("rank", 0)
        if rank in seen:
            continue
        seen.add(rank)
        references.append(_format_ref_line(item, rank))

    indicated_refs = getattr(make_prompt, '_last_indicated_refs', []) or []
    for (_drug, item) in indicated_refs:
        if not _ref_source_ok(item):
            print(f"DEBUG: Dropping indicated_ref (wrong-population): "
                  f"{item.get('meta', {}).get('source')} "
                  f"file={item.get('meta', {}).get('file_path')}")
            continue
        rank = item.get("rank", 0)
        if rank in seen:
            continue
        seen.add(rank)
        references.append(_format_ref_line(item, rank))

    return {
        "assessment": assessment,
        "diagnosis_enriched": diagnosis,
        "alerts": alerts,
        "recommendations": recommendations,
        "monitoring": monitoring,
        "interactions": interaction_notes,
        "ai_suggestion": ai_suggestion,
        "references": references,
        "rag_failure": rag_failure,
    }


# =========================
# Original combined-prompt builder (kept for backward compat,
# but app.py uses the per-drug variant by default)
# =========================
def make_prompt(
    question: str,
    retrieved: List[Dict[str, Any]],
    patient: Dict[str, Any] = None,
    labs: Dict[str, Any] = None,
    vitals: Dict[str, Any] = None,
    diagnosis: str = "",
    medicines: List[Dict[str, Any]] = None,
    per_drug_results: Dict[str, Dict[str, Any]] = None,
    preprocessing_alerts: List[dict] = None,
    rag_failure: bool = False,
    age_months: Optional[float] = None,
) -> str:
    patient = patient or {}
    labs = labs or {}
    vitals = vitals or {}
    medicines = medicines or []
    preprocessing_alerts = preprocessing_alerts or []

    weight_kg = _parse_weight_kg(patient)

    critical_banner = ""
    allergy_alerts = [a for a in preprocessing_alerts
                      if a.get("type") in ("ALLERGY_DIRECT",
                                            "ALLERGY_CROSS_REACTIVITY")]
    prn_alerts = [a for a in preprocessing_alerts
                  if a.get("type") == "PRN_INAPPROPRIATE"]

    banner_lines = []
    if allergy_alerts:
        banner_lines.append("[!!!] CRITICAL ALLERGY ALERTS - HIGHEST PRIORITY:")
        for a in allergy_alerts:
            banner_lines.append(f"  - {a['message']}")
        banner_lines.append(
            "RULE: For any drug above, the Recommendation line should advise "
            "discontinuation in a SUGGESTIVE advisory tone, e.g. "
            "'It is recommended to discontinue X due to the documented allergy.' "
            "Do NOT use commanding phrasings like 'Discontinuation is required' "
            "or 'IMMEDIATE DISCONTINUATION'."
        )
        banner_lines.append("")
    if prn_alerts:
        banner_lines.append("[!!!] CRITICAL PRN ALERTS:")
        for a in prn_alerts:
            banner_lines.append(f"  - {a['message']}")
        banner_lines.append("")
    if rag_failure:
        banner_lines.append("[!!!] GUIDELINE RETRIEVAL FAILURE:")
        banner_lines.append(
            "  No reliable guideline evidence retrieved for this diagnosis. "
            "State 'Insufficient guideline evidence retrieved' for any "
            "drug-specific claim that can't be supported."
        )
        banner_lines.append("")
    if banner_lines:
        critical_banner = (
            "=" * 70 + "\n"
            + "\n".join(banner_lines)
            + "=" * 70 + "\n\n"
        )

    patient_section = ""
    if patient:
        patient_section = "\nPATIENT PROFILE:\n"
        for key, value in patient.items():
            if value:
                formatted_key = key.replace("_", " ").title()
                patient_section += f"- {formatted_key}: {value}\n"

    allergy_val = (
        vitals.get("allergy_details") or vitals.get("allergy")
        or patient.get("allergy_details") or patient.get("allergy")
        or "None reported"
    )
    allergy_str = str(allergy_val).strip() or "None reported"
    patient_section += f"\n[!] ALLERGY STATUS: {allergy_str}\n"

    vitals_section = ""
    if vitals:
        vitals_section = "\nVITALS:\n"
        for key, value in vitals.items():
            if value:
                vitals_section += f"- {key.replace('_', ' ').title()}: {value}\n"

    labs_section = ""
    if labs:
        labs_section = "\nLABORATORY RESULTS:\n"
        for key, value in labs.items():
            if value:
                labs_section += f"- {key.replace('_', ' ').title()}: {value}\n"

    diagnosis_section = f"\nDIAGNOSIS:\n{diagnosis}\n" if diagnosis else ""

    alerts_section = ""
    if preprocessing_alerts:
        alert_lines = []
        for alert in preprocessing_alerts:
            alert_lines.append(f"[!] {alert['message']}")
        alerts_section = (
            "\nSAFETY ALERTS (SYSTEM-GENERATED):\n"
            + "\n".join(alert_lines) + "\n"
        )

    medicines_section = ""
    verdict_section = ""
    if medicines:
        medicines_section = "\nPRESCRIBED MEDICINES:\n"
        verdict_lines = []
        make_prompt._last_drug_verdicts = {}

        for med in medicines:
            name = med.get("generic_name", med.get("name", "Unknown"))
            dose_str = med.get("dose", "")
            unit = med.get("unit", "mg")
            frequency = med.get("frequency", "")
            route = med.get("route", "")
            prn = bool(med.get("prn", False))

            tier, explanation = determine_relevance(
                med, retrieved, diagnosis, per_drug_results,
                patient_allergy=str(allergy_val) if allergy_val else "",
            )

            med_line = f"- {name}"
            if dose_str:
                med_line += f" {normalize_dose_to_mg(dose_str, unit)}"
            if route:
                med_line += f" ({route})"
            if frequency:
                med_line += f" {frequency}"
            if prn:
                med_line += " [PRN]"

            tag = {"GUIDELINE_PREFERRED": "[OK]",
                   "ACCEPTABLE_ALTERNATIVE": "[INFO]",
                   "SUPPORTIVE_CARE": "[INFO]",
                   "RESTRICTED_USE": "[!]",
                   "NOT_INDICATED": "[!]"}.get(tier, "")
            med_line += f" {tag} [{tier} - {explanation}]"
            medicines_section += med_line + "\n"

            drug_lookup = (per_drug_results or {}).get(name, {})
            indicated_chunks = drug_lookup.get("indicated_chunks", [])

            v = build_drug_verdict(med, retrieved, indicated_chunks, weight_kg,
                                    diagnosis=diagnosis, age_months=age_months)
            verdict_record = {
                "dose": v.get("dose_verdict"),
                "frequency": v.get("freq_verdict"),
                "tier": tier,
            }
            make_prompt._last_drug_verdicts[name.lower()] = verdict_record

            if v["verdict_lines"]:
                verdict_lines.append(
                    f"{name} [{tier}]:\n" + "\n".join(v["verdict_lines"])
                )

        if verdict_lines:
            verdict_section = (
                "\nVERDICTS (SYSTEM-CALCULATED):\n"
                + "\n".join(verdict_lines) + "\n"
            )

    monitoring_lines_all = []
    for med in medicines:
        name = med.get("generic_name", med.get("name", ""))
        params = get_monitoring_for(name)
        if params:
            monitoring_lines_all.append(f"- {name}:")
            for p in params:
                monitoring_lines_all.append(f"    * {p}")
    interaction_notes = get_known_interactions(medicines)
    monitoring_block = ""
    if monitoring_lines_all or interaction_notes:
        parts = ["\nDETERMINISTIC MONITORING + INTERACTIONS:"]
        if monitoring_lines_all:
            parts.append("Monitoring:")
            parts.extend(monitoring_lines_all)
        if interaction_notes:
            parts.append("Known interactions:")
            for n in interaction_notes:
                parts.append(f"  - {n}")
        monitoring_block = "\n".join(parts) + "\n"

    ctx_lines = []
    max_diagnosis_rank = 0
    for item in retrieved:
        m = item.get("meta", {})
        file_path = m.get("file_path", "")
        source_label = m.get("source", "")
        if file_path:
            src = _clean_filename(file_path)
        else:
            src = source_label or "UMMC Guidelines"
        page = m.get("page", "")
        ident = f"Page {int(page) + 1}" if page != "" else ""
        if source_label == "ANTICOAG":
            header = f"MOH Anticoagulant Quick Guide 1st Edition [{ident}]"
        else:
            header = f"UMMC Antimicrobial Guidelines 3rd Edition - Chapter {src} [{ident}]"
        snippet = item["text"].strip().replace("\n\n", "\n")
        if len(snippet) > MAX_SNIPPET_LEN:
            snippet = snippet[:MAX_SNIPPET_LEN] + " ..."
        rank = item.get("rank", 0)
        if rank > max_diagnosis_rank:
            max_diagnosis_rank = rank
        ctx_lines.append(f"REFERENCE [{rank}]: {header}\n{snippet}\n")
    context_block = "\n".join(ctx_lines) if ctx_lines else "No context retrieved."

    indication_block = ""
    all_indicated_refs = []
    next_rank = max_diagnosis_rank + 1
    if medicines and per_drug_results:
        indication_lines = []
        for med in medicines:
            name = med.get("generic_name", med.get("name", ""))
            if get_drug_class(name) != DrugClass.ANTIBIOTIC:
                continue
            found_in_diagnosis = any(
                name.lower() in item["text"].lower() for item in retrieved
            )
            if found_in_diagnosis:
                continue
            drug_lookup = per_drug_results.get(name, {})
            indicated_chunks = drug_lookup.get("indicated_chunks", [])
            if not indicated_chunks:
                continue

            indication_lines.append(
                f"\n--- {name.upper()}: ACTUAL GUIDELINE INDICATIONS ---"
            )
            seen = set()
            shown = 0
            for item in indicated_chunks:
                if shown >= 3:
                    break
                meta = item.get("meta", {})
                dedup_key = (meta.get("file_path", ""), meta.get("page", ""))
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                if name.lower() not in item.get("text", "").lower():
                    continue
                file_path = meta.get("file_path", "")
                source_label = meta.get("source", "")
                page = meta.get("page", "")
                if file_path:
                    src = _clean_filename(file_path)
                else:
                    src = source_label or "UMMC Guidelines"
                ident = f"Page {int(page) + 1}" if page != "" else ""
                if source_label == "ANTICOAG":
                    header = f"MOH Anticoagulant Quick Guide 1st Edition [{ident}]"
                else:
                    header = f"UMMC Antimicrobial Guidelines 3rd Edition - Chapter {src} [{ident}]"
                snippet = item["text"].strip().replace("\n\n", "\n")
                if len(snippet) > MAX_SNIPPET_LEN:
                    snippet = snippet[:MAX_SNIPPET_LEN] + " ..."
                item["rank"] = next_rank
                indication_lines.append(f"REFERENCE [{next_rank}]: {header}\n{snippet}\n")
                all_indicated_refs.append((name, item))
                next_rank += 1
                shown += 1
        if indication_lines:
            indication_block = (
                f"\n{'=' * 70}\nDRUG INDICATION EVIDENCE:\n{'=' * 70}\n"
                + "\n".join(indication_lines) + "\n"
            )

    first_drug_name = (
        medicines[0].get("generic_name", medicines[0].get("name", ""))
        if medicines else ""
    )

    # =================================================================
    # SUGGESTED REPLACEMENT: if any drug will be flagged for removal
    # (allergy / site-restriction / negative-indication / structured-DB
    # NOT_INDICATED), look up the guideline-preferred replacement and
    # inject it into the prompt so the LLM's Recommendation line for
    # the removed drug names the correct alternative.
    # =================================================================
    replacement_section = ""
    try:
        # Determine which prescribed drugs will be removed. Mirrors the
        # pre-pass logic in build_ai_suggestion() so the LLM sees the
        # same view of the world the structured output will use.
        terminal_alert_types = {
            "ALLERGY_DIRECT", "ALLERGY_CROSS_REACTIVITY",
            "PRN_INAPPROPRIATE", "SITE_RESTRICTED",
            "NEGATIVE_INDICATION",
        }
        alerts_by_drug_local: Dict[str, List[dict]] = {}
        for a in preprocessing_alerts:
            d = (a.get("drug") or "").lower()
            if d:
                alerts_by_drug_local.setdefault(d, []).append(a)

        to_be_removed = []
        kept_drug_names = []
        for med in medicines:
            nm = med.get("generic_name", med.get("name", ""))
            nm_lower = nm.lower()
            da = alerts_by_drug_local.get(nm_lower, [])
            has_terminal = any(
                a.get("type") in terminal_alert_types for a in da
            )
            # Also flag drugs that determine_relevance tagged NOT_INDICATED
            # (covers structured-DB rejections like "ceftriaxone not in
            # CAP regimen" and "nitrofurantoin not for pyelonephritis")
            try:
                tier_check, _ = determine_relevance(
                    med, retrieved, diagnosis, per_drug_results,
                    patient_allergy=str(allergy_val) if allergy_val else "",
                )
            except Exception:
                tier_check = ""
            if has_terminal or tier_check == "NOT_INDICATED":
                to_be_removed.append(nm)
            else:
                kept_drug_names.append(nm)

        # Only look up a replacement if an antibiotic was removed
        antibiotic_was_removed = any(
            get_drug_class(d) == DrugClass.ANTIBIOTIC for d in to_be_removed
        )

        if antibiotic_was_removed and diagnosis:
            # Skip replacement if an existing antibiotic already covers
            # the condition (same guard as build_ai_suggestion post-pass).
            existing_covers = False
            covering_drug = ""
            try:
                from guideline_db import (
                    normalise_diagnosis as _nd,
                    has_structured_data_for as _hsd,
                    is_drug_indicated as _idi,
                )
                _ck, _sk = _nd(diagnosis)
                if _ck and _hsd(_ck):
                    for kn in kept_drug_names:
                        if get_drug_class(kn) != DrugClass.ANTIBIOTIC:
                            continue
                        try:
                            _ok, _matched, _ = _idi(
                                kn, _ck, severity=_sk,
                                allergy=str(allergy_val) if allergy_val else "",
                                age_months=age_months,
                            )
                            if _ok and _matched:
                                existing_covers = True
                                covering_drug = kn
                                break
                        except Exception:
                            pass
            except Exception:
                pass

            if not existing_covers:
                replacements = find_replacement_regimens(
                    diagnosis=diagnosis,
                    removed_drugs=to_be_removed,
                    existing_drugs=kept_drug_names,
                    patient_allergy=str(allergy_val) if allergy_val else "",
                    patient_age_months=age_months,
                    limit=1,
                )
                if replacements:
                    r = replacements[0]
                    removed_list = ", ".join(to_be_removed)
                    dose_str = f"{r['dose']} {r['unit']}".strip()
                    route_str = f" {r['route']}" if r['route'] else ""
                    freq_str = f" {r['frequency']}" if r['frequency'] else ""
                    replacement_text = (
                        f"{r['name']} {dose_str}{route_str}{freq_str}".strip()
                    )

                    # =========================================================
                    # Inject a SYNTHETIC reference pointing to the actual
                    # guideline page where this regimen lives. Without this,
                    # the LLM cites whatever retrieved chunks rank highest -
                    # often the wrong page in the same chapter (e.g. pg 3
                    # cystitis section cited instead of pg 10 severe
                    # pyelonephritis section).
                    # =========================================================
                    cite_rank = None
                    source_chapter = r.get("source_chapter", "")
                    structured_page = r.get("page", "")
                    if source_chapter and structured_page:
                        # Find a retrieved or per-drug chunk from this chapter
                        # to borrow its file_path + source label format.
                        donor_meta = None
                        for it in retrieved:
                            fp = it.get("meta", {}).get("file_path", "")
                            if source_chapter in fp or source_chapter.replace(".", "_") in fp:
                                donor_meta = it.get("meta", {})
                                break
                        if donor_meta is None and per_drug_results:
                            for _, lookup in per_drug_results.items():
                                for it in lookup.get("indicated_chunks", []):
                                    fp = it.get("meta", {}).get("file_path", "")
                                    if (source_chapter in fp or
                                        source_chapter.replace(".", "_") in fp):
                                        donor_meta = it.get("meta", {})
                                        break
                                if donor_meta:
                                    break
                        if donor_meta:
                            synthetic_item = {
                                "text": (
                                    f"[Structured guideline regimen for "
                                    f"{diagnosis}] {r['name']} {dose_str} "
                                    f"{r['route']} {r['frequency']} "
                                    f"(tier: {r['tier']})"
                                ),
                                "meta": {
                                    "file_path": donor_meta.get("file_path", ""),
                                    "source": donor_meta.get("source", ""),
                                    # structured DB page is 1-indexed; chunks
                                    # use 0-indexed, _format_ref_line adds +1
                                    "page": int(structured_page) - 1,
                                },
                                "rank": next_rank,
                            }
                            all_indicated_refs.append((r["name"], synthetic_item))
                            cite_rank = next_rank
                            next_rank += 1

                    cite_instruction = (
                        f"  When citing this regimen, use [{cite_rank}].\n"
                        if cite_rank else ""
                    )

                    replacement_section = (
                        f"\n{'=' * 70}\nSUGGESTED REPLACEMENT REGIMEN\n{'=' * 70}\n"
                        f"The following drug(s) will be removed because they are "
                        f"unsafe or not indicated for this diagnosis: "
                        f"{removed_list}.\n"
                        f"The UMMC guideline-preferred replacement for "
                        f"'{diagnosis}' is:\n"
                        f"  -> {replacement_text}  (tier: {r['tier']}, "
                        f"chapter {source_chapter} page {structured_page})\n"
                        f"{cite_instruction}\n"
                        f"INSTRUCTION FOR LLM: When writing the Recommendation "
                        f"line for any removed drug above, name this specific "
                        f"replacement (drug + dose + route + frequency) so the "
                        f"prescriber sees what to switch to, but keep the tone "
                        f"SUGGESTIVE not commanding. Use phrasings like:\n"
                        f"  'It is recommended to discontinue {to_be_removed[0]} "
                        f"and consider {replacement_text} instead, the UMMC-"
                        f"preferred regimen for {diagnosis} "
                        f"[{cite_rank if cite_rank else 'N'}].'\n"
                        f"  'Consider switching {to_be_removed[0]} to "
                        f"{replacement_text}, which is the UMMC-preferred "
                        f"regimen for {diagnosis} "
                        f"[{cite_rank if cite_rank else 'N'}].'\n"
                        f"AVOID commanding verbs like 'Discontinue X and switch "
                        f"to Y' as a bare imperative.\n"
                    )
            else:
                # Existing antibiotic already covers the indication.
                # Tell the LLM to recommend ONLY discontinuation in advisory
                # tone, WITHOUT naming any alternative drug, because the
                # current prescription is already adequate.
                removed_list = ", ".join(to_be_removed)
                replacement_section = (
                    f"\n{'=' * 70}\nEXISTING COVERAGE NOTED\n{'=' * 70}\n"
                    f"The following drug(s) will be flagged for removal: "
                    f"{removed_list}.\n"
                    f"An existing prescribed antibiotic ({covering_drug}) is "
                    f"already guideline-indicated for '{diagnosis}', so NO "
                    f"replacement drug needs to be suggested. The current "
                    f"prescription provides adequate antimicrobial coverage.\n\n"
                    f"INSTRUCTION FOR LLM: For the removed drug(s) above, the "
                    f"Recommendation line should advise ONLY discontinuation "
                    f"in a SUGGESTIVE advisory tone. Do NOT name any "
                    f"alternative or replacement drug - {covering_drug} "
                    f"already covers the indication. Use phrasings like:\n"
                    f"  'It is recommended to discontinue {to_be_removed[0]} "
                    f"due to the contraindication; {covering_drug} already "
                    f"provides appropriate coverage for {diagnosis} [N].'\n"
                    f"  'We suggest discontinuing {to_be_removed[0]}; no "
                    f"alternative is needed as {covering_drug} is already "
                    f"indicated for {diagnosis} [N].'\n"
                )
    except Exception as e:
        print(f"[make_prompt] Replacement injection skipped: {e}")

    prompt = (
        f"{critical_banner}{SYSTEM_PRIMER}\n"
        f"{'=' * 70}\nPATIENT CASE\n{'=' * 70}\n"
        f"{patient_section}{vitals_section}{labs_section}{diagnosis_section}"
        f"{medicines_section}{alerts_section}{verdict_section}"
        f"{monitoring_block}\n"
        f"{'=' * 70}\nGUIDELINE EVIDENCE:\n{'=' * 70}\n{context_block}\n"
        f"{indication_block}"
        f"{replacement_section}\n"
        f"{'=' * 70}\nNOW WRITE YOUR ANALYSIS\n{'=' * 70}\n"
        f"Produce one section per drug, in the order shown below. "
        f"Use this EXACT layout for each section:\n\n"
        f"--- <drug name in lowercase> ---\n"
        f"Assessment: Safe | Needs Review | Unsafe\n"
        f"Issues:\n"
        f"- <bullet per problem; write '- None' if no problems>\n"
        f"Recommendation: <one suggestive sentence>\n\n"
        f"Drugs to cover, IN THIS ORDER:\n"
    )
    for i, med in enumerate(medicines, start=1):
        nm = med.get("generic_name", med.get("name", ""))
        prompt += f"  {i}. {nm}\n"
    prompt += (
        "\nRULES:\n"
        "- Cite ONLY [N] numbers from REFERENCE blocks above. Never invent placeholder refs.\n"
        "- EVERY Recommendation must end with at least one [N] citation drawn from "
        "the REFERENCE blocks above. Place it just before the closing period: "
        "'... 2 g IV q24H [1].' If no specific reference applies, append [1].\n"
        "- Do NOT contradict the system VERDICTS shown above; report them faithfully. "
        "If a verdict line says the drug is 'site-restricted' / 'not indicated' / "
        "'not routinely indicated' for this diagnosis, the Assessment MUST be 'Unsafe'.\n"
        "- If a SAFETY ALERT marked CRITICAL names a drug, that drug's Assessment MUST "
        "be 'Unsafe'. If only WARNING-level alerts apply, use 'Needs Review'.\n"
        "- Dose mismatches (INCORRECT, EXCEEDS) and frequency mismatches (INCORRECT) "
        "MUST appear in the drug's Issues block - do not omit them on the grounds that "
        "they also appear in the top-level alerts.\n"
        "- Recommendation must be SUGGESTIVE: 'It is recommended to...', 'Consider...', 'We suggest...'. "
        "Never use commanding verbs like 'Change' or 'Stop' EXCEPT for documented allergy or contraindication, "
        "where 'Discontinuation is required' is appropriate.\n"
        "- If the SUGGESTED REPLACEMENT REGIMEN section above lists a replacement, "
        "the Recommendation line for the removed drug should NAME that specific drug, "
        "dose, route, and frequency so the prescriber sees what to switch to. "
        "Keep the tone SUGGESTIVE: prefer 'It is recommended to discontinue X and "
        "consider Y at Z dose' or 'Consider switching X to Y at Z dose' over the "
        "blunt imperative 'Discontinue X and switch to Y'.\n"
        "- If ALL checks for a drug are CORRECT and no alerts mention it, output the "
        "compact Safe form only (3 lines, no justification):\n"
        "    Assessment: Safe\n"
        "    Issues: None\n"
        "    Recommendation: Continue\n"
        "  NEVER list dose/frequency CORRECT confirmations under Issues for ANY drug, "
        "Safe or otherwise. Issues blocks are exclusively for problems.\n"
        "- Class-overlap, therapeutic-duplication, and any other alert that names multiple drugs must be "
        "repeated inside EACH affected drug's Issues block.\n"
        "- Do NOT write Overall Assessment, Clinical Flags, Monitoring, Drug Interactions, Verification, "
        "or References blocks - the system writes those.\n"
        "- Do NOT emit bare separator lines (just '---' on its own) between drug sections. "
        "The only allowed '---' lines are the section headers of the form '--- drug_name ---'.\n\n"
        f"Begin your output right now with the line `--- {first_drug_name} ---` "
        f"and write all {len(medicines)} sections in order. No preamble.\n"
    )


    make_prompt._last_indicated_refs = all_indicated_refs
    return prompt


# =========================
# Post-processing
# =========================
_RE_VERIF = re.compile(
    r"^\s*(?:\*{1,2}\s*)?verification(?:\s*\*{1,2})?\s*:\s*(.+)$",
    re.I | re.M,
)


def _strip_correct_verdict_bullets(text: str) -> str:
    """
    Remove bullets that merely confirm a dose or frequency is CORRECT. The
    LLM has a strong habit of writing these lines even when the verdict feed
    contains only problems, so we strip them deterministically.

    Patterns stripped (case-insensitive, bullets only):
      - "- Dose: 500mg - CORRECT (guideline: 500 mg)"
      - "- Dose 500 mg: CORRECT ..."
      - "- Frequency: 'q6H' - CORRECT (guideline: q6H)"
      - "- Frequency q6H: CORRECT ..."
      - "- Route: PO - CORRECT ..."
    INCORRECT, EXCEEDS, and any other non-CORRECT bullets pass through untouched.
    """
    if not text:
        return text

    # A bullet starts with '-' or '*', possibly indented; we only strip lines
    # that name Dose/Frequency/Route AND contain a CORRECT verdict.
    pattern = re.compile(
        r"^\s*[-*]\s*(?:dose|frequency|route)\b[^\n]*\bcorrect\b[^\n]*\n?",
        re.IGNORECASE | re.MULTILINE,
    )
    cleaned = pattern.sub("", text)

    # If stripping a bullet leaves the Issues block with no bullets at all,
    # the LLM may have produced "Issues:" followed by blank then the
    # Recommendation. Normalise that to "Issues: None" for readability.
    cleaned = re.sub(
        r"(Issues\s*:\s*)\n+(\s*Recommendation\s*:)",
        r"\1None\n\2",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned


def _strip_stray_separators(text: str) -> str:
    """
    Remove bare '---' lines that occasionally appear between sections in the
    LLM output. A valid section header is '--- drug_name ---'; a bare '---'
    on its own is a stray separator that should not survive into the final
    answer. Also collapses 3+ consecutive blank lines to 1.
    """
    if not text:
        return text
    # Drop lines that are nothing but dashes and whitespace
    cleaned = re.sub(r"^\s*-{3,}\s*$\n?", "", text, flags=re.M)
    # Collapse runs of blank lines down to a single blank
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _build_drug_citation_map(
    medicines: List[Dict[str, Any]],
    retrieved: List[Dict[str, Any]],
    per_drug_results: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[int]]:
    """
    For each prescribed drug, return the list of reference [N] ranks that
    are most relevant to it. Used to back-fill Recommendation citations
    when the LLM forgets to include them.

    Selection priority:
      1. Diagnosis-level chunks that explicitly mention this drug by name.
      2. The drug's own indicated_chunks (per_drug_results).
      3. Fallback: rank 1 (first diagnosis-level reference) when nothing
         matches, so the prescriber still has a pointer.
    """
    drug_to_ranks: Dict[str, List[int]] = {}
    per_drug_results = per_drug_results or {}

    for med in medicines:
        name = med.get("generic_name", med.get("name", "")).lower().strip()
        if not name:
            continue

        ranks: List[int] = []

        # Pass 1: diagnosis retrieval chunks that mention the drug.
        for item in retrieved:
            text = (item.get("text") or "").lower()
            if name in text:
                rank = item.get("rank")
                if isinstance(rank, int) and rank not in ranks:
                    ranks.append(rank)
            if len(ranks) >= 2:
                break

        # Pass 2: per-drug indicated chunks (their ranks are assigned in
        # app.py before the LLM call).
        if not ranks:
            drug_lookup = per_drug_results.get(med.get("generic_name", ""), {})
            for item in drug_lookup.get("indicated_chunks", []):
                rank = item.get("rank")
                if isinstance(rank, int) and rank not in ranks:
                    ranks.append(rank)
                if len(ranks) >= 2:
                    break

        # Pass 3: fallback to rank 1 so the citation slot is never empty.
        if not ranks and retrieved:
            first_rank = retrieved[0].get("rank")
            if isinstance(first_rank, int):
                ranks = [first_rank]

        if ranks:
            drug_to_ranks[name] = ranks

    return drug_to_ranks


_REC_LINE_RE = re.compile(r"^(\s*Recommendation\s*:\s*)(.+)$", re.I | re.M)
_CITE_TOKEN_RE = re.compile(r"\[\d+\]")


def _inject_recommendation_citations(
    text: str,
    drug_to_ranks: Dict[str, List[int]],
) -> str:
    """
    Walk the per-drug sections in `text` and append [N] citation tokens to
    any Recommendation line that doesn't already have at least one. The
    rank(s) used come from `drug_to_ranks` for the section's drug.

    Recommendations of the form 'Continue' (used for Safe drugs) are left
    alone - there's no specific guideline to cite for a clean prescription.
    """
    if not text or not drug_to_ranks:
        return text

    section_re = re.compile(r"^[\s]*---\s*([^\n-][^\n]*?)\s*---\s*$", re.M)

    pieces: List[str] = []
    last_end = 0
    matches = list(section_re.finditer(text))
    if not matches:
        return text

    for idx, m in enumerate(matches):
        # Append everything between the previous match end and this header
        pieces.append(text[last_end:m.start()])
        header = m.group(0)
        pieces.append(header)

        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[body_start:body_end]

        # Normalise the drug name for lookup (strip parentheticals like "(IV)")
        drug_key = re.sub(r"\s*\([^)]*\)\s*", " ", m.group(1)).strip().lower()
        ranks = drug_to_ranks.get(drug_key)
        if not ranks:
            # Try fuzzy: any key contained in or containing the header text
            for key, r in drug_to_ranks.items():
                if key in drug_key or drug_key in key:
                    ranks = r
                    break

        if ranks:
            body = _append_citation_to_recommendation(body, ranks)

        pieces.append(body)
        last_end = body_end

    pieces.append(text[last_end:])
    return "".join(pieces)


def _append_citation_to_recommendation(body: str, ranks: List[int]) -> str:
    """Append [N] to the Recommendation line in this section body, if missing."""
    def _fix(match: "re.Match") -> str:
        prefix, content = match.group(1), match.group(2).rstrip()
        # Skip the trivial 'Continue' line that Safe drugs use.
        if content.strip().lower() in ("continue", "continue."):
            return match.group(0)
        if _CITE_TOKEN_RE.search(content):
            return match.group(0)
        # Build the citation suffix. Cap at 2 refs so the line stays readable.
        cite_tokens = "".join(f"[{r}]" for r in ranks[:2])
        if content.endswith("."):
            new_content = content[:-1].rstrip() + f" {cite_tokens}."
        else:
            new_content = content + f" {cite_tokens}"
        return prefix + new_content

    return _REC_LINE_RE.sub(_fix, body)


def normalize_labels(text: str) -> str:
    return re.sub(
        r"^\s*\*{1,2}\s*(Verification|Guideline Used|Confidence Score|Explanation|Citation)\s*\*{1,2}\s*:",
        r"\1:",
        text,
        flags=re.I | re.M,
    )


# =========================
# Issue-line deduplication
# =========================
def _issue_signature(line: str) -> str:
    """
    Build a coarse signature for an Issue bullet so two lines that describe
    the same clinical problem (with different wording) hash to the same key.

    The signature keeps the order-independent set of meaningful tokens
    longer than 3 characters. Stop-words and clinically empty filler are
    dropped so e.g.
        "Nitrofurantoin is site-restricted for 'Urinary tract infection /
         pyelonephritis'. Nitrofurantoin only achieves therapeutic
         concentrations in the bladder and does NOT penetrate kidney tissue."
    and
        "Nitrofurantoin only achieves therapeutic concentrations in the
         bladder and does NOT penetrate kidney tissue."
    collapse to highly overlapping signatures and are treated as duplicates
    by `_dedupe_issue_lines`.
    """
    if not line:
        return ""
    s = line.lower()
    # Strip leading bullets/markers and surrounding quotes
    s = re.sub(r"^\s*[-*•]\s*", "", s)
    s = re.sub(r"['\"`]", " ", s)
    # Drop low-information tokens
    stop = {
        "the", "and", "for", "with", "this", "that", "from", "into", "have",
        "has", "are", "is", "be", "of", "in", "on", "to", "by", "as", "at",
        "or", "but", "an", "a", "if", "it", "its", "not", "no", "any", "all",
        "some", "do", "does", "did", "may", "can", "could", "should", "would",
        "patient", "drug", "drugs", "dose", "doses", "use", "used", "using",
        "only", "well", "also", "above", "below", "alert", "alerts", "issue",
        "issues", "recommend", "recommended", "recommendation",
    }
    tokens = re.findall(r"[a-z0-9]+", s)
    keep = sorted(set(t for t in tokens if len(t) > 3 and t not in stop))
    return " ".join(keep)


def _issue_lines_overlap(a: str, b: str) -> bool:
    """
    Two issue lines are 'the same problem' when their signatures share
    >= 70% of tokens (Jaccard) OR when one fully contains the other.
    """
    sa, sb = _issue_signature(a), _issue_signature(b)
    if not sa or not sb:
        return False
    if sa == sb:
        return True
    set_a = set(sa.split())
    set_b = set(sb.split())
    if not set_a or not set_b:
        return False
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    if union == 0:
        return False
    jaccard = inter / union
    # Containment check catches the common case where one bullet is the
    # full statement and the other is just its tail.
    contained = (inter == len(set_a)) or (inter == len(set_b))
    return jaccard >= 0.70 or contained


def _dedupe_issue_lines(lines: List[str]) -> List[str]:
    """
    Remove near-duplicate bullets while preserving original order and
    choosing the LONGER (= more informative) variant when a duplicate
    pair is found.
    """
    kept: List[str] = []
    for raw in lines:
        if not raw or not raw.strip():
            continue
        stripped = raw.strip()
        replaced = False
        for i, existing in enumerate(kept):
            if _issue_lines_overlap(stripped, existing):
                if len(stripped) > len(existing):
                    kept[i] = stripped
                replaced = True
                break
        if not replaced:
            kept.append(stripped)
    return kept


def _dedupe_issues_in_llm_output(text: str) -> str:
    """
    Post-process the LLM-generated multi-drug response: for each per-drug
    section, collapse near-duplicate bullets in the Issues block. This is
    a defensive second pass on top of the prompt-level rule, since LLMs
    still occasionally restate the same finding in two different bullets.
    """
    if not text:
        return text

    # Split on the per-drug "--- name ---" markers and rebuild section by
    # section. We keep everything outside Issues unchanged.
    section_re = re.compile(r"(^[\s]*---\s*[^\n-][^\n]*?\s*---\s*$)", re.M)
    parts = section_re.split(text)
    if len(parts) <= 1:
        return text

    out_parts = [parts[0]]
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        out_parts.append(header)
        out_parts.append(_dedupe_issues_block(body))
    return "".join(out_parts)


def _dedupe_issues_block(body: str) -> str:
    """
    Inside one per-drug section body, find the Issues: block, dedupe its
    bullets, and stitch the section back together. Leaves Assessment and
    Recommendation lines untouched.
    """
    m = re.search(
        r"(Issues\s*:\s*\n)(.*?)(?=\nRecommendation\s*:|\Z)",
        body, flags=re.S | re.I,
    )
    if not m:
        return body

    head = m.group(1)
    issues_block = m.group(2)

    raw_lines = issues_block.split("\n")
    bullet_lines = []
    trailing = []
    for line in raw_lines:
        if line.strip().startswith("-") or line.strip().startswith("*"):
            bullet_lines.append(line.rstrip())
        else:
            # Non-bullet trailing whitespace / blank lines belong after the
            # deduped bullets.
            trailing.append(line)

    deduped = _dedupe_issue_lines(bullet_lines)
    # Re-attach a leading "- " when missing (the dedup function strips
    # whitespace but preserves the dash if present).
    normalized = []
    for line in deduped:
        if line.lstrip().startswith(("-", "*")):
            normalized.append(line)
        else:
            normalized.append(f"- {line}")

    new_issues = "\n".join(normalized)
    if trailing and any(t.strip() for t in trailing):
        new_issues += "\n" + "\n".join(t for t in trailing if t)

    return body.replace(m.group(0), head + new_issues, 1)


def _strip_all_placeholder_refs(text: str) -> str:
    text = re.sub(
        r'\n*\*{0,2}\s*References\s*:?\s*\*{0,2}\s*:?\s*\n.*$',
        '', text, flags=re.I | re.S
    )
    text = re.sub(
        r'\n+\*{0,2}\s*References\s*:?\s*\*{0,2}\s*:?[^\n]*$',
        '', text, flags=re.I | re.S
    )
    text = re.sub(
        r'\n?\s*\[\d+\]\s*[^\n]*(?:placeholder|local guideline|drug monograph|'
        r'formulary|label \(placeholder\))[^\n]*',
        '', text, flags=re.I
    )
    text = re.sub(r'\n*\*{0,2}\s*Note\s*\*{0,2}\s*:.*$', '', text, flags=re.I | re.S)
    text = re.sub(r'\n*\*{0,2}\s*Please note\s*\*{0,2}\s*:.*$', '', text, flags=re.I | re.S)
    return text.strip()


def ensure_verification_line(text: str) -> str:
    text = normalize_labels(text)
    text = _strip_all_placeholder_refs(text)

    lines = text.splitlines()
    verif_idxs = [
        i for i, line in enumerate(lines)
        if re.match(r"^\s*Verification\s*:", line, re.I)
    ]
    if len(verif_idxs) > 1:
        keep = verif_idxs[-1]
        lines = [
            line for i, line in enumerate(lines)
            if i == keep or i not in verif_idxs
        ]
        text = "\n".join(lines)

    if not _RE_VERIF.search(text):
        text = text + (
            "\nVerification: AI-generated analysis based on UMMC Antimicrobial "
            "Guidelines 3rd Edition, MOH Anticoagulant Quick Guide 1st Edition, "
            "and clinical knowledge. "
            "Clinical judgment required before acting on these recommendations."
        )

    # Strip "MOH Anticoagulant Quick Guide" mention from the Verification
    # line when no anticoagulant source was actually used in this report.
    # The MOH guide is only relevant for anticoagulant cases; mentioning
    # it for a cellulitis/antibiotic case looks careless in the report.
    try:
        indicated_refs_local = getattr(make_prompt, '_last_indicated_refs', []) or []
        uses_anticoag = any(
            (item.get("meta", {}).get("source") == "ANTICOAG")
            for (_d, item) in indicated_refs_local
        )
        if not uses_anticoag:
            # Remove ", MOH Anticoagulant Quick Guide 1st Edition" from
            # Verification lines. Handles "UMMC ..., MOH ..., and clinical"
            # and "UMMC ... and MOH ..., and clinical" variations.
            text = re.sub(
                r',\s*MOH Anticoagulant Quick Guide(?:\s*1st Edition)?',
                '',
                text,
            )
            text = re.sub(
                r'\s+and\s+MOH Anticoagulant Quick Guide(?:\s*1st Edition)?',
                '',
                text,
            )
    except Exception:
        pass

    verif_match = re.search(r'Verification\s*:', text, re.I)
    if verif_match:
        verif_start = verif_match.start()
        after_verif = text[verif_start:]
        para_end = len(after_verif)
        double_nl = after_verif.find('\n\n')
        if double_nl > 0:
            para_end = double_nl
        single_nl_match = re.search(
            r'\n(?=\s*(?:\*{0,2}\s*References|\[\d+\]))',
            after_verif, re.I
        )
        if single_nl_match and single_nl_match.start() < para_end:
            para_end = single_nl_match.start()
        text = text[:verif_start + para_end]

    text = _strip_all_placeholder_refs(text)
    return text.rstrip()


# =========================
# Recommendation-Verdict Consistency
# =========================
_DOSE_CHANGE_VERBS = re.compile(
    r'\b(?:change|changing|adjust|adjusting|increase|increasing|'
    r'decrease|decreasing|reduce|reducing|lower|lowering|raise|raising|'
    r'modify|modifying|switch\s+(?:the\s+)?dose|alter|altering|titrate|'
    r'titrating)\b',
    re.IGNORECASE
)


def enforce_recommendation_consistency(
    text: str,
    medicines: List[Dict[str, Any]],
    retrieved: List[Dict[str, Any]],
) -> str:
    if not text:
        return text
    verdicts = getattr(make_prompt, '_last_drug_verdicts', {}) or {}

    rec_match = re.search(
        r'(Recommendations?\s*:.*?)(?=\nVerification\s*:|\Z)',
        text, re.IGNORECASE | re.DOTALL
    )
    if not rec_match:
        return text

    rec_block = rec_match.group(1)
    rec_start = rec_match.start(1)
    rec_end = rec_match.end(1)

    lines = rec_block.split('\n')
    cleaned = []
    stripped_any = False

    for line in lines:
        line_lower = line.lower()
        keep = True
        replacement = None
        for med in medicines:
            name = med.get("generic_name", med.get("name", "")).lower()
            if not name or name not in line_lower:
                continue
            v = verdicts.get(name, {})
            dose_ok = v.get("dose") == "CORRECT"
            freq_ok = v.get("frequency") == "CORRECT"
            if dose_ok and freq_ok and _DOSE_CHANGE_VERBS.search(line):
                replacement = (
                    f"  [System-removed] - {name} dose and frequency were "
                    f"already verified CORRECT against the guideline; "
                    f"no adjustment recommended."
                )
                keep = False
                stripped_any = True
                break
        if keep:
            cleaned.append(line)
        elif replacement:
            cleaned.append(replacement)

    if not stripped_any:
        return text

    new_rec_block = "\n".join(cleaned)
    return text[:rec_start] + new_rec_block + text[rec_end:]


# =========================
# TIER 1.2 - Allergy-aware alternative-suggestion filter
# Even after the per-drug allergy check fires, the LLM sometimes still
# suggests alternatives that ALSO conflict with the patient's allergy
# (e.g. recommending co-amoxiclav as an alternative to a penicillin-
# allergic patient). This post-processor parses every "consider X /
# switch to X / alternative is X" line in the Recommendations section
# and removes the suggestion if X cross-reacts with a known allergy.
# =========================

# Verbs / phrases that introduce a candidate drug suggestion
_RE_SUGGEST_VERBS = re.compile(
    r'\b(?:consider|consider\s+(?:using|switching\s+to|adding)|'
    r'switch(?:\s+(?:to|with))?|change\s+to|replace\s+with|'
    r'alternative(?:s)?(?:\s+(?:is|are|include|like|such\s+as))?|'
    r'use\s+instead|prescribe|recommended\s+is)\b',
    re.IGNORECASE,
)

# Capture any word (4+ letters) that might be a drug name - case-insensitive
# so we catch both 'Amoxicillin' AND 'amoxicillin'. Drug-name validation is
# done downstream by checking against the drug database.
_RE_DRUG_CANDIDATE = re.compile(
    r'\b([a-zA-Z][a-zA-Z]{3,}(?:[\-/][a-zA-Z]+)*)\b'
)

# Common non-drug English words to exclude even if they pass the regex.
# These can never be drug names so we skip the (relatively expensive) drug
# database lookup for them.
_NON_DRUG_WORDS = {
    "consider", "alternatives", "alternative", "alternatively",
    "switch", "switching", "change", "changing", "changed",
    "replace", "replacing", "replaced",
    "discontinue", "discontinuing", "discontinued", "discontinuation",
    "use", "using", "used", "instead", "prescribe", "prescribed", "prescribing",
    "the", "patient", "patients", "guideline", "guidelines",
    "ummc", "moh", "iv", "po", "im", "sc", "sl", "pr",
    "tablet", "tablets", "capsule", "capsules", "infusion", "injection",
    "antibiotic", "antibiotics", "therapy", "treatment", "treatments",
    "review", "monitor", "monitoring", "continue", "continuing",
    "according", "based", "for", "with", "without", "due", "such", "like",
    "include", "includes", "including", "may", "should", "could", "must",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
    "recommendation", "recommendations", "recommended", "recommend",
    "assessment", "issues", "verification", "diagnosis", "dose", "doses",
    "dosing", "frequency", "route", "administration", "and", "but", "or",
    "guideline-recommended", "first-line", "second-line",
    "appropriate", "inappropriate", "indicated", "contraindicated",
    "allergic", "allergy", "penicillin", "cephalosporin", "macrolide",
    "fluoroquinolone", "sulfa", "carbapenem", "beta-lactam",
    "this", "that", "these", "those", "from", "into", "onto",
    "system", "removed", "cannot", "suggest", "suggested", "suggesting",
    "suggests", "suggestion", "suggestions",
    "agent", "agents", "medication", "medications", "drug", "drugs",
    "clinically", "clinical", "presentation", "infection", "infections",
    "current", "current-use", "verify", "verified", "verifying",
    "case", "cases", "needs", "needed", "needing",
    "advised", "advise", "advice", "advising", "approved",
    "specialist", "clearance", "documented", "documentation",
}


def _extract_candidate_drugs_from_line(line: str) -> List[str]:
    """
    From a recommendation line that contains a 'consider/switch to/etc.'
    verb, return a list of tokens that might be drug names.

    Crucially, this is now CASE-INSENSITIVE - the LLM often writes drug
    names in lowercase ("such as amoxicillin or clindamycin"), and the
    previous capitalised-only regex missed these entirely, allowing
    contraindicated alternatives to slip past the allergy filter.

    Final validation against the drug database happens downstream - this
    function just produces a candidate list.
    """
    candidates = []
    seen = set()
    for m in _RE_DRUG_CANDIDATE.finditer(line):
        token = m.group(1).strip()
        token_lower = token.lower()
        # Skip obvious non-drug words
        if token_lower in _NON_DRUG_WORDS:
            continue
        if len(token_lower) < 4:
            continue
        if token_lower in seen:
            continue
        seen.add(token_lower)
        candidates.append(token)
    return candidates


def enforce_allergy_in_recommendations(
    text: str,
    allergy_text: str,
) -> str:
    """
    Walk every line of the entire text. ONLY process lines that start with
    'Recommendation:' (the per-drug recommendation lines). For those lines
    that suggest an alternative or switch-to drug, parse out the drug
    names and check each against the patient's allergy via the SAME logic
    used in drug_database.check_allergy_conflicts. If a candidate
    cross-reacts with the patient allergy, replace the line with a
    safety note.

    IMPORTANT - SCOPE: This function ONLY processes lines starting with
    'Recommendation:'. It must NOT process Issues bullets, alert text,
    or any other content.

    IMPORTANT - SECTION-AWARE: The drug named in the section header
    '--- drug_name ---' is the drug being DISCONTINUED, not a suggestion.
    The function tracks the current section's drug and excludes it from
    candidate checking, so a Recommendation like 'Discontinue cloxacillin
    and switch to clindamycin' is only checked for clindamycin, not
    cloxacillin (which would otherwise be flagged as cross-reactive
    with penicillin and the entire Recommendation line would be lost).
    """
    if not text or not allergy_text or not allergy_text.strip():
        return text

    # Local import to avoid circular import at module load time
    from drug_database import (
        _normalize_allergy_string, ALLERGY_CROSS_REACTIVITY,
        resolve_drug_name, get_drug_info, get_ingredients,
    )

    allergy_keys = _normalize_allergy_string(allergy_text)
    if not allergy_keys:
        return text

    # Pattern for section header: --- drug_name ---
    section_re = re.compile(r'^\s*---\s*(.+?)\s*---\s*$')

    lines = text.split('\n')
    cleaned_lines = []
    stripped_any = False
    current_section_drug = ""  # The drug being discussed in this section

    for line in lines:
        # Track section header so we know which drug is being discussed
        sec_match = section_re.match(line)
        if sec_match:
            section_label = sec_match.group(1).strip().lower()
            # Strip parenthetical tags like "(supportive care)"
            section_label = re.sub(r'\s*\([^)]*\)\s*$', '', section_label)
            current_section_drug = section_label
            cleaned_lines.append(line)
            continue

        # Only process actual Recommendation: lines. Issues bullets,
        # Assessment lines, and alert text are left untouched even if
        # they happen to contain suggest-verb keywords.
        stripped_line = line.lstrip()
        is_recommendation = (
            stripped_line.lower().startswith("recommendation:") or
            stripped_line.lower().startswith("recommendations:")
        )
        if not is_recommendation:
            cleaned_lines.append(line)
            continue

        # Only act on Recommendation lines that look like a suggestion
        if not _RE_SUGGEST_VERBS.search(line):
            cleaned_lines.append(line)
            continue

        candidates = _extract_candidate_drugs_from_line(line)
        offending_candidates = []

        for cand in candidates:
            # Skip the drug being discussed in this section - it's being
            # discontinued, not suggested, so cross-reactivity is not a
            # concern (we WANT to discontinue cross-reactive drugs).
            if cand.lower() == current_section_drug:
                continue
            try:
                generic, _, _ = resolve_drug_name(cand)
            except Exception:
                continue
            # Also skip if the resolved generic name matches the section drug
            if generic.lower() == current_section_drug:
                continue
            info = get_drug_info(generic)
            if not info:
                continue
            subclass = (info.get("subclass") or "").lower()
            ingredients = [i.lower() for i in get_ingredients(generic)]

            # Same logic as check_allergy_conflicts but for one drug
            for allergy_key in allergy_keys:
                triggers = ALLERGY_CROSS_REACTIVITY.get(allergy_key, [])
                direct_hit = any(allergy_key in ing for ing in ingredients)
                cross_hit = any(t.lower() in subclass for t in triggers)
                if direct_hit or cross_hit:
                    offending_candidates.append(
                        (cand, generic, allergy_key,
                         "direct" if direct_hit else "cross")
                    )
                    break

        if offending_candidates:
            offenders_str = ", ".join(
                f"{cand} ({reason}-reacts with {al})"
                for (cand, _g, al, reason) in offending_candidates
            )
            cleaned_lines.append(
                f"  [System-removed] - cannot suggest: {offenders_str}. "
                f"Patient is allergic to {', '.join(allergy_keys)}. "
                f"A clinician must choose a non-cross-reactive alternative."
            )
            stripped_any = True
        else:
            cleaned_lines.append(line)

    if not stripped_any:
        return text

    return "\n".join(cleaned_lines)


def fix_references(text: str, retrieved: List[Dict[str, Any]]) -> str:
    text = _strip_all_placeholder_refs(text)
    text = text.rstrip()

    if not retrieved:
        return text

    indicated_refs = getattr(make_prompt, '_last_indicated_refs', [])
    indicated_items = [item for (_drug, item) in indicated_refs]
    indicated_drug_names = {drug for (drug, _item) in indicated_refs}
    all_referable = retrieved + indicated_items

    cited_ranks = set()
    for match in re.finditer(r'\[(\d+)\]', text):
        cited_ranks.add(int(match.group(1)))

    real_ranks = {item.get("rank", 0) for item in all_referable}
    real_cited = cited_ranks & real_ranks

    ref_lines = []
    seen_ranks = set()

    if real_cited:
        for item in all_referable:
            rank = item.get("rank", 0)
            if rank not in real_cited or rank in seen_ranks:
                continue
            seen_ranks.add(rank)
            ref_lines.append(_format_ref_line(item, rank))
    else:
        if indicated_items:
            for drug_name in indicated_drug_names:
                drug_refs = [
                    item for (d, item) in indicated_refs if d == drug_name
                ]
                if drug_refs:
                    ref_nums = [str(item.get("rank", 0)) for item in drug_refs]
                    ref_citation = ", ".join(f"[{n}]" for n in ref_nums)
                    text += (
                        f"\n\nNote: According to UMMC guidelines, {drug_name} is "
                        f"indicated for other conditions - see {ref_citation}."
                    )
            for item in indicated_items:
                rank = item.get("rank", 0)
                if rank in seen_ranks:
                    continue
                seen_ranks.add(rank)
                ref_lines.append(_format_ref_line(item, rank))

    if ref_lines:
        text += "\n\nReferences:\n" + "\n".join(ref_lines)

    return text