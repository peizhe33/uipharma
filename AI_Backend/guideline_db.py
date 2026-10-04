"""
Structured Clinical Guideline Database (Path A from the evaluation report).

This module is the structured-lookup half of the new hybrid architecture:
    Structured lookup  -->  if hit, use deterministically
            |
            v  (miss)
    RAG retrieval      -->  fallback for everything not yet structured

WHY THIS EXISTS
---------------
Pure RAG returns blobs of guideline text. The LLM then has to interpret
which severity tier, which alternative, which exception applies. It often
guesses wrong (see test report - Case 3 cefalexin missed; metronidazole
mis-tagged; clindamycin 1080mg overdose from wrong row).

A structured table makes that lookup deterministic. You ask:
    "What is the regimen for cellulitis, mild severity, penicillin allergy?"
and you get back a list of exact regimen rows from the guideline.

SCHEMA
------
Top-level dict GUIDELINE_REGIMENS maps a chapter key (e.g. "ssti") to
a list of regimen rows. Each row has:

    condition           lower-case canonical name (e.g. "cellulitis")
    severity            "mild" | "moderate" | "severe" | None
    tier                "preferred" | "alternative" | "penicillin_allergy"
                        | "mrsa_suspected" | "mrsa_severe" | etc.
    drug                lower-case generic name
    dose_value          numeric dose value
    dose_unit           "mg" | "g" | "mg/kg" | "tablet" | "iu"
    dose_qualifier      free-text qualifier (e.g. "(max 2 g)" or
                        "loading then maintenance")
    route               "PO" | "IV" | "IM" | "SC" | "Topical" | "PR" | "SL"
    frequency           "q6H" | "q8H" | "q12H" | "q24H" | "BID" | etc.
    duration_days       "5-7" | "10-14" | "7" | None
    notes               list of free-text clinical notes
    page                page number in the PDF (for citation)
    source_chapter      chapter identifier (e.g. "3.10")
    contraindications   list of patient-state strings (e.g. ["penicillin allergy"])
    pathogen_context    list of organisms covered (e.g. ["S. aureus"])

OPTIONAL AGE FIELDS (added when paediatric coverage was introduced)
-------------------------------------------------------------------
    age_group           "adult" | "paediatric" | "neonatal" | "all"
                        If absent, treated implicitly as "adult" so the
                        original 543 adult rows do not need editing.
    age_min_months      float, inclusive minimum age in months (optional)
    age_max_months      float, exclusive maximum age in months (optional)
                        When age_min/max are present they take precedence
                        over age_group. Use both to encode fine-grained
                        constraints like "nitrofurantoin paediatric, only
                        >=3 months" -> age_group="paediatric", age_min_months=3.

PUBLIC API
----------
    lookup_regimens(condition, severity=None, tier=None, age_months=None)
        -> list[dict]   matching regimen rows, or empty list

    find_drug_in_regimen(drug, condition, severity=None, age_months=None)
        -> dict | None  the matching row if drug is in the regimen for
                        this condition/severity/age

    is_drug_indicated(drug, condition, severity=None, allergy=None,
                       age_months=None)
        -> (bool, list[dict], str)   (indicated?, which rows it matches,
                                       explanation)

    expected_doses_for(drug, condition, severity=None, age_months=None)
        -> list[(value, unit, route, frequency)]
                        all expected dose patterns for drug+condition+age

AGE FILTERING SEMANTICS
-----------------------
    age_months=None             -> no age filtering (backward compatible)
    age_months >= 216 (>=18yr)  -> only "adult" + "all" rows
    2 <= age_months < 216       -> only "paediatric" + "all" rows
    age_months < 2              -> only "neonatal" + "all" rows
    Rows with explicit age_min/max bounds further refine matching.
    Rows with severity=None match ANY queried severity (treat as
    severity-agnostic, useful for paediatric chapters where UMMC does
    not differentiate severity).

COVERAGE
--------
Adult chapters: all 16 chapters of UMMC Antimicrobial Guidelines 3rd Ed
plus MOH Anticoagulant Quick Guide are populated.
Paediatric chapters: Urology (4.9) is populated. Other paediatric
chapters (4.x) follow the same schema and will be added incrementally.
The system falls back to RAG for any chapter not yet structured.
"""

from typing import Dict, List, Optional, Tuple, Any


# =========================================================================
# REGIMEN DATA - this is the structured-knowledge core.
#
# Adding a chapter is purely a data change - no code modification needed.
# Just append regimen rows to the "ssti" list, or add a new chapter key
# (e.g. "rti", "urology") and add rows under it.
# =========================================================================

GUIDELINE_REGIMENS: Dict[str, List[Dict[str, Any]]] = {

    # =====================================================================
    # CHAPTER 3.10 - SKIN AND SOFT TISSUE INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-22
    # =====================================================================
    "ssti": [

        # ----- CELLULITIS - MILD (page 6) -----
        # Preferred: Cloxacillin / Phenoxymethylpenicillin / Amoxicillin 500mg PO q6H
        # Alternative: Cefalexin 500mg PO q6H
        # Penicillin-allergy options (separate page entries): Clindamycin 300mg PO q6H
        {
            "condition": "cellulitis", "severity": "mild", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "First-line for mild cellulitis.",
                "S. pyogenes / S. aureus coverage.",
                "Elevation of the leg is important to aid healing.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 6, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "mild", "tier": "preferred",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["* If only S. pyogenes is strongly suspected or cultured."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "mild", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["* If only S. pyogenes is strongly suspected or cultured."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "mild", "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "Listed as alternative for mild cellulitis in UMMC guideline.",
                "Use with caution in penicillin-allergic patients - cross-reactivity is well-documented.",
            ],
            "contraindications": ["severe penicillin allergy (anaphylaxis)"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 6, "source_chapter": "3.10",
        },
        # Penicillin-allergy option for mild/moderate cellulitis (page 7)
        {
            "condition": "cellulitis", "severity": "mild", "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 300, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "Penicillin-allergy alternative for cellulitis.",
                "Also listed when MRSA is suspected in mild infection.",
                "Monitor for C. difficile-associated diarrhoea.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes",
                                  "MRSA (mild)"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "mild", "tier": "penicillin_allergy",
            "drug": "erythromycin",
            "dose_value": 400, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "Erythromycin ethyl succinate - macrolide alternative for penicillin allergy.",
            ],
            "contraindications": [],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "mild", "tier": "penicillin_allergy",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "3-4 tablets",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": [
                "Co-trimoxazole. May NOT cover Streptococci - consider only if S. aureus is the likely pathogen.",
            ],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 6, "source_chapter": "3.10",
        },

        # ----- CELLULITIS - MODERATE (page 7) -----
        {
            "condition": "cellulitis", "severity": "moderate", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["IV antibiotics should be de-escalated to oral once clinical improvement occurs."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "moderate", "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "If not responded to Cefazolin or Cloxacillin, consider Co-amoxiclav 1.2g IV q8H.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 7, "source_chapter": "3.10",
        },

        # ----- CELLULITIS - SEVERE (page 7) -----
        {
            "condition": "cellulitis", "severity": "severe", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": ["Severe cellulitis - IV therapy required."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "severe", "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "severe", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["** If not responded to Cefazolin or Cloxacillin."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus",
                                 "anaerobes"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "severe", "tier": "alternative",
            "drug": "ampicillin-sulbactam",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["** If not responded to Cefazolin or Cloxacillin."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "staphylococcus aureus",
                                 "anaerobes"],
            "page": 7, "source_chapter": "3.10",
        },
        # MRSA-suspected paths (page 7)
        {
            "condition": "cellulitis", "severity": "severe", "tier": "mrsa_severe",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "(max 1 g); 20 mg/kg (max 2 g) IV single loading dose first",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "10-14",
            "notes": [
                "Only when MRSA is suspected in severe infection.",
                "Optimise dose with therapeutic drug monitoring (trough 15-20 mg/L).",
                "Monitor renal function.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 7, "source_chapter": "3.10",
        },
        # Special-population add-on regimens (page 7 notes)
        {
            "condition": "cellulitis", "severity": "severe",
            "tier": "diabetic_or_immunocompromised",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": [
                "Reserve for: diabetic / immunocompromised / shock / non-responder to co-amoxiclav or ampicillin-sulbactam.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad spectrum"],
            "page": 7, "source_chapter": "3.10",
        },
        {
            "condition": "cellulitis", "severity": "severe", "tier": "esbl_or_pen_allergy",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "Reserve for ESBL risk, failed piperacillin-tazobactam, or penicillin allergy.",
                "Carbapenem - restricted use.",
            ],
            "contraindications": [],
            "pathogen_context": ["ESBL", "broad spectrum"],
            "page": 7, "source_chapter": "3.10",
        },

        # =================================================================
        # IMPETIGO (page 5)
        # Mild: topical mupirocin / fusidic acid
        # Severe / extensive: oral cloxacillin or similar
        # =================================================================
        {
            "condition": "impetigo", "severity": "mild", "tier": "preferred",
            "drug": "mupirocin",
            "dose_value": 2, "dose_unit": "%",
            "dose_qualifier": "topical ointment",
            "route": "Topical", "frequency": "q8H",
            "duration_days": "5",
            "notes": ["Apply to affected area. Topical first-line for localised impetigo."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes"],
            "page": 5, "source_chapter": "3.10",
        },
        {
            "condition": "impetigo", "severity": "moderate", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["For extensive impetigo or treatment failure of topical therapy."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes"],
            "page": 5, "source_chapter": "3.10",
        },

        # =================================================================
        # ERYSIPELAS (page 8)
        # =================================================================
        {
            "condition": "erysipelas", "severity": "mild", "tier": "preferred",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": ["Streptococcus pyogenes is the primary pathogen in erysipelas."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 8, "source_chapter": "3.10",
        },
        {
            "condition": "erysipelas", "severity": "mild", "tier": "penicillin_allergy",
            "drug": "erythromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": [],
            "contraindications": [],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 8, "source_chapter": "3.10",
        },
        {
            "condition": "erysipelas", "severity": "moderate", "tier": "preferred",
            "drug": "benzylpenicillin",
            "dose_value": 1.2, "dose_unit": "g",
            "dose_qualifier": "(2 million units)",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": ["IV therapy for moderate-to-severe erysipelas."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 8, "source_chapter": "3.10",
        },

        # =================================================================
        # NECROTISING FASCIITIS (page 9-10)
        # Emergency, broad-spectrum + anaerobic + MRSA cover required
        # =================================================================
        {
            "condition": "necrotising fasciitis", "severity": "severe", "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "until source-controlled and clinically improved",
            "notes": [
                "Emergency surgical debridement is the priority.",
                "Add clindamycin for toxin suppression.",
                "Consider IVIG for streptococcal toxic shock.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["polymicrobial", "group A strep", "anaerobes"],
            "page": 9, "source_chapter": "3.10",
        },
        {
            "condition": "necrotising fasciitis", "severity": "severe",
            "tier": "adjunct_toxin_suppression",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until source-controlled",
            "notes": [
                "Toxin-suppression adjunct in necrotising fasciitis - not monotherapy.",
            ],
            "contraindications": [],
            "pathogen_context": ["group A strep", "anaerobes"],
            "page": 9, "source_chapter": "3.10",
        },
        {
            "condition": "necrotising fasciitis", "severity": "severe", "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "loading 20 mg/kg first",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "until source-controlled",
            "notes": ["MRSA cover when risk factors present."],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 9, "source_chapter": "3.10",
        },

        # =================================================================
        # ANIMAL / HUMAN BITES (page 11)
        # =================================================================
        {
            "condition": "bite wound", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7 (prophylactic) or 10-14 (established infection)",
            "notes": [
                "Covers anaerobes (Pasteurella for cats, Eikenella for humans).",
                "Tetanus prophylaxis as appropriate.",
                "Consider rabies post-exposure prophylaxis where indicated.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["pasteurella multocida", "anaerobes", "streptococcus"],
            "page": 11, "source_chapter": "3.10",
        },
        {
            "condition": "bite wound", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["polymicrobial"],
            "page": 11, "source_chapter": "3.10",
        },
        {
            "condition": "bite wound", "severity": "mild", "tier": "penicillin_allergy",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": ["Combine with metronidazole for anaerobic coverage."],
            "contraindications": ["pregnancy", "children <8 years"],
            "pathogen_context": ["pasteurella multocida"],
            "page": 11, "source_chapter": "3.10",
        },
        {
            "condition": "bite wound", "severity": "mild",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 400, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "Anaerobic-coverage add-on (paired with doxycycline) for penicillin-allergic bite wound.",
            ],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 11, "source_chapter": "3.10",
        },

        # =================================================================
        # DIABETIC FOOT INFECTION (page 12-13)
        # =================================================================
        {
            "condition": "diabetic foot infection", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": [
                "Optimise glycaemic control and offloading.",
                "Obtain deep tissue culture if possible.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus", "anaerobes"],
            "page": 12, "source_chapter": "3.10",
        },
        {
            "condition": "diabetic foot infection", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["polymicrobial"],
            "page": 12, "source_chapter": "3.10",
        },
        {
            "condition": "diabetic foot infection", "severity": "severe", "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "14-21",
            "notes": [
                "Severe diabetic foot with systemic features or limb-threatening infection.",
                "Add vancomycin if MRSA suspected.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["polymicrobial", "anaerobes", "Pseudomonas"],
            "page": 12, "source_chapter": "3.10",
        },

        # =================================================================
        # ABSCESS (page 14)
        # Drainage primary; antibiotics adjunct
        # =================================================================
        {
            "condition": "abscess", "severity": "mild", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "Incision and drainage is the primary treatment.",
                "Antibiotics only if surrounding cellulitis, systemic features, "
                "immunocompromised, or large/multiple abscesses.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 14, "source_chapter": "3.10",
        },
        {
            "condition": "abscess", "severity": "mild", "tier": "mrsa_suspected",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "2 tablets",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": ["Cover for community-acquired MRSA when prevalence is high."],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["MRSA (community)"],
            "page": 14, "source_chapter": "3.10",
        },

        # =================================================================
        # SURGICAL SITE INFECTION - SUPERFICIAL (page 15) - cross-referenced
        # =================================================================
        {
            "condition": "surgical site infection", "severity": "mild", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["For superficial SSI without systemic features."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 15, "source_chapter": "3.10",
        },
    ],

    # =====================================================================
    # CHAPTER 3.8 - RESPIRATORY TRACT INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-19
    # Covers: CAP, HAP, VAP, Aspiration pneumonia, Lung abscess,
    # Bronchiectasis, AECOPD, Viral pneumonia, Influenza
    # =====================================================================
    "rti": [

        # ----- COMMUNITY-ACQUIRED PNEUMONIA - LOW SEVERITY (page 4) -----
        # CURB-65 = 0-1 or CRB-65 = 0
        # Duration: beta-lactams 5-7 days, azithromycin 3 days,
        # doxycycline 7-10 days (legionella up to 21d)
        {
            "condition": "pneumonia", "severity": "mild", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 500, "dose_unit": "mg",
            "dose_qualifier": "500-1000 mg range",
            "dose_min_mg": 500, "dose_max_mg": 1000,
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for low-severity (outpatient) CAP.",
                "CURB-65 = 0-1 or CRB-65 = 0.",
                "Dose range 500mg-1g - higher end for inpatient or larger patients.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 4, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative first-line - broader gram-negative cover."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae",
                                 "moraxella catarrhalis"],
            "page": 4, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "mild",
            "tier": "atypical_coverage_addon",
            "drug": "doxycycline",
            "dose_value": 200, "dose_unit": "mg",
            "dose_qualifier": "single load, then 100mg q12H",
            "route": "PO", "frequency": "single dose then q12H",
            "duration_days": "5-7",
            "notes": [
                "Add for atypical pathogen coverage (Mycoplasma, Chlamydophila).",
                "If Legionella suspected: extend to 7-10 days (up to 21 days).",
            ],
            "contraindications": ["pregnancy", "children <8 years"],
            "pathogen_context": ["mycoplasma pneumoniae", "chlamydophila pneumoniae",
                                 "legionella"],
            "page": 4, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "mild",
            "tier": "atypical_coverage_addon",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "3",
            "notes": [
                "Add for atypical pathogen coverage.",
                "If Legionella suspected: extend to 5 days.",
            ],
            "contraindications": [],
            "pathogen_context": ["mycoplasma pneumoniae", "chlamydophila pneumoniae",
                                 "legionella"],
            "page": 4, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "mild", "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": [
                "Alternative for moderate-risk penicillin allergy "
                "(delayed rash without urticaria/DRESS/SJS/TEN).",
            ],
            "contraindications": ["severe penicillin allergy (anaphylaxis)"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 4, "source_chapter": "3.8",
        },

        # ----- CAP - MODERATE SEVERITY / INPATIENT (page 4-5) -----
        # CURB-65 = 2 (9% mortality) or CRB-65 = 1-2
        {
            "condition": "pneumonia", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for moderate inpatient CAP.",
                "Hospitalisation recommended.",
                "De-escalate to oral when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 4, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "moderate", "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["First-line for moderate inpatient CAP (alternative beta-lactam)."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "moderate",
            "tier": "atypical_coverage_addon",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO/IV", "frequency": "q24H",
            "duration_days": "3",
            "notes": ["Add for atypical pathogen coverage in moderate CAP."],
            "contraindications": [],
            "pathogen_context": ["atypical pathogens"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "moderate", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5-7",
            "notes": [
                "Alternative for moderate-severity CAP - typically combined with azithromycin.",
                "Also used in penicillin-allergic patients unable to tolerate oral.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "moderate",
            "tier": "atypical_coverage_addon",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": ["Alternative atypical coverage for moderate CAP."],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["atypical pathogens"],
            "page": 5, "source_chapter": "3.8",
        },

        # ----- CAP - HIGH SEVERITY (page 5) -----
        # CURB-65 = 3-5 (15-40% mortality), HDU/ICU management
        {
            "condition": "pneumonia", "severity": "severe", "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5-7",
            "notes": [
                "First-line for high-severity CAP (CURB-65 3-5).",
                "Manage in HDU or ICU.",
                "Must be combined with azithromycin for atypical cover.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "severe",
            "tier": "atypical_coverage_addon",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "3",
            "notes": ["Mandatory addition to beta-lactam in severe CAP."],
            "contraindications": [],
            "pathogen_context": ["atypical pathogens", "legionella"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "severe", "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative for severe CAP - broader spectrum."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "broad gram-negative"],
            "page": 5, "source_chapter": "3.8",
        },
        # MRSA addon for severe CAP
        {
            "condition": "pneumonia", "severity": "severe", "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "5-7",
            "notes": [
                "Add when MRSA is suspected.",
                "Therapeutic drug monitoring required (trough 15-20 mg/L).",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 5, "source_chapter": "3.8",
        },
        # Melioidosis-suspected CAP
        {
            "condition": "pneumonia", "severity": "severe", "tier": "melioidosis_suspected",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "intensive phase 14 days, eradication 12+ weeks",
            "notes": [
                "Use when melioidosis is suspected.",
                "Risk factors: diabetes mellitus (poor control), renal dysfunction, occupational exposure.",
            ],
            "contraindications": [],
            "pathogen_context": ["burkholderia pseudomallei"],
            "page": 5, "source_chapter": "3.8",
        },
        {
            "condition": "pneumonia", "severity": "severe", "tier": "melioidosis_suspected",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "intensive phase 14 days",
            "notes": ["Alternative to meropenem for suspected melioidosis."],
            "contraindications": [],
            "pathogen_context": ["burkholderia pseudomallei"],
            "page": 5, "source_chapter": "3.8",
        },

        # ----- HOSPITAL-ACQUIRED PNEUMONIA / VAP - EARLY ONSET (page 7) -----
        # 2-4 days of admission/intubation
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Early-onset HAP/VAP (2-4 days of admission/intubation)."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["community-pathogen profile"],
            "page": 7, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "atypical_coverage_addon",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "3",
            "notes": ["Atypical cover in early-onset HAP/VAP."],
            "contraindications": [],
            "pathogen_context": ["atypical pathogens"],
            "page": 7, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5-7",
            "notes": ["Alternative for early-onset HAP/VAP."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["community-pathogen profile"],
            "page": 7, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "aspiration_addon",
            "drug": "metronidazole",
            "dose_value": 400, "dose_unit": "mg",
            "route": "PO", "frequency": "q8-12H",
            "duration_days": "5-7",
            "notes": [
                "Add when aspiration is suspected or after thoraco-abdominal surgery.",
                "IV form: 500mg q8H.",
            ],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 7, "source_chapter": "3.8",
        },

        # ----- HAP/VAP - LATE ONSET NON-SEVERE (page 7) -----
        # 5+ days, non-severe, no IV antibiotics in 90 days
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "late_onset_preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": [
                "Late-onset HAP/VAP (5+ days) - non-severe pneumonia.",
                "No IV antibiotics in preceding 90 days.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["community + selected hospital pathogens"],
            "page": 7, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "moderate",
            "tier": "late_onset_alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "7",
            "notes": ["Alternative for late-onset non-severe HAP/VAP."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["community + selected hospital pathogens"],
            "page": 7, "source_chapter": "3.8",
        },

        # ----- HAP/VAP - LATE ONSET SEVERE (page 8) -----
        # Severe pneumonia OR received IV antibiotics in preceding 90 days
        {
            "condition": "hospital-acquired pneumonia", "severity": "severe",
            "tier": "preferred",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": [
                "First-line for late-onset severe HAP/VAP.",
                "De-escalate based on culture and sensitivity.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "acinetobacter baumannii",
                                  "MRSA"],
            "page": 8, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "severe",
            "tier": "alternative",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7",
            "notes": ["Alternative broad-spectrum for severe late-onset HAP/VAP."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["pseudomonas", "broad gram-negative"],
            "page": 8, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "severe",
            "tier": "alternative",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": [
                "Reserve carbapenem for confirmed ESBL or treatment failure.",
                "Stewardship review required.",
            ],
            "contraindications": [],
            "pathogen_context": ["ESBL", "broad-spectrum"],
            "page": 8, "source_chapter": "3.8",
        },
        {
            "condition": "hospital-acquired pneumonia", "severity": "severe",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g; load with 20mg/kg max 2g first",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "7",
            "notes": [
                "Add for MRSA-colonised patients.",
                "Therapeutic drug monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 8, "source_chapter": "3.8",
        },

        # ----- ASPIRATION PNEUMONIA (page 8-9) -----
        # Most aspiration is sterile; antibiotics only if infection develops
        {
            "condition": "aspiration pneumonia", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "Community-acquired aspiration pneumonia (mild).",
                "Most aspiration is sterile - antibiotics only when infection develops.",
                "Antibiotics NOT indicated for aspiration chemical pneumonitis.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["anaerobes", "mouth streptococci"],
            "page": 8, "source_chapter": "3.8",
        },
        {
            "condition": "aspiration pneumonia", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Inpatient aspiration pneumonia requiring IV therapy."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["anaerobes", "mouth streptococci"],
            "page": 9, "source_chapter": "3.8",
        },
        {
            "condition": "aspiration pneumonia", "severity": "moderate", "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 750, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative for moderate aspiration pneumonia - add metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["mouth streptococci"],
            "page": 8, "source_chapter": "3.8",
        },
        {
            "condition": "aspiration pneumonia", "severity": "moderate",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Anaerobic-coverage addon paired with cefuroxime."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 9, "source_chapter": "3.8",
        },

        # ----- LUNG ABSCESS (page 9-10) -----
        # Drained: 2-4 weeks; undrained/empyema: 4-6 weeks
        {
            "condition": "lung abscess", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "2-4 weeks (drained), 4-6 weeks (undrained/empyema)",
            "notes": [
                "First-line for empirical lung abscess - community-acquired.",
                "May step-down to Co-amoxiclav 1g PO q8H after improvement.",
                "Attempt drainage for empyema.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["anaerobes", "mouth streptococci",
                                  "klebsiella pneumoniae"],
            "page": 9, "source_chapter": "3.8",
        },
        {
            "condition": "lung abscess", "severity": "moderate", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "2-4 weeks",
            "notes": ["Alternative for lung abscess - combine with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["gram-negatives"],
            "page": 9, "source_chapter": "3.8",
        },
        {
            "condition": "lung abscess", "severity": "moderate",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "2-4 weeks",
            "notes": ["Add to ceftriaxone for anaerobic cover when aspiration suspected."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 9, "source_chapter": "3.8",
        },
        {
            "condition": "lung abscess", "severity": "moderate", "tier": "alternative",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV/PO", "frequency": "q6H",
            "duration_days": "2-4 weeks",
            "notes": ["Alternative for penicillin-allergic patients."],
            "contraindications": [],
            "pathogen_context": ["anaerobes", "gram-positives"],
            "page": 9, "source_chapter": "3.8",
        },
        # Lung abscess with S. aureus identified - streamline therapy
        {
            "condition": "lung abscess", "severity": "moderate",
            "tier": "streamline_staph_aureus",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4-6H",
            "duration_days": "4-6 weeks",
            "notes": ["Streamline when S. aureus is identified."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 10, "source_chapter": "3.8",
        },
        # PO step-down for S. aureus lung abscess
        {
            "condition": "lung abscess", "severity": "moderate",
            "tier": "po_stepdown_staph",
            "drug": "cefalexin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q6H",
            "duration_days": "to complete 4-6 weeks total",
            "notes": ["Oral step-down once patient improved."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 10, "source_chapter": "3.8",
        },

        # ----- BRONCHIECTASIS - MILD/MODERATE EXACERBATION (page 12) -----
        {
            "condition": "bronchiectasis exacerbation", "severity": "mild",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": [
                "First-line for mild/moderate exacerbation of bronchiectasis.",
                "Trace previous sputum bacteriology if available.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["haemophilus influenzae", "streptococcus pneumoniae",
                                  "moraxella catarrhalis"],
            "page": 12, "source_chapter": "3.8",
        },
        {
            "condition": "bronchiectasis exacerbation", "severity": "mild",
            "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7-14",
            "notes": ["Alternative for moderate penicillin allergy."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["community pathogens"],
            "page": 12, "source_chapter": "3.8",
        },

        # ----- BRONCHIECTASIS - SEVERE / FAILED ORAL (page 12) -----
        {
            "condition": "bronchiectasis exacerbation", "severity": "severe",
            "tier": "preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": [
                "First-line for severe bronchiectasis exacerbation or failed oral therapy.",
                "Anti-Pseudomonal cover.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 12, "source_chapter": "3.8",
        },
        {
            "condition": "bronchiectasis exacerbation", "severity": "severe",
            "tier": "alternative",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "14",
            "notes": ["Alternative anti-Pseudomonal cover."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 12, "source_chapter": "3.8",
        },
        {
            "condition": "bronchiectasis exacerbation", "severity": "severe",
            "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": ["Alternative anti-Pseudomonal cover for high-risk penicillin allergy."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 12, "source_chapter": "3.8",
        },
        # Sepsis addon - aminoglycoside
        {
            "condition": "bronchiectasis exacerbation", "severity": "severe",
            "tier": "sepsis_addon",
            "drug": "gentamicin",
            "dose_value": 5, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per response",
            "notes": [
                "Add aminoglycoside in sepsis.",
                "Renal function monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["gram-negative"],
            "page": 12, "source_chapter": "3.8",
        },
        {
            "condition": "bronchiectasis exacerbation", "severity": "severe",
            "tier": "sepsis_addon",
            "drug": "amikacin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per response",
            "notes": ["Alternative aminoglycoside for sepsis."],
            "contraindications": [],
            "pathogen_context": ["gram-negative"],
            "page": 12, "source_chapter": "3.8",
        },

        # ----- BRONCHIECTASIS - CHRONIC SUPPRESSIVE (page 13) -----
        # For frequent exacerbations
        {
            "condition": "bronchiectasis maintenance", "severity": "chronic",
            "tier": "preferred",
            "drug": "azithromycin",
            "dose_value": 250, "dose_unit": "mg",
            "dose_qualifier": "250-500 mg range",
            "dose_min_mg": 250, "dose_max_mg": 500,
            "route": "PO", "frequency": "3 times weekly",
            "duration_days": "long-term",
            "notes": [
                "Chronic suppressive treatment for frequent exacerbations (>=3 per 12 months).",
                "Monitor QT interval and hearing.",
            ],
            "contraindications": ["QT prolongation"],
            "pathogen_context": [],
            "page": 13, "source_chapter": "3.8",
        },
        {
            "condition": "bronchiectasis maintenance", "severity": "chronic",
            "tier": "alternative",
            "drug": "erythromycin",
            "dose_value": 400, "dose_unit": "mg",
            "dose_qualifier": "Erythromycin Ethyl Succinate",
            "route": "PO", "frequency": "q12H",
            "duration_days": "long-term",
            "notes": ["Alternative macrolide for chronic suppression."],
            "contraindications": [],
            "pathogen_context": [],
            "page": 13, "source_chapter": "3.8",
        },

        # ----- BRONCHIECTASIS - PSEUDOMONAS ERADICATION (page 13) -----
        {
            "condition": "bronchiectasis eradication", "severity": "severe",
            "tier": "preferred",
            "drug": "ciprofloxacin",
            "dose_value": 500, "dose_unit": "mg",
            "dose_qualifier": "500-750 mg range",
            "dose_min_mg": 500, "dose_max_mg": 750,
            "route": "PO", "frequency": "q12H",
            "duration_days": "2 weeks (initial)",
            "notes": [
                "Pseudomonas aeruginosa eradication therapy.",
                "Initial 2 weeks treatment, followed by 3-month nebulised course.",
                "To treat based on sensitivities.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 13, "source_chapter": "3.8",
        },

        # ----- ACUTE EXACERBATION OF COPD - OUTPATIENT (page 15) -----
        # Antibiotics for Anthonisen Type 1 or Type 2 with purulent sputum/fever
        {
            "condition": "AECOPD", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for outpatient AECOPD.",
                "Antibiotics only if purulent sputum, fever, or hospitalisation needed.",
                "Not all COPD exacerbations require antibiotic therapy.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["haemophilus influenzae", "streptococcus pneumoniae"],
            "page": 15, "source_chapter": "3.8",
        },
        {
            "condition": "AECOPD", "severity": "mild", "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": ["Alternative for moderate penicillin allergy."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["community pathogens"],
            "page": 15, "source_chapter": "3.8",
        },
        {
            "condition": "AECOPD", "severity": "mild",
            "tier": "atypical_coverage_addon",
            "drug": "doxycycline",
            "dose_value": 200, "dose_unit": "mg",
            "dose_qualifier": "single load, then 100mg q12H",
            "route": "PO", "frequency": "single dose then q12H",
            "duration_days": "5-7",
            "notes": ["Atypical cover for outpatient AECOPD."],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["atypical pathogens"],
            "page": 15, "source_chapter": "3.8",
        },
        {
            "condition": "AECOPD", "severity": "mild",
            "tier": "atypical_coverage_addon",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "3",
            "notes": ["Atypical cover for outpatient AECOPD."],
            "contraindications": [],
            "pathogen_context": ["atypical pathogens"],
            "page": 15, "source_chapter": "3.8",
        },

        # ----- AECOPD - INPATIENT (page 15-16) -----
        {
            "condition": "AECOPD", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["First-line for inpatient AECOPD."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["community pathogens"],
            "page": 15, "source_chapter": "3.8",
        },
        {
            "condition": "AECOPD", "severity": "moderate", "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["First-line alternative for inpatient AECOPD."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["community pathogens"],
            "page": 15, "source_chapter": "3.8",
        },
        {
            "condition": "AECOPD", "severity": "moderate", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5-7",
            "notes": ["Alternative for inpatient AECOPD."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["community pathogens"],
            "page": 15, "source_chapter": "3.8",
        },

        # ----- VIRAL PNEUMONIA - VARICELLA ZOSTER (page 16) -----
        {
            "condition": "viral pneumonia", "severity": "moderate", "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": [
                "Varicella zoster pneumonia.",
                "Pregnancy 3rd trimester: 800mg PO 5x daily OR 10mg/kg IV q8H for 5 days.",
            ],
            "contraindications": [],
            "pathogen_context": ["varicella zoster virus"],
            "page": 16, "source_chapter": "3.8",
        },
        {
            "condition": "viral pneumonia", "severity": "moderate", "tier": "alternative",
            "drug": "valaciclovir",
            "dose_value": 1000, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5",
            "notes": [
                "NOT in UMMC formulary - alternative for VZV pneumonia.",
            ],
            "contraindications": [],
            "pathogen_context": ["varicella zoster virus"],
            "page": 16, "source_chapter": "3.8",
        },

        # ----- INFLUENZA TREATMENT (page 17) -----
        # At-risk population: initiate within 48h of symptom onset
        {
            "condition": "influenza", "severity": "moderate", "tier": "preferred",
            "drug": "oseltamivir",
            "dose_value": 75, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5",
            "notes": [
                "Treatment of influenza in at-risk population.",
                "Initiate within 48 hours of symptom onset.",
                "Antibiotics NOT routinely given for uncomplicated influenza.",
                "Investigate bacterial coinfection if deterioration after initial improvement.",
            ],
            "contraindications": [],
            "pathogen_context": ["influenza A", "influenza B"],
            "page": 17, "source_chapter": "3.8",
        },
    ],

    # =====================================================================
    # CHAPTER 3.9 - UROLOGY INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition (2024), pages 1-22
    # Covers: cystitis (uncomplicated/complicated), pyelonephritis,
    # prostatitis, epididymo-orchitis, CAUTI, PD-related infections,
    # dialysis CLABSI
    # =====================================================================
    "urology": [

        # ----- ACUTE UNCOMPLICATED CYSTITIS (page 5-6) -----
        # Symptomatic infection in non-pregnant women with normal urinary tract
        {
            "condition": "cystitis", "severity": "mild", "tier": "preferred",
            "drug": "nitrofurantoin",
            "dose_value": 50, "dose_unit": "mg",
            "dose_qualifier": "50-100 mg range",
            "dose_min_mg": 50, "dose_max_mg": 100,
            "route": "PO", "frequency": "q6H",
            "duration_days": "5",
            "notes": [
                "First-line for uncomplicated cystitis in non-pregnant women.",
                "AVOID if GFR < 30 mL/min - bladder concentration is "
                "subtherapeutic.",
                "NOT for pyelonephritis - achieves no kidney-tissue "
                "concentration.",
            ],
            "contraindications": ["eGFR < 30", "pyelonephritis"],
            "pathogen_context": ["escherichia coli", "enterococcus"],
            "page": 5, "source_chapter": "3.9",
        },
        {
            "condition": "cystitis", "severity": "mild", "tier": "preferred",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5",
            "notes": [
                "First-line for uncomplicated cystitis.",
                "Preferred choice in pregnancy.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 5, "source_chapter": "3.9",
        },
        {
            "condition": "cystitis", "severity": "mild", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5",
            "notes": ["Alternative for uncomplicated cystitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 5, "source_chapter": "3.9",
        },
        {
            "condition": "cystitis", "severity": "mild", "tier": "alternative",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "2 tablets per dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": "3",
            "notes": [
                "Alternative for uncomplicated cystitis.",
                "NOT recommended in pregnancy.",
            ],
            "contraindications": ["pregnancy", "sulfa allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 5, "source_chapter": "3.9",
        },
        {
            "condition": "cystitis", "severity": "mild", "tier": "alternative",
            "drug": "fosfomycin",
            "dose_value": 3, "dose_unit": "g",
            "route": "PO", "frequency": "single dose",
            "duration_days": "1",
            "notes": [
                "Single-dose alternative for uncomplicated cystitis.",
                "Consider for suspected MDR gram-negative.",
            ],
            "contraindications": [],
            "pathogen_context": ["escherichia coli", "MDR gram-negative"],
            "page": 6, "source_chapter": "3.9",
        },

        # ----- ACUTE COMPLICATED CYSTITIS (page 6) -----
        # Complicated UTI: men, pregnant, immunocompromised, structural
        # abnormality, indwelling catheter, etc.
        {
            "condition": "complicated cystitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "nitrofurantoin",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7",
            "notes": [
                "Oral therapy for complicated cystitis.",
                "Avoid if GFR < 30 mL/min.",
                "Not for upper UTI - bladder coverage only.",
            ],
            "contraindications": ["eGFR < 30", "pyelonephritis", "upper UTI"],
            "pathogen_context": ["escherichia coli"],
            "page": 6, "source_chapter": "3.9",
        },
        {
            "condition": "complicated cystitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7",
            "notes": ["First-line oral therapy for complicated cystitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 6, "source_chapter": "3.9",
        },
        {
            "condition": "complicated cystitis", "severity": "moderate",
            "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative oral therapy for complicated cystitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 6, "source_chapter": "3.9",
        },
        {
            "condition": "complicated cystitis", "severity": "moderate",
            "tier": "parenteral_preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": [
                "IV therapy for complicated cystitis requiring "
                "hospitalisation.",
                "Convert to oral when patient improves.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 6, "source_chapter": "3.9",
        },
        {
            "condition": "complicated cystitis", "severity": "moderate",
            "tier": "parenteral_alternative",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": ["IV alternative for complicated cystitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 6, "source_chapter": "3.9",
        },

        # ----- PYELONEPHRITIS - COMMUNITY ONSET, MILD (page 10) -----
        # Mild systemic symptoms, low-grade fever, no N/V - outpatient
        {
            "condition": "pyelonephritis", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": [
                "First-line for community-onset mild pyelonephritis.",
                "Targeted therapy should be based on culture results.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "pyelonephritis", "severity": "mild", "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": [
                "Alternative for community-onset mild pyelonephritis.",
                "Preferred choice in pregnancy.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 10, "source_chapter": "3.9",
        },

        # ----- PYELONEPHRITIS - COMMUNITY ONSET, SEVERE (page 10) -----
        # Systemic symptoms (fever, N/V, severe pain) - hospitalisation
        # required - THIS IS CASE 2's REGIMEN
        {
            "condition": "pyelonephritis", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14 (IV+PO total, not exceeding 21)",
            "notes": [
                "First-line for community-onset severe pyelonephritis.",
                "Take urine and blood cultures on hospitalised patients.",
                "Step down to oral when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "pyelonephritis", "severity": "severe", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "10-14",
            "notes": [
                "Alternative for community-onset severe pyelonephritis.",
                "Suitable for patients with mild-moderate penicillin allergy.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "pyelonephritis", "severity": "severe",
            "tier": "esbl_or_sepsis",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "Reserve for ESBL/CRE risk OR septic shock.",
                "Stewardship review required.",
            ],
            "contraindications": [],
            "pathogen_context": ["ESBL", "CRE"],
            "page": 10, "source_chapter": "3.9",
        },

        # ----- PYELONEPHRITIS - HOSPITAL ONSET (page 10) -----
        {
            "condition": "pyelonephritis", "severity": "severe",
            "tier": "hospital_onset_preferred",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["First-line for hospital-onset pyelonephritis."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["broad gram-negative", "pseudomonas"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "pyelonephritis", "severity": "severe",
            "tier": "hospital_onset_alternative",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["Alternative for hospital-onset pyelonephritis."],
            "contraindications": [],
            "pathogen_context": ["ESBL", "broad-spectrum"],
            "page": 10, "source_chapter": "3.9",
        },

        # ----- ACUTE PROSTATITIS WITH STD RISK (page 7) -----
        {
            "condition": "prostatitis", "severity": "moderate",
            "tier": "preferred_std_risk",
            "drug": "ceftriaxone",
            "dose_value": 500, "dose_unit": "mg",
            "dose_qualifier": "1g IM if weight >=150kg",
            "route": "IM", "frequency": "single dose",
            "duration_days": "1",
            "notes": [
                "Acute prostatitis with STD risk.",
                "Combine with doxycycline.",
                "Test for STDs (HIV, Hep B, Hep C, Syphilis, Gonorrhoea).",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["neisseria gonorrhoeae", "chlamydia trachomatis"],
            "page": 7, "source_chapter": "3.9",
        },
        {
            "condition": "prostatitis", "severity": "moderate",
            "tier": "std_addon",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7",
            "notes": [
                "Combined with ceftriaxone for acute prostatitis with STD risk.",
                "Extend to 21 days if bloody discharge / mucosal ulcers / "
                "positive rectal chlamydia test.",
            ],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["chlamydia trachomatis"],
            "page": 7, "source_chapter": "3.9",
        },

        # ----- PROSTATITIS / PROSTATIC ABSCESS (page 8) -----
        {
            "condition": "prostatitis", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14 (longer for abscess)",
            "notes": [
                "First-line IV therapy for prostatitis/prostatic abscess.",
                "Ensure cultures before starting antibiotics.",
                "Adequate source control required for abscess.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "enterobacterales"],
            "page": 8, "source_chapter": "3.9",
        },
        {
            "condition": "prostatitis", "severity": "moderate",
            "tier": "oral_stepdown_preferred",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "2 tablets per dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": "to complete 10-14 total",
            "notes": ["Oral step-down once patient improved/outpatient therapy."],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 8, "source_chapter": "3.9",
        },
        {
            "condition": "prostatitis", "severity": "moderate",
            "tier": "oral_stepdown_alternative",
            "drug": "co-amoxiclav",
            "dose_value": 875, "dose_unit": "mg",
            "dose_qualifier": "875/125 mg combination tablet",
            "route": "PO", "frequency": "q8H",
            "duration_days": "to complete 10-14 total",
            "notes": ["Alternative oral step-down."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 8, "source_chapter": "3.9",
        },
        {
            "condition": "prostatitis", "severity": "moderate",
            "tier": "oral_stepdown_alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "to complete 10-14 total",
            "notes": ["Alternative oral step-down."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 8, "source_chapter": "3.9",
        },

        # ----- CHRONIC PROSTATITIS (page 8) -----
        # Symptoms >= 3 months, perineal/scrotal/penile pain + LUTS
        {
            "condition": "chronic prostatitis", "severity": "chronic",
            "tier": "preferred",
            "drug": "ciprofloxacin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "28-42 (4-6 weeks)",
            "notes": [
                "First-line for chronic prostatitis (symptoms >=3 months).",
                "Reassess after 2 weeks - only continue if cultures positive "
                "or symptoms improving.",
                "Consider non-bacterial prostatitis if no improvement.",
            ],
            "contraindications": [],
            "pathogen_context": ["escherichia coli"],
            "page": 8, "source_chapter": "3.9",
        },
        {
            "condition": "chronic prostatitis", "severity": "chronic",
            "tier": "alternative",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "2 tablets per dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": "28-42",
            "notes": ["Alternative for chronic prostatitis."],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["escherichia coli"],
            "page": 8, "source_chapter": "3.9",
        },

        # ----- HAEMODIALYSIS CATHETER EXIT-SITE INFECTION (page 10-11) -----
        {
            "condition": "haemodialysis catheter exit-site infection",
            "severity": "mild", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-14",
            "notes": [
                "Exit-site infection (oral therapy).",
                "If signs of systemic infection, obtain blood cultures.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "haemodialysis catheter exit-site infection",
            "severity": "moderate", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7-14",
            "notes": ["IV alternative if oral not tolerated or systemic features."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 10, "source_chapter": "3.9",
        },
        {
            "condition": "haemodialysis catheter exit-site infection",
            "severity": "mild", "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7-14",
            "notes": ["Alternative oral therapy for exit-site infection."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 10, "source_chapter": "3.9",
        },

        # ----- HAEMODIALYSIS CATHETER TUNNEL INFECTION (page 11) -----
        {
            "condition": "haemodialysis catheter tunnel infection",
            "severity": "moderate", "tier": "preferred",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "3 times weekly after dialysis",
            "duration_days": "10-14",
            "notes": [
                "First-line for tunnel infection.",
                "Catheter should be removed without exchange over a wire.",
                "Duration: 10-14 days if no bacteraemia.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 11, "source_chapter": "3.9",
        },
        {
            "condition": "haemodialysis catheter tunnel infection",
            "severity": "moderate", "tier": "alternative",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": ["Alternative for tunnel infection."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 11, "source_chapter": "3.9",
        },
        {
            "condition": "haemodialysis catheter tunnel infection",
            "severity": "moderate", "tier": "mrsa_or_pen_allergy",
            "drug": "vancomycin",
            "dose_value": 20, "dose_unit": "mg/kg",
            "dose_qualifier": "single dose, then TDM-guided",
            "route": "IV", "frequency": "single load then TDM",
            "duration_days": "10-14",
            "notes": [
                "For penicillin-allergic or MRSA-suspected tunnel infection.",
                "Therapeutic drug monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 11, "source_chapter": "3.9",
        },

        # ----- PD-RELATED EXIT-SITE INFECTION (page 11) -----
        {
            "condition": "PD exit-site infection", "severity": "mild",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14",
            "notes": [
                "First-line for PD-related exit-site infection.",
                "If due to Pseudomonas, refer ID.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "pseudomonas"],
            "page": 11, "source_chapter": "3.9",
        },
        {
            "condition": "PD exit-site infection", "severity": "mild",
            "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "14",
            "notes": ["Alternative for PD exit-site infection."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 11, "source_chapter": "3.9",
        },

        # ----- DIALYSIS CLABSI - NON-SEVERE (page 19-20) -----
        {
            "condition": "dialysis CLABSI", "severity": "moderate",
            "tier": "preferred",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "dose_qualifier": "2g if next HD 48h, 3g if next HD 72h",
            "route": "IV", "frequency": "single dose after each dialysis",
            "duration_days": "varies by organism",
            "notes": [
                "First-line empiric for non-severe HD-CLABSI.",
                "Obtain peripheral and central blood cultures before "
                "antibiotics.",
                "Consider vancomycin if catheter inserted >3 days or MRSA "
                "suspected.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["MSSA", "MSCoNS"],
            "page": 19, "source_chapter": "3.9",
        },
        {
            "condition": "dialysis CLABSI", "severity": "moderate",
            "tier": "alternative",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "varies by organism",
            "notes": ["Alternative for non-severe HD-CLABSI."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 19, "source_chapter": "3.9",
        },
        {
            "condition": "dialysis CLABSI", "severity": "moderate",
            "tier": "gram_negative_addon",
            "drug": "ceftazidime",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q24H after dialysis on HD days",
            "duration_days": "varies",
            "notes": ["Anti-Pseudomonal gram-negative cover for HD-CLABSI."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas", "gram-negative"],
            "page": 19, "source_chapter": "3.9",
        },
        {
            "condition": "dialysis CLABSI", "severity": "moderate",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 20, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g per dose, then TDM-guided",
            "route": "IV", "frequency": "single load then TDM",
            "duration_days": "varies",
            "notes": [
                "When MRSA suspected (catheter >3 days, prior MRSA carrier).",
                "Therapeutic drug monitoring mandatory.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA", "MRCoNS"],
            "page": 19, "source_chapter": "3.9",
        },

        # ----- DIALYSIS CLABSI - SUSPECTED CANDIDEMIA (page 21) -----
        {
            "condition": "dialysis CLABSI", "severity": "severe",
            "tier": "candida_preferred",
            "drug": "fluconazole",
            "dose_value": 100, "dose_unit": "mg",
            "dose_qualifier": "100-400 mg range",
            "dose_min_mg": 100, "dose_max_mg": 400,
            "route": "IV/PO", "frequency": "q24H after dialysis on HD days",
            "duration_days": "varies",
            "notes": [
                "For suspected catheter-related candidemia.",
                "De-escalate based on susceptibility results.",
                "Remove catheter if fungal infection proven.",
            ],
            "contraindications": [],
            "pathogen_context": ["candida"],
            "page": 21, "source_chapter": "3.9",
        },
        {
            "condition": "dialysis CLABSI", "severity": "severe",
            "tier": "candida_alternative",
            "drug": "micafungin",
            "dose_value": 100, "dose_unit": "mg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "varies",
            "notes": [
                "Alternative for catheter-related candidemia.",
                "Increase to 150-200 mg IV q24H if patient on CRRT.",
            ],
            "contraindications": [],
            "pathogen_context": ["candida"],
            "page": 21, "source_chapter": "3.9",
        },

        # ===================================================================
        # CHAPTER 4.9 - PAEDIATRIC UROLOGY INFECTIONS
        # Source: UMMC Antimicrobial Guidelines 3rd Edition, Paediatric Section
        #
        # UMMC paediatric urology uses two age strata:
        #   0-2 months -> neonatal combination regimen
        #   >2 months  -> single-agent cephalosporin first-line
        #
        # Within the neonatal band, ampicillin frequency varies by exact
        # day-of-life: <7d q12H, 7-20d q8H, >=21d q6H. Encoded as separate
        # rows with age_min/max_months (1 day ~= 0.033 months).
        # ===================================================================

        # ----- ACUTE CYSTITIS - NEONATAL 0-7 days (page 1) -----
        {
            "condition": "cystitis", "severity": None, "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q12H",
            "duration_days": None,
            "notes": [
                "Neonatal acute cystitis component, <7 days of life.",
                "Always combine with gentamicin 4-5 mg/kg/dose IV q24H.",
                "Recurrent UTI from structural anomaly: refer to previous "
                "culture for choice of antibiotic.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 1, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.0, "age_max_months": 0.23,
        },
        # ----- ACUTE CYSTITIS - NEONATAL 7-20 days (page 1) -----
        {
            "condition": "cystitis", "severity": None, "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q8H",
            "duration_days": None,
            "notes": [
                "Neonatal acute cystitis component, 7-20 days of life.",
                "Always combine with gentamicin 4-5 mg/kg/dose IV q24H.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 1, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.23, "age_max_months": 0.69,
        },
        # ----- ACUTE CYSTITIS - NEONATAL >=21 days, <2 months (page 1) -----
        {
            "condition": "cystitis", "severity": None, "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q6H",
            "duration_days": None,
            "notes": [
                "Neonatal acute cystitis component, >=21 days of life.",
                "Always combine with gentamicin 4-5 mg/kg/dose IV q24H.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 1, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.69, "age_max_months": 2.0,
        },
        # ----- ACUTE CYSTITIS - NEONATAL gentamicin partner -----
        {
            "condition": "cystitis", "severity": None, "tier": "neonatal_combo",
            "drug": "gentamicin",
            "dose_value": 4, "dose_unit": "mg/kg",
            "dose_qualifier": "4-5 mg/kg/dose",
            "route": "IV", "frequency": "q24H",
            "duration_days": None,
            "notes": [
                "Gentamicin partner of the neonatal ampicillin combination.",
                "Monitor serum levels; renal function before each dose.",
            ],
            "contraindications": ["aminoglycoside allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 1, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.0, "age_max_months": 2.0,
        },

        # ----- ACUTE CYSTITIS - PAEDIATRIC >2 months, RECOMMENDED (page 1) -----
        {
            "condition": "cystitis", "severity": None, "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25 mg/kg/dose",
            "route": "IV", "frequency": "q8H",
            "duration_days": None,
            "notes": [
                "First-line IV regimen for paediatric acute cystitis "
                ">2 months of age.",
                "Convert to oral therapy once clinical improvement is "
                "documented.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 1, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },

        # ----- ACUTE CYSTITIS - PAEDIATRIC >2 months, ALTERNATIVE oral (page 2) -----
        {
            "condition": "cystitis", "severity": None, "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 10, "dose_unit": "mg/kg",
            "dose_qualifier": "10-15 mg/kg/dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": None,
            "notes": [
                "Oral alternative for paediatric acute cystitis "
                ">2 months of age.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },
        {
            "condition": "cystitis", "severity": None, "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 12.5, "dose_unit": "mg/kg",
            "dose_qualifier": "12.5-25 mg/kg/dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": None,
            "notes": [
                "Oral alternative for paediatric acute cystitis "
                ">2 months of age.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },
        {
            "condition": "cystitis", "severity": None, "tier": "alternative",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 4, "dose_unit": "mg/kg",
            "dose_qualifier": "4-5 mg/kg/dose of trimethoprim",
            "route": "PO", "frequency": "q12H",
            "duration_days": None,
            "notes": [
                "Oral alternative for paediatric acute cystitis "
                ">2 months of age.",
                "Check G6PD status before initiating - haemolysis risk.",
            ],
            "contraindications": ["g6pd deficiency", "sulfa allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },
        {
            "condition": "cystitis", "severity": None, "tier": "alternative",
            "drug": "nitrofurantoin",
            "dose_value": 1, "dose_unit": "mg/kg",
            "dose_qualifier": "1-1.5 mg/kg/dose, max 100 mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": None,
            "notes": [
                "Oral alternative for paediatric acute cystitis.",
                "Only for patients >=3 months old - haemolytic anaemia "
                "risk in younger infants.",
                "CONTRAINDICATED in G6PD deficiency - acute haemolysis.",
                "Bladder concentration only - not for upper UTI.",
            ],
            "contraindications": ["g6pd deficiency", "pyelonephritis",
                                  "upper UTI", "eGFR < 30"],
            "pathogen_context": ["escherichia coli"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 3.0,
        },

        # ----- ACUTE PYELONEPHRITIS - NEONATAL 0-7 days (page 2-3) -----
        {
            "condition": "pyelonephritis", "severity": None,
            "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q12H",
            "duration_days": "10-14",
            "notes": [
                "Neonatal acute pyelonephritis component, <7 days of life.",
                "Always combine with cefotaxime 50 mg/kg/dose IV q8H "
                "for 10-14 days.",
                "Repeat culture within 48 hours if poor response.",
                "Continue IV until afebrile 2-3 days, then switch to "
                "appropriate oral per culture.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.0, "age_max_months": 0.23,
        },
        # ----- ACUTE PYELONEPHRITIS - NEONATAL 7-20 days -----
        {
            "condition": "pyelonephritis", "severity": None,
            "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "Neonatal acute pyelonephritis component, 7-20 days of life.",
                "Always combine with cefotaxime 50 mg/kg/dose IV q8H.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.23, "age_max_months": 0.69,
        },
        # ----- ACUTE PYELONEPHRITIS - NEONATAL >=21 days -----
        {
            "condition": "pyelonephritis", "severity": None,
            "tier": "neonatal_combo",
            "drug": "ampicillin",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25-50 mg/kg/dose",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": [
                "Neonatal acute pyelonephritis component, >=21 days of life.",
                "Always combine with cefotaxime 50 mg/kg/dose IV q8H.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.69, "age_max_months": 2.0,
        },
        # ----- ACUTE PYELONEPHRITIS - NEONATAL cefotaxime partner -----
        {
            "condition": "pyelonephritis", "severity": None,
            "tier": "neonatal_combo",
            "drug": "cefotaxime",
            "dose_value": 50, "dose_unit": "mg/kg",
            "dose_qualifier": "50 mg/kg/dose",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "Cefotaxime partner of the neonatal ampicillin combination "
                "for acute pyelonephritis.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 2, "source_chapter": "4.9",
            "age_group": "neonatal",
            "age_min_months": 0.0, "age_max_months": 2.0,
        },

        # ----- ACUTE PYELONEPHRITIS - PAEDIATRIC >2 months recommended (pg 3) -----
        {
            "condition": "pyelonephritis", "severity": None, "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 25, "dose_unit": "mg/kg",
            "dose_qualifier": "25 mg/kg/dose",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "First-line IV regimen for paediatric acute pyelonephritis "
                ">2 months of age.",
                "Antibiotics may be changed per culture and sensitivity.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 3, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },
        # ----- ACUTE PYELONEPHRITIS - PAEDIATRIC >2 months alternative -----
        {
            "condition": "pyelonephritis", "severity": None, "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 50, "dose_unit": "mg/kg",
            "dose_qualifier": "50 mg/kg/dose",
            "route": "IV", "frequency": "q12H",
            "duration_days": "10-14",
            "notes": [
                "IV alternative for paediatric acute pyelonephritis "
                ">2 months of age.",
                "Avoid concomitant IV calcium in neonates - precipitation risk.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["escherichia coli", "proteus spp"],
            "page": 3, "source_chapter": "4.9",
            "age_group": "paediatric",
            "age_min_months": 2.0,
        },

        # ----- ASYMPTOMATIC BACTERIURIA - PAEDIATRIC (page 3) -----
        # UMMC explicitly states "No treatment is recommended" for
        # paediatric asymptomatic bacteriuria. We encode a placeholder row
        # with tier="no_treatment" so the system can return a clear
        # "no antimicrobial indicated" verdict rather than falling through
        # to RAG and matching the wrong condition.
        {
            "condition": "asymptomatic bacteriuria", "severity": None,
            "tier": "no_treatment",
            "drug": "no antimicrobial",
            "dose_value": 0, "dose_unit": "",
            "route": "", "frequency": "",
            "duration_days": None,
            "notes": [
                "No antimicrobial treatment recommended for paediatric "
                "asymptomatic bacteriuria. Monitor only.",
            ],
            "contraindications": [],
            "pathogen_context": [],
            "page": 3, "source_chapter": "4.9",
            "age_group": "paediatric",
        },
    ],

    # =====================================================================
    # CHAPTER 3.5 - EAR, NOSE, AND THROAT INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-13
    # Covers: otitis externa (acute/malignant), otitis media (bacterial,
    # intracranial extension, CSOM), mastoiditis (acute first/second
    # episode, chronic), acute pharyngitis/tonsillitis, diphtheria,
    # peritonsillar abscess (Quinsy), acute epiglottitis,
    # parapharyngeal abscess, acute rhinosinusitis (mild/moderate-severe)
    # =====================================================================
    "ent": [

        # ----- ACUTE OTITIS EXTERNA - MILD/MODERATE, TM INTACT (page 2) -----
        {
            "condition": "otitis externa", "severity": "mild", "tier": "preferred",
            "drug": "ofloxacin",
            "dose_value": 10, "dose_unit": "drops",
            "dose_qualifier": "0.3% ear drop, 10 drops per dose",
            "route": "ear drop", "frequency": "q12H",
            "duration_days": "7",
            "notes": [
                "First-line topical for acute otitis externa with intact TM.",
                "Can be combined with steroid ear drops (not available in UMMC).",
                "Culture from ear drainage ideally before therapy.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa", "staphylococcus aureus"],
            "page": 2, "source_chapter": "3.5",
        },
        {
            "condition": "otitis externa", "severity": "mild", "tier": "alternative",
            "drug": "ciprofloxacin",
            "dose_value": 250, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5",
            "notes": ["Oral fluoroquinolone alternative for otitis externa."],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 2, "source_chapter": "3.5",
        },
        {
            "condition": "otitis externa", "severity": "moderate",
            "tier": "systemic_addon",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "Consider when systemic symptoms present.",
                "Step down to oral when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 2, "source_chapter": "3.5",
        },

        # ----- ACUTE OTITIS EXTERNA - TM NOT INTACT (page 2) -----
        {
            "condition": "otitis externa perforated TM", "severity": "moderate",
            "tier": "preferred",
            "drug": "ofloxacin",
            "dose_value": 10, "dose_unit": "drops",
            "dose_qualifier": "0.3% ear drop, 10 drops per dose",
            "route": "ear drop", "frequency": "q24H",
            "duration_days": "7",
            "notes": [
                "First-line topical when tympanic membrane is not intact.",
                "Combine with systemic antibiotic.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 2, "source_chapter": "3.5",
        },
        {
            "condition": "otitis externa perforated TM", "severity": "moderate",
            "tier": "systemic_preferred",
            "drug": "ciprofloxacin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-7",
            "notes": ["Systemic cover for perforated TM otitis externa."],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 2, "source_chapter": "3.5",
        },
        {
            "condition": "otitis externa perforated TM", "severity": "moderate",
            "tier": "systemic_alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative systemic cover."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 2, "source_chapter": "3.5",
        },
        {
            "condition": "otitis externa perforated TM", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 300, "dose_unit": "mg",
            "route": "PO", "frequency": "q6-8H",
            "duration_days": "5",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 2, "source_chapter": "3.5",
        },

        # ----- MALIGNANT/NECROTISING OTITIS EXTERNA (page 3) -----
        {
            "condition": "malignant otitis externa", "severity": "severe",
            "tier": "preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "28-42 (4-6 weeks minimum)",
            "notes": [
                "First-line anti-Pseudomonal for malignant otitis externa.",
                "Switch to Ciprofloxacin PO 750mg q12H once clinical response.",
                "Total duration: minimum 4-6 weeks.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 3, "source_chapter": "3.5",
        },
        {
            "condition": "malignant otitis externa", "severity": "severe",
            "tier": "alternative",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "28-42",
            "notes": ["Alternative anti-Pseudomonal cover."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 3, "source_chapter": "3.5",
        },
        {
            "condition": "malignant otitis externa", "severity": "severe",
            "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "28-42",
            "notes": ["Alternative anti-Pseudomonal cover."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 3, "source_chapter": "3.5",
        },
        {
            "condition": "malignant otitis externa", "severity": "severe",
            "tier": "oral_stepdown",
            "drug": "ciprofloxacin",
            "dose_value": 750, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "to complete 4-6 weeks total",
            "notes": ["Oral step-down once clinical response."],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 3, "source_chapter": "3.5",
        },

        # ----- OTITIS MEDIA - BACTERIAL (page 3) -----
        {
            "condition": "otitis media", "severity": "moderate", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for bacterial otitis media.",
                "If received amoxicillin in previous consultation: "
                "use Co-amoxiclav 625mg PO q8H for 5-7 days.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae",
                                  "moraxella catarrhalis"],
            "page": 3, "source_chapter": "3.5",
        },
        {
            "condition": "otitis media", "severity": "moderate", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["For patients who received amoxicillin recently."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 3, "source_chapter": "3.5",
        },
        {
            "condition": "otitis media", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "5",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pneumoniae"],
            "page": 3, "source_chapter": "3.5",
        },

        # ----- OTITIS MEDIA WITH INTRACRANIAL EXTENSION (page 4) -----
        {
            "condition": "otitis media intracranial extension", "severity": "severe",
            "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "discussed between ENT and ID teams",
            "notes": [
                "First-line for otitis media with suspected intracranial "
                "extension. Combine with metronidazole. Cases should be "
                "discussed between ENT and ID teams.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "anaerobes"],
            "page": 4, "source_chapter": "3.5",
        },
        {
            "condition": "otitis media intracranial extension", "severity": "severe",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "as per total duration",
            "notes": ["Anaerobic coverage paired with ceftriaxone."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 4, "source_chapter": "3.5",
        },

        # ----- CHRONIC SUPPURATIVE OTITIS MEDIA (CSOM) (page 4) -----
        {
            "condition": "chronic suppurative otitis media", "severity": "moderate",
            "tier": "preferred",
            "drug": "ofloxacin",
            "dose_value": 10, "dose_unit": "drops",
            "dose_qualifier": "0.3% ear drop, 10 drops per dose",
            "route": "ear drop", "frequency": "q24H",
            "duration_days": "10-14",
            "notes": [
                "First-line topical for CSOM.",
                "Aural toilet for discharging ears and keep external ear "
                "canal dry.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa", "staphylococcus aureus"],
            "page": 4, "source_chapter": "3.5",
        },

        # ----- ACUTE MASTOIDITIS - FIRST EPISODE (page 4) -----
        {
            "condition": "acute mastoiditis", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": [
                "First-line for first episode of acute mastoiditis.",
                "Obtain specimens (deep pus) for C&S. De-escalate when "
                "results available. Surgical debridement/drainage if mastoid "
                "abscess.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "streptococcus pyogenes",
                                  "staphylococcus aureus", "haemophilus influenzae"],
            "page": 4, "source_chapter": "3.5",
        },

        # ----- ACUTE MASTOIDITIS - SECOND EPISODE (page 5) -----
        {
            "condition": "acute mastoiditis", "severity": "severe",
            "tier": "second_episode_preferred",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-14",
            "notes": ["First-line for second episode of acute mastoiditis."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.5",
        },
        {
            "condition": "acute mastoiditis", "severity": "severe",
            "tier": "second_episode_alternative",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7-14",
            "notes": [
                "Alternative for second episode of acute mastoiditis.",
                "If MRSA risk: add vancomycin 15 mg/kg IV q8-12H.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.5",
        },

        # ----- CHRONIC MASTOIDITIS (page 5-6) -----
        {
            "condition": "chronic mastoiditis", "severity": "moderate",
            "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "28-42",
            "notes": [
                "First-line empirical when cultures negative.",
                "Total duration: 4-6 weeks (usual treatment for osteomyelitis).",
                "Surgical evaluation indicated for cholesteatoma.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["anaerobes", "staphylococcus aureus",
                                  "pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.5",
        },
        {
            "condition": "chronic mastoiditis", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "28-42",
            "notes": ["Alternative paired with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.5",
        },
        {
            "condition": "chronic mastoiditis", "severity": "moderate",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "28-42",
            "notes": ["Anaerobic coverage paired with cefepime."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 5, "source_chapter": "3.5",
        },

        # ----- ACUTE PHARYNGITIS/TONSILLITIS - BACTERIAL (page 6) -----
        # S. pyogenes - antibiotics only if Centor score >=3 or proven
        {
            "condition": "acute pharyngitis", "severity": "mild", "tier": "preferred",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8-12H",
            "duration_days": "7-10",
            "notes": [
                "First-line for bacterial pharyngitis (S. pyogenes).",
                "Antibiotics only required if Centor score >=3 or proven "
                "bacterial infection.",
                "Total duration: 5 days (suggested, can be adjusted).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.5",
        },
        {
            "condition": "acute pharyngitis", "severity": "mild", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": ["Alternative first-line for bacterial pharyngitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.5",
        },
        {
            "condition": "acute pharyngitis", "severity": "mild", "tier": "preferred",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "10",
            "notes": ["Alternative first-line cephalosporin."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.5",
        },
        {
            "condition": "acute pharyngitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "benzylpenicillin",
            "dose_value": 2, "dose_unit": "MU",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": ["Parenteral first-line if oral not tolerated."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.5",
        },
        {
            "condition": "acute pharyngitis", "severity": "mild",
            "tier": "penicillin_allergy",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "3-5",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 6, "source_chapter": "3.5",
        },

        # ----- DIPHTHERIA (page 6-7) -----
        # Antitoxin is primary treatment - antibiotics adjunctive
        {
            "condition": "diphtheria", "severity": "severe", "tier": "preferred",
            "drug": "benzylpenicillin",
            "dose_value": 50000, "dose_unit": "units/kg",
            "dose_qualifier": "max 1.2 MU per dose",
            "route": "IV", "frequency": "q12H",
            "duration_days": "14",
            "notes": [
                "Antitoxin is primary treatment - antibiotics adjunctive.",
                "Followed by Phenoxymethylpenicillin 250 mg PO q6H.",
                "Total duration: 14 days.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["corynebacterium diphtheriae"],
            "page": 6, "source_chapter": "3.5",
        },
        {
            "condition": "diphtheria", "severity": "severe", "tier": "oral_stepdown",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 250, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "to complete 14 total",
            "notes": ["Oral step-down for diphtheria treatment."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["corynebacterium diphtheriae"],
            "page": 7, "source_chapter": "3.5",
        },
        {
            "condition": "diphtheria", "severity": "moderate", "tier": "oral_alternative",
            "drug": "erythromycin",
            "dose_value": 400, "dose_unit": "mg",
            "dose_qualifier": "Erythromycin Ethyl Succinate",
            "route": "PO", "frequency": "q6H",
            "duration_days": "14",
            "notes": ["Oral alternative if able to take orally."],
            "contraindications": [],
            "pathogen_context": ["corynebacterium diphtheriae"],
            "page": 7, "source_chapter": "3.5",
        },

        # ----- PERITONSILLAR ABSCESS (QUINSY) (page 7-8) -----
        {
            "condition": "peritonsillar abscess", "severity": "severe",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "First-line for peritonsillar abscess (Quinsy).",
                "Surgical drainage is mandatory for abscess.",
                "IV to oral switch when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes", "anaerobes"],
            "page": 7, "source_chapter": "3.5",
        },
        {
            "condition": "peritonsillar abscess", "severity": "severe",
            "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "10-14",
            "notes": ["Alternative for peritonsillar abscess. Combine with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 7, "source_chapter": "3.5",
        },
        {
            "condition": "peritonsillar abscess", "severity": "severe",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": ["Anaerobic coverage paired with ceftriaxone."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 7, "source_chapter": "3.5",
        },
        {
            "condition": "peritonsillar abscess", "severity": "moderate",
            "tier": "oral_stepdown",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "to complete 10-14 total",
            "notes": ["Oral step-down once clinical improvement. Combine with metronidazole."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 7, "source_chapter": "3.5",
        },
        {
            "condition": "peritonsillar abscess", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pyogenes", "anaerobes"],
            "page": 8, "source_chapter": "3.5",
        },

        # ----- ACUTE EPIGLOTTITIS / SUPRAGLOTTITIS (page 8) -----
        {
            "condition": "acute epiglottitis", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5",
            "notes": [
                "First-line for acute epiglottitis (supraglottitis).",
                "If suspected concomitant meningitis: consider Ceftriaxone 2g IV q12H.",
                "IV to oral switch when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["haemophilus influenzae", "streptococcus pyogenes",
                                  "streptococcus pneumoniae", "staphylococcus aureus"],
            "page": 8, "source_chapter": "3.5",
        },
        {
            "condition": "acute epiglottitis", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "ciprofloxacin",
            "dose_value": 400, "dose_unit": "mg",
            "route": "IV", "frequency": "q12H",
            "duration_days": "5",
            "notes": [
                "For penicillin allergy.",
                "Combine with metronidazole 500 mg IV q8H.",
            ],
            "contraindications": [],
            "pathogen_context": ["haemophilus influenzae"],
            "page": 8, "source_chapter": "3.5",
        },
        {
            "condition": "acute epiglottitis", "severity": "severe",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "5",
            "notes": [
                "Add when MRSA suspected: moderate-severe sepsis, "
                "concomitant meningitis, high MRSA prevalence area.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 8, "source_chapter": "3.5",
        },

        # ----- PARAPHARYNGEAL ABSCESS (deep neck abscess) (page 9) -----
        {
            "condition": "parapharyngeal abscess", "severity": "severe",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": [
                "First-line for parapharyngeal/deep neck abscess.",
                "Surgical drainage is mandatory.",
                "Total duration: minimum 2 weeks and until resolution.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus", "staphylococcus aureus", "anaerobes",
                                  "fusobacterium necrophorum"],
            "page": 9, "source_chapter": "3.5",
        },
        {
            "condition": "parapharyngeal abscess", "severity": "severe",
            "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": ["Alternative paired with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus", "staphylococcus aureus"],
            "page": 9, "source_chapter": "3.5",
        },
        {
            "condition": "parapharyngeal abscess", "severity": "severe",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": ["Anaerobic coverage paired with cefazolin."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 9, "source_chapter": "3.5",
        },
        {
            "condition": "parapharyngeal abscess", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "dose_qualifier": "600-900 mg range",
            "dose_min_mg": 600, "dose_max_mg": 900,
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococcus", "anaerobes"],
            "page": 9, "source_chapter": "3.5",
        },

        # ----- ACUTE RHINOSINUSITIS - MILD (page 10) -----
        # Antibiotics only if >=3 of: purulent discharge, severe pain, fever,
        # elevated ESR/CRP, double sickening
        {
            "condition": "acute rhinosinusitis", "severity": "mild", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5",
            "notes": [
                "First-line for mild acute rhinosinusitis when antibiotics indicated.",
                "Avoid routine antibiotics for ARS - most resolve in 7-10 days.",
                "Indications: >=3 of purulent discharge, severe pain (VAS 8-10), "
                "fever, elevated ESR/CRP, double sickening.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae",
                                  "moraxella catarrhalis"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "mild", "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5",
            "notes": ["Alternative first-line for mild acute rhinosinusitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "mild",
            "tier": "recent_abx_preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5",
            "notes": ["First-line when recent antibiotic use within 30 days."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "mild",
            "tier": "penicillin_allergy",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "5",
            "notes": [
                "For patients with penicillin allergy.",
                "Avoid in pregnancy.",
            ],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["atypical pathogens"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "mild",
            "tier": "penicillin_allergy",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "5",
            "notes": ["Preferred in pregnancy for penicillin-allergic patient."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pneumoniae"],
            "page": 10, "source_chapter": "3.5",
        },

        # ----- ACUTE RHINOSINUSITIS - MODERATE/SEVERE (page 10) -----
        {
            "condition": "acute rhinosinusitis", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5",
            "notes": [
                "First-line for moderate/severe acute rhinosinusitis.",
                "Consider diagnostic tap/aspiration if treated with antibiotics. "
                "Send for culture.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae",
                                  "staphylococcus aureus"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "severe", "tier": "preferred",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5",
            "notes": ["Alternative first-line for moderate/severe ARS."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae"],
            "page": 10, "source_chapter": "3.5",
        },
        {
            "condition": "acute rhinosinusitis", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5",
            "notes": ["For patients with penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pneumoniae"],
            "page": 10, "source_chapter": "3.5",
        },
    ],

    # =====================================================================
    # CHAPTER 3.6 - FEBRILE NEUTROPENIA
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-5
    # Definition: Neutrophils < 0.5 x 10^9/L, or < 1 x 10^9/L with
    # predicted decline to < 0.5 x 10^9/L + fever >= 38C
    # Risk stratification: MASCC score >=21 = low risk; <21 = high risk
    # Covers: low-risk (outpatient), high-risk stable, high-risk unstable
    # =====================================================================
    "febrile_neutropenia": [

        # ----- LOW-RISK / OUTPATIENT (page 1-2) -----
        # MASCC score >= 21, can take orally, accessible to hospital care
        {
            "condition": "febrile neutropenia", "severity": "mild", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "until afebrile 48h AND ANC > 0.5 x 10^9/L",
            "notes": [
                "Low-risk outpatient (MASCC score >= 21).",
                "First dose to be administered in clinic or ED.",
                "Combine with Ciprofloxacin 750 mg PO q12H if colonised by "
                "Pseudomonas previously (within last 6 months).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["gram-negatives", "streptococci"],
            "page": 1, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "mild",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 900, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "until afebrile 48h AND ANC > 0.5 x 10^9/L",
            "notes": [
                "For penicillin-allergic low-risk patient.",
                "Combine with Ciprofloxacin 750 mg PO q12H.",
            ],
            "contraindications": [],
            "pathogen_context": ["gram-positives", "anaerobes"],
            "page": 1, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "mild",
            "tier": "gram_negative_addon",
            "drug": "ciprofloxacin",
            "dose_value": 750, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "until afebrile 48h AND ANC > 0.5 x 10^9/L",
            "notes": [
                "Gram-negative cover paired with co-amoxiclav or clindamycin.",
                "Higher 750mg dose preferred for febrile neutropenia.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa", "gram-negatives"],
            "page": 1, "source_chapter": "3.6",
        },

        # ----- HIGH-RISK / STABLE - INITIAL FEVER (page 2) -----
        # MASCC < 21, anticipate >= 7 days neutropenia
        {
            "condition": "febrile neutropenia", "severity": "moderate",
            "tier": "preferred",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until afebrile 48h AND ANC > 0.5 x 10^9/L",
            "notes": [
                "First-line monotherapy for high-risk stable patient.",
                "Combine with amikacin if septic or known gram-negative risk.",
                "Vancomycin is NOT routinely added - reserve for known MRSA "
                "coloniser, suspected catheter infection, skin/soft tissue "
                "infection, or shock. Stop after 48h if no gram-positive cocci.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "broad gram-negative"],
            "page": 2, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "moderate",
            "tier": "alternative",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "until afebrile 48h AND ANC > 0.5 x 10^9/L",
            "notes": ["Alternative broad-spectrum monotherapy for high-risk stable."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "anaerobes"],
            "page": 2, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "moderate",
            "tier": "gram_negative_addon",
            "drug": "amikacin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per clinical course",
            "notes": [
                "Aminoglycoside addon if septic or gram-negative risk.",
                "Therapeutic drug monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["pseudomonas aeruginosa", "broad gram-negative"],
            "page": 2, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "moderate",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "stop at 48h if no gram-positive cocci",
            "notes": [
                "NOT routine. Only add for: known MRSA coloniser, suspected "
                "catheter-related infection, skin/soft tissue infection, or shock.",
                "Stop after 48 hours if no evidence of gram-positive cocci.",
                "Therapeutic drug monitoring required (trough 15-20 mg/L).",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 2, "source_chapter": "3.6",
        },

        # ----- HIGH-RISK / STABLE - PERSISTENT FEVER (page 2) -----
        # Persistent fever or new fever after 4-7 days, or deterioration
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "persistent_fever_preferred",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "as per clinical course",
            "notes": [
                "Escalation for persistent or new fever after 4-7 days, or "
                "clinical deterioration.",
                "Consider VRE and resistant gram-negatives.",
                "Refer ID consult. Consider imaging and further microbiology.",
            ],
            "contraindications": [],
            "pathogen_context": ["ESBL", "resistant gram-negative"],
            "page": 2, "source_chapter": "3.6",
        },

        # ----- ANTIFUNGAL ADDON - NO PRIOR PROPHYLAXIS (page 3) -----
        # Add antifungal if fever persists >= 4-7 days, high-risk patients
        # (neutropenia >10 days, allogeneic HCT, high-dose steroids)
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_preferred",
            "drug": "micafungin",
            "dose_value": 100, "dose_unit": "mg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "yeast min 2 weeks after first negative blood culture; mould min 12 weeks",
            "notes": [
                "First-line antifungal addon when fungal infection suspected.",
                "Received no or only Fluconazole prophylaxis.",
                "Sinus/chest CT NOT suggestive of fungal infection.",
            ],
            "contraindications": [],
            "pathogen_context": ["candida"],
            "page": 3, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_mould_preferred",
            "drug": "voriconazole",
            "dose_value": 6, "dose_unit": "mg/kg",
            "dose_qualifier": "loading 6 mg/kg q12H on Day 1, then 4 mg/kg q12H",
            "route": "IV", "frequency": "q12H",
            "duration_days": "mould min 12 weeks",
            "notes": [
                "First-line if mould suspected (without sinus involvement).",
                "Therapeutic drug monitoring required.",
                "Multiple drug interactions - check before starting.",
            ],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["aspergillus", "mould"],
            "page": 3, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_alternative",
            "drug": "amphotericin B",
            "dose_value": 0.7, "dose_unit": "mg/kg",
            "dose_qualifier": "Deoxycholate; 0.7-1 mg/kg range",
            "dose_min_mg": None, "dose_max_mg": None,
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per fungal type and response",
            "notes": [
                "Alternative antifungal addon.",
                "Monitor renal function and electrolytes.",
                "Premedicate to reduce infusion reactions.",
            ],
            "contraindications": [],
            "pathogen_context": ["broad fungal coverage"],
            "page": 3, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_alternative",
            "drug": "amphotericin B lipid complex",
            "dose_value": 5, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per fungal type and response",
            "notes": ["Lipid formulation - reduced nephrotoxicity vs deoxycholate."],
            "contraindications": [],
            "pathogen_context": ["broad fungal coverage"],
            "page": 3, "source_chapter": "3.6",
        },

        # ----- ANTIFUNGAL - CT SUGGESTIVE OF FUNGAL INFECTION (page 3-4) -----
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_proven_sinus",
            "drug": "amphotericin B",
            "dose_value": 0.7, "dose_unit": "mg/kg",
            "dose_qualifier": "Deoxycholate; 0.7-1 mg/kg range",
            "route": "IV", "frequency": "q24H",
            "duration_days": "mould min 12 weeks",
            "notes": ["Preferred when CT suggestive of fungal infection with sinus involvement."],
            "contraindications": [],
            "pathogen_context": ["aspergillus", "mucormycosis"],
            "page": 3, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_proven_no_sinus",
            "drug": "voriconazole",
            "dose_value": 6, "dose_unit": "mg/kg",
            "dose_qualifier": "loading 6 mg/kg q12H Day 1, then 4 mg/kg q12H",
            "route": "IV", "frequency": "q12H",
            "duration_days": "mould min 12 weeks",
            "notes": [
                "Preferred when CT suggestive of fungal infection WITHOUT "
                "sinus involvement.",
            ],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["aspergillus"],
            "page": 4, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_alternative",
            "drug": "posaconazole",
            "dose_value": 300, "dose_unit": "mg",
            "dose_qualifier": "M/R 300 mg PO q12H Day 1-2, then 300 mg q24H",
            "route": "PO", "frequency": "q12H load then q24H",
            "duration_days": "mould min 12 weeks",
            "notes": ["Alternative azole for proven fungal infection."],
            "contraindications": [],
            "pathogen_context": ["aspergillus", "mucormycosis"],
            "page": 3, "source_chapter": "3.6",
        },

        # ----- ANTIFUNGAL - PRIOR AZOLE PROPHYLAXIS (page 4) -----
        # Patient received Voriconazole or Posaconazole prophylaxis
        {
            "condition": "febrile neutropenia", "severity": "severe",
            "tier": "antifungal_post_azole_prophylaxis",
            "drug": "amphotericin B",
            "dose_value": 0.7, "dose_unit": "mg/kg",
            "dose_qualifier": "Deoxycholate; 0.7-1 mg/kg range",
            "route": "IV", "frequency": "q24H",
            "duration_days": "mould min 12 weeks",
            "notes": [
                "First-line when patient received Voriconazole or "
                "Posaconazole prophylaxis - switch class to avoid resistance.",
            ],
            "contraindications": [],
            "pathogen_context": ["azole-resistant aspergillus", "mucormycosis"],
            "page": 4, "source_chapter": "3.6",
        },

        # ----- HIGH-RISK / UNSTABLE - INITIAL FEVER (page 4) -----
        {
            "condition": "febrile neutropenia", "severity": "critical",
            "tier": "preferred",
            "drug": "meropenem",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "as per clinical course",
            "notes": [
                "First-line for high-risk UNSTABLE patient.",
                "Vancomycin addition is appropriate empirically in unstable "
                "patients (unlike stable patients).",
                "ID consult mandatory.",
            ],
            "contraindications": [],
            "pathogen_context": ["broad gram-negative", "ESBL"],
            "page": 4, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "critical",
            "tier": "preferred_empiric_gram_positive",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "as per cultures",
            "notes": [
                "Empiric gram-positive cover in unstable patient.",
                "Therapeutic drug monitoring required (trough 15-20 mg/L).",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA", "MRSE", "streptococci"],
            "page": 4, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "critical",
            "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "as per clinical course",
            "notes": [
                "Alternative for high-risk unstable patient.",
                "Combine with amikacin and vancomycin.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 4, "source_chapter": "3.6",
        },
        {
            "condition": "febrile neutropenia", "severity": "critical",
            "tier": "gram_negative_addon",
            "drug": "amikacin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "as per clinical course",
            "notes": ["Aminoglycoside addon for unstable patient with cefepime."],
            "contraindications": [],
            "pathogen_context": ["broad gram-negative"],
            "page": 4, "source_chapter": "3.6",
        },
    ],

    # =====================================================================
    # CHAPTER 3.7 - GASTROINTESTINAL INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-11
    # Covers: infectious diarrhoea (mild/severe), V. cholerae,
    # C. difficile (non-severe/severe/fulminant), SBP (community/hospital/
    # secondary), perforated GU/DU, pyogenic liver abscess, amoebic
    # abscess, H. pylori (first/second-line)
    # =====================================================================
    "gi": [

        # ----- ACUTE MILD-MODERATE DIARRHOEA (page 1) -----
        # Usually self-limiting. No antibiotics routinely.
        # NEGATIVE INDICATION - antibiotic not indicated for typical case
        {
            "condition": "acute diarrhoea", "severity": "mild",
            "tier": "supportive_only",
            "drug": "oral rehydration",
            "dose_value": 0, "dose_unit": "",
            "route": "PO", "frequency": "as needed",
            "duration_days": "until resolution",
            "notes": [
                "Mild-moderate diarrhoea is self-limiting.",
                "NO ANTIBIOTICS REQUIRED for typical presentation.",
                "Fluid replacement and supportive therapy only.",
                "Mild: <=3 unformed stools, minimal symptoms.",
                "Moderate: >=3 unformed stools and/or symptomatic.",
            ],
            "contraindications": [],
            "pathogen_context": ["norovirus", "salmonella", "viral"],
            "page": 1, "source_chapter": "3.7",
        },

        # ----- ACUTE SEVERE DIARRHOEA (page 2) -----
        # >= 6 unformed stools/day, fever, bloody stools, tenesmus
        # Antibiotics indicated only if ill immunocompetent + fever, recent
        # travel, suspected enteric fever, or dysentery
        {
            "condition": "severe diarrhoea", "severity": "severe", "tier": "preferred",
            "drug": "ciprofloxacin",
            "dose_value": 500, "dose_unit": "mg",
            "dose_qualifier": "500-750 mg range",
            "dose_min_mg": 500, "dose_max_mg": 750,
            "route": "PO", "frequency": "q12H",
            "duration_days": "3-5",
            "notes": [
                "First-line empirical for severe diarrhoea or dysentery.",
                "Indications: ill patient with fever, abdominal pain, bloody "
                "diarrhoea, dysentery (Shigella suspected), recent "
                "international travel with fever >=38.5C/sepsis, or "
                "suspected enteric fever.",
            ],
            "contraindications": [],
            "pathogen_context": ["campylobacter", "salmonella", "shigella",
                                  "yersinia", "aeromonas"],
            "page": 2, "source_chapter": "3.7",
        },
        {
            "condition": "severe diarrhoea", "severity": "severe", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "3-5",
            "notes": ["Alternative for severe diarrhoea, especially if IV needed."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["salmonella", "shigella"],
            "page": 2, "source_chapter": "3.7",
        },
        {
            "condition": "severe diarrhoea", "severity": "severe", "tier": "alternative",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "3",
            "notes": ["Alternative for severe diarrhoea. Also single 1g dose option."],
            "contraindications": [],
            "pathogen_context": ["campylobacter", "shigella"],
            "page": 2, "source_chapter": "3.7",
        },
        {
            "condition": "severe diarrhoea", "severity": "severe", "tier": "alternative",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 480, "dose_unit": "mg",
            "dose_qualifier": "2 tablets per dose",
            "route": "PO", "frequency": "q12H",
            "duration_days": "3-5",
            "notes": ["Alternative for severe diarrhoea."],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["susceptible enteric pathogens"],
            "page": 2, "source_chapter": "3.7",
        },

        # ----- VIBRIO CHOLERAE (page 2) -----
        # Mild = hydration only; severe/immunocompromised = antibiotic
        {
            "condition": "cholera", "severity": "severe", "tier": "preferred",
            "drug": "azithromycin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "single dose",
            "duration_days": "1",
            "notes": [
                "For severe disease or immunocompromised patient.",
                "Antibiotics NOT required for mild cholera - hydration is primary.",
            ],
            "contraindications": [],
            "pathogen_context": ["vibrio cholerae"],
            "page": 2, "source_chapter": "3.7",
        },
        {
            "condition": "cholera", "severity": "severe", "tier": "alternative",
            "drug": "doxycycline",
            "dose_value": 300, "dose_unit": "mg",
            "route": "PO", "frequency": "single dose",
            "duration_days": "1",
            "notes": ["Single-dose alternative for severe cholera."],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["vibrio cholerae"],
            "page": 2, "source_chapter": "3.7",
        },

        # ----- C. DIFFICILE - INITIAL NON-SEVERE (page 3) -----
        {
            "condition": "C. difficile infection", "severity": "mild",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 125, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "10",
            "notes": [
                "First-line for initial non-severe C. difficile infection.",
                "ORAL vancomycin - works locally in gut.",
                "Discontinue inciting antibiotic if possible.",
                "Refer ID team if persistent/recurrent.",
            ],
            "contraindications": [],
            "pathogen_context": ["clostridioides difficile"],
            "page": 3, "source_chapter": "3.7",
        },
        {
            "condition": "C. difficile infection", "severity": "mild",
            "tier": "alternative",
            "drug": "metronidazole",
            "dose_value": 400, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "10",
            "notes": ["Alternative when oral vancomycin not available."],
            "contraindications": [],
            "pathogen_context": ["clostridioides difficile"],
            "page": 3, "source_chapter": "3.7",
        },

        # ----- C. DIFFICILE - INITIAL SEVERE (page 3) -----
        # WBC > 15 x 10^9/L, creatinine 50% above baseline, temp > 38.5C
        {
            "condition": "C. difficile infection", "severity": "severe",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 125, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "10",
            "notes": [
                "First-line for initial severe C. difficile infection.",
                "Severe = WBC >15, creatinine 50% above baseline, "
                "temp >38.5C, severe colitis.",
                "Combine with IV metronidazole 500 mg q8H.",
            ],
            "contraindications": [],
            "pathogen_context": ["clostridioides difficile"],
            "page": 3, "source_chapter": "3.7",
        },
        {
            "condition": "C. difficile infection", "severity": "severe",
            "tier": "preferred_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10",
            "notes": ["IV metronidazole paired with oral vancomycin for severe CDI."],
            "contraindications": [],
            "pathogen_context": ["clostridioides difficile"],
            "page": 3, "source_chapter": "3.7",
        },

        # ----- C. DIFFICILE - FULMINANT (page 3-4) -----
        # Hypotension/shock, ileus, megacolon
        {
            "condition": "C. difficile infection", "severity": "critical",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO/NG", "frequency": "q6H",
            "duration_days": "10",
            "notes": [
                "First-line for fulminant CDI (hypotension/shock/ileus/megacolon).",
                "Higher 500 mg dose via PO or NG tube.",
                "Combine with IV metronidazole 500 mg q8H.",
                "If ileus present: add rectal vancomycin 500 mg in 100 mL "
                "normal saline retention enema q6H, or faecal microbiota "
                "transplant.",
                "Refer ID team and consult surgeon.",
            ],
            "contraindications": [],
            "pathogen_context": ["clostridioides difficile"],
            "page": 3, "source_chapter": "3.7",
        },

        # ----- SPONTANEOUS BACTERIAL PERITONITIS (SBP) -----
        # Community-acquired, no prior antibiotic exposure (page 5)
        {
            "condition": "spontaneous bacterial peritonitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for community-acquired SBP, no antibiotic exposure.",
                "Indications: ascites + temp >37.8C, abdominal pain/"
                "tenderness, altered mental status, ascitic fluid PMN "
                ">=250 cells/microL.",
                "Send peritoneal fluid prior to antibiotics.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella pneumoniae"],
            "page": 5, "source_chapter": "3.7",
        },
        {
            "condition": "spontaneous bacterial peritonitis", "severity": "moderate",
            "tier": "prior_abx_exposure",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "5-7",
            "notes": ["First-line when patient has history of antibiotic exposure."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["resistant enterobacterales"],
            "page": 5, "source_chapter": "3.7",
        },

        # ----- SBP - HOSPITAL-ACQUIRED (page 5) -----
        # Occurs >48 hours after hospital admission
        {
            "condition": "spontaneous bacterial peritonitis", "severity": "severe",
            "tier": "hospital_acquired_preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "First-line for hospital-acquired SBP without instrumentation.",
                ">48 hours after admission.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "enterococcus"],
            "page": 5, "source_chapter": "3.7",
        },

        # ----- SBP - SECONDARY BACTERIAL PERITONITIS (page 5-6) -----
        # Post-instrumentation
        {
            "condition": "secondary bacterial peritonitis", "severity": "severe",
            "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "First-line for secondary peritonitis (post-instrumentation).",
                "Combine with vancomycin if MRSA suspected.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "anaerobes", "enterococcus"],
            "page": 5, "source_chapter": "3.7",
        },
        {
            "condition": "secondary bacterial peritonitis", "severity": "severe",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "5-7",
            "notes": [
                "MRSA cover for post-instrumentation peritonitis.",
                "Therapeutic drug monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 6, "source_chapter": "3.7",
        },

        # ----- PERFORATED GASTRIC/DUODENAL ULCER -----
        # Community-acquired (page 6)
        {
            "condition": "perforated peptic ulcer", "severity": "severe",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for community-acquired perforated gastric/"
                "duodenal ulcer. Surgical management required.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["mouth flora", "anaerobes"],
            "page": 6, "source_chapter": "3.7",
        },
        {
            "condition": "perforated peptic ulcer", "severity": "severe",
            "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 750, "dose_unit": "mg",
            "dose_qualifier": "750-1500 mg range",
            "dose_min_mg": 750, "dose_max_mg": 1500,
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative paired with metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["gram-negatives", "streptococci"],
            "page": 6, "source_chapter": "3.7",
        },
        {
            "condition": "perforated peptic ulcer", "severity": "severe",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Anaerobic coverage paired with cefuroxime."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 6, "source_chapter": "3.7",
        },

        # ----- PERFORATED PEPTIC ULCER - HOSPITAL-ACQUIRED -----
        {
            "condition": "perforated peptic ulcer", "severity": "critical",
            "tier": "shock_preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["For hospital-acquired perforated ulcer with shock."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "anaerobes"],
            "page": 6, "source_chapter": "3.7",
        },
        {
            "condition": "perforated peptic ulcer", "severity": "severe",
            "tier": "non_shock_preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "Hospital-acquired perforated ulcer without shock.",
                "Combine with metronidazole.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas", "gram-negatives"],
            "page": 6, "source_chapter": "3.7",
        },
        {
            "condition": "perforated peptic ulcer", "severity": "severe",
            "tier": "non_shock_alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["Alternative for hospital-acquired perforated ulcer."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas", "broad gram-negative"],
            "page": 6, "source_chapter": "3.7",
        },

        # ----- PYOGENIC LIVER ABSCESS - COMMUNITY-ACQUIRED (page 7) -----
        {
            "condition": "pyogenic liver abscess", "severity": "moderate",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14-42 (depending on response)",
            "notes": [
                "First-line for community-acquired pyogenic liver abscess.",
                "Abscess drainage is optimal therapy.",
                "If stepping down to oral co-amoxiclav: give higher dose 1g q8H.",
                "Longer courses (up to several months) if not drained.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["escherichia coli", "klebsiella pneumoniae",
                                  "streptococcus milleri"],
            "page": 7, "source_chapter": "3.7",
        },
        {
            "condition": "pyogenic liver abscess", "severity": "moderate",
            "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "14-42",
            "notes": ["Alternative paired with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["klebsiella pneumoniae", "escherichia coli"],
            "page": 7, "source_chapter": "3.7",
        },
        {
            "condition": "pyogenic liver abscess", "severity": "moderate",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14-42",
            "notes": ["Anaerobic coverage paired with ceftriaxone."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 7, "source_chapter": "3.7",
        },

        # ----- PYOGENIC LIVER ABSCESS - HOSPITAL-ACQUIRED (page 7) -----
        {
            "condition": "pyogenic liver abscess", "severity": "severe",
            "tier": "hospital_acquired_preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "14-42",
            "notes": [
                "First-line for hospital-acquired pyogenic liver abscess.",
                "Post-invasive procedures involving GIT (e.g., ERCP).",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "anaerobes"],
            "page": 7, "source_chapter": "3.7",
        },

        # ----- AMOEBIC LIVER ABSCESS (page 8) -----
        {
            "condition": "amoebic liver abscess", "severity": "moderate",
            "tier": "tissue_agent_preferred",
            "drug": "metronidazole",
            "dose_value": 800, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": [
                "Tissue agent for amoebic liver abscess.",
                "Follow with luminal agent (paromomycin) to eliminate "
                "residual colonic colonisation.",
            ],
            "contraindications": ["alcohol consumption"],
            "pathogen_context": ["entamoeba histolytica"],
            "page": 8, "source_chapter": "3.7",
        },
        {
            "condition": "amoebic liver abscess", "severity": "moderate",
            "tier": "luminal_agent",
            "drug": "paromomycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7",
            "notes": [
                "Luminal agent to eliminate residual colonic colonisation.",
                "Not available in Malaysia - per UMMC formulary note.",
            ],
            "contraindications": [],
            "pathogen_context": ["entamoeba histolytica"],
            "page": 8, "source_chapter": "3.7",
        },

        # ----- H. PYLORI - FIRST-LINE THERAPY (page 8-9) -----
        # Triple therapy: PPI + amoxicillin + clarithromycin
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "first_line_preferred",
            "drug": "omeprazole",
            "dose_value": 20, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14",
            "notes": [
                "First-line triple therapy: PPI + amoxicillin + clarithromycin.",
                "Alternative PPIs: Pantoprazole 40 mg q12H, Esomeprazole 20 mg q12H.",
                "Duration: 14 days.",
            ],
            "contraindications": [],
            "pathogen_context": ["helicobacter pylori"],
            "page": 8, "source_chapter": "3.7",
        },
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "first_line_preferred",
            "drug": "amoxicillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14",
            "notes": ["Part of H. pylori first-line triple therapy."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["helicobacter pylori"],
            "page": 9, "source_chapter": "3.7",
        },
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "first_line_preferred",
            "drug": "clarithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14",
            "notes": [
                "Part of H. pylori first-line triple therapy.",
                "Consider metronidazole 400 mg q12H if clarithromycin "
                "resistance rate >15%.",
            ],
            "contraindications": [],
            "pathogen_context": ["helicobacter pylori"],
            "page": 9, "source_chapter": "3.7",
        },
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "first_line_clarithromycin_resistance",
            "drug": "metronidazole",
            "dose_value": 400, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14",
            "notes": ["Alternative for clarithromycin if resistance rate >15%."],
            "contraindications": [],
            "pathogen_context": ["helicobacter pylori"],
            "page": 9, "source_chapter": "3.7",
        },

        # ----- H. PYLORI - PENICILLIN ALLERGY (page 8) -----
        # PPI + bismuth + tetracycline + (clarithromycin OR metronidazole)
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "tetracycline",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "14",
            "notes": [
                "For penicillin-allergic patient (quadruple therapy).",
                "Combined with PPI + Bismuth + clarithromycin/metronidazole.",
                "Bismuth not available in UMMC (available in UMSC).",
            ],
            "contraindications": ["pregnancy", "children <8 years"],
            "pathogen_context": ["helicobacter pylori"],
            "page": 9, "source_chapter": "3.7",
        },

        # ----- H. PYLORI - SECOND-LINE BISMUTH QUADRUPLE (page 9-10) -----
        # Used when clarithromycin resistance rate > 15% or first-line failed
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "second_line_quadruple",
            "drug": "tetracycline",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "14",
            "notes": [
                "Part of second-line bismuth quadruple regime.",
                "PPI + Bismuth + Tetracycline + Metronidazole.",
            ],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["helicobacter pylori"],
            "page": 9, "source_chapter": "3.7",
        },

        # ----- H. PYLORI - FLUOROQUINOLONE TRIPLE (page 10) -----
        # PPI + levofloxacin + amoxicillin
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "fluoroquinolone_triple",
            "drug": "levofloxacin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "14",
            "notes": ["Part of fluoroquinolone triple therapy for H. pylori."],
            "contraindications": [],
            "pathogen_context": ["helicobacter pylori"],
            "page": 10, "source_chapter": "3.7",
        },

        # ----- H. PYLORI - RESCUE HIGH-DOSE DUAL (page 10) -----
        # High-dose PPI + amoxicillin
        {
            "condition": "Helicobacter pylori infection", "severity": "moderate",
            "tier": "rescue_dual_therapy",
            "drug": "amoxicillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q6-8H",
            "duration_days": "14",
            "notes": [
                "High-dose rescue dual therapy for H. pylori treatment "
                "failure.",
                "Combined with high-dose PPI q8H.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["helicobacter pylori"],
            "page": 10, "source_chapter": "3.7",
        },
    ],

    # =====================================================================
    # CHAPTER 3.1 - BONE AND JOINT INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition (2024), pages 1-19
    # Covers: septic arthritis (with/without STD risk), osteomyelitis
    # (acute/chronic/vertebral), paronychia, flexor tenosynovitis,
    # open fractures, fracture fixation infection, spinal implant
    # infection, prosthetic joint infection (MSSA/MRSA/Streptococci)
    # =====================================================================
    "bone_joint": [

        # ----- SEPTIC ARTHRITIS - NO STD RISK (page 3) -----
        {
            "condition": "septic arthritis", "severity": "moderate", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4-6H",
            "duration_days": "14 IV then 14-28 PO; total 4-6 weeks",
            "notes": [
                "First-line for acute monoarticular septic arthritis without "
                "STD risk factors.",
                "Drainage, debridement and washout of infected joint required.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 3, "source_chapter": "3.1",
        },
        {
            "condition": "septic arthritis", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "14 IV then 14-28 PO; total 4-6 weeks",
            "notes": ["Alternative beta-lactam for septic arthritis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 3, "source_chapter": "3.1",
        },
        {
            "condition": "septic arthritis", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14 IV then PO; total 4-6 weeks",
            "notes": ["For penicillin-allergic patients."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 3, "source_chapter": "3.1",
        },

        # ----- SEPTIC ARTHRITIS - STD RISK (page 3) -----
        {
            "condition": "septic arthritis std risk", "severity": "moderate",
            "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "7-14",
            "notes": [
                "First-line for patients with STD risk factors.",
                "Combine with doxycycline.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["neisseria gonorrhoeae", "streptococcus",
                                  "staphylococcus"],
            "page": 3, "source_chapter": "3.1",
        },
        {
            "condition": "septic arthritis std risk", "severity": "moderate",
            "tier": "preferred_addon",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7",
            "notes": ["Atypical coverage for STD-related septic arthritis."],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["chlamydia trachomatis"],
            "page": 3, "source_chapter": "3.1",
        },

        # ----- ACUTE OSTEOMYELITIS (page 4) -----
        {
            "condition": "osteomyelitis", "severity": "moderate", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "14 IV then PO; total minimum 6 weeks",
            "notes": [
                "First-line for acute osteomyelitis.",
                "S. aureus accounts for ~80% of cases.",
                "Tailor to tissue culture - bone biopsy preferred over swab.",
                "If fully resected: 5d if no soft tissue infection, "
                "10-14d if soft tissue involved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes"],
            "page": 4, "source_chapter": "3.1",
        },
        {
            "condition": "osteomyelitis", "severity": "moderate", "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14 IV then PO; total minimum 6 weeks",
            "notes": ["Alternative for acute osteomyelitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 4, "source_chapter": "3.1",
        },
        {
            "condition": "osteomyelitis", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14 IV then PO; total minimum 6 weeks",
            "notes": ["For penicillin-allergic patients."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 4, "source_chapter": "3.1",
        },
        {
            "condition": "osteomyelitis", "severity": "moderate",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "6 weeks",
            "notes": [
                "For MRSA-suspected or penicillin-allergic patient.",
                "Therapeutic drug monitoring required.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 4, "source_chapter": "3.1",
        },

        # ----- VERTEBRAL OSTEOMYELITIS (page 6) -----
        {
            "condition": "vertebral osteomyelitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "minimum 6 weeks; 8-12 if abscess/extensive destruction",
            "notes": [
                "First-line for vertebral osteomyelitis.",
                "Withhold empirical therapy unless septic or neurological "
                "compromise.",
                "Investigate for brucellosis/TB if indicated.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 6, "source_chapter": "3.1",
        },
        {
            "condition": "vertebral osteomyelitis", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "minimum 6 weeks",
            "notes": ["Alternative for vertebral osteomyelitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 6, "source_chapter": "3.1",
        },

        # ----- PARONYCHIA / FELON (page 8) -----
        {
            "condition": "paronychia", "severity": "mild", "tier": "preferred",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-10",
            "notes": [
                "First-line for bacterial paronychia/felon.",
                "For deep-seated/systemic: surgical debridement + IV antibiotics.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 8, "source_chapter": "3.1",
        },
        {
            "condition": "paronychia", "severity": "mild", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-10",
            "notes": [
                "Alternative for paronychia.",
                "Indicated for finger sucking/nail biting (oral flora).",
                "Covers E. corrodens and beta-lactamase producing anaerobes.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "eikenella corrodens",
                                  "anaerobes"],
            "page": 8, "source_chapter": "3.1",
        },
        {
            "condition": "paronychia", "severity": "mild", "tier": "mrsa_coverage",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 960, "dose_unit": "mg",
            "dose_qualifier": "960-1920 mg range",
            "dose_min_mg": 960, "dose_max_mg": 1920,
            "route": "PO", "frequency": "q12H",
            "duration_days": "5-10",
            "notes": ["For patients with MRSA colonization risk."],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["MRSA"],
            "page": 8, "source_chapter": "3.1",
        },

        # ----- FLEXOR TENOSYNOVITIS (page 9) -----
        {
            "condition": "flexor tenosynovitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "5-10",
            "notes": [
                "First-line for flexor tenosynovitis.",
                "Combine with gentamicin if gram-negative coverage needed.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 9, "source_chapter": "3.1",
        },
        {
            "condition": "flexor tenosynovitis", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 1, "dose_unit": "g",
            "dose_qualifier": "1-2 g range",
            "dose_min_mg": 1000, "dose_max_mg": 2000,
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-10",
            "notes": ["Alternative for flexor tenosynovitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 9, "source_chapter": "3.1",
        },

        # ----- OPEN FRACTURES (page 9) -----
        {
            "condition": "open fracture", "severity": "moderate", "tier": "preferred",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "24h after wound closure (Gustilo I-II); 72h after debridement (Gustilo III)",
            "notes": [
                "First-line prophylaxis for open fractures.",
                "Combine with metronidazole and gentamicin based on severity.",
                "Administer within 6 hours to reduce osteomyelitis risk.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 9, "source_chapter": "3.1",
        },
        {
            "condition": "open fracture", "severity": "moderate",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "24-72h",
            "notes": ["Anaerobic coverage for contaminated open fractures."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 9, "source_chapter": "3.1",
        },
        {
            "condition": "open fracture", "severity": "severe",
            "tier": "contaminated_alternative",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "24-72h",
            "notes": ["For significant contamination - broader coverage."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["broad coverage"],
            "page": 9, "source_chapter": "3.1",
        },

        # ----- FRACTURE FIXATION / OAI - ACUTE (page 7) -----
        {
            "condition": "fracture fixation infection", "severity": "moderate",
            "tier": "acute_preferred",
            "drug": "ampicillin-sulbactam",
            "dose_value": 3, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "6 weeks (minimum, until bone union)",
            "notes": [
                "First-line for early/acute fracture fixation infection (<3 weeks).",
                "Combine with vancomycin if MRSA risk.",
                "Add rifampicin after wound is clean and dry (5-7 days).",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "broad coverage"],
            "page": 7, "source_chapter": "3.1",
        },
        {
            "condition": "fracture fixation infection", "severity": "severe",
            "tier": "delayed_preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until fractures united",
            "notes": [
                "For delayed (>=3 weeks) fracture fixation infection.",
                "Combine with vancomycin and metronidazole.",
                "Implant removal usually recommended.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "broad gram-negative"],
            "page": 7, "source_chapter": "3.1",
        },

        # ----- PROSTHETIC JOINT INFECTION - MSSA/MSSE (page 12) -----
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mssa_preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4-6H",
            "duration_days": "12 weeks (DAIR or one-stage exchange)",
            "notes": [
                "First-line for MSSA/MSSE prosthetic joint infection.",
                "Combine with rifampicin 600mg PO q24H for 2-6 weeks.",
                "Then oral step-down: cefalexin OR cloxacillin + rifampicin.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["MSSA", "MSSE"],
            "page": 12, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mssa_addon",
            "drug": "rifampicin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H",
            "duration_days": "2-6 weeks (initial), continue through oral phase",
            "notes": [
                "For Staphylococcal PJI - add only after wound dry and "
                "drains removed (5-7 days).",
                "Check Staphylococcus sensitivity to rifampicin first.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus"],
            "page": 12, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mssa_alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "12 weeks",
            "notes": ["Alternative for MSSA PJI."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 12, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mssa_oral_stepdown",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "dose_qualifier": "500-1000 mg range",
            "dose_min_mg": 500, "dose_max_mg": 1000,
            "route": "PO", "frequency": "q6H",
            "duration_days": "to complete 12 weeks",
            "notes": ["Oral step-down for MSSA PJI - combine with rifampicin."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 12, "source_chapter": "3.1",
        },

        # ----- PROSTHETIC JOINT INFECTION - MRSA/MRSE (page 13) -----
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mrsa_preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "12 weeks",
            "notes": [
                "First-line for MRSA/MRSE prosthetic joint infection.",
                "Combine with rifampicin 600 mg PO q24H.",
                "Oral step-down: sodium fusidate + rifampicin.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA", "MRSE"],
            "page": 13, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "mrsa_oral_stepdown",
            "drug": "sodium fusidate",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "to complete 12 weeks",
            "notes": ["Oral step-down for MRSA PJI - combine with rifampicin."],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 13, "source_chapter": "3.1",
        },

        # ----- PROSTHETIC JOINT INFECTION - STREPTOCOCCI (page 13) -----
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "streptococcus_preferred",
            "drug": "benzylpenicillin",
            "dose_value": 20, "dose_unit": "MU",
            "dose_qualifier": "20-24 MU daily divided",
            "route": "IV", "frequency": "q6H",
            "duration_days": "12 weeks",
            "notes": ["First-line for beta-haemolytic Streptococcal PJI."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["beta-haemolytic streptococci"],
            "page": 13, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "streptococcus_alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "12 weeks",
            "notes": ["Alternative for Streptococcal PJI."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["streptococci"],
            "page": 13, "source_chapter": "3.1",
        },
        {
            "condition": "prosthetic joint infection", "severity": "severe",
            "tier": "streptococcus_alternative",
            "drug": "clindamycin",
            "dose_value": 600, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "12 weeks",
            "notes": ["Alternative for Streptococcal PJI in penicillin allergy."],
            "contraindications": [],
            "pathogen_context": ["streptococci"],
            "page": 13, "source_chapter": "3.1",
        },
    ],

    # =====================================================================
    # CHAPTER 3.2 - CARDIOVASCULAR SYSTEM INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-15
    # Covers: infective endocarditis (empirical, viridans strep,
    # enterococcus, S. aureus MSSA/MRSA, prosthetic valve, HACEK,
    # culture-negative), pericarditis, streptococcal pharyngitis
    # =====================================================================
    "cardiovascular": [

        # ----- IE EMPIRICAL - NATIVE/PROSTHETIC VALVE (page 1) -----
        {
            "condition": "infective endocarditis", "severity": "severe",
            "tier": "empirical_preferred",
            "drug": "benzylpenicillin",
            "dose_value": 4, "dose_unit": "MU",
            "dose_qualifier": "total 24 MU daily",
            "route": "IV", "frequency": "q4H",
            "duration_days": "4-6 weeks (native 4w, prosthetic 6w)",
            "notes": [
                "Empirical first-line for severely ill IE patient.",
                "Combine with cloxacillin + gentamicin.",
                "Get 3 sets of blood cultures from different sites first.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["viridans streptococci", "enterococcus"],
            "page": 1, "source_chapter": "3.2",
        },
        {
            "condition": "infective endocarditis", "severity": "severe",
            "tier": "empirical_addon",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "4-6 weeks",
            "notes": ["S. aureus cover in empirical IE therapy."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 1, "source_chapter": "3.2",
        },
        {
            "condition": "infective endocarditis", "severity": "severe",
            "tier": "empirical_addon",
            "drug": "gentamicin",
            "dose_value": 3, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "2-4 weeks",
            "notes": [
                "Synergistic addition in IE.",
                "Avoid in elderly and renal impaired.",
                "Discontinue once cultures known except for Streptococcal/"
                "Enterococcal IE.",
                "TDM: pre-dose trough <1 mg/L.",
            ],
            "contraindications": ["renal impairment"],
            "pathogen_context": ["synergistic coverage"],
            "page": 1, "source_chapter": "3.2",
        },
        {
            "condition": "infective endocarditis", "severity": "severe",
            "tier": "empirical_penicillin_allergy",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "4-6 weeks",
            "notes": [
                "For penicillin-allergic IE patient.",
                "Combine with gentamicin.",
            ],
            "contraindications": [],
            "pathogen_context": ["broad gram-positive"],
            "page": 1, "source_chapter": "3.2",
        },
        {
            "condition": "infective endocarditis", "severity": "severe",
            "tier": "empirical_alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-6 weeks",
            "notes": [
                "Alternative for mild-moderate penicillin allergy.",
                "Combine with gentamicin IM or IV.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococci"],
            "page": 1, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - VIRIDANS STREP MIC < 0.125 (page 3) -----
        {
            "condition": "viridans streptococcal endocarditis", "severity": "severe",
            "tier": "mic_sensitive_preferred",
            "drug": "benzylpenicillin",
            "dose_value": 3, "dose_unit": "MU",
            "route": "IV", "frequency": "q4-6H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": [
                "Penicillin-susceptible viridans streptococci (MIC <0.125).",
                "Monotherapy is adequate.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["viridans streptococci (susceptible)"],
            "page": 3, "source_chapter": "3.2",
        },
        {
            "condition": "viridans streptococcal endocarditis", "severity": "severe",
            "tier": "mic_sensitive_alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": ["Alternative for penicillin-susceptible viridans strep IE."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["viridans streptococci"],
            "page": 3, "source_chapter": "3.2",
        },
        {
            "condition": "viridans streptococcal endocarditis", "severity": "severe",
            "tier": "mic_sensitive_alternative",
            "drug": "ampicillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": ["Alternative for penicillin-susceptible viridans strep IE."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["viridans streptococci"],
            "page": 3, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - ENTEROCOCCUS (page 4-5) -----
        {
            "condition": "enterococcal endocarditis", "severity": "severe",
            "tier": "preferred",
            "drug": "ampicillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "4 weeks (native <3mo symptoms); 6 weeks (prosthetic or >3mo)",
            "notes": [
                "First-line for penicillin/gentamicin-sensitive enterococcus.",
                "Combine with gentamicin 3 mg/kg q24H for 2 weeks.",
                "Check for HLAR (high-level aminoglycoside resistance) - "
                "stop gentamicin if present.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterococcus (susceptible)"],
            "page": 4, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - S. AUREUS MSSA NATIVE (page 6) -----
        {
            "condition": "staphylococcal endocarditis MSSA", "severity": "severe",
            "tier": "native_preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "4-6 weeks (uncomplicated right-sided 2-4 weeks)",
            "notes": [
                "First-line for MSSA native valve IE.",
                "Left-sided or complicated right-sided: 4-6 weeks.",
                "Uncomplicated right-sided (tricuspid): 2-4 weeks.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 6, "source_chapter": "3.2",
        },
        {
            "condition": "staphylococcal endocarditis MSSA", "severity": "severe",
            "tier": "native_alternative_non_immediate_pen_allergy",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-6 weeks",
            "notes": ["For non-immediate hypersensitivity to penicillin."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 6, "source_chapter": "3.2",
        },
        {
            "condition": "staphylococcal endocarditis MSSA", "severity": "severe",
            "tier": "native_immediate_pen_allergy",
            "drug": "daptomycin",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "4-6 weeks",
            "notes": [
                "For immediate hypersensitivity (anaphylaxis) to penicillin.",
                "Refer ID for daptomycin use.",
            ],
            "contraindications": [],
            "pathogen_context": ["MSSA"],
            "page": 6, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - S. AUREUS MRSA (page 8) -----
        {
            "condition": "staphylococcal endocarditis MRSA", "severity": "severe",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "4-6 weeks (native); >=6 weeks (prosthetic)",
            "notes": [
                "First-line for MRSA IE with MIC <1 mg/mL.",
                "TDM trough 15-20 mg/L.",
                "Combine with gentamicin + rifampicin for prosthetic valve.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 8, "source_chapter": "3.2",
        },
        {
            "condition": "staphylococcal endocarditis MRSA", "severity": "severe",
            "tier": "high_mic_preferred",
            "drug": "daptomycin",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "4-6 weeks",
            "notes": [
                "First-line if Vancomycin MIC >1 mg/mL.",
                "Also alternative for vancomycin-intolerant patients.",
                "Refer ID for daptomycin use.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA (high MIC)"],
            "page": 8, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - PROSTHETIC VALVE (page 7-8) -----
        {
            "condition": "prosthetic valve endocarditis", "severity": "severe",
            "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": ">=6 weeks",
            "notes": [
                "First-line for MSSA prosthetic valve IE.",
                "Combine with gentamicin + rifampicin (450 mg PO q12H).",
                "Start rifampicin only after 3-5 days of effective Cloxacillin.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["MSSA"],
            "page": 7, "source_chapter": "3.2",
        },
        {
            "condition": "prosthetic valve endocarditis", "severity": "severe",
            "tier": "preferred_addon",
            "drug": "rifampicin",
            "dose_value": 450, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": ">=6 weeks",
            "notes": [
                "Synergistic addition for prosthetic valve staph IE.",
                "Start after 3-5 days of effective initial therapy.",
                "Many drug interactions - check before adding.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococci on prosthetic material"],
            "page": 7, "source_chapter": "3.2",
        },

        # ----- IE DIRECTED - HACEK (page 9) -----
        {
            "condition": "HACEK endocarditis", "severity": "severe", "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": [
                "First-line for HACEK organism IE.",
                "Haemophilus, Aggregatibacter, Cardiobacterium, Eikenella, "
                "Kingella.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["HACEK organisms"],
            "page": 9, "source_chapter": "3.2",
        },
        {
            "condition": "HACEK endocarditis", "severity": "severe", "tier": "alternative",
            "drug": "ampicillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": ["Alternative for HACEK IE - combine with gentamicin."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["HACEK organisms"],
            "page": 9, "source_chapter": "3.2",
        },
        {
            "condition": "HACEK endocarditis", "severity": "severe", "tier": "alternative",
            "drug": "ciprofloxacin",
            "dose_value": 400, "dose_unit": "mg",
            "route": "IV", "frequency": "q12H",
            "duration_days": "native 4 weeks, prosthetic 6 weeks",
            "notes": ["Alternative for HACEK IE. Oral form: 500 mg q12H."],
            "contraindications": [],
            "pathogen_context": ["HACEK organisms"],
            "page": 9, "source_chapter": "3.2",
        },

        # ----- IE - CANDIDA (page 12) -----
        {
            "condition": "candida endocarditis", "severity": "severe", "tier": "preferred",
            "drug": "amphotericin B",
            "dose_value": 0.6, "dose_unit": "mg/kg",
            "dose_qualifier": "Deoxycholate, 0.6-1 mg/kg",
            "dose_min_mg": None, "dose_max_mg": None,
            "route": "IV", "frequency": "q24H",
            "duration_days": "6 weeks after valve replacement",
            "notes": [
                "First-line for Candida endocarditis.",
                "Valve replacement is mandatory.",
                "Step-down: Fluconazole 400-800 mg PO q24H if susceptible.",
            ],
            "contraindications": [],
            "pathogen_context": ["candida"],
            "page": 12, "source_chapter": "3.2",
        },
        {
            "condition": "candida endocarditis", "severity": "severe", "tier": "alternative",
            "drug": "micafungin",
            "dose_value": 150, "dose_unit": "mg",
            "route": "IV", "frequency": "q24H",
            "duration_days": "6 weeks after valve replacement",
            "notes": ["Alternative when ampho B not tolerated."],
            "contraindications": [],
            "pathogen_context": ["candida"],
            "page": 12, "source_chapter": "3.2",
        },

        # ----- PURULENT PERICARDITIS (page 12-13) -----
        {
            "condition": "purulent pericarditis", "severity": "severe",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "2-4 weeks with adequate source control",
            "notes": [
                "First-line empirical for purulent pericarditis.",
                "Combine with cefepime.",
                "Source control (pericardiocentesis) is crucial.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pneumoniae"],
            "page": 12, "source_chapter": "3.2",
        },
        {
            "condition": "purulent pericarditis", "severity": "severe",
            "tier": "preferred_addon",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "2-4 weeks",
            "notes": ["Gram-negative cover paired with vancomycin."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 13, "source_chapter": "3.2",
        },
        {
            "condition": "purulent pericarditis", "severity": "severe", "tier": "alternative",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "2-4 weeks",
            "notes": ["Alternative gram-negative cover."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 13, "source_chapter": "3.2",
        },

        # ----- STREPTOCOCCAL PHARYNGITIS / RHEUMATIC FEVER PREVENTION (page 13) -----
        {
            "condition": "streptococcal pharyngitis", "severity": "mild", "tier": "preferred",
            "drug": "phenoxymethylpenicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "10",
            "notes": [
                "Rheumatic fever prevention.",
                "Screen and treat household contacts if GAS confirmed.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 13, "source_chapter": "3.2",
        },
        {
            "condition": "streptococcal pharyngitis", "severity": "mild", "tier": "preferred",
            "drug": "amoxicillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "10",
            "notes": ["Alternative first-line for streptococcal pharyngitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pyogenes"],
            "page": 13, "source_chapter": "3.2",
        },
    ],

    # =====================================================================
    # CHAPTER 3.3 - CENTRAL NERVOUS SYSTEM INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-9
    # Covers: bacterial meningitis (age-stratified, immunocompromised),
    # penetrating head injury, trauma with basilar skull fracture,
    # ventriculitis (healthcare-associated), brain abscess (primary,
    # sinusitis, chronic otitis media, post-surgical, cyanotic heart),
    # encephalitis (HSV)
    # =====================================================================
    "cns": [

        # ----- BACTERIAL MENINGITIS - <50 YEARS, IMMUNOCOMPETENT (page 3) -----
        {
            "condition": "bacterial meningitis", "severity": "severe",
            "tier": "young_immunocompetent_preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "10-14 (S. pneumoniae); 7 (N. meningitidis, H. influenzae)",
            "notes": [
                "First-line for <50 years immunocompetent adult.",
                "Get blood C&S and CSF examination ASAP.",
                "Do NOT delay therapy for CT or LP.",
                "CT brain before LP if: CNS disease history, new seizure, "
                "papilloedema, altered consciousness, focal deficit.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "neisseria meningitidis",
                                  "haemophilus influenzae"],
            "page": 3, "source_chapter": "3.3",
        },

        # ----- BACTERIAL MENINGITIS - >50 YEARS (page 3-4) -----
        {
            "condition": "bacterial meningitis", "severity": "severe",
            "tier": "elderly_preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "21 (Listeria); 10-14 (S. pneumoniae); 21 (gram-negative)",
            "notes": [
                "First-line for >50 years adult.",
                "Must combine with ampicillin to cover Listeria.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "listeria"],
            "page": 3, "source_chapter": "3.3",
        },
        {
            "condition": "bacterial meningitis", "severity": "severe",
            "tier": "elderly_addon",
            "drug": "ampicillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q4H",
            "duration_days": "21 (Listeria coverage)",
            "notes": [
                "Listeria coverage paired with ceftriaxone in >50yo.",
                "Also for immunocompromised, pregnant, debilitated patients.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["listeria monocytogenes"],
            "page": 4, "source_chapter": "3.3",
        },

        # ----- BACTERIAL MENINGITIS - IMMUNOCOMPROMISED (page 4) -----
        {
            "condition": "bacterial meningitis", "severity": "severe",
            "tier": "immunocompromised_preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "21 (Listeria); 21 (gram-negative bacilli)",
            "notes": [
                "First-line for immunocompromised (HIV/AIDS, alcoholism, "
                "pregnant, debilitated).",
                "Combine with ampicillin for Listeria coverage.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "listeria",
                                  "gram-negatives"],
            "page": 4, "source_chapter": "3.3",
        },

        # ----- PENETRATING HEAD INJURY (page 4) -----
        {
            "condition": "penetrating head injury meningitis", "severity": "severe",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "10-14 typical",
            "notes": [
                "First-line empirical for penetrating head injury.",
                "Combine with ceftazidime for gram-negative cover.",
                "Aim for vancomycin trough 15-20 mg/L.",
                "Refer ID if anaphylaxis to beta-lactams.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus epidermidis", "staphylococcus aureus",
                                  "P. acnes"],
            "page": 4, "source_chapter": "3.3",
        },
        {
            "condition": "penetrating head injury meningitis", "severity": "severe",
            "tier": "preferred_addon",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "Gram-negative cover paired with vancomycin.",
                "Active against Pseudomonas aeruginosa.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "A. baumannii"],
            "page": 4, "source_chapter": "3.3",
        },
        {
            "condition": "penetrating head injury meningitis", "severity": "severe",
            "tier": "alternative_addon",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["Alternative gram-negative cover."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 4, "source_chapter": "3.3",
        },

        # ----- BASILAR SKULL FRACTURE (page 5) -----
        # Antibiotics NOT routinely required unless infection develops
        {
            "condition": "basilar skull fracture", "severity": "mild",
            "tier": "no_antibiotics_required",
            "drug": "observation",
            "dose_value": 0, "dose_unit": "",
            "route": "", "frequency": "",
            "duration_days": "",
            "notes": [
                "Antibiotics NOT required unless evidence of infection.",
                "If infected: Vancomycin + Ceftazidime.",
            ],
            "contraindications": [],
            "pathogen_context": ["streptococcus pneumoniae", "H. influenzae"],
            "page": 5, "source_chapter": "3.3",
        },
        {
            "condition": "basilar skull fracture", "severity": "severe",
            "tier": "infected_preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "10-14",
            "notes": ["Treatment if evidence of infection. Combine with ceftazidime."],
            "contraindications": [],
            "pathogen_context": ["streptococcus pneumoniae", "staphylococci"],
            "page": 5, "source_chapter": "3.3",
        },

        # ----- HEALTHCARE-ASSOCIATED VENTRICULITIS (page 5) -----
        {
            "condition": "ventriculitis", "severity": "severe", "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "10-14 (S. aureus/gram-negative bacilli after CSF clears)",
            "notes": [
                "First-line for healthcare-associated ventriculitis.",
                "Combine with ceftazidime.",
                "Remove infected shunt - re-implantation timing based on "
                "organism and culture clearance.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococci", "gram-negatives"],
            "page": 5, "source_chapter": "3.3",
        },
        {
            "condition": "ventriculitis", "severity": "severe", "tier": "preferred_addon",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["Gram-negative cover paired with vancomycin for ventriculitis."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas", "gram-negatives"],
            "page": 5, "source_chapter": "3.3",
        },

        # ----- BRAIN ABSCESS - PRIMARY (page 6) -----
        {
            "condition": "brain abscess", "severity": "severe", "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "until response on neuroimaging (typically 6-8 weeks)",
            "notes": [
                "First-line for primary brain abscess (unknown source or "
                "sinusitis origin).",
                "Must combine with metronidazole.",
                "Surgical drainage is mandatory.",
                "Add vancomycin if S. aureus suspected.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococci",
                                  "gram-negative", "anaerobes"],
            "page": 6, "source_chapter": "3.3",
        },
        {
            "condition": "brain abscess", "severity": "severe", "tier": "preferred_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until neuroimaging response",
            "notes": ["Anaerobic coverage paired with ceftriaxone for brain abscess."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 6, "source_chapter": "3.3",
        },
        {
            "condition": "brain abscess", "severity": "severe", "tier": "penicillin_allergy",
            "drug": "ciprofloxacin",
            "dose_value": 400, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until response on neuroimaging",
            "notes": [
                "For penicillin allergy - refer ID first.",
                "Combine with metronidazole.",
            ],
            "contraindications": [],
            "pathogen_context": ["gram-negative", "streptococci"],
            "page": 6, "source_chapter": "3.3",
        },

        # ----- BRAIN ABSCESS - CHRONIC OTITIS MEDIA (page 7) -----
        {
            "condition": "brain abscess otitis", "severity": "severe", "tier": "preferred",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "until response on neuroimaging",
            "notes": [
                "For brain abscess from chronic otitis media source.",
                "Combine with metronidazole.",
                "Surgical drainage mandatory.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["gram-negative", "streptococci", "anaerobes"],
            "page": 7, "source_chapter": "3.3",
        },

        # ----- BRAIN ABSCESS - POST-SURGICAL / TRAUMATIC / SUBDURAL EMPYEMA (page 7) -----
        {
            "condition": "post-surgical brain abscess", "severity": "severe",
            "tier": "preferred",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 15 mg/kg max 1g",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "until neuroimaging response",
            "notes": [
                "For post-surgical, traumatic brain abscess or subdural "
                "empyema. Combine with ceftazidime or cefepime.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococci", "enterobacteriaceae"],
            "page": 7, "source_chapter": "3.3",
        },

        # ----- BRAIN ABSCESS - CYANOTIC HEART DISEASE (page 7) -----
        {
            "condition": "cyanotic heart brain abscess", "severity": "severe",
            "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "until neuroimaging response",
            "notes": [
                "For brain abscess in patient with cyanotic heart disease.",
                "Streptococcus viridans is most common pathogen.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus viridans"],
            "page": 7, "source_chapter": "3.3",
        },

        # ----- ENCEPHALITIS - HSV (page 8) -----
        {
            "condition": "viral encephalitis", "severity": "severe", "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14",
            "notes": [
                "First-line empirical for suspected HSV/VZV encephalitis.",
                "Total duration: 14 days.",
                "Add Doxycycline 100 mg PO q12H if Rickettsia/Mycoplasma suspected.",
                "Renal dose adjustment required.",
            ],
            "contraindications": [],
            "pathogen_context": ["HSV", "VZV"],
            "page": 8, "source_chapter": "3.3",
        },
    ],

    # =====================================================================
    # CHAPTER 3.4 - OPHTHALMOLOGY INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-14
    # Covers: blepharitis, meibomian abscess (internal hordeolum),
    # stye (external hordeolum), orbital cellulitis, preseptal cellulitis,
    # dacryocystitis, conjunctivitis (mild/severe/gonococcal),
    # chlamydia/trachoma, keratitis (HSV, bacterial, corneal ulcer),
    # acute retinal necrosis, PORN, endophthalmitis (endogenous,
    # exogenous, fungal), ophthalmic zoster
    # =====================================================================
    "ophthalmology": [

        # ----- CHRONIC BLEPHARITIS - SEVERE (page 1) -----
        # Mild/moderate = symptomatic only (warm compress, lid hygiene)
        {
            "condition": "chronic blepharitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "chloramphenicol",
            "dose_value": 0.5, "dose_unit": "%",
            "dose_qualifier": "0.5% eye drops",
            "route": "eye drop", "frequency": "q4-6H",
            "duration_days": "14-28 (long-term for anti-inflammatory effects)",
            "notes": [
                "First-line for chronic moderate-severe blepharitis with "
                "inadequate response to topical therapy.",
                "Symptomatic measures first: warm compress, lid hygiene, "
                "artificial tears.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "rosacea-associated"],
            "page": 1, "source_chapter": "3.4",
        },
        {
            "condition": "chronic blepharitis", "severity": "moderate",
            "tier": "alternative",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "14 (then 100 mg q24H continued)",
            "notes": [
                "Oral alternative for chronic blepharitis - anti-inflammatory "
                "effect.",
                "Followed by 100 mg PO q24H for maintenance.",
            ],
            "contraindications": ["pregnancy", "children <8 years"],
            "pathogen_context": ["rosacea-associated"],
            "page": 1, "source_chapter": "3.4",
        },
        {
            "condition": "chronic blepharitis", "severity": "moderate",
            "tier": "alternative",
            "drug": "azithromycin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q24H day 1 then 250 mg q24H",
            "duration_days": "5",
            "notes": ["Alternative oral therapy for chronic blepharitis."],
            "contraindications": [],
            "pathogen_context": ["rosacea-associated"],
            "page": 1, "source_chapter": "3.4",
        },

        # ----- MEIBOMIAN ABSCESS (INTERNAL HORDEOLUM) (page 2) -----
        {
            "condition": "meibomian abscess", "severity": "moderate",
            "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV/PO", "frequency": "q6H",
            "duration_days": "until resolution of abscess",
            "notes": [
                "First-line for meibomian abscess (internal hordeolum).",
                "Combine with symptomatic measures (warm compress, lid hygiene).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 2, "source_chapter": "3.4",
        },
        {
            "condition": "meibomian abscess", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 1, "dose_unit": "g",
            "dose_qualifier": "1-2 g range",
            "dose_min_mg": 1000, "dose_max_mg": 2000,
            "route": "IV", "frequency": "q8H",
            "duration_days": "until resolution",
            "notes": ["IV alternative for meibomian abscess."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 2, "source_chapter": "3.4",
        },
        {
            "condition": "meibomian abscess", "severity": "moderate",
            "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "until resolution",
            "notes": ["Oral alternative for meibomian abscess."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 2, "source_chapter": "3.4",
        },
        {
            "condition": "meibomian abscess", "severity": "moderate",
            "tier": "mrsa_or_pen_allergy",
            "drug": "trimethoprim-sulfamethoxazole",
            "dose_value": 5, "dose_unit": "mg/kg",
            "dose_qualifier": "5-10 mg/kg/day of TMP component",
            "route": "PO", "frequency": "q12H",
            "duration_days": "until resolution",
            "notes": [
                "For beta-lactam allergy or MRSA concern.",
                "Dose expressed as TMP component.",
            ],
            "contraindications": ["sulfa allergy"],
            "pathogen_context": ["MRSA"],
            "page": 2, "source_chapter": "3.4",
        },

        # ----- STYE (EXTERNAL HORDEOLUM) (page 2) -----
        # NEGATIVE INDICATION - antibiotics NOT indicated
        {
            "condition": "stye", "severity": "mild",
            "tier": "supportive_only",
            "drug": "symptomatic measures",
            "dose_value": 0, "dose_unit": "",
            "route": "topical", "frequency": "as needed",
            "duration_days": "until resolution",
            "notes": [
                "Stye (external hordeolum): symptomatic measures only.",
                "Warm compress and lid hygiene.",
                "Systemic antibiotics NOT indicated.",
                "Refer to ophthalmology if abscess or cellulitis develops.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 2, "source_chapter": "3.4",
        },

        # ----- ORBITAL CELLULITIS (POST ORBITAL) (page 3) -----
        {
            "condition": "orbital cellulitis", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": [
                "First-line for orbital (post-orbital) cellulitis.",
                "Step-down to oral Co-amoxiclav 625 mg PO q8H once "
                "clinical response.",
                "Surgical drainage if worsening signs and symptoms.",
                "Add Vancomycin 15 mg/kg q8-12H if high MRSA risk.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "haemophilus influenzae",
                                  "staphylococcus aureus", "anaerobes"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "orbital cellulitis", "severity": "severe",
            "tier": "intracranial_extension",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q12H",
            "duration_days": "10-14",
            "notes": [
                "For suspected intracranial extension.",
                "Combine with metronidazole 500 mg IV q8H.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["streptococcus pneumoniae", "anaerobes"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "orbital cellulitis", "severity": "severe",
            "tier": "intracranial_extension_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["Anaerobic cover for orbital cellulitis with intracranial extension."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "orbital cellulitis", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "ciprofloxacin",
            "dose_value": 750, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7-10",
            "notes": [
                "For penicillin-allergic patient.",
                "Combine with Metronidazole 400 mg PO q8H.",
            ],
            "contraindications": [],
            "pathogen_context": ["gram-negative", "anaerobes"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "orbital cellulitis", "severity": "severe",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "7-10",
            "notes": ["Add when MRSA suspected. TDM required."],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 3, "source_chapter": "3.4",
        },

        # ----- PRESEPTAL CELLULITIS (PERIORBITAL) (page 3) -----
        # Different age groups: <5 years (H. influenzae risk if unvaccinated)
        # and >5 years (Staph predominant)
        {
            "condition": "preseptal cellulitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": [
                "First-line for periorbital (preseptal) cellulitis.",
                "For all age groups.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pneumoniae"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "preseptal cellulitis", "severity": "moderate",
            "tier": "preferred",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["Alternative first-line for preseptal cellulitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "preseptal cellulitis", "severity": "moderate",
            "tier": "unvaccinated_alternative",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": ["For patients <5 years who did not complete vaccination (H. influenzae cover)."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["haemophilus influenzae"],
            "page": 3, "source_chapter": "3.4",
        },
        {
            "condition": "preseptal cellulitis", "severity": "moderate",
            "tier": "penicillin_allergy",
            "drug": "clindamycin",
            "dose_value": 300, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["For penicillin-allergic patients."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 3, "source_chapter": "3.4",
        },

        # ----- DACRYOCYSTITIS - MILD (page 4) -----
        {
            "condition": "dacryocystitis", "severity": "mild", "tier": "preferred",
            "drug": "cloxacillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": [
                "First-line for mild dacryocystitis.",
                "Aspiration and drainage recommended.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes"],
            "page": 4, "source_chapter": "3.4",
        },
        {
            "condition": "dacryocystitis", "severity": "mild", "tier": "alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": ["Alternative for mild dacryocystitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 4, "source_chapter": "3.4",
        },

        # ----- DACRYOCYSTITIS - ACUTE SEVERE (page 4) -----
        {
            "condition": "dacryocystitis", "severity": "severe", "tier": "preferred",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": ["First-line for acute severe dacryocystitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pyogenes"],
            "page": 4, "source_chapter": "3.4",
        },
        {
            "condition": "dacryocystitis", "severity": "severe", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": ["Alternative for acute severe dacryocystitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 4, "source_chapter": "3.4",
        },

        # ----- BACTERIAL CONJUNCTIVITIS - MILD (page 4) -----
        {
            "condition": "bacterial conjunctivitis", "severity": "mild", "tier": "preferred",
            "drug": "chloramphenicol",
            "dose_value": 0.5, "dose_unit": "%",
            "dose_qualifier": "0.5% eye drops",
            "route": "eye drop", "frequency": "q6H",
            "duration_days": "5-7",
            "notes": ["First-line topical therapy for mild bacterial conjunctivitis."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pneumoniae"],
            "page": 4, "source_chapter": "3.4",
        },
        {
            "condition": "bacterial conjunctivitis", "severity": "mild", "tier": "alternative",
            "drug": "tobramycin",
            "dose_value": 0.3, "dose_unit": "%",
            "dose_qualifier": "0.3% tobramycin / 0.1% dexamethasone eye drops",
            "route": "eye drop", "frequency": "as labelled",
            "duration_days": "5-7",
            "notes": ["Combination eye drops for mild bacterial conjunctivitis."],
            "contraindications": [],
            "pathogen_context": ["gram-negative"],
            "page": 4, "source_chapter": "3.4",
        },

        # ----- BACTERIAL CONJUNCTIVITIS - SEVERE (page 5) -----
        {
            "condition": "bacterial conjunctivitis", "severity": "severe", "tier": "preferred",
            "drug": "tobramycin",
            "dose_value": 0.3, "dose_unit": "%",
            "dose_qualifier": "0.3% tobramycin / 0.1% dexamethasone eye drops",
            "route": "eye drop", "frequency": "as labelled",
            "duration_days": "5-7",
            "notes": ["First-line for severe bacterial conjunctivitis."],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.4",
        },
        {
            "condition": "bacterial conjunctivitis", "severity": "severe", "tier": "alternative",
            "drug": "moxifloxacin",
            "dose_value": 0.5, "dose_unit": "%",
            "dose_qualifier": "0.5% eye drops, 1 drop per dose",
            "route": "eye drop", "frequency": "q8-12H",
            "duration_days": "5-7",
            "notes": ["Fluoroquinolone alternative for severe bacterial conjunctivitis."],
            "contraindications": [],
            "pathogen_context": ["broad coverage"],
            "page": 5, "source_chapter": "3.4",
        },
        {
            "condition": "bacterial conjunctivitis", "severity": "severe", "tier": "alternative",
            "drug": "levofloxacin",
            "dose_value": 0.5, "dose_unit": "%",
            "dose_qualifier": "0.5% eye drops, 1 drop per dose",
            "route": "eye drop", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "Fluoroquinolone alternative.",
                "Not available in UMMC.",
            ],
            "contraindications": [],
            "pathogen_context": ["broad coverage"],
            "page": 5, "source_chapter": "3.4",
        },

        # ----- CHLAMYDIA CONJUNCTIVITIS (Inclusion / Trachoma) (page 5) -----
        {
            "condition": "chlamydia conjunctivitis", "severity": "mild", "tier": "preferred",
            "drug": "azithromycin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "single dose",
            "duration_days": "1",
            "notes": [
                "First-line for chlamydia inclusion conjunctivitis or trachoma.",
                "For trachoma, doxycycline alternative duration is 21 days.",
            ],
            "contraindications": [],
            "pathogen_context": ["chlamydia trachomatis"],
            "page": 5, "source_chapter": "3.4",
        },
        {
            "condition": "chlamydia conjunctivitis", "severity": "mild", "tier": "alternative",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7 (inclusion conjunctivitis); 21 (trachoma)",
            "notes": ["Alternative for chlamydia conjunctivitis."],
            "contraindications": ["pregnancy", "children <8 years"],
            "pathogen_context": ["chlamydia trachomatis"],
            "page": 5, "source_chapter": "3.4",
        },

        # ----- GONOCOCCAL CONJUNCTIVITIS (page 6) -----
        {
            "condition": "gonococcal conjunctivitis", "severity": "severe", "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 1, "dose_unit": "g",
            "route": "IV/IM", "frequency": "single dose",
            "duration_days": "1",
            "notes": [
                "First-line for gonococcal conjunctivitis.",
                "Add azithromycin 1g PO single dose if Chlamydia suspected.",
                "Treat mother and sexual partner for ophthalmia neonatorum.",
                "Consider chemoprophylaxis if N. meningitidis suspected.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["neisseria gonorrhoeae"],
            "page": 6, "source_chapter": "3.4",
        },
        {
            "condition": "gonococcal conjunctivitis", "severity": "severe",
            "tier": "penicillin_allergy",
            "drug": "doxycycline",
            "dose_value": 100, "dose_unit": "mg",
            "route": "PO", "frequency": "q12H",
            "duration_days": "7",
            "notes": ["For penicillin-allergic patient with gonococcal conjunctivitis."],
            "contraindications": ["pregnancy"],
            "pathogen_context": ["neisseria gonorrhoeae"],
            "page": 6, "source_chapter": "3.4",
        },

        # ----- KERATITIS - DENDRITIC ULCER (HSV) (page 6) -----
        {
            "condition": "HSV keratitis", "severity": "moderate", "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 800, "dose_unit": "mg",
            "route": "PO", "frequency": "five times daily",
            "duration_days": "7-10",
            "notes": [
                "First-line systemic for HSV dendritic ulcer keratitis.",
                "Combine with chloramphenicol 1% eye ointment q8H + "
                "aciclovir 3% eye ointment.",
                "Consider long-term aciclovir for recurrent HSV keratitis.",
                "Aciclovir 3% eye ointment is NOT available in UMMC.",
            ],
            "contraindications": [],
            "pathogen_context": ["HSV"],
            "page": 6, "source_chapter": "3.4",
        },

        # ----- BACTERIAL CORNEAL ULCER (page 7) -----
        {
            "condition": "bacterial corneal ulcer", "severity": "severe", "tier": "preferred",
            "drug": "gentamicin",
            "dose_value": 1.4, "dose_unit": "%",
            "dose_qualifier": "1.4% eye drops (fortified)",
            "route": "eye drop", "frequency": "intensive (q15-60min initially)",
            "duration_days": "as per response",
            "notes": [
                "First-line for bacterial corneal ulcer.",
                "Combine with vancomycin 5% eye drops OR moxifloxacin 0.5% "
                "eye drops.",
                "Intensive dosing typically: q15-30min for first hours, "
                "then taper.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococcus aureus", "streptococcus pneumoniae",
                                  "pseudomonas aeruginosa", "enterobacteriaceae"],
            "page": 7, "source_chapter": "3.4",
        },
        {
            "condition": "bacterial corneal ulcer", "severity": "severe",
            "tier": "gram_positive_cover_addon",
            "drug": "vancomycin",
            "dose_value": 5, "dose_unit": "%",
            "dose_qualifier": "5% eye drops (fortified)",
            "route": "eye drop", "frequency": "intensive (q15-60min initially)",
            "duration_days": "as per response",
            "notes": [
                "Gram-positive cover (MRSA) paired with gentamicin for "
                "bacterial corneal ulcer.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA", "gram-positive"],
            "page": 7, "source_chapter": "3.4",
        },
        {
            "condition": "bacterial corneal ulcer", "severity": "severe", "tier": "alternative",
            "drug": "moxifloxacin",
            "dose_value": 0.5, "dose_unit": "%",
            "dose_qualifier": "0.5% eye drops",
            "route": "eye drop", "frequency": "intensive (q15-60min initially)",
            "duration_days": "as per response",
            "notes": ["Alternative monotherapy for bacterial corneal ulcer."],
            "contraindications": [],
            "pathogen_context": ["broad coverage"],
            "page": 7, "source_chapter": "3.4",
        },

        # ----- ACUTE RETINAL NECROSIS (VZV / HSV) (page 7-8) -----
        {
            "condition": "acute retinal necrosis", "severity": "severe", "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10 (IV), then PO 800 mg five times daily for 6 weeks",
            "notes": [
                "First-line for acute retinal necrosis (VZV/HSV).",
                "Followed by Aciclovir 800 mg PO five times daily for 6 weeks.",
                "Secondary prophylaxis: Aciclovir 400 mg PO q12H for 6-12 months.",
                "May add intravitreal antimicrobial (foscarnet 2.4 mg or "
                "ganciclovir 2 mg in 0.1 mL).",
            ],
            "contraindications": [],
            "pathogen_context": ["VZV", "HSV"],
            "page": 7, "source_chapter": "3.4",
        },
        {
            "condition": "acute retinal necrosis", "severity": "severe", "tier": "alternative",
            "drug": "valaciclovir",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": ["Oral alternative for acute retinal necrosis."],
            "contraindications": [],
            "pathogen_context": ["VZV", "HSV"],
            "page": 7, "source_chapter": "3.4",
        },

        # ----- PROGRESSIVE OUTER RETINAL NECROSIS (PORN) (page 8) -----
        {
            "condition": "progressive outer retinal necrosis", "severity": "severe",
            "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "14-21 IV, then PO 800 mg five times daily for 6 weeks",
            "notes": [
                "First-line for PORN.",
                "Consider Foscarnet IV if not responding to aciclovir.",
                "Total duration: 6 weeks.",
                "Secondary prophylaxis: Aciclovir 400 mg PO q12H for 6-12 months.",
            ],
            "contraindications": [],
            "pathogen_context": ["VZV"],
            "page": 8, "source_chapter": "3.4",
        },

        # ----- ENDOPHTHALMITIS - EMPIRICAL (ENDOGENOUS) (page 9-10) -----
        {
            "condition": "endophthalmitis", "severity": "severe",
            "tier": "topical_preferred",
            "drug": "vancomycin",
            "dose_value": 5, "dose_unit": "%",
            "dose_qualifier": "5% eye drops (fortified)",
            "route": "eye drop", "frequency": "intensive (q1H initially)",
            "duration_days": "4-6 weeks",
            "notes": [
                "Topical gram-positive cover for endogenous endophthalmitis.",
                "Combine with moxifloxacin 0.5% eye drops.",
                "Take blood and vitreous cultures before therapy.",
            ],
            "contraindications": [],
            "pathogen_context": ["staphylococci", "streptococci"],
            "page": 10, "source_chapter": "3.4",
        },
        {
            "condition": "endophthalmitis", "severity": "severe",
            "tier": "systemic_preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "4-6 weeks",
            "notes": [
                "First-line systemic for empirical endophthalmitis.",
                "Combine with vancomycin systemic.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["gram-negative bacilli", "streptococci"],
            "page": 10, "source_chapter": "3.4",
        },
        {
            "condition": "endophthalmitis", "severity": "severe",
            "tier": "systemic_preferred_addon",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "4-6 weeks",
            "notes": ["Systemic gram-positive cover paired with ceftriaxone."],
            "contraindications": [],
            "pathogen_context": ["MRSA", "staphylococci"],
            "page": 10, "source_chapter": "3.4",
        },

        # ----- ENDOPHTHALMITIS - FUNGAL (page 10-11) -----
        {
            "condition": "fungal endophthalmitis", "severity": "severe",
            "tier": "topical_preferred",
            "drug": "amphotericin B",
            "dose_value": 0.15, "dose_unit": "%",
            "dose_qualifier": "0.15% eye drops",
            "route": "eye drop", "frequency": "intensive",
            "duration_days": "4-6 weeks",
            "notes": [
                "First-line topical for suspected fungal endophthalmitis.",
                "Intravitreal: Amphotericin B 5 mcg in 0.1 mL.",
                "Add Amphotericin B Deoxycholate 1-1.5 mg/kg IV q24H if "
                "systemic infection suspected.",
            ],
            "contraindications": [],
            "pathogen_context": ["candida", "fungal"],
            "page": 10, "source_chapter": "3.4",
        },
        {
            "condition": "fungal endophthalmitis", "severity": "severe",
            "tier": "topical_alternative",
            "drug": "voriconazole",
            "dose_value": 1, "dose_unit": "%",
            "dose_qualifier": "1% eye drops",
            "route": "eye drop", "frequency": "intensive",
            "duration_days": "4-6 weeks",
            "notes": [
                "Alternative topical for fungal endophthalmitis.",
                "Intravitreal Voriconazole 0.1 mg in 0.1 mL.",
            ],
            "contraindications": [],
            "pathogen_context": ["aspergillus", "candida"],
            "page": 11, "source_chapter": "3.4",
        },

        # ----- ENDOPHTHALMITIS - EXOGENOUS (POST-OP / POST-INJECTION) (page 11-12) -----
        {
            "condition": "exogenous endophthalmitis", "severity": "severe",
            "tier": "intravitreal_preferred",
            "drug": "vancomycin",
            "dose_value": 1, "dose_unit": "mg",
            "dose_qualifier": "1 mg in 0.1 mL intravitreal",
            "route": "intravitreal", "frequency": "single dose, may repeat",
            "duration_days": "based on clinical response",
            "notes": [
                "First-line intravitreal for post-operative / post-injection / "
                "post-traumatic endophthalmitis.",
                "Combine with intravitreal ceftazidime 2-2.25 mg in 0.1 mL.",
                "Vitrectomy and lens removal in chronic post-ocular surgery.",
            ],
            "contraindications": [],
            "pathogen_context": ["coagulase-negative staphylococci",
                                  "staphylococcus aureus"],
            "page": 11, "source_chapter": "3.4",
        },
        {
            "condition": "exogenous endophthalmitis", "severity": "severe",
            "tier": "intravitreal_preferred_addon",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "mg",
            "dose_qualifier": "2-2.25 mg in 0.1 mL intravitreal",
            "route": "intravitreal", "frequency": "single dose, may repeat",
            "duration_days": "based on clinical response",
            "notes": ["Intravitreal gram-negative cover paired with vancomycin."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "gram-negatives"],
            "page": 12, "source_chapter": "3.4",
        },
        {
            "condition": "exogenous endophthalmitis", "severity": "severe",
            "tier": "systemic_preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-6 weeks",
            "notes": [
                "Systemic gram-negative cover for exogenous endophthalmitis.",
                "Combine with systemic vancomycin.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 12, "source_chapter": "3.4",
        },

        # ----- OPHTHALMIC ZOSTER (page 12) -----
        {
            "condition": "ophthalmic zoster", "severity": "moderate", "tier": "preferred",
            "drug": "aciclovir",
            "dose_value": 800, "dose_unit": "mg",
            "route": "PO", "frequency": "five times daily",
            "duration_days": "7",
            "notes": [
                "First-line oral for ophthalmic zoster (herpes zoster ophthalmicus).",
                "Initiate within 72 hours of rash onset.",
            ],
            "contraindications": [],
            "pathogen_context": ["VZV"],
            "page": 12, "source_chapter": "3.4",
        },
        {
            "condition": "ophthalmic zoster", "severity": "severe", "tier": "alternative",
            "drug": "aciclovir",
            "dose_value": 10, "dose_unit": "mg/kg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": ["IV alternative for severe ophthalmic zoster."],
            "contraindications": [],
            "pathogen_context": ["VZV"],
            "page": 12, "source_chapter": "3.4",
        },
    ],

    # =====================================================================
    # CHAPTER 3.15 - SURGICAL RELATED INFECTIONS
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-9
    # Covers: hepato-pancreato-biliary (pancreatitis, biliary tract),
    # GI (diverticulitis, GI perforation, appendicitis, rectal abscess),
    # trauma (abdominal trauma), vascular (mycotic aneurysm, vascular
    # prosthesis, ischaemic limb ulcers), soft tissue (breast abscess/
    # mastitis)
    # =====================================================================
    "surgical_related": [

        # ----- ACUTE PANCREATITIS - MILD/MODERATE (page 1) -----
        # NEGATIVE INDICATION
        {
            "condition": "acute pancreatitis", "severity": "mild",
            "tier": "supportive_only",
            "drug": "supportive care",
            "dose_value": 0, "dose_unit": "",
            "route": "", "frequency": "",
            "duration_days": "",
            "notes": [
                "Mild-moderate (including alcoholic) pancreatitis: "
                "antibiotics NOT required.",
                "Severe non-necrotizing pancreatitis: antibiotics NOT required.",
                "Severe non-infected necrotizing pancreatitis: prophylactic "
                "antibiotics NO LONGER recommended (no benefit, possible harm).",
                "Surgical debridement if clinically indicated.",
            ],
            "contraindications": [],
            "pathogen_context": [],
            "page": 1, "source_chapter": "3.15",
        },

        # ----- ACUTE PANCREATITIS - SEVERE INFECTED NECROTIZING (page 2) -----
        {
            "condition": "infected pancreatitis", "severity": "severe", "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "based on organ involvement and culture",
            "notes": [
                "First-line for severe infected pancreatitis (infected "
                "pseudocyst, pancreatic abscess).",
                "Obtain tissue/infected drain fluid cultures.",
                "May consider meropenem if ESBL suspected.",
                "Stop if culture negative and no source identified.",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "enterococci",
                                  "staphylococcus aureus", "anaerobes"],
            "page": 2, "source_chapter": "3.15",
        },
        {
            "condition": "infected pancreatitis", "severity": "severe", "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "based on organ involvement",
            "notes": ["Alternative paired with metronidazole 500 mg IV q8H."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["broad gram-negative"],
            "page": 2, "source_chapter": "3.15",
        },
        {
            "condition": "infected pancreatitis", "severity": "severe",
            "tier": "anaerobic_coverage_addon",
            "drug": "metronidazole",
            "dose_value": 500, "dose_unit": "mg",
            "route": "IV", "frequency": "q8H",
            "duration_days": "as per total duration",
            "notes": ["Anaerobic cover paired with cefepime for infected pancreatitis."],
            "contraindications": [],
            "pathogen_context": ["anaerobes"],
            "page": 2, "source_chapter": "3.15",
        },

        # ----- CHOLECYSTITIS / CHOLANGITIS - COMMUNITY (page 3) -----
        {
            "condition": "cholecystitis", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "4-7",
            "notes": [
                "First-line for cholecystitis, cholangitis, biliary sepsis "
                "from common duct obstruction, gallbladder empyema.",
                "Community-acquired.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "bacteroides"],
            "page": 3, "source_chapter": "3.15",
        },
        {
            "condition": "cholecystitis", "severity": "moderate", "tier": "alternative",
            "drug": "ampicillin-sulbactam",
            "dose_value": 1.5, "dose_unit": "g",
            "dose_qualifier": "1.5-3 g range",
            "dose_min_mg": 1500, "dose_max_mg": 3000,
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "4-7",
            "notes": ["Alternative for community-acquired cholecystitis/cholangitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 3, "source_chapter": "3.15",
        },
        {
            "condition": "cholecystitis", "severity": "moderate", "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-7",
            "notes": ["Alternative for community-acquired cholecystitis. Combine with metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 3, "source_chapter": "3.15",
        },

        # ----- CHOLECYSTITIS / CHOLANGITIS - HOSPITAL-ACQUIRED (page 3) -----
        {
            "condition": "cholecystitis", "severity": "severe",
            "tier": "hospital_acquired_preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "4-7",
            "notes": ["First-line for hospital-acquired cholecystitis/cholangitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "anaerobes"],
            "page": 3, "source_chapter": "3.15",
        },
        {
            "condition": "cholecystitis", "severity": "severe",
            "tier": "hospital_acquired_alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-7",
            "notes": ["Alternative for hospital-acquired cholangitis. Combine with metronidazole."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas", "broad gram-negative"],
            "page": 3, "source_chapter": "3.15",
        },

        # ----- DIVERTICULITIS - COMMUNITY-ONSET (page 4) -----
        {
            "condition": "diverticulitis", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": [
                "First-line for community-onset diverticulitis, no prior abx.",
                "Antibiotics indicated when: fever, elevated WBC, failed "
                "conservative management, peritonitis, age >70, "
                "immunosuppression, significant comorbidity.",
                "De-escalate to oral when clinically improved.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "anaerobes"],
            "page": 4, "source_chapter": "3.15",
        },
        {
            "condition": "diverticulitis", "severity": "moderate", "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7-10",
            "notes": ["Alternative for community-onset diverticulitis. Combine with metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 4, "source_chapter": "3.15",
        },
        {
            "condition": "diverticulitis", "severity": "severe",
            "tier": "hospital_onset_severe",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "7-10",
            "notes": ["For severe hospital-onset diverticulitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative"],
            "page": 4, "source_chapter": "3.15",
        },

        # ----- GI TRACT PERFORATION - COMMUNITY (page 5) -----
        {
            "condition": "GI perforation", "severity": "severe", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "4-7 (with adequate source control)",
            "notes": [
                "First-line for community-acquired GI tract perforation.",
                "Adequate source control required.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "anaerobes"],
            "page": 5, "source_chapter": "3.15",
        },
        {
            "condition": "GI perforation", "severity": "critical",
            "tier": "hospital_onset_severe",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "4-7",
            "notes": ["For severe hospital-onset GI tract perforation."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad gram-negative", "anaerobes"],
            "page": 5, "source_chapter": "3.15",
        },

        # ----- APPENDICITIS (page 6) -----
        {
            "condition": "appendicitis", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "discontinue within 24h if no perforation/abscess/peritonitis",
            "notes": [
                "First-line for simple/non-perforated appendicitis, "
                "perforated appendix, perforated viscus, appendicular mass.",
                "Immediate appendectomy within 12 hours of decision unless "
                "septic or free/generalised perforation (emergent surgery).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "enterococci", "bacteroides"],
            "page": 6, "source_chapter": "3.15",
        },
        {
            "condition": "appendicitis", "severity": "moderate", "tier": "alternative",
            "drug": "cefuroxime",
            "dose_value": 1.5, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "discontinue within 24h if no complications",
            "notes": ["Alternative for appendicitis. Combine with metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae"],
            "page": 6, "source_chapter": "3.15",
        },

        # ----- RECTAL ABSCESS (page 6) -----
        {
            "condition": "rectal abscess", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-7 (with drainage and source control)",
            "notes": [
                "First-line for rectal abscess.",
                "Drainage required.",
                "Routine antibiotics NOT recommended in otherwise healthy "
                "patients.",
                "Need to rule out sexually transmitted infections.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["enterobacteriaceae", "anaerobes"],
            "page": 6, "source_chapter": "3.15",
        },
        {
            "condition": "rectal abscess", "severity": "moderate", "tier": "alternative",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "4-7",
            "notes": ["Alternative for rectal abscess. Combine with metronidazole."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococci"],
            "page": 6, "source_chapter": "3.15",
        },

        # ----- ABDOMINAL TRAUMA (page 7) -----
        {
            "condition": "abdominal trauma", "severity": "moderate", "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "4-7 (with adequate source control)",
            "notes": [
                "First-line for abdominal trauma, stab wound, suspected "
                "bowel or solid organ injury.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["gram-negative aerobes", "anaerobes"],
            "page": 7, "source_chapter": "3.15",
        },
        {
            "condition": "abdominal trauma", "severity": "moderate", "tier": "alternative",
            "drug": "ampicillin-sulbactam",
            "dose_value": 1.5, "dose_unit": "g",
            "dose_qualifier": "1.5-3 g range",
            "dose_min_mg": 1500, "dose_max_mg": 3000,
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "4-7",
            "notes": ["Alternative for abdominal trauma."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["gram-negative", "anaerobes"],
            "page": 7, "source_chapter": "3.15",
        },

        # ----- MYCOTIC ANEURYSM (page 7) -----
        {
            "condition": "mycotic aneurysm", "severity": "severe", "tier": "preferred",
            "drug": "ceftriaxone",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q24H",
            "duration_days": "minimum 6 weeks (IV then oral)",
            "notes": [
                "First-line for mycotic aneurysm.",
                "Add Vancomycin 15 mg/kg q8-12H if MRSA/CoNS prosthesis "
                "infection suspected.",
                "If Burkholderia pseudomallei suspected: refer Chapter 3.14.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["staphylococcus aureus", "salmonella"],
            "page": 7, "source_chapter": "3.15",
        },
        {
            "condition": "mycotic aneurysm", "severity": "severe", "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 15, "dose_unit": "mg/kg",
            "dose_qualifier": "max 1 g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "minimum 6 weeks",
            "notes": ["MRSA cover for mycotic aneurysm with prosthesis."],
            "contraindications": [],
            "pathogen_context": ["MRSA", "MRSE"],
            "page": 7, "source_chapter": "3.15",
        },

        # ----- VASCULAR PROSTHESIS INFECTION (page 7) -----
        {
            "condition": "vascular prosthesis infection", "severity": "severe",
            "tier": "preferred",
            "drug": "piperacillin-tazobactam",
            "dose_value": 4.5, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "minimum 6 weeks",
            "notes": ["First-line for vascular prosthesis infection."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["broad coverage"],
            "page": 7, "source_chapter": "3.15",
        },

        # ----- ISCHAEMIC LIMB ULCERS WITH INFECTION (page 7) -----
        {
            "condition": "ischaemic limb ulcer", "severity": "moderate", "tier": "preferred",
            "drug": "ampicillin-sulbactam",
            "dose_value": 1.5, "dose_unit": "g",
            "dose_qualifier": "1.5-3 g range",
            "dose_min_mg": 1500, "dose_max_mg": 3000,
            "route": "IV", "frequency": "q6-8H",
            "duration_days": "7 (longer if bone infection / debridement needed)",
            "notes": [
                "First-line for infected ischaemic limb ulcers.",
                "May need longer duration if bone infection.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["mixed flora"],
            "page": 7, "source_chapter": "3.15",
        },
        {
            "condition": "ischaemic limb ulcer", "severity": "moderate", "tier": "alternative",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "7",
            "notes": ["Alternative for ischaemic limb ulcer infection."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["mixed flora"],
            "page": 7, "source_chapter": "3.15",
        },

        # ----- BREAST ABSCESS / MASTITIS - LOW RISK OUTPATIENT (page 8) -----
        {
            "condition": "mastitis", "severity": "mild", "tier": "outpatient_preferred",
            "drug": "cloxacillin",
            "dose_value": 1, "dose_unit": "g",
            "route": "PO", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": [
                "First-line outpatient for low/moderate risk breast abscess/"
                "mastitis.",
                "Drainage may be required for abscess.",
                "For lactating mastitis: send breastmilk for C&S if not "
                "responding after 48 hours.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 8, "source_chapter": "3.15",
        },
        {
            "condition": "mastitis", "severity": "mild", "tier": "outpatient_alternative",
            "drug": "cefalexin",
            "dose_value": 500, "dose_unit": "mg",
            "route": "PO", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": ["Outpatient alternative for low-risk mastitis."],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 8, "source_chapter": "3.15",
        },
        {
            "condition": "mastitis", "severity": "moderate", "tier": "inpatient_preferred",
            "drug": "cloxacillin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q6H",
            "duration_days": "10-14",
            "notes": ["IV inpatient therapy for moderate breast abscess/mastitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus"],
            "page": 8, "source_chapter": "3.15",
        },
        {
            "condition": "mastitis", "severity": "moderate", "tier": "high_risk_preferred",
            "drug": "co-amoxiclav",
            "dose_value": 625, "dose_unit": "mg",
            "route": "PO", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": [
                "First-line outpatient for HIGH risk (uncontrolled DM, "
                "immunosuppressive therapy, neutropenia).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "anaerobes"],
            "page": 8, "source_chapter": "3.15",
        },
        {
            "condition": "mastitis", "severity": "severe", "tier": "high_risk_inpatient",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "10-14",
            "notes": ["IV inpatient for high-risk mastitis."],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["broad coverage"],
            "page": 8, "source_chapter": "3.15",
        },
    ],

    # =====================================================================
    # CHAPTER 3.16 - SURGICAL SITE INFECTION
    # Source: UMMC Antimicrobial Guidelines 3rd Edition, pages 1-6
    # CDC definition: infection near surgical site within 30 days post-op
    # (90 days if implant). Classification: superficial incisional, deep
    # incisional, organ/space.
    # =====================================================================
    "surgical_site": [

        # ----- SSI - NO ANTIBIOTICS INDICATED (page 3) -----
        # NEGATIVE INDICATION when:
        # - WBC not raised
        # - Erythema < 5 cm
        # - No pus discharge
        # - No surrounding cellulitis/induration/necrosis
        {
            "condition": "surgical site infection", "severity": "mild",
            "tier": "no_antibiotics_indicated",
            "drug": "wound care only",
            "dose_value": 0, "dose_unit": "",
            "route": "", "frequency": "",
            "duration_days": "",
            "notes": [
                "Antibiotics NOT indicated when ALL of: WBC not raised, "
                "erythema <5 cm around incision, no pus discharge, no "
                "surrounding cellulitis/induration/necrosis.",
                "Change dressing and monitor wound and clinical condition.",
            ],
            "contraindications": [],
            "pathogen_context": [],
            "page": 3, "source_chapter": "3.16",
        },

        # ----- SSI - WOUND OF PERINEUM/GIT/FEMALE GENITAL TRACT (page 4) -----
        {
            "condition": "surgical site infection perineum", "severity": "moderate",
            "tier": "preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5 (mild); 5-7 (moderate-severe)",
            "notes": [
                "First-line for SSI involving wound of perineum, GIT, or "
                "female genital tract.",
                "Collect deep samples for C&S.",
                "Streamline based on intraoperative culture results.",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["gram-negative", "anaerobes", "enterococci"],
            "page": 4, "source_chapter": "3.16",
        },

        # ----- SSI - CLEAN WOUND WITHOUT IMPLANT (page 4) -----
        {
            "condition": "surgical site infection clean", "severity": "mild",
            "tier": "superficial_preferred",
            "drug": "cefazolin",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5",
            "notes": [
                "First-line for superficial SSI of clean wound on trunk, "
                "head, neck, extremities (without implant).",
            ],
            "contraindications": ["severe penicillin allergy"],
            "pathogen_context": ["staphylococcus aureus", "streptococcus"],
            "page": 4, "source_chapter": "3.16",
        },
        {
            "condition": "surgical site infection clean", "severity": "moderate",
            "tier": "deep_preferred",
            "drug": "co-amoxiclav",
            "dose_value": 1.2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "5-7",
            "notes": [
                "First-line for deep SSI of clean wound on trunk, head, "
                "neck, extremities (without implant).",
            ],
            "contraindications": ["penicillin allergy"],
            "pathogen_context": ["mixed flora"],
            "page": 4, "source_chapter": "3.16",
        },

        # ----- SSI - CLEAN WOUND WITH IMPLANT (page 5) -----
        {
            "condition": "surgical site infection implant", "severity": "severe",
            "tier": "preferred",
            "drug": "ceftazidime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "based on clinical response",
            "notes": [
                "First-line for SSI of clean wound on trunk, head, neck, "
                "extremities WITH implant.",
                "If MRSA risk: add Vancomycin (limit load to 2g, maintenance "
                "to 1g/dose to avoid toxicity; TDM at 3rd dose).",
                "If ESBL colonisation and severe sepsis/shock: consider Meropenem.",
            ],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa", "broad gram-negative"],
            "page": 5, "source_chapter": "3.16",
        },
        {
            "condition": "surgical site infection implant", "severity": "severe",
            "tier": "alternative",
            "drug": "cefepime",
            "dose_value": 2, "dose_unit": "g",
            "route": "IV", "frequency": "q8H",
            "duration_days": "based on clinical response",
            "notes": ["Alternative for SSI with implant."],
            "contraindications": ["severe cephalosporin allergy"],
            "pathogen_context": ["pseudomonas aeruginosa"],
            "page": 5, "source_chapter": "3.16",
        },
        {
            "condition": "surgical site infection implant", "severity": "severe",
            "tier": "mrsa_suspected",
            "drug": "vancomycin",
            "dose_value": 10, "dose_unit": "mg/kg",
            "dose_qualifier": "load 20 mg/kg max 2g, then 10-15 mg/kg max 1g per dose",
            "route": "IV", "frequency": "q8-12H",
            "duration_days": "based on clinical response",
            "notes": [
                "For SSI with implant when MRSA suspected.",
                "Limit loading dose to 2g, maintenance to 1g per dose to "
                "avoid toxicity.",
                "Monitor renal function and send TDM samples at 3rd dose.",
            ],
            "contraindications": [],
            "pathogen_context": ["MRSA"],
            "page": 5, "source_chapter": "3.16",
        },
    ],
}


# =========================================================================
# Helper: condition / severity / allergy normalisation
# =========================================================================

# Maps free-text diagnosis -> canonical condition key + suggested severity
# Add new diagnosis aliases here as you discover them in test cases.
_DIAGNOSIS_ALIASES = {
    # Cellulitis variants
    "cellulitis": ("cellulitis", None),
    "skin and soft tissue infection": ("cellulitis", None),
    "sti / skin and soft tissue infection": ("cellulitis", None),
    "cellulitis / skin and soft tissue infection": ("cellulitis", None),
    "mild cellulitis": ("cellulitis", "mild"),
    "moderate cellulitis": ("cellulitis", "moderate"),
    "severe cellulitis": ("cellulitis", "severe"),
    "non-purulent cellulitis": ("cellulitis", "moderate"),
    "purulent cellulitis": ("abscess", "mild"),
    # Erysipelas
    "erysipelas": ("erysipelas", None),
    # Impetigo
    "impetigo": ("impetigo", "mild"),
    "bullous impetigo": ("impetigo", "moderate"),
    # Necrotising fasciitis
    "necrotising fasciitis": ("necrotising fasciitis", "severe"),
    "necrotizing fasciitis": ("necrotising fasciitis", "severe"),
    # Bite wounds
    "bite wound": ("bite wound", "mild"),
    "animal bite": ("bite wound", "mild"),
    "human bite": ("bite wound", "mild"),
    "cat bite": ("bite wound", "mild"),
    "dog bite": ("bite wound", "mild"),
    # Diabetic foot
    "diabetic foot infection": ("diabetic foot infection", "mild"),
    "diabetic foot": ("diabetic foot infection", "mild"),
    # Abscess
    "abscess": ("abscess", "mild"),
    "cutaneous abscess": ("abscess", "mild"),
    "skin abscess": ("abscess", "mild"),
    # SSI
    "surgical site infection": ("surgical site infection", "mild"),
    "ssi": ("surgical site infection", "mild"),

    # =====================================================================
    # CHAPTER 3.8 - RESPIRATORY TRACT INFECTIONS
    # =====================================================================
    # Community-Acquired Pneumonia (CAP) - severity from CURB-65 wording
    "pneumonia": ("pneumonia", None),
    "community-acquired pneumonia": ("pneumonia", "mild"),
    "community acquired pneumonia": ("pneumonia", "mild"),
    "cap": ("pneumonia", "mild"),
    "community-acquired pneumonia (suspected bacterial)": ("pneumonia", "mild"),
    "low severity pneumonia": ("pneumonia", "mild"),
    "low severity cap": ("pneumonia", "mild"),
    "mild pneumonia": ("pneumonia", "mild"),
    "moderate severity pneumonia": ("pneumonia", "moderate"),
    "moderate severity cap": ("pneumonia", "moderate"),
    "moderate pneumonia": ("pneumonia", "moderate"),
    "inpatient pneumonia": ("pneumonia", "moderate"),
    "high severity pneumonia": ("pneumonia", "severe"),
    "high severity cap": ("pneumonia", "severe"),
    "severe pneumonia": ("pneumonia", "severe"),
    "severe cap": ("pneumonia", "severe"),
    "icu pneumonia": ("pneumonia", "severe"),

    # Hospital-Acquired / Ventilator-Associated Pneumonia
    "hospital-acquired pneumonia": ("hospital-acquired pneumonia", "moderate"),
    "hospital acquired pneumonia": ("hospital-acquired pneumonia", "moderate"),
    "hap": ("hospital-acquired pneumonia", "moderate"),
    "ventilator-associated pneumonia": ("hospital-acquired pneumonia", "moderate"),
    "ventilator associated pneumonia": ("hospital-acquired pneumonia", "moderate"),
    "vap": ("hospital-acquired pneumonia", "moderate"),
    "early onset hap": ("hospital-acquired pneumonia", "moderate"),
    "late onset hap": ("hospital-acquired pneumonia", "moderate"),
    "late onset severe hap": ("hospital-acquired pneumonia", "severe"),
    "nosocomial pneumonia": ("hospital-acquired pneumonia", "moderate"),

    # Aspiration pneumonia
    "aspiration pneumonia": ("aspiration pneumonia", "mild"),
    "aspiration": ("aspiration pneumonia", "mild"),

    # Lung abscess
    "lung abscess": ("lung abscess", "moderate"),
    "pulmonary abscess": ("lung abscess", "moderate"),
    "necrotising pneumonia": ("lung abscess", "moderate"),
    "necrotizing pneumonia": ("lung abscess", "moderate"),
    "lung empyema": ("lung abscess", "moderate"),
    "empyema": ("lung abscess", "moderate"),

    # Bronchiectasis exacerbation
    "bronchiectasis exacerbation": ("bronchiectasis exacerbation", "mild"),
    "exacerbation of bronchiectasis": ("bronchiectasis exacerbation", "mild"),
    "infective exacerbation of bronchiectasis": ("bronchiectasis exacerbation", "mild"),
    "mild bronchiectasis exacerbation": ("bronchiectasis exacerbation", "mild"),
    "moderate bronchiectasis exacerbation": ("bronchiectasis exacerbation", "mild"),
    "severe bronchiectasis exacerbation": ("bronchiectasis exacerbation", "severe"),

    # Bronchiectasis maintenance / eradication
    "bronchiectasis maintenance": ("bronchiectasis maintenance", "chronic"),
    "chronic suppressive treatment": ("bronchiectasis maintenance", "chronic"),
    "bronchiectasis eradication": ("bronchiectasis eradication", "severe"),
    "pseudomonas eradication": ("bronchiectasis eradication", "severe"),

    # AECOPD
    "aecopd": ("AECOPD", "mild"),
    "acute exacerbation of copd": ("AECOPD", "mild"),
    "exacerbation of copd": ("AECOPD", "mild"),
    "copd exacerbation": ("AECOPD", "mild"),
    "infective exacerbation of copd": ("AECOPD", "mild"),
    "outpatient aecopd": ("AECOPD", "mild"),
    "inpatient aecopd": ("AECOPD", "moderate"),

    # Viral pneumonia
    "viral pneumonia": ("viral pneumonia", "moderate"),
    "varicella zoster pneumonia": ("viral pneumonia", "moderate"),
    "vzv pneumonia": ("viral pneumonia", "moderate"),
    "chickenpox pneumonia": ("viral pneumonia", "moderate"),

    # Influenza
    "influenza": ("influenza", "moderate"),
    "flu": ("influenza", "moderate"),
    "influenza a": ("influenza", "moderate"),
    "influenza b": ("influenza", "moderate"),

    # =====================================================================
    # CHAPTER 3.9 - UROLOGY INFECTIONS
    # =====================================================================
    # Uncomplicated cystitis (lower UTI in non-pregnant women, normal tract)
    "cystitis": ("cystitis", "mild"),
    "acute cystitis": ("cystitis", "mild"),
    "uncomplicated cystitis": ("cystitis", "mild"),
    "uncomplicated uti": ("cystitis", "mild"),
    "lower urinary tract infection": ("cystitis", "mild"),
    "lower uti": ("cystitis", "mild"),
    "bladder infection": ("cystitis", "mild"),
    # Paediatric urology mirrors the adult condition keys; age-band
    # filtering at lookup time selects the right rows. These aliases just
    # make the paediatric phrasings normalise correctly.
    "paediatric cystitis": ("cystitis", "mild"),
    "pediatric cystitis": ("cystitis", "mild"),
    "infant cystitis": ("cystitis", "mild"),
    "neonatal cystitis": ("cystitis", "mild"),
    "neonatal uti": ("cystitis", "mild"),
    "paediatric uti": ("cystitis", "mild"),
    "pediatric uti": ("cystitis", "mild"),
    "asymptomatic bacteriuria": ("asymptomatic bacteriuria", None),
    "paediatric asymptomatic bacteriuria":
        ("asymptomatic bacteriuria", None),

    # Complicated cystitis (men, pregnant, immunocompromised, structural abn)
    "complicated cystitis": ("complicated cystitis", "moderate"),
    "complicated uti": ("complicated cystitis", "moderate"),
    "complicated lower uti": ("complicated cystitis", "moderate"),
    "uti in male": ("complicated cystitis", "moderate"),
    "uti in pregnancy": ("complicated cystitis", "moderate"),
    "cauti": ("complicated cystitis", "moderate"),
    "catheter associated uti": ("complicated cystitis", "moderate"),
    "catheter-associated uti": ("complicated cystitis", "moderate"),

    # Pyelonephritis - severity from systemic symptoms wording
    "pyelonephritis": ("pyelonephritis", "severe"),
    "acute pyelonephritis": ("pyelonephritis", "severe"),
    "upper urinary tract infection": ("pyelonephritis", "severe"),
    "upper uti": ("pyelonephritis", "severe"),
    "urosepsis": ("pyelonephritis", "severe"),
    "kidney infection": ("pyelonephritis", "severe"),
    "renal infection": ("pyelonephritis", "severe"),
    "mild pyelonephritis": ("pyelonephritis", "mild"),
    "outpatient pyelonephritis": ("pyelonephritis", "mild"),
    "severe pyelonephritis": ("pyelonephritis", "severe"),
    "urinary tract infection / pyelonephritis": ("pyelonephritis", "severe"),
    "uti / pyelonephritis": ("pyelonephritis", "severe"),
    "hospital-onset pyelonephritis": ("pyelonephritis", "severe"),
    "hospital onset pyelonephritis": ("pyelonephritis", "severe"),

    # Prostatitis
    "prostatitis": ("prostatitis", "moderate"),
    "acute prostatitis": ("prostatitis", "moderate"),
    "prostatic abscess": ("prostatitis", "severe"),
    "chronic prostatitis": ("chronic prostatitis", "chronic"),

    # Haemodialysis catheter infections
    "haemodialysis exit-site infection": ("haemodialysis catheter exit-site infection", "mild"),
    "hd exit-site infection": ("haemodialysis catheter exit-site infection", "mild"),
    "haemodialysis tunnel infection": ("haemodialysis catheter tunnel infection", "moderate"),
    "hd tunnel infection": ("haemodialysis catheter tunnel infection", "moderate"),

    # PD-related infections
    "pd exit-site infection": ("PD exit-site infection", "mild"),
    "peritoneal dialysis exit-site infection": ("PD exit-site infection", "mild"),

    # Dialysis CLABSI
    "clabsi": ("dialysis CLABSI", "moderate"),
    "hd clabsi": ("dialysis CLABSI", "moderate"),
    "central line associated bloodstream infection": ("dialysis CLABSI", "moderate"),
    "dialysis bloodstream infection": ("dialysis CLABSI", "moderate"),
    "catheter-related candidemia": ("dialysis CLABSI", "severe"),
    "catheter related candidemia": ("dialysis CLABSI", "severe"),

    # =====================================================================
    # CHAPTER 3.5 - ENT INFECTIONS
    # =====================================================================
    # Otitis externa
    "otitis externa": ("otitis externa", "mild"),
    "acute otitis externa": ("otitis externa", "mild"),
    "swimmer's ear": ("otitis externa", "mild"),
    "mild otitis externa": ("otitis externa", "mild"),
    "moderate otitis externa": ("otitis externa", "moderate"),
    "otitis externa perforated": ("otitis externa perforated TM", "moderate"),
    "otitis externa with perforated tm": ("otitis externa perforated TM", "moderate"),
    "perforated tympanic membrane otitis externa": ("otitis externa perforated TM", "moderate"),
    "malignant otitis externa": ("malignant otitis externa", "severe"),
    "necrotising otitis externa": ("malignant otitis externa", "severe"),
    "necrotizing otitis externa": ("malignant otitis externa", "severe"),

    # Otitis media
    "otitis media": ("otitis media", "moderate"),
    "acute otitis media": ("otitis media", "moderate"),
    "aom": ("otitis media", "moderate"),
    "bacterial otitis media": ("otitis media", "moderate"),
    "otitis media intracranial": ("otitis media intracranial extension", "severe"),
    "otitis media with intracranial extension": ("otitis media intracranial extension", "severe"),
    "csom": ("chronic suppurative otitis media", "moderate"),
    "chronic suppurative otitis media": ("chronic suppurative otitis media", "moderate"),

    # Mastoiditis
    "mastoiditis": ("acute mastoiditis", "moderate"),
    "acute mastoiditis": ("acute mastoiditis", "moderate"),
    "first episode mastoiditis": ("acute mastoiditis", "moderate"),
    "second episode mastoiditis": ("acute mastoiditis", "severe"),
    "recurrent mastoiditis": ("acute mastoiditis", "severe"),
    "chronic mastoiditis": ("chronic mastoiditis", "moderate"),

    # Pharyngitis / tonsillitis
    "pharyngitis": ("acute pharyngitis", "mild"),
    "acute pharyngitis": ("acute pharyngitis", "mild"),
    "tonsillitis": ("acute pharyngitis", "mild"),
    "acute tonsillitis": ("acute pharyngitis", "mild"),
    "strep throat": ("acute pharyngitis", "mild"),
    "streptococcal pharyngitis": ("acute pharyngitis", "mild"),
    "bacterial pharyngitis": ("acute pharyngitis", "mild"),
    "bacterial tonsillitis": ("acute pharyngitis", "mild"),

    # Diphtheria
    "diphtheria": ("diphtheria", "severe"),

    # Peritonsillar abscess
    "peritonsillar abscess": ("peritonsillar abscess", "severe"),
    "quinsy": ("peritonsillar abscess", "severe"),

    # Epiglottitis
    "epiglottitis": ("acute epiglottitis", "severe"),
    "acute epiglottitis": ("acute epiglottitis", "severe"),
    "supraglottitis": ("acute epiglottitis", "severe"),
    "acute supraglottitis": ("acute epiglottitis", "severe"),

    # Parapharyngeal abscess / deep neck infection
    "parapharyngeal abscess": ("parapharyngeal abscess", "severe"),
    "deep neck abscess": ("parapharyngeal abscess", "severe"),
    "deep neck infection": ("parapharyngeal abscess", "severe"),
    "retropharyngeal abscess": ("parapharyngeal abscess", "severe"),
    "ludwig's angina": ("parapharyngeal abscess", "severe"),
    "ludwigs angina": ("parapharyngeal abscess", "severe"),
    "lemierre's syndrome": ("parapharyngeal abscess", "severe"),

    # Rhinosinusitis
    "rhinosinusitis": ("acute rhinosinusitis", "mild"),
    "acute rhinosinusitis": ("acute rhinosinusitis", "mild"),
    "ars": ("acute rhinosinusitis", "mild"),
    "acute bacterial rhinosinusitis": ("acute rhinosinusitis", "mild"),
    "mild rhinosinusitis": ("acute rhinosinusitis", "mild"),
    "moderate rhinosinusitis": ("acute rhinosinusitis", "severe"),
    "severe rhinosinusitis": ("acute rhinosinusitis", "severe"),
    "sinusitis": ("acute rhinosinusitis", "mild"),
    "acute sinusitis": ("acute rhinosinusitis", "mild"),
    "bacterial sinusitis": ("acute rhinosinusitis", "mild"),

    # =====================================================================
    # CHAPTER 3.6 - FEBRILE NEUTROPENIA
    # =====================================================================
    "febrile neutropenia": ("febrile neutropenia", None),
    "neutropenic fever": ("febrile neutropenia", None),
    "neutropenic sepsis": ("febrile neutropenia", "critical"),
    "low-risk febrile neutropenia": ("febrile neutropenia", "mild"),
    "low risk febrile neutropenia": ("febrile neutropenia", "mild"),
    "outpatient febrile neutropenia": ("febrile neutropenia", "mild"),
    "high-risk febrile neutropenia": ("febrile neutropenia", "moderate"),
    "high risk febrile neutropenia": ("febrile neutropenia", "moderate"),
    "stable febrile neutropenia": ("febrile neutropenia", "moderate"),
    "persistent fever neutropenia": ("febrile neutropenia", "severe"),
    "new fever neutropenia": ("febrile neutropenia", "severe"),
    "unstable febrile neutropenia": ("febrile neutropenia", "critical"),
    "septic febrile neutropenia": ("febrile neutropenia", "critical"),

    # =====================================================================
    # CHAPTER 3.7 - GASTROINTESTINAL INFECTIONS
    # =====================================================================
    # Acute diarrhoea
    "acute diarrhoea": ("acute diarrhoea", "mild"),
    "acute diarrhea": ("acute diarrhoea", "mild"),
    "diarrhoea": ("acute diarrhoea", "mild"),
    "diarrhea": ("acute diarrhoea", "mild"),
    "infectious diarrhoea": ("acute diarrhoea", "mild"),
    "infectious diarrhea": ("acute diarrhoea", "mild"),
    "mild diarrhoea": ("acute diarrhoea", "mild"),
    "moderate diarrhoea": ("acute diarrhoea", "mild"),
    "gastroenteritis": ("acute diarrhoea", "mild"),
    "viral gastroenteritis": ("acute diarrhoea", "mild"),

    # Severe diarrhoea / dysentery
    "severe diarrhoea": ("severe diarrhoea", "severe"),
    "severe diarrhea": ("severe diarrhoea", "severe"),
    "bloody diarrhoea": ("severe diarrhoea", "severe"),
    "bloody diarrhea": ("severe diarrhoea", "severe"),
    "dysentery": ("severe diarrhoea", "severe"),
    "bacillary dysentery": ("severe diarrhoea", "severe"),
    "shigellosis": ("severe diarrhoea", "severe"),
    "salmonellosis": ("severe diarrhoea", "severe"),
    "campylobacter enteritis": ("severe diarrhoea", "severe"),
    "travellers diarrhoea": ("severe diarrhoea", "severe"),
    "traveler's diarrhea": ("severe diarrhoea", "severe"),
    "enteric fever": ("severe diarrhoea", "severe"),

    # Cholera
    "cholera": ("cholera", "severe"),
    "vibrio cholerae": ("cholera", "severe"),
    "v. cholerae": ("cholera", "severe"),

    # C. difficile infection
    "c. difficile infection": ("C. difficile infection", "mild"),
    "c diff": ("C. difficile infection", "mild"),
    "cdi": ("C. difficile infection", "mild"),
    "clostridium difficile": ("C. difficile infection", "mild"),
    "clostridioides difficile": ("C. difficile infection", "mild"),
    "pseudomembranous colitis": ("C. difficile infection", "moderate"),
    "non-severe cdi": ("C. difficile infection", "mild"),
    "non severe cdi": ("C. difficile infection", "mild"),
    "severe cdi": ("C. difficile infection", "severe"),
    "fulminant cdi": ("C. difficile infection", "critical"),
    "fulminant c. difficile": ("C. difficile infection", "critical"),
    "c. difficile colitis": ("C. difficile infection", "severe"),

    # Spontaneous bacterial peritonitis
    "spontaneous bacterial peritonitis": ("spontaneous bacterial peritonitis", "moderate"),
    "sbp": ("spontaneous bacterial peritonitis", "moderate"),
    "ascitic infection": ("spontaneous bacterial peritonitis", "moderate"),
    "community-acquired sbp": ("spontaneous bacterial peritonitis", "moderate"),
    "hospital-acquired sbp": ("spontaneous bacterial peritonitis", "severe"),
    "hospital acquired sbp": ("spontaneous bacterial peritonitis", "severe"),

    # Secondary bacterial peritonitis
    "secondary bacterial peritonitis": ("secondary bacterial peritonitis", "severe"),
    "secondary peritonitis": ("secondary bacterial peritonitis", "severe"),
    "post-instrumentation peritonitis": ("secondary bacterial peritonitis", "severe"),

    # Perforated peptic ulcer
    "perforated peptic ulcer": ("perforated peptic ulcer", "severe"),
    "perforated gastric ulcer": ("perforated peptic ulcer", "severe"),
    "perforated duodenal ulcer": ("perforated peptic ulcer", "severe"),
    "perforated du": ("perforated peptic ulcer", "severe"),
    "perforated gu": ("perforated peptic ulcer", "severe"),
    "pud perforation": ("perforated peptic ulcer", "severe"),
    "peptic perforation": ("perforated peptic ulcer", "severe"),

    # Pyogenic liver abscess
    "pyogenic liver abscess": ("pyogenic liver abscess", "moderate"),
    "liver abscess": ("pyogenic liver abscess", "moderate"),
    "hepatic abscess": ("pyogenic liver abscess", "moderate"),
    "bacterial liver abscess": ("pyogenic liver abscess", "moderate"),

    # Amoebic liver abscess
    "amoebic liver abscess": ("amoebic liver abscess", "moderate"),
    "amebic liver abscess": ("amoebic liver abscess", "moderate"),
    "amoebic abscess": ("amoebic liver abscess", "moderate"),
    "amebic abscess": ("amoebic liver abscess", "moderate"),
    "entamoeba histolytica infection": ("amoebic liver abscess", "moderate"),

    # H. pylori
    "helicobacter pylori infection": ("Helicobacter pylori infection", "moderate"),
    "h. pylori": ("Helicobacter pylori infection", "moderate"),
    "h pylori": ("Helicobacter pylori infection", "moderate"),
    "h. pylori infection": ("Helicobacter pylori infection", "moderate"),
    "helicobacter pylori": ("Helicobacter pylori infection", "moderate"),
    "h. pylori eradication": ("Helicobacter pylori infection", "moderate"),

    # =====================================================================
    # CHAPTER 3.1 - BONE AND JOINT INFECTIONS
    # =====================================================================
    # Septic arthritis
    "septic arthritis": ("septic arthritis", "moderate"),
    "acute septic arthritis": ("septic arthritis", "moderate"),
    "monoarticular septic arthritis": ("septic arthritis", "moderate"),
    "bacterial arthritis": ("septic arthritis", "moderate"),
    "septic arthritis with std risk": ("septic arthritis std risk", "moderate"),
    "gonococcal arthritis": ("septic arthritis std risk", "moderate"),

    # Osteomyelitis
    "osteomyelitis": ("osteomyelitis", "moderate"),
    "acute osteomyelitis": ("osteomyelitis", "moderate"),
    "chronic osteomyelitis": ("osteomyelitis", "moderate"),
    "bone infection": ("osteomyelitis", "moderate"),
    "vertebral osteomyelitis": ("vertebral osteomyelitis", "moderate"),
    "spinal osteomyelitis": ("vertebral osteomyelitis", "moderate"),
    "discitis": ("vertebral osteomyelitis", "moderate"),
    "spondylodiscitis": ("vertebral osteomyelitis", "moderate"),
    "epidural abscess": ("vertebral osteomyelitis", "severe"),

    # Paronychia / Felon
    "paronychia": ("paronychia", "mild"),
    "felon": ("paronychia", "mild"),
    "bacterial paronychia": ("paronychia", "mild"),

    # Flexor tenosynovitis
    "flexor tenosynovitis": ("flexor tenosynovitis", "moderate"),
    "tenosynovitis": ("flexor tenosynovitis", "moderate"),
    "kanavel's signs": ("flexor tenosynovitis", "moderate"),

    # Open fractures
    "open fracture": ("open fracture", "moderate"),
    "open fractures": ("open fracture", "moderate"),
    "gustilo type i": ("open fracture", "moderate"),
    "gustilo type ii": ("open fracture", "moderate"),
    "gustilo type iii": ("open fracture", "severe"),

    # Fracture fixation infection
    "fracture fixation infection": ("fracture fixation infection", "moderate"),
    "osteosynthesis associated infection": ("fracture fixation infection", "moderate"),
    "oai": ("fracture fixation infection", "moderate"),
    "acute fracture fixation infection": ("fracture fixation infection", "moderate"),
    "delayed fracture fixation infection": ("fracture fixation infection", "severe"),

    # Prosthetic joint infection
    "prosthetic joint infection": ("prosthetic joint infection", "severe"),
    "pji": ("prosthetic joint infection", "severe"),
    "infected joint prosthesis": ("prosthetic joint infection", "severe"),
    "infected hip prosthesis": ("prosthetic joint infection", "severe"),
    "infected knee prosthesis": ("prosthetic joint infection", "severe"),

    # =====================================================================
    # CHAPTER 3.2 - CARDIOVASCULAR SYSTEM INFECTIONS
    # =====================================================================
    # Infective endocarditis - empirical
    "infective endocarditis": ("infective endocarditis", "severe"),
    "endocarditis": ("infective endocarditis", "severe"),
    "ie": ("infective endocarditis", "severe"),
    "bacterial endocarditis": ("infective endocarditis", "severe"),
    "native valve endocarditis": ("infective endocarditis", "severe"),

    # IE - viridans streptococci
    "viridans streptococcal endocarditis": ("viridans streptococcal endocarditis", "severe"),
    "viridans strep endocarditis": ("viridans streptococcal endocarditis", "severe"),
    "streptococcal endocarditis": ("viridans streptococcal endocarditis", "severe"),

    # IE - enterococcus
    "enterococcal endocarditis": ("enterococcal endocarditis", "severe"),
    "enterococcus endocarditis": ("enterococcal endocarditis", "severe"),

    # IE - Staph aureus
    "staphylococcal endocarditis": ("staphylococcal endocarditis MSSA", "severe"),
    "staph aureus endocarditis": ("staphylococcal endocarditis MSSA", "severe"),
    "mssa endocarditis": ("staphylococcal endocarditis MSSA", "severe"),
    "mrsa endocarditis": ("staphylococcal endocarditis MRSA", "severe"),

    # IE - prosthetic valve
    "prosthetic valve endocarditis": ("prosthetic valve endocarditis", "severe"),
    "pve": ("prosthetic valve endocarditis", "severe"),

    # IE - HACEK
    "hacek endocarditis": ("HACEK endocarditis", "severe"),
    "culture negative endocarditis": ("HACEK endocarditis", "severe"),

    # IE - Candida
    "candida endocarditis": ("candida endocarditis", "severe"),
    "fungal endocarditis": ("candida endocarditis", "severe"),

    # Pericarditis
    "purulent pericarditis": ("purulent pericarditis", "severe"),
    "bacterial pericarditis": ("purulent pericarditis", "severe"),
    "septic pericarditis": ("purulent pericarditis", "severe"),

    # Streptococcal pharyngitis (cardiovascular chapter - rheumatic fever prevention)
    "streptococcal pharyngitis": ("streptococcal pharyngitis", "mild"),
    "gas pharyngitis": ("streptococcal pharyngitis", "mild"),
    "rheumatic fever prevention": ("streptococcal pharyngitis", "mild"),

    # =====================================================================
    # CHAPTER 3.3 - CENTRAL NERVOUS SYSTEM INFECTIONS
    # =====================================================================
    # Bacterial meningitis
    "bacterial meningitis": ("bacterial meningitis", "severe"),
    "meningitis": ("bacterial meningitis", "severe"),
    "acute bacterial meningitis": ("bacterial meningitis", "severe"),
    "community-acquired meningitis": ("bacterial meningitis", "severe"),
    "pneumococcal meningitis": ("bacterial meningitis", "severe"),
    "meningococcal meningitis": ("bacterial meningitis", "severe"),
    "listeria meningitis": ("bacterial meningitis", "severe"),

    # Penetrating head injury
    "penetrating head injury": ("penetrating head injury meningitis", "severe"),
    "penetrating head injury meningitis": ("penetrating head injury meningitis", "severe"),
    "post-traumatic meningitis": ("penetrating head injury meningitis", "severe"),

    # Basilar skull fracture
    "basilar skull fracture": ("basilar skull fracture", "mild"),
    "skull base fracture": ("basilar skull fracture", "mild"),

    # Ventriculitis
    "ventriculitis": ("ventriculitis", "severe"),
    "post-neurosurgical ventriculitis": ("ventriculitis", "severe"),
    "healthcare-associated ventriculitis": ("ventriculitis", "severe"),
    "shunt infection": ("ventriculitis", "severe"),
    "csf shunt infection": ("ventriculitis", "severe"),

    # Brain abscess
    "brain abscess": ("brain abscess", "severe"),
    "cerebral abscess": ("brain abscess", "severe"),
    "primary brain abscess": ("brain abscess", "severe"),
    "brain abscess from sinusitis": ("brain abscess", "severe"),
    "brain abscess otitis": ("brain abscess otitis", "severe"),
    "brain abscess from chronic otitis media": ("brain abscess otitis", "severe"),
    "post-surgical brain abscess": ("post-surgical brain abscess", "severe"),
    "subdural empyema": ("post-surgical brain abscess", "severe"),
    "cyanotic heart brain abscess": ("cyanotic heart brain abscess", "severe"),

    # Encephalitis
    "encephalitis": ("viral encephalitis", "severe"),
    "viral encephalitis": ("viral encephalitis", "severe"),
    "herpes encephalitis": ("viral encephalitis", "severe"),
    "hsv encephalitis": ("viral encephalitis", "severe"),
    "varicella encephalitis": ("viral encephalitis", "severe"),

    # =====================================================================
    # CHAPTER 3.4 - OPHTHALMOLOGY INFECTIONS
    # =====================================================================
    # Blepharitis
    "blepharitis": ("chronic blepharitis", "moderate"),
    "chronic blepharitis": ("chronic blepharitis", "moderate"),
    "rosacea blepharitis": ("chronic blepharitis", "moderate"),

    # Meibomian abscess / hordeolum
    "meibomian abscess": ("meibomian abscess", "moderate"),
    "internal hordeolum": ("meibomian abscess", "moderate"),
    "stye": ("stye", "mild"),
    "external hordeolum": ("stye", "mild"),

    # Orbital cellulitis
    "orbital cellulitis": ("orbital cellulitis", "severe"),
    "post-orbital cellulitis": ("orbital cellulitis", "severe"),
    "post orbital cellulitis": ("orbital cellulitis", "severe"),

    # Preseptal / periorbital cellulitis
    "preseptal cellulitis": ("preseptal cellulitis", "moderate"),
    "periorbital cellulitis": ("preseptal cellulitis", "moderate"),

    # Dacryocystitis
    "dacryocystitis": ("dacryocystitis", "mild"),
    "acute dacryocystitis": ("dacryocystitis", "severe"),
    "mild dacryocystitis": ("dacryocystitis", "mild"),
    "severe dacryocystitis": ("dacryocystitis", "severe"),

    # Bacterial conjunctivitis
    "bacterial conjunctivitis": ("bacterial conjunctivitis", "mild"),
    "conjunctivitis": ("bacterial conjunctivitis", "mild"),
    "acute bacterial conjunctivitis": ("bacterial conjunctivitis", "mild"),
    "mild conjunctivitis": ("bacterial conjunctivitis", "mild"),
    "severe conjunctivitis": ("bacterial conjunctivitis", "severe"),

    # Chlamydia conjunctivitis / trachoma
    "chlamydia conjunctivitis": ("chlamydia conjunctivitis", "mild"),
    "chlamydial conjunctivitis": ("chlamydia conjunctivitis", "mild"),
    "inclusion conjunctivitis": ("chlamydia conjunctivitis", "mild"),
    "trachoma": ("chlamydia conjunctivitis", "mild"),

    # Gonococcal conjunctivitis
    "gonococcal conjunctivitis": ("gonococcal conjunctivitis", "severe"),
    "ophthalmia neonatorum": ("gonococcal conjunctivitis", "severe"),

    # Keratitis
    "hsv keratitis": ("HSV keratitis", "moderate"),
    "herpes keratitis": ("HSV keratitis", "moderate"),
    "dendritic ulcer": ("HSV keratitis", "moderate"),
    "herpetic keratitis": ("HSV keratitis", "moderate"),

    # Bacterial corneal ulcer
    "bacterial corneal ulcer": ("bacterial corneal ulcer", "severe"),
    "corneal ulcer": ("bacterial corneal ulcer", "severe"),
    "bacterial keratitis": ("bacterial corneal ulcer", "severe"),

    # Acute retinal necrosis / PORN
    "acute retinal necrosis": ("acute retinal necrosis", "severe"),
    "arn": ("acute retinal necrosis", "severe"),
    "progressive outer retinal necrosis": ("progressive outer retinal necrosis", "severe"),
    "porn": ("progressive outer retinal necrosis", "severe"),

    # Endophthalmitis
    "endophthalmitis": ("endophthalmitis", "severe"),
    "endogenous endophthalmitis": ("endophthalmitis", "severe"),
    "haematogenous endophthalmitis": ("endophthalmitis", "severe"),
    "fungal endophthalmitis": ("fungal endophthalmitis", "severe"),
    "exogenous endophthalmitis": ("exogenous endophthalmitis", "severe"),
    "post-operative endophthalmitis": ("exogenous endophthalmitis", "severe"),
    "post operative endophthalmitis": ("exogenous endophthalmitis", "severe"),
    "post-intravitreal endophthalmitis": ("exogenous endophthalmitis", "severe"),
    "post-traumatic endophthalmitis": ("exogenous endophthalmitis", "severe"),

    # Ophthalmic zoster
    "ophthalmic zoster": ("ophthalmic zoster", "moderate"),
    "herpes zoster ophthalmicus": ("ophthalmic zoster", "moderate"),
    "hzo": ("ophthalmic zoster", "moderate"),

    # =====================================================================
    # CHAPTER 3.15 - SURGICAL RELATED INFECTIONS
    # =====================================================================
    # Acute pancreatitis
    "acute pancreatitis": ("acute pancreatitis", "mild"),
    "pancreatitis": ("acute pancreatitis", "mild"),
    "alcoholic pancreatitis": ("acute pancreatitis", "mild"),
    "non-necrotizing pancreatitis": ("acute pancreatitis", "mild"),
    "necrotizing pancreatitis": ("acute pancreatitis", "mild"),

    # Infected pancreatitis
    "infected pancreatitis": ("infected pancreatitis", "severe"),
    "infected pseudocyst": ("infected pancreatitis", "severe"),
    "pancreatic abscess": ("infected pancreatitis", "severe"),
    "infected necrotizing pancreatitis": ("infected pancreatitis", "severe"),

    # Biliary tract infection - cholecystitis / cholangitis
    "cholecystitis": ("cholecystitis", "moderate"),
    "cholangitis": ("cholecystitis", "moderate"),
    "acute cholecystitis": ("cholecystitis", "moderate"),
    "acute cholangitis": ("cholecystitis", "moderate"),
    "biliary sepsis": ("cholecystitis", "moderate"),
    "gallbladder empyema": ("cholecystitis", "moderate"),
    "common duct obstruction infection": ("cholecystitis", "moderate"),
    "hospital-acquired cholecystitis": ("cholecystitis", "severe"),
    "hospital-acquired cholangitis": ("cholecystitis", "severe"),

    # Diverticulitis
    "diverticulitis": ("diverticulitis", "moderate"),
    "acute diverticulitis": ("diverticulitis", "moderate"),
    "complicated diverticulitis": ("diverticulitis", "severe"),

    # GI perforation
    "gi perforation": ("GI perforation", "severe"),
    "gastrointestinal perforation": ("GI perforation", "severe"),
    "perforated viscus": ("GI perforation", "severe"),
    "bowel perforation": ("GI perforation", "severe"),
    "small bowel perforation": ("GI perforation", "severe"),
    "large bowel perforation": ("GI perforation", "severe"),
    "colonic perforation": ("GI perforation", "severe"),

    # Appendicitis
    "appendicitis": ("appendicitis", "moderate"),
    "acute appendicitis": ("appendicitis", "moderate"),
    "simple appendicitis": ("appendicitis", "moderate"),
    "non-perforated appendicitis": ("appendicitis", "moderate"),
    "perforated appendicitis": ("appendicitis", "moderate"),
    "perforated appendix": ("appendicitis", "moderate"),
    "appendicular mass": ("appendicitis", "moderate"),
    "appendicular abscess": ("appendicitis", "moderate"),

    # Rectal abscess
    "rectal abscess": ("rectal abscess", "moderate"),
    "perianal abscess": ("rectal abscess", "moderate"),
    "perirectal abscess": ("rectal abscess", "moderate"),
    "ischiorectal abscess": ("rectal abscess", "moderate"),

    # Abdominal trauma
    "abdominal trauma": ("abdominal trauma", "moderate"),
    "stab wound abdomen": ("abdominal trauma", "moderate"),
    "abdominal stab wound": ("abdominal trauma", "moderate"),
    "blunt abdominal trauma": ("abdominal trauma", "moderate"),
    "penetrating abdominal trauma": ("abdominal trauma", "moderate"),

    # Mycotic aneurysm
    "mycotic aneurysm": ("mycotic aneurysm", "severe"),
    "infected aneurysm": ("mycotic aneurysm", "severe"),

    # Vascular prosthesis infection
    "vascular prosthesis infection": ("vascular prosthesis infection", "severe"),
    "infected vascular graft": ("vascular prosthesis infection", "severe"),
    "vascular graft infection": ("vascular prosthesis infection", "severe"),

    # Ischaemic limb ulcer
    "ischaemic limb ulcer": ("ischaemic limb ulcer", "moderate"),
    "ischemic limb ulcer": ("ischaemic limb ulcer", "moderate"),
    "infected ischaemic ulcer": ("ischaemic limb ulcer", "moderate"),
    "arterial ulcer": ("ischaemic limb ulcer", "moderate"),

    # Mastitis / breast abscess
    "mastitis": ("mastitis", "mild"),
    "breast abscess": ("mastitis", "mild"),
    "lactational mastitis": ("mastitis", "mild"),
    "lactating mastitis": ("mastitis", "mild"),
    "puerperal mastitis": ("mastitis", "mild"),
    "non-lactational mastitis": ("mastitis", "mild"),

    # =====================================================================
    # CHAPTER 3.16 - SURGICAL SITE INFECTION
    # =====================================================================
    "surgical site infection": ("surgical site infection", "mild"),
    "ssi": ("surgical site infection", "mild"),
    "post-operative wound infection": ("surgical site infection", "mild"),
    "post operative wound infection": ("surgical site infection", "mild"),
    "post-op wound infection": ("surgical site infection", "mild"),
    "wound infection": ("surgical site infection", "mild"),
    "post-surgical wound infection": ("surgical site infection", "mild"),

    # SSI - perineum / GIT / female genital tract wound
    "ssi perineum": ("surgical site infection perineum", "moderate"),
    "post-c-section wound infection": ("surgical site infection perineum", "moderate"),
    "post-caesarean wound infection": ("surgical site infection perineum", "moderate"),
    "perineal wound infection": ("surgical site infection perineum", "moderate"),

    # SSI - clean wound without implant
    "ssi clean": ("surgical site infection clean", "mild"),
    "superficial ssi": ("surgical site infection clean", "mild"),
    "superficial wound infection": ("surgical site infection clean", "mild"),
    "deep ssi": ("surgical site infection clean", "moderate"),
    "deep wound infection": ("surgical site infection clean", "moderate"),

    # SSI - clean wound with implant
    "ssi with implant": ("surgical site infection implant", "severe"),
    "implant infection": ("surgical site infection implant", "severe"),
    "infected mesh": ("surgical site infection implant", "severe"),
    "infected vascular graft post-op": ("surgical site infection implant", "severe"),
    "organ space ssi": ("surgical site infection implant", "severe"),
}


def normalise_diagnosis(diagnosis: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Map free-text diagnosis to (condition_key, severity).
    Returns (None, None) if the diagnosis does not match any known condition
    in the structured database - caller should fall back to RAG.
    """
    if not diagnosis:
        return (None, None)
    d = diagnosis.lower().strip()
    # Exact match first
    if d in _DIAGNOSIS_ALIASES:
        return _DIAGNOSIS_ALIASES[d]
    # Substring match - try longer keys first so "severe cellulitis" wins
    # over "cellulitis".
    for key in sorted(_DIAGNOSIS_ALIASES.keys(), key=len, reverse=True):
        if key in d:
            cond, sev = _DIAGNOSIS_ALIASES[key]
            # If diagnosis text contains a severity word, that overrides
            for explicit_sev in ("mild", "moderate", "severe"):
                if explicit_sev in d:
                    sev = explicit_sev
                    break
            return (cond, sev)
    return (None, None)


# =========================================================================
# Public API
# =========================================================================

def _iter_all_regimens():
    """Yield every regimen row in every chapter."""
    for chapter, rows in GUIDELINE_REGIMENS.items():
        for row in rows:
            yield row


# =========================================================================
# Age-band filtering helper
# =========================================================================
# Adults are anyone >= 18 years (216 months) for SmartPharma's purposes;
# this matches PAEDIATRIC_AGE_THRESHOLD in config.py. Neonates are <2
# months (UMMC's paediatric urology grouping). Everyone else is paediatric.
# Rows with no age_group are treated as implicit "adult" so the original
# 543 adult rows do not need editing.

_ADULT_AGE_MONTHS = 216  # 18 years * 12 = 216 months
_NEONATAL_MAX_MONTHS = 2  # UMMC paediatric urology grouping


def _row_matches_age(row, patient_age_months):
    """
    Return True if `row` applies to a patient aged `patient_age_months`.

    Semantics:
      - patient_age_months=None -> match (no age filter applied)
      - age_min_months / age_max_months on row (if set) take precedence
        over the categorical age_group field
      - age_group="all" matches any patient
      - age_group="adult" requires age >= 216 months (18 years)
      - age_group="paediatric" requires 0 <= age < 216 months
      - age_group="neonatal" requires age < 2 months
      - Missing age_group is treated as implicit "adult"
    """
    if patient_age_months is None:
        return True

    age_min = row.get("age_min_months")
    age_max = row.get("age_max_months")
    if age_min is not None or age_max is not None:
        if age_min is not None and patient_age_months < age_min:
            return False
        if age_max is not None and patient_age_months >= age_max:
            return False
        return True

    age_group = (row.get("age_group") or "adult").lower()
    if age_group == "all":
        return True
    if age_group == "neonatal":
        return patient_age_months < _NEONATAL_MAX_MONTHS
    if age_group == "paediatric":
        return 0 <= patient_age_months < _ADULT_AGE_MONTHS
    if age_group == "adult":
        return patient_age_months >= _ADULT_AGE_MONTHS
    return True


def lookup_regimens(
    condition: str,
    severity: Optional[str] = None,
    tier: Optional[str] = None,
    age_months: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Return all regimen rows matching the filter. Empty list if none.

    severity matching is flexible: a row with no severity field is
    treated as "applies to all severities". This lets paediatric chapters
    (where UMMC does not always differentiate mild/moderate) work
    correctly when the diagnosis-normalisation step produces a severity.
    """
    if not condition:
        return []
    cond_lower = condition.lower().strip()
    sev_lower = severity.lower().strip() if severity else None
    tier_lower = tier.lower().strip() if tier else None

    out = []
    for row in _iter_all_regimens():
        if row["condition"].lower() != cond_lower:
            continue
        # Severity match: row severity=None means "any severity".
        if sev_lower:
            row_sev = (row.get("severity") or "").lower()
            if row_sev and row_sev != sev_lower:
                continue
        if tier_lower and (row.get("tier") or "").lower() != tier_lower:
            continue
        if not _row_matches_age(row, age_months):
            continue
        out.append(row)
    return out


def find_drug_in_regimen(
    drug: str,
    condition: str,
    severity: Optional[str] = None,
    age_months: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return the first regimen row where `drug` matches the row's drug field
    for the given condition (and severity / age, if provided). Returns
    None if the drug is not listed for this condition.
    """
    if not drug or not condition:
        return None
    drug_lower = drug.lower().strip()
    rows = lookup_regimens(condition, severity=severity, age_months=age_months)
    for r in rows:
        if r["drug"].lower() == drug_lower:
            return r
    return None


def is_drug_indicated(
    drug: str,
    condition: str,
    severity: Optional[str] = None,
    allergy: Optional[str] = None,
    age_months: Optional[float] = None,
) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Determine whether `drug` is indicated for `condition` based on the
    structured database, with optional severity / allergy / age filtering.

    Returns:
        (indicated, matching_rows, explanation_text)

    indicated:    True if drug appears in the regimen for this condition
                  (and matches the patient's age band if age_months
                  provided); False otherwise.
    matching_rows: list of the regimen rows where the drug matches
                  (empty if not indicated).
    explanation:  human-readable explanation suitable for the LLM prompt
                  or pharmacist display.
    """
    if not drug or not condition:
        return (False, [], "Insufficient information for structured lookup.")

    drug_lower = drug.lower().strip()
    all_rows_for_condition = lookup_regimens(
        condition, severity=severity, age_months=age_months,
    )

    if not all_rows_for_condition:
        return (False, [], "")  # caller should fall back to RAG

    matching = [r for r in all_rows_for_condition
                if r["drug"].lower() == drug_lower]

    if not matching:
        # Drug is NOT in the regimen for this condition+severity+age
        preferred = [r for r in all_rows_for_condition
                     if r.get("tier") == "preferred"]
        suggested = ", ".join(sorted({r["drug"] for r in preferred[:3]}))
        sev_text = f" ({severity})" if severity else ""
        age_text = ""
        if age_months is not None:
            if age_months < _NEONATAL_MAX_MONTHS:
                age_text = " for neonatal age band"
            elif age_months < _ADULT_AGE_MONTHS:
                age_text = " for paediatric age band"
            else:
                age_text = ""  # adult is the implicit default
        msg = (
            f"{drug} is NOT in the UMMC structured guideline for "
            f"{condition}{sev_text}{age_text}. "
            f"Preferred regimen{'s' if len(preferred) > 1 else ''}: "
            f"{suggested or 'see guideline'}."
        )
        return (False, [], msg)

    # Drug IS in the regimen. Check whether it conflicts with allergy.
    if allergy:
        allergy_lower = allergy.lower()
        for row in matching:
            row_contras = [c.lower() for c in row.get("contraindications", [])]
            for contra in row_contras:
                if allergy_lower in contra or any(
                    a in contra for a in allergy_lower.split()
                ):
                    sev_text = f" ({severity})" if severity else ""
                    msg = (
                        f"{drug} appears in the {condition}{sev_text} regimen "
                        f"under tier '{row.get('tier')}', BUT is contraindicated "
                        f"by patient allergy: {contra}. "
                        f"Consider penicillin-allergy alternatives in the "
                        f"same regimen."
                    )
                    return (False, matching, msg)

    # Drug indicated, no allergy conflict
    tiers = sorted({r.get("tier", "?") for r in matching})
    sev_text = f" ({severity})" if severity else ""
    msg = (
        f"{drug} is in the UMMC structured guideline for {condition}{sev_text} "
        f"under tier(s): {', '.join(tiers)}."
    )
    return (True, matching, msg)


def expected_doses_for(
    drug: str,
    condition: str,
    severity: Optional[str] = None,
    age_months: Optional[float] = None,
) -> List[Tuple[Any, str, str, str]]:
    """
    Return all expected dose patterns for a drug+condition combo.
    Each entry is (dose_value, dose_unit, route, frequency).
    Empty list if drug is not in the regimen for this condition.
    """
    rows = lookup_regimens(condition, severity=severity, age_months=age_months)
    if not rows:
        return []
    drug_lower = drug.lower().strip()
    out = []
    for r in rows:
        if r["drug"].lower() == drug_lower:
            out.append((
                r["dose_value"],
                r["dose_unit"],
                r.get("route", ""),
                r.get("frequency", ""),
            ))
    return out


def has_structured_data_for(condition: str) -> bool:
    """
    Quick check: does the structured DB contain ANY rows for this condition?
    Used as a gate before deciding to do structured-lookup vs RAG-fallback.
    """
    if not condition:
        return False
    cond_lower = condition.lower().strip()
    for row in _iter_all_regimens():
        if row["condition"].lower() == cond_lower:
            return True
    return False


def format_regimen_for_prompt(row: Dict[str, Any]) -> str:
    """
    Compact human-readable summary of a regimen row, suitable for injection
    into the LLM prompt or the pharmacist-facing report.
    """
    parts = [row["drug"]]
    parts.append(f"{row['dose_value']}{row['dose_unit']}")
    if row.get("dose_qualifier"):
        parts.append(row["dose_qualifier"])
    if row.get("route"):
        parts.append(row["route"])
    if row.get("frequency"):
        parts.append(row["frequency"])
    if row.get("duration_days"):
        parts.append(f"for {row['duration_days']} days")
    head = " ".join(str(p) for p in parts)
    tier = row.get("tier", "")
    page = row.get("page", "?")
    return f"  - [{tier}] {head}  (pg {page})"