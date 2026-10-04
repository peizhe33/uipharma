"""
Flask REST API for SmartPharma RAG backend.

Pipeline:
  1. Pre-processing: drug name resolution, allergy/PRN/restricted/site checks
  2. Diagnosis-level retrieval
  3. Per-drug reverse lookup (cheap vector searches, no LLM)
  4. SINGLE unified LLM call covering all drugs at once
  5. Parse per-drug sections from the unified response
  6. Build structured `report` JSON for Flutter
  7. Return both `answer` (assembled text) and `report` (structured)
"""

import re
import time
import json
from flask import Flask, request, jsonify, make_response

from config import (
    TOP_K, OLLAMA_MODEL,
    FLASK_HOST, FLASK_PORT, FLASK_DEBUG,
    ALLOWED_SOURCES, allowed_sources_for_age, PAEDIATRIC_AGE_THRESHOLD,
)
from vector_store import build_or_load_store
from prompt_builder import (
    make_prompt, build_drug_verdict, build_report_json,
    extract_drug_recommendation, ensure_verification_line,
    fix_references, normalize_frequency_to_hours,
    enforce_allergy_in_recommendations,
    _parse_weight_kg, determine_relevance,
    _dedupe_issue_lines, _dedupe_issues_in_llm_output,
    _strip_stray_separators, _build_drug_citation_map,
    _inject_recommendation_citations, _append_citation_to_recommendation,
    _strip_correct_verdict_bullets,
    filter_and_renumber_citations,
)
from llm_client import call_ollama
from drug_database import (
    resolve_drug_name, get_drug_class,
    check_ingredient_duplication, check_class_overlap, check_max_dose_safety,
    check_allergy_conflicts, check_prn_appropriateness,
    check_restricted_drugs, check_negative_indications,
    DrugClass,
)
from reranker import hybrid_rerank

try:
    from flask_cors import CORS
    _HAS_CORS = True
except ImportError:
    _HAS_CORS = False


# ============================================================
# Metadata-aware retrieval helper
# ============================================================
def infer_expected_metadata(diagnosis: str, medicines: list) -> dict:
    """
    Build the `expected` dict that vector_store.search() uses for metadata
    reranking. Pulls condition/chapter/severity from guideline_db aliases.
    """
    expected = {
        "chapter": "", "condition": "", "section_type": "treatment",
        "severity": "", "route": "", "drug_names": [],
    }
    if not diagnosis:
        return expected

    diag_lower = diagnosis.lower()

    try:
        from guideline_db import normalise_diagnosis
        cond, sev = normalise_diagnosis(diagnosis)
        if cond:
            expected["condition"] = cond
        if sev:
            sev_map = {"mild": "mild_or_low", "moderate": "moderate",
                       "severe": "severe_or_high"}
            expected["severity"] = sev_map.get(sev, sev)
    except Exception:
        pass

    chapter_keywords = [
        ("skin", "Skin and Soft Tissue Infections"),
        ("cellulitis", "Skin and Soft Tissue Infections"),
        ("abscess", "Skin and Soft Tissue Infections"),
        ("urin", "Urology Infections"),
        ("pyelonephritis", "Urology Infections"),
        ("cystitis", "Urology Infections"),
        ("uti", "Urology Infections"),
        ("respiratory", "Respiratory Tract Infections"),
        ("pneumonia", "Respiratory Tract Infections"),
        ("cap", "Respiratory Tract Infections"),
        ("hap", "Respiratory Tract Infections"),
        ("meningitis", "Central Nervous System Infections"),
        ("encephalitis", "Central Nervous System Infections"),
        ("bone", "Bone and Joint Infections"),
        ("joint", "Bone and Joint Infections"),
        ("osteomyelitis", "Bone and Joint Infections"),
        ("septic arthritis", "Bone and Joint Infections"),
        ("ent", "Ear, Nose, and Throat Infections"),
        ("otitis", "Ear, Nose, and Throat Infections"),
        ("sinusitis", "Ear, Nose, and Throat Infections"),
        ("pharyngitis", "Ear, Nose, and Throat Infections"),
        ("ophthalm", "Ophthalmology Infections"),
        ("conjunctivitis", "Ophthalmology Infections"),
        ("hiv", "HIV Related Opportunistic Infections"),
        ("tropical", "Tropical Infections"),
        ("dengue", "Tropical Infections"),
        ("typhoid", "Tropical Infections"),
        ("malaria", "Tropical Infections"),
        ("cardiovascular", "Cardiovascular System Infections"),
        ("endocarditis", "Cardiovascular System Infections"),
        ("gastro", "Gastrointestinal Infections"),
        ("diarrhoea", "Gastrointestinal Infections"),
        ("diarrhea", "Gastrointestinal Infections"),
        ("cholecystitis", "Gastrointestinal Infections"),
        ("febrile neutropenia", "Febrile Neutropenia"),
        ("surgical site", "Surgical Site Infection"),
        ("genital", "Genital and Sexually Transmitted Infections"),
        ("gynae", "Obstetrics and Gynaecology Infections"),
        ("obstetric", "Obstetrics and Gynaecology Infections"),
    ]
    for kw, chapter_name in chapter_keywords:
        if kw in diag_lower:
            expected["chapter"] = chapter_name
            break

    routes = set()
    for m in medicines or []:
        r = (m.get("route") or "").upper().strip()
        if r in ("PO", "IV", "IM", "SC"):
            routes.add(r)
    if routes == {"PO"}:
        expected["route"] = "PO"
    elif "IV" in routes:
        expected["route"] = "IV"

    expected["drug_names"] = [
        m.get("generic_name", "").lower()
        for m in medicines or []
        if m.get("drug_class") == DrugClass.ANTIBIOTIC and m.get("generic_name")
    ]

    return expected


# ============================================================
# Parse the unified LLM response into per-drug sections
# ============================================================
_SECTION_PATTERN = re.compile(
    r'^[\s]*---\s*([^\n-][^\n]*?)\s*---\s*$',
    re.MULTILINE,
)


def parse_unified_response(text: str, medicines: list) -> dict:
    """
    Split the unified LLM output on `--- drug_name ---` markers and map each
    section to a prescribed drug by name match. Returns a dict keyed by
    lowercase drug name -> section body text.
    """
    drug_names = [m["generic_name"].lower() for m in medicines]
    sections = {}

    matches = list(_SECTION_PATTERN.finditer(text))
    for i, match in enumerate(matches):
        header = match.group(1).strip().lower()
        # strip optional parenthetical e.g. "ceftriaxone (iv)"
        header = re.sub(r'\s*\([^)]*\)\s*', ' ', header).strip()

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # Match header to a prescribed drug name
        matched = None
        for dn in drug_names:
            if header == dn or dn in header or header in dn:
                matched = dn
                break
        if matched and matched not in sections:
            sections[matched] = body

    return sections


# ============================================================
# Flask app setup
# ============================================================
app = Flask(__name__)

if _HAS_CORS:
    CORS(app, resources={r"/*": {"origins": "*"}})


@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


print("Initializing vector store...")
STORE = build_or_load_store()
print(f"Vector store ready with {len(STORE.texts)} documents")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "docs": len(STORE.texts), "model": OLLAMA_MODEL})


@app.route("/ask", methods=["POST", "OPTIONS"])
def ask():
    if request.method == "OPTIONS":
        resp = make_response("", 200)
        req_headers = request.headers.get("Access-Control-Request-Headers", "")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = (
            req_headers if req_headers else "Content-Type, Authorization"
        )
        return resp

    t0 = time.time()
    data = request.get_json(force=True, silent=True) or {}

    with open('received_data.json', 'w') as json_file:
        json.dump(data, json_file, indent=2)

    print("\n" + "=" * 60)
    print("DEBUG: Received data from Flutter")
    print("=" * 60)
    print(json.dumps(data, indent=2))

    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing 'question'"}), 400

    k = int(data.get("k", TOP_K))
    age_raw = data.get("age", None)
    try:
        age = int(age_raw) if age_raw else None
    except (ValueError, TypeError):
        age = None

    patient_data = data.get("patient", {})
    labs_data = data.get("labs", {})
    vitals_data = data.get("vitals", {})
    diagnosis = (data.get("diagnosis") or "").strip()
    medicines_raw = data.get("prescribed_medicines", [])

    if age and age < 18:
        print(f"[INFO] Paediatric patient (age={age}) - "
              f"restricting retrieval to PAEDIATRIC + RENAL + ANTICOAG sources")
    elif age:
        print(f"[INFO] Adult patient (age={age}) - "
              f"restricting retrieval to ADULT + RENAL + ANTICOAG sources")
    else:
        print("[INFO] Age not provided - allowing all guideline sources")

    # Age-gated guideline routing:
    #   age <= PAEDIATRIC_AGE_THRESHOLD (18) -> only 4_xx paediatric files
    #   age >  PAEDIATRIC_AGE_THRESHOLD       -> only 3_xx adult files
    #   age missing                           -> fall back to all sources
    # Renal-dose and anticoagulant guides are always included since they
    # apply across populations.
    allowed = allowed_sources_for_age(age)
    print(f"[INFO] Allowed retrieval sources for this request: {sorted(allowed)}")

    # =====================================================
    # PHASE 1: PRE-PROCESSING
    # =====================================================
    medicines = []
    preprocessing_alerts = []

    for med in medicines_raw:
        if not med:
            continue
        original_name = med.get("name", "").strip()
        if not original_name:
            continue

        generic_name, original, was_corrected = resolve_drug_name(original_name)

        if was_corrected:
            print(f"DEBUG: Drug name corrected: '{original_name}' -> '{generic_name}'")
            preprocessing_alerts.append({
                "type": "SPELL_CORRECTION",
                "severity": "INFO",
                "message": (
                    f"Drug name '{original_name}' was auto-corrected to "
                    f"'{generic_name}'. Please verify this is correct."
                )
            })

        enriched = {
            "name": generic_name,
            "generic_name": generic_name,
            "original_name": original_name,
            "was_corrected": was_corrected,
            "dose": med.get("dose", ""),
            "unit": med.get("unit", "mg"),
            "frequency": med.get("frequency", ""),
            "route": med.get("route", ""),
            "prn": bool(med.get("prn", False)),
            "drug_class": get_drug_class(generic_name),
        }

        raw_freq = enriched["frequency"]
        if raw_freq:
            freq_hours = normalize_frequency_to_hours(raw_freq)
            if freq_hours:
                standard_freq = {
                    4: "q4H", 6: "q6H", 8: "q8H", 12: "q12H",
                    24: "q24H", 48: "q48H", 72: "q72H",
                }.get(freq_hours)
                if standard_freq:
                    enriched["frequency_raw"] = raw_freq
                    enriched["frequency"] = standard_freq
                    enriched["frequency_hours"] = freq_hours
                    print(f"DEBUG: Frequency normalised: '{raw_freq}' -> "
                          f"'{standard_freq}' ({freq_hours}h)")

        medicines.append(enriched)

    print(f"\nDEBUG: Processed {len(medicines)} medicines:")
    for m in medicines:
        prn_tag = " [PRN]" if m.get("prn") else ""
        route_tag = f" ({m['route']})" if m.get("route") else ""
        print(f"  {m['original_name']} -> {m['generic_name']} "
              f"[{m['drug_class']}]{route_tag}{prn_tag}")

    # =====================================================
    # PHASE 2: DETERMINISTIC SAFETY CHECKS
    # =====================================================
    allergy_text = (
        vitals_data.get("allergy_details") or vitals_data.get("allergy")
        or patient_data.get("allergy_details") or patient_data.get("allergy")
        or ""
    )

    preprocessing_alerts.extend(check_allergy_conflicts(medicines, allergy_text))
    preprocessing_alerts.extend(check_prn_appropriateness(medicines))
    preprocessing_alerts.extend(check_restricted_drugs(medicines))
    preprocessing_alerts.extend(check_negative_indications(medicines, diagnosis))
    preprocessing_alerts.extend(check_ingredient_duplication(medicines))
    preprocessing_alerts.extend(check_class_overlap(medicines))

    for med in medicines:
        dose_str = med.get("dose", "")
        unit = med.get("unit", "mg")
        frequency = med.get("frequency", "")
        try:
            dose_val = float(dose_str)
            if unit.lower() == 'g':
                dose_val = dose_val * 1000
        except (ValueError, TypeError):
            continue
        freq_hours = normalize_frequency_to_hours(frequency) if frequency else None
        dose_alert = check_max_dose_safety(med["generic_name"], dose_val, freq_hours)
        if dose_alert:
            preprocessing_alerts.append(dose_alert)

    if preprocessing_alerts:
        print(f"\nDEBUG: Total preprocessing alerts: {len(preprocessing_alerts)}")
        for a in preprocessing_alerts:
            print(f"  [{a['severity']}] {a['message']}")

    # =====================================================
    # PHASE 3: DIAGNOSIS-LEVEL RETRIEVAL
    # =====================================================
    antimicrobial_names = [
        m["generic_name"] for m in medicines
        if m["drug_class"] == DrugClass.ANTIBIOTIC
    ]

    print(f"DEBUG: Retrieval query: {diagnosis}")
    expected_meta = infer_expected_metadata(diagnosis, medicines)
    print(f"DEBUG: Expected metadata: {expected_meta}")

    try:
        retrieved_all = STORE.search(
            diagnosis, k=max(k * 3, k + 5), expected=expected_meta,
        )
        retrieved = [
            item for item in retrieved_all
            if item.get("meta", {}).get("source") in allowed
        ]

        # Hard rule: if the age-based source filter wiped everything out, do
        # NOT silently fall back to the unfiltered list. The previous
        # behaviour was `if not retrieved: retrieved = retrieved_all`, which
        # is what allowed paediatric chunks to leak into adult outputs
        # (and vice versa) whenever the filter eliminated all candidates.
        # Instead, flag RAG failure so downstream stages know the LLM is
        # operating without retrieved evidence for this population.
        rag_failure = False
        if not retrieved:
            print(
                f"[WARN] No chunks matched allowed sources {sorted(allowed)} "
                f"for age={age}. Flagging RAG failure rather than leaking "
                f"wrong-population content."
            )
            rag_failure = True

        rerank_query = f"{diagnosis} {' '.join(antimicrobial_names)} antimicrobial treatment"
        retrieved = hybrid_rerank(rerank_query, retrieved, top_k=k)
        print(f"DEBUG: Retrieved {len(retrieved)} documents for diagnosis")

        # RAG-failure guardrail (also catches the case where rerank dropped
        # everything below min_score)
        if len(retrieved) == 0:
            rag_failure = True
            print("DEBUG: RAG FAILURE - no diagnosis chunks retrieved.")
        elif diagnosis:
            diag_keywords = [w for w in diagnosis.lower().split() if len(w) > 3]
            any_diag_mention = any(
                any(kw in item.get("text", "").lower() for kw in diag_keywords)
                for item in retrieved
            )
            if not any_diag_mention:
                rag_failure = True
                print("DEBUG: RAG FAILURE - retrieved chunks don't mention diagnosis.")

        # Per-drug reverse lookup (cheap - no LLM, just vector search)
        per_drug_results = {}
        for med in medicines:
            drug_name = med["generic_name"]
            found_in_diagnosis_chunks = any(
                drug_name.lower() in item["text"].lower() for item in retrieved
            )

            # Pass the diagnosis-level expected metadata so the chapter/route
            # preference is baked into distance ranking BEFORE the source
            # filter step. This gives defensive depth: even if a chunk has a
            # stale `source` tag in ChromaDB (e.g. a paediatric file mistagged
            # as ADULT from an older build), the chapter mismatch will demote
            # it in the adjusted distance.
            drug_expected = dict(expected_meta)
            drug_expected["drug_names"] = [drug_name.lower()]
            drug_results_raw = STORE.search(
                drug_name, k=10, expected=drug_expected,
            )
            drug_results = [
                item for item in drug_results_raw
                if item.get("meta", {}).get("source") in allowed
            ]

            indicated_contexts = []
            indicated_chunks = []
            for item in drug_results:
                if drug_name.lower() in item["text"].lower():
                    meta = item.get("meta", {})
                    file_path = meta.get("file_path", "")
                    source_label = meta.get("source", "")
                    page = meta.get("page", "")
                    import os
                    basename = os.path.basename(file_path) if file_path else ""
                    chapter_name = basename
                    for ext in ('.pdf', '.PDF', '.txt', '.docx'):
                        if chapter_name.endswith(ext):
                            chapter_name = chapter_name[:-len(ext)]
                    context_entry = {
                        "chapter": chapter_name,
                        "source": source_label,
                        "page": page,
                        "snippet": item["text"][:300],
                    }
                    if chapter_name not in [c["chapter"] for c in indicated_contexts]:
                        indicated_contexts.append(context_entry)
                    indicated_chunks.append(item)

            per_drug_results[drug_name] = {
                "found_in_diagnosis_chunks": found_in_diagnosis_chunks,
                "indicated_contexts": indicated_contexts,
                "indicated_chunks": indicated_chunks,
                "results": drug_results,
            }
            print(f"DEBUG: Drug '{drug_name}' - "
                  f"in_diagnosis_chunks={found_in_diagnosis_chunks}, "
                  f"indicated_chapters={[c['chapter'] for c in indicated_contexts]}")

        # =====================================================
        # PHASE 4: COMPUTE DETERMINISTIC VERDICTS + ASSIGN RANKS
        # =====================================================
        weight_kg = _parse_weight_kg(patient_data)

        drug_verdicts = {}
        for med in medicines:
            name = med["generic_name"]
            drug_lookup = per_drug_results.get(name, {})
            indicated_chunks = drug_lookup.get("indicated_chunks", [])
            verdict = build_drug_verdict(
                med, retrieved, indicated_chunks, weight_kg, diagnosis=diagnosis
            )
            drug_verdicts[name.lower()] = verdict

        # Assign reference ranks across diagnosis + per-drug indicated chunks
        next_rank = 1
        seen_ids = set()
        for item in retrieved:
            key = (item.get("meta", {}).get("file_path", ""),
                   item.get("meta", {}).get("page", ""),
                   item.get("text", "")[:80])
            if key in seen_ids:
                continue
            seen_ids.add(key)
            item["rank"] = next_rank
            next_rank += 1

        for drug_name, drug_lookup in per_drug_results.items():
            for item in drug_lookup.get("indicated_chunks", []):
                key = (item.get("meta", {}).get("file_path", ""),
                       item.get("meta", {}).get("page", ""),
                       item.get("text", "")[:80])
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                item["rank"] = next_rank
                next_rank += 1

        # =====================================================
        # PHASE 5: SINGLE UNIFIED LLM CALL
        # =====================================================
        prompt = make_prompt(
            question=question,
            retrieved=retrieved,
            patient=patient_data,
            labs=labs_data,
            vitals=vitals_data,
            diagnosis=diagnosis,
            medicines=medicines,
            per_drug_results=per_drug_results,
            preprocessing_alerts=preprocessing_alerts,
            rag_failure=rag_failure,
        )
        print(f"DEBUG: Unified prompt length: {len(prompt)} chars")

        try:
            llm_response = call_ollama(prompt)
            print(f"DEBUG: Raw LLM response ({len(llm_response)} chars):")
            print("=" * 60)
            print(llm_response)
            print("=" * 60)
            llm_response = ensure_verification_line(llm_response)
            llm_response = enforce_allergy_in_recommendations(llm_response, allergy_text)
            llm_response = fix_references(llm_response, retrieved)
            # Strip "- Dose: X - CORRECT ..." and "- Frequency: X - CORRECT ..."
            # bullets that the LLM emits even when the verdict feed doesn't
            # contain them. Issues blocks must only show problems.
            llm_response = _strip_correct_verdict_bullets(llm_response)
            # Collapse near-duplicate Issues bullets that the LLM occasionally
            # emits when both VERDICTS and SAFETY ALERTS describe the same
            # finding (e.g. site-restricted + does-not-penetrate-kidney).
            llm_response = _dedupe_issues_in_llm_output(llm_response)
            # Drop bare '---' separator lines that aren't part of a real
            # '--- drug_name ---' header.
            llm_response = _strip_stray_separators(llm_response)
            # Backfill [N] citations on any Recommendation line that the
            # LLM forgot to cite, using the most drug-relevant reference.
            drug_to_ranks = _build_drug_citation_map(
                medicines, retrieved, per_drug_results,
            )
            llm_response = _inject_recommendation_citations(
                llm_response, drug_to_ranks,
            )
        except Exception as llm_err:
            print(f"DEBUG: !!! Unified LLM call failed: {llm_err}")
            import traceback
            traceback.print_exc()
            llm_response = (
                "The AI analysis service is temporarily unavailable. "
                "System-computed verdicts (dose checks, allergy alerts, class overlap, "
                "monitoring) below are still valid. Please review each drug manually "
                "against the UMMC Antimicrobial Guidelines."
            )

        # =====================================================
        # PHASE 6: PARSE PER-DRUG SECTIONS FROM UNIFIED RESPONSE
        # =====================================================
        parsed_sections = parse_unified_response(llm_response, medicines)
        print(f"DEBUG: Parsed {len(parsed_sections)} per-drug sections from LLM output")

        drug_recommendations = {}
        per_drug_responses = []

        for med in medicines:
            name = med["generic_name"]
            name_lower = name.lower()
            section_text = parsed_sections.get(name_lower, "")

            if not section_text:
                # LLM skipped this drug - synthesize a section from the
                # deterministic verdict + alerts. The Assessment and
                # Recommendation are chosen based on what was actually found,
                # not a generic "review manually" default.
                v = drug_verdicts.get(name_lower, {})

                # Collect drug-specific alerts (single-drug or multi-drug)
                drug_alert_lines = []
                has_critical_alert = False
                has_warning_alert = False
                for a in preprocessing_alerts:
                    single = (a.get("drug") or "").lower().strip()
                    multi = [str(d).lower().strip() for d in (a.get("drugs") or [])]
                    if name_lower == single or name_lower in multi:
                        sev = a.get("severity", "")
                        msg = (a.get("message") or "").strip()
                        if msg:
                            drug_alert_lines.append(f"- {msg}")
                        if sev == "CRITICAL":
                            has_critical_alert = True
                        elif sev == "WARNING":
                            has_warning_alert = True

                should_discontinue = v.get("should_discontinue", False)
                dose_bad = v.get("dose_verdict") in ("INCORRECT", "EXCEEDS")
                freq_bad = v.get("freq_verdict") == "INCORRECT"

                # Assessment label
                if (should_discontinue or has_critical_alert
                        or v.get("dose_verdict") == "EXCEEDS"):
                    assessment = "Unsafe"
                elif dose_bad or freq_bad or has_warning_alert:
                    assessment = "Needs Review"
                else:
                    assessment = "Safe"

                # Compact form for Safe: no need to list CORRECT verdicts or
                # write a long justification - just 3 short lines.
                if assessment == "Safe":
                    section_text = (
                        "Assessment: Safe\n"
                        "Issues: None\n"
                        "Recommendation: Continue"
                    )
                else:
                    fallback_lines = [f"Assessment: {assessment}", "Issues:"]

                    # Collect all candidate issue lines, then deduplicate to
                    # avoid the "site-restricted + does NOT penetrate kidney
                    # tissue" double-listing seen in earlier test rounds.
                    candidate_issues = []
                    if v.get("verdict_lines"):
                        for line in v["verdict_lines"]:
                            candidate_issues.append(line.strip())
                    candidate_issues.extend(drug_alert_lines)

                    deduped_issues = _dedupe_issue_lines(candidate_issues)
                    for line in deduped_issues:
                        # Normalize bullet prefix - some sources already include
                        # a leading "- ", others don't.
                        if line.lstrip().startswith("-"):
                            fallback_lines.append(line)
                        else:
                            fallback_lines.append(f"- {line}")
                    if not deduped_issues:
                        fallback_lines.append("- None")

                    # Recommendation - pick the most actionable one
                    if should_discontinue:
                        reason = v.get("discontinue_reason") or "this drug is not indicated"
                        rec = (
                            f"It is recommended to discontinue {name} and switch to a "
                            f"guideline-recommended alternative, since {reason}."
                        )
                    elif has_critical_alert:
                        rec = (
                            f"It is recommended to discontinue {name} due to the safety "
                            f"alert above and consult the prescriber for an alternative."
                        )
                    elif dose_bad and v.get("dose_target_str"):
                        rec = (
                            f"It is recommended to adjust the dose of {name} to match the "
                            f"guideline target ({v['dose_target_str']})."
                        )
                    elif freq_bad and v.get("freq_target_str"):
                        rec = (
                            f"It is recommended to adjust the frequency of {name} to match "
                            f"the guideline target ({v['freq_target_str']})."
                        )
                    elif has_warning_alert:
                        rec = (
                            f"It is recommended to review {name} with the prescriber given "
                            f"the alert(s) above."
                        )
                    else:
                        rec = (
                            f"It is recommended to review {name} manually against the "
                            f"UMMC Antimicrobial Guidelines."
                        )

                    fallback_lines.append(f"Recommendation: {rec}")
                    section_text = "\n".join(fallback_lines)

                    # Append [N] citation to the fallback Recommendation so
                    # the prescriber gets a pointer even when the LLM didn't
                    # produce a section.
                    fallback_ranks_map = _build_drug_citation_map(
                        [med], retrieved, per_drug_results,
                    )
                    fallback_ranks = fallback_ranks_map.get(name_lower, [])
                    if fallback_ranks:
                        section_text = _append_citation_to_recommendation(
                            section_text, fallback_ranks,
                        )

            drug_recommendations[name_lower] = extract_drug_recommendation(section_text)
            tier, tier_explanation = determine_relevance(
                med, retrieved, diagnosis, per_drug_results,
                patient_allergy=allergy_text,
            )

            # Feed NOT_INDICATED tier back into drug_verdicts so that
            # build_ai_suggestion() (Phase 7) knows this drug should be
            # removed from the AI suggestion. determine_relevance() uses
            # the structured guideline DB which is more comprehensive than
            # the NEGATIVE_INDICATIONS table that build_drug_verdict()
            # checks, so this catches cases like "ceftriaxone not in CAP
            # regimen" that the verdict alone would miss.
            if tier == "NOT_INDICATED":
                v = drug_verdicts.get(name_lower, {})
                if not v.get("should_discontinue"):
                    v["should_discontinue"] = True
                    v["discontinue_reason"] = (
                        v.get("discontinue_reason")
                        or f"{name} is not indicated for '{diagnosis}'"
                    )
                    drug_verdicts[name_lower] = v
                    print(f"DEBUG: Updated verdict for '{name}' - "
                          f"should_discontinue=True (from determine_relevance)")

            per_drug_responses.append({
                "drug": name, "tier": tier, "response": section_text,
            })
            print(f"DEBUG: Drug '{name}' tier={tier} "
                  f"action={drug_recommendations[name_lower]['action']}")

        # =====================================================
        # PHASE 7: BUILD STRUCTURED REPORT
        # =====================================================
        # Compute age in months for guideline lookup (some structured
        # regimens have age_min_months / age_max_months bounds).
        patient_age_months = None
        if age is not None:
            try:
                patient_age_months = float(age) * 12.0
            except (ValueError, TypeError):
                patient_age_months = None

        report = build_report_json(
            diagnosis=diagnosis,
            medicines=medicines,
            preprocessing_alerts=preprocessing_alerts,
            drug_verdicts=drug_verdicts,
            drug_recommendations=drug_recommendations,
            retrieved=retrieved,
            rag_failure=rag_failure,
            patient_allergy=allergy_text,
            patient_age_months=patient_age_months,
            allowed_sources=allowed,
        )

        # =====================================================
        # PHASE 8: ASSEMBLE PLAIN-TEXT ANSWER
        # =====================================================
        answer_parts = []
        answer_parts.append(f"Assessment: {report['assessment']}")
        answer_parts.append(f"Diagnosis: {diagnosis}")
        answer_parts.append("")

        if report.get("alerts"):
            answer_parts.append("Clinical Flags:")
            for a in report["alerts"]:
                answer_parts.append(f"  - {a}")
            answer_parts.append("")

        for r in per_drug_responses:
            tier = r.get("tier", "")
            drug_name = r["drug"]
            from drug_database import is_supportive_care as _is_sc
            if tier == "SUPPORTIVE_CARE" or _is_sc(drug_name):
                header = f"--- {drug_name} (supportive care) ---"
            else:
                header = f"--- {drug_name} ---"
            answer_parts.append(header)
            answer_parts.append(r["response"])
            answer_parts.append("")

        if report.get("monitoring"):
            answer_parts.append("Monitoring:")
            for m in report["monitoring"]:
                answer_parts.append(f"  {m['drug']}:")
                for p in m["params"]:
                    answer_parts.append(f"    * {p}")
            answer_parts.append("")

        if report.get("interactions"):
            answer_parts.append("Drug-drug interactions:")
            for n in report["interactions"]:
                answer_parts.append(f"  - {n}")
            answer_parts.append("")

        answer_text = "\n".join(answer_parts).rstrip()
        answer_text = ensure_verification_line(answer_text)

        # Filter references to only those actually cited in the answer text,
        # and renumber so the cited ones become [1], [2], ... consecutively.
        # Update both the answer text (citations renumbered inline) and
        # report["references"] (so the Flutter UI shows the same trimmed list).
        if report.get("references"):
            answer_text, filtered_refs = filter_and_renumber_citations(
                answer_text, report["references"]
            )
            report["references"] = filtered_refs
            if filtered_refs:
                answer_text += "\n\nReferences:\n" + "\n".join(filtered_refs)

        elapsed = round(time.time() - t0, 3)
        print(f"DEBUG: Total request time: {elapsed}s")

        return jsonify({
            "question": question,
            "answer": answer_text,
            "report": report,
            "retrieved": retrieved,
            "preprocessing_alerts": preprocessing_alerts,
            "rag_failure": rag_failure,
            "elapsed_s": elapsed,
        })

    except Exception as e:
        elapsed = round(time.time() - t0, 3)
        print(f"DEBUG: ERROR - {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Backend failed: {e}", "elapsed_s": elapsed}), 500


if __name__ == "__main__":
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)