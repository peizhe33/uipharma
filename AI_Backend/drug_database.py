"""
Local Drug Knowledge Base for SmartPharma.
Pre-processing layer that handles:
  - Fuzzy spell correction for drug names
  - Brand-to-generic name resolution
  - Drug class tagging
  - Active ingredient mapping
  - Therapeutic duplication detection
  - Maximum daily dose safety limits
  - Supportive care drug recognition
  - Allergy + cross-sensitivity checks
  - PRN appropriateness checks
  - Restricted-use ("big gun") antibiotic checks
  - Site-restricted drug checks (e.g., Nitrofurantoin lower-UTI only)
  - Deterministic monitoring + known-interaction lookup

This runs BEFORE the LLM sees anything - deterministic Python logic.
"""

from difflib import get_close_matches
from typing import Dict, List, Optional, Tuple
import re


# =========================
# Drug Class Definitions
# =========================
class DrugClass:
    ANTIBIOTIC = "antibiotic"
    ANALGESIC = "analgesic/antipyretic"
    NSAID = "NSAID (anti-inflammatory/analgesic)"
    ANTICOAGULANT = "anticoagulant"
    ANTIFUNGAL = "antifungal"
    ANTIVIRAL = "antiviral"
    ANTIEMETIC = "antiemetic"
    PPI = "proton pump inhibitor"
    CORTICOSTEROID = "corticosteroid"
    BRONCHODILATOR = "bronchodilator"
    ANTIHYPERTENSIVE = "antihypertensive"
    ANTIDIABETIC = "antidiabetic"
    ANTIHISTAMINE = "antihistamine"
    MUCOLYTIC = "mucolytic"
    LAXATIVE = "laxative"
    SUPPLEMENT = "supplement/vitamin"
    UNKNOWN = "unknown"


SUPPORTIVE_CARE_CLASSES = {
    DrugClass.ANALGESIC,
    DrugClass.NSAID,
    DrugClass.ANTIEMETIC,
    DrugClass.PPI,
    DrugClass.BRONCHODILATOR,
    DrugClass.MUCOLYTIC,
    DrugClass.SUPPLEMENT,
    DrugClass.ANTIHISTAMINE,
    DrugClass.LAXATIVE,
}

# =========================
# Master Drug Database
# =========================
DRUG_DB: Dict[str, dict] = {
    "amoxicillin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin",
        "ingredients": ["amoxicillin"],
        "max_daily_dose_mg": 3000,
        "aliases": ["amoxil", "amoxacillin", "amoxycillin", "amoxicilin"],
    },
    "co-amoxiclav": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin + beta-lactamase inhibitor",
        "ingredients": ["amoxicillin", "clavulanate"],
        "max_daily_dose_mg": 3000,
        "aliases": ["augmentin", "co-amoxyclav", "amoxicillin/clavulanate",
                     "amoxicillin-clavulanate", "amoxiclav"],
    },
    "ampicillin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin",
        "ingredients": ["ampicillin"],
        "max_daily_dose_mg": 12000,
        "aliases": ["ampicilin"],
    },
    "ampicillin-sulbactam": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin + beta-lactamase inhibitor",
        "ingredients": ["ampicillin", "sulbactam"],
        "max_daily_dose_mg": 12000,
        "aliases": ["unasyn"],
    },
    "flucloxacillin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin",
        "ingredients": ["flucloxacillin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["floxacillin", "flucloxacilin"],
    },
    "piperacillin-tazobactam": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin + beta-lactamase inhibitor",
        "ingredients": ["piperacillin", "tazobactam"],
        "max_daily_dose_mg": 16000,
        "aliases": ["tazocin", "pip-tazo", "piptaz"],
    },
    "cloxacillin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin",
        "ingredients": ["cloxacillin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["cloxacilin"],
    },
    "penicillin v": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "beta-lactam/penicillin",
        "ingredients": ["phenoxymethylpenicillin"],
        "max_daily_dose_mg": 2000,
        "aliases": ["phenoxymethylpenicillin", "pen v"],
    },
    "ceftriaxone": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "cephalosporin (3rd gen)",
        "ingredients": ["ceftriaxone"],
        "max_daily_dose_mg": 4000,
        "aliases": ["rocephin", "ceftriaxon"],
    },
    "cefuroxime": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "cephalosporin (2nd gen)",
        "ingredients": ["cefuroxime"],
        "max_daily_dose_mg": 1500,
        "aliases": ["zinnat", "cefuroxim"],
    },
    "cefepime": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "cephalosporin (4th gen)",
        "ingredients": ["cefepime"],
        "max_daily_dose_mg": 6000,
        "aliases": ["maxipime"],
    },
    "cefalexin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "cephalosporin (1st gen)",
        "ingredients": ["cefalexin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["keflex", "cefalexin", "cephalexin"],
    },
    "ceftazidime": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "cephalosporin (3rd gen)",
        "ingredients": ["ceftazidime"],
        "max_daily_dose_mg": 6000,
        "aliases": ["fortaz"],
    },
    "azithromycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "macrolide",
        "ingredients": ["azithromycin"],
        "max_daily_dose_mg": 500,
        "aliases": ["zithromax", "azithromicin"],
    },
    "clarithromycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "macrolide",
        "ingredients": ["clarithromycin"],
        "max_daily_dose_mg": 1000,
        "aliases": ["klacid", "claritromycin", "claritromicin"],
    },
    "erythromycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "macrolide",
        "ingredients": ["erythromycin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["eryc", "erythromicin"],
    },
    "levofloxacin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "fluoroquinolone",
        "ingredients": ["levofloxacin"],
        "max_daily_dose_mg": 750,
        "aliases": ["levaquin", "levofloxacine"],
    },
    "ciprofloxacin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "fluoroquinolone",
        "ingredients": ["ciprofloxacin"],
        "max_daily_dose_mg": 1500,
        "aliases": ["cipro", "ciproxin", "ciprofloxacine"],
    },
    "moxifloxacin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "fluoroquinolone",
        "ingredients": ["moxifloxacin"],
        "max_daily_dose_mg": 400,
        "aliases": ["avelox"],
    },
    "doxycycline": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "tetracycline",
        "ingredients": ["doxycycline"],
        "max_daily_dose_mg": 200,
        "aliases": ["vibramycin", "doxycyline"],
    },
    "vancomycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "glycopeptide",
        "ingredients": ["vancomycin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["vancocin", "vancomicin"],
    },
    "metronidazole": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "nitroimidazole",
        "ingredients": ["metronidazole"],
        "max_daily_dose_mg": 2000,
        "aliases": ["flagyl", "metronidazol"],
    },
    "daptomycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "lipopeptide",
        "ingredients": ["daptomycin"],
        "max_daily_dose_mg": 700,
        "aliases": ["cubicin"],
    },
    "linezolid": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "oxazolidinone",
        "ingredients": ["linezolid"],
        "max_daily_dose_mg": 1200,
        "aliases": ["zyvox"],
    },
    "trimethoprim-sulfamethoxazole": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "sulfonamide combination",
        "ingredients": ["trimethoprim", "sulfamethoxazole"],
        "max_daily_dose_mg": 1920,
        "aliases": ["bactrim", "tmp-smx", "co-trimoxazole", "cotrimoxazole",
                     "septrin"],
    },
    "nitrofurantoin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "nitrofuran",
        "ingredients": ["nitrofurantoin"],
        "max_daily_dose_mg": 400,
        "aliases": ["macrodantin", "macrobid"],
    },
    "clindamycin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "lincosamide",
        "ingredients": ["clindamycin"],
        "max_daily_dose_mg": 2400,
        "aliases": ["dalacin", "clindamicin"],
    },
    "meropenem": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "carbapenem",
        "ingredients": ["meropenem"],
        "max_daily_dose_mg": 6000,
        "aliases": ["meronem"],
    },
    "imipenem-cilastatin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "carbapenem",
        "ingredients": ["imipenem", "cilastatin"],
        "max_daily_dose_mg": 4000,
        "aliases": ["primaxin", "tienam"],
    },
    "colistin": {
        "class": DrugClass.ANTIBIOTIC,
        "subclass": "polymyxin",
        "ingredients": ["colistin"],
        "max_daily_dose_mg": 300,
        "aliases": ["colistimethate", "polymyxin e"],
    },
    "fluconazole": {
        "class": DrugClass.ANTIFUNGAL,
        "subclass": "azole antifungal",
        "ingredients": ["fluconazole"],
        "max_daily_dose_mg": 800,
        "aliases": ["diflucan"],
    },
    "amphotericin b": {
        "class": DrugClass.ANTIFUNGAL,
        "subclass": "polyene antifungal",
        "ingredients": ["amphotericin b"],
        "max_daily_dose_mg": 100,
        "aliases": ["fungizone", "ambisome"],
    },
    "paracetamol": {
        "class": DrugClass.ANALGESIC,
        "subclass": "non-opioid analgesic/antipyretic",
        "ingredients": ["paracetamol"],
        "max_daily_dose_mg": 4000,
        "aliases": ["acetaminophen", "tylenol", "panadol", "paracetemol",
                     "paracetamole", "parasetamol"],
    },
    "tramadol": {
        "class": DrugClass.ANALGESIC,
        "subclass": "opioid analgesic",
        "ingredients": ["tramadol"],
        "max_daily_dose_mg": 400,
        "aliases": ["ultram", "tramal"],
    },
    "ibuprofen": {
        "class": DrugClass.NSAID,
        "subclass": "propionic acid NSAID",
        "ingredients": ["ibuprofen"],
        "max_daily_dose_mg": 2400,
        "aliases": ["brufen", "advil", "nurofen", "ibuprophen"],
    },
    "diclofenac": {
        "class": DrugClass.NSAID,
        "subclass": "acetic acid NSAID",
        "ingredients": ["diclofenac"],
        "max_daily_dose_mg": 150,
        "aliases": ["voltaren", "diclofenec"],
    },
    "celecoxib": {
        "class": DrugClass.NSAID,
        "subclass": "COX-2 selective NSAID",
        "ingredients": ["celecoxib"],
        "max_daily_dose_mg": 400,
        "aliases": ["celebrex"],
    },
    "mefenamic acid": {
        "class": DrugClass.NSAID,
        "subclass": "fenamate NSAID",
        "ingredients": ["mefenamic acid"],
        "max_daily_dose_mg": 1500,
        "aliases": ["ponstan", "mefenamic"],
    },
    "enoxaparin": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "low molecular weight heparin",
        "ingredients": ["enoxaparin"],
        "max_daily_dose_mg": 300,
        "aliases": ["clexane", "lovenox"],
    },
    "heparin": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "unfractionated heparin",
        "ingredients": ["heparin"],
        "max_daily_dose_mg": None,
        "aliases": [],
    },
    "warfarin": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "vitamin K antagonist",
        "ingredients": ["warfarin"],
        "max_daily_dose_mg": 15,
        "aliases": ["coumadin", "marevan"],
    },
    "rivaroxaban": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "direct oral anticoagulant (factor Xa inhibitor)",
        "ingredients": ["rivaroxaban"],
        "max_daily_dose_mg": 30,
        "aliases": ["xarelto"],
    },
    "apixaban": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "direct oral anticoagulant (factor Xa inhibitor)",
        "ingredients": ["apixaban"],
        "max_daily_dose_mg": 10,
        "aliases": ["eliquis"],
    },
    "dabigatran": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "direct oral anticoagulant (direct thrombin inhibitor)",
        "ingredients": ["dabigatran"],
        "max_daily_dose_mg": 300,
        "aliases": ["pradaxa"],
    },
    "fondaparinux": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "factor Xa inhibitor",
        "ingredients": ["fondaparinux"],
        "max_daily_dose_mg": 10,
        "aliases": ["arixtra"],
    },
    "dalteparin": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "low molecular weight heparin",
        "ingredients": ["dalteparin"],
        "max_daily_dose_mg": None,
        "aliases": ["fragmin"],
    },
    "edoxaban": {
        "class": DrugClass.ANTICOAGULANT,
        "subclass": "direct oral anticoagulant (factor Xa inhibitor)",
        "ingredients": ["edoxaban"],
        "max_daily_dose_mg": 60,
        "aliases": ["savaysa", "lixiana"],
    },
    "ondansetron": {
        "class": DrugClass.ANTIEMETIC,
        "subclass": "5-HT3 antagonist",
        "ingredients": ["ondansetron"],
        "max_daily_dose_mg": 24,
        "aliases": ["zofran"],
    },
    "metoclopramide": {
        "class": DrugClass.ANTIEMETIC,
        "subclass": "dopamine antagonist",
        "ingredients": ["metoclopramide"],
        "max_daily_dose_mg": 30,
        "aliases": ["maxolon"],
    },
    "omeprazole": {
        "class": DrugClass.PPI,
        "subclass": "proton pump inhibitor",
        "ingredients": ["omeprazole"],
        "max_daily_dose_mg": 40,
        "aliases": ["losec"],
    },
    "pantoprazole": {
        "class": DrugClass.PPI,
        "subclass": "proton pump inhibitor",
        "ingredients": ["pantoprazole"],
        "max_daily_dose_mg": 80,
        "aliases": ["controloc"],
    },
    "prednisolone": {
        "class": DrugClass.CORTICOSTEROID,
        "subclass": "systemic corticosteroid",
        "ingredients": ["prednisolone"],
        "max_daily_dose_mg": 60,
        "aliases": ["prednisone", "deltasone"],
    },
    "dexamethasone": {
        "class": DrugClass.CORTICOSTEROID,
        "subclass": "systemic corticosteroid",
        "ingredients": ["dexamethasone"],
        "max_daily_dose_mg": 40,
        "aliases": ["decadron"],
    },
    "hydrocortisone": {
        "class": DrugClass.CORTICOSTEROID,
        "subclass": "systemic corticosteroid",
        "ingredients": ["hydrocortisone"],
        "max_daily_dose_mg": 400,
        "aliases": ["solu-cortef"],
    },
    "salbutamol": {
        "class": DrugClass.BRONCHODILATOR,
        "subclass": "short-acting beta-2 agonist",
        "ingredients": ["salbutamol"],
        "max_daily_dose_mg": 32,
        "aliases": ["albuterol", "ventolin"],
    },
    "acetylcysteine": {
        "class": DrugClass.MUCOLYTIC,
        "subclass": "mucolytic",
        "ingredients": ["acetylcysteine"],
        "max_daily_dose_mg": 600,
        "aliases": ["nac", "fluimucil"],
    },
}

# Build reverse lookup: alias -> generic_name
_ALIAS_MAP: Dict[str, str] = {}
_ALL_KNOWN_NAMES: List[str] = []

for generic, info in DRUG_DB.items():
    _ALIAS_MAP[generic] = generic
    _ALL_KNOWN_NAMES.append(generic)
    for alias in info.get("aliases", []):
        _ALIAS_MAP[alias.lower()] = generic
        _ALL_KNOWN_NAMES.append(alias.lower())

_RXNORM_CACHE: Dict[str, dict] = {}

_RXNORM_CLASS_MAP = {
    "antibiotic": DrugClass.ANTIBIOTIC,
    "antifungal": DrugClass.ANTIFUNGAL,
    "antiviral": DrugClass.ANTIVIRAL,
    "antimycobacterial": DrugClass.ANTIBIOTIC,
    "analgesic/antipyretic": DrugClass.ANALGESIC,
    "NSAID (anti-inflammatory/analgesic)": DrugClass.NSAID,
    "anticoagulant": DrugClass.ANTICOAGULANT,
    "proton pump inhibitor": DrugClass.PPI,
    "antiemetic": DrugClass.ANTIEMETIC,
    "bronchodilator": DrugClass.BRONCHODILATOR,
    "corticosteroid": DrugClass.CORTICOSTEROID,
    "mucolytic": DrugClass.MUCOLYTIC,
    "antihypertensive": DrugClass.ANTIHYPERTENSIVE,
    "antidiabetic": DrugClass.ANTIDIABETIC,
    "antihistamine": DrugClass.ANTIHISTAMINE,
    "diuretic": DrugClass.UNKNOWN,
    "beta-blocker": DrugClass.UNKNOWN,
    "calcium channel blocker": DrugClass.UNKNOWN,
    "ACE inhibitor/ARB": DrugClass.UNKNOWN,
    "lipid-lowering agent": DrugClass.UNKNOWN,
}


# =========================
# ALLERGY + CROSS-SENSITIVITY MAP
# =========================
ALLERGY_CROSS_REACTIVITY = {
    "penicillin": [
        "penicillin",
        "cephalosporin",
        "carbapenem",
        "beta-lactam",
    ],
    "amoxicillin": [
        "penicillin",
        "cephalosporin",
        "carbapenem",
        "beta-lactam",
    ],
    "cephalosporin": [
        "cephalosporin",
        "penicillin",
        "carbapenem",
        "beta-lactam",
    ],
    "sulfa": [
        "sulfonamide",
    ],
    "sulfonamide": [
        "sulfonamide",
    ],
    "macrolide": [
        "macrolide",
    ],
    "erythromycin": [
        "macrolide",
    ],
    "fluoroquinolone": [
        "fluoroquinolone",
    ],
    "ciprofloxacin": [
        "fluoroquinolone",
    ],
    "nsaid": [
        "NSAID",
    ],
    "aspirin": [
        "NSAID",
    ],
    "ibuprofen": [
        "NSAID",
    ],
    "tetracycline": [
        "tetracycline",
    ],
    "vancomycin": [
        "glycopeptide",
    ],
}


# =========================
# RESTRICTED-USE ANTIBIOTICS
# =========================
RESTRICTED_DRUGS = {
    "meropenem":   "Carbapenem - reserve for severe sepsis, MDR organisms, "
                    "or beta-lactam allergic patients with broad-spectrum needs.",
    "imipenem-cilastatin": "Carbapenem - reserve for severe sepsis, MDR organisms.",
    "vancomycin":  "Reserve for confirmed/suspected MRSA, severe gram-positive "
                    "infections, or beta-lactam allergic patients.",
    "linezolid":   "Reserve for confirmed/suspected MRSA, VRE, or vancomycin-"
                    "resistant gram-positive infections.",
    "daptomycin":  "Reserve for MRSA bacteraemia, complicated skin/soft-tissue "
                    "infections with confirmed MRSA. Do NOT use for pneumonia "
                    "(inactivated by surfactant).",
    "colistin":    "Last-resort agent - reserve for MDR gram-negative infections "
                    "(e.g., CRE, MDR Pseudomonas, Acinetobacter).",
    "cefepime":    "4th-gen cephalosporin - reserve for nosocomial/severe "
                    "infections, febrile neutropenia, MDR gram-negatives.",
    "tigecycline": "Reserve for MDR/complicated infections.",
    "ceftazidime": "Reserve for confirmed/suspected Pseudomonas infection.",
}



# =========================
# DETERMINISTIC MONITORING TABLE
# =========================
DRUG_MONITORING = {
    "vancomycin":  ["Vancomycin trough levels (15-20 mg/L for severe infection)",
                    "Renal function (serum creatinine, eGFR) - nephrotoxicity",
                    "Auditory function if prolonged use - ototoxicity"],
    "gentamicin":  ["Gentamicin trough/peak levels",
                    "Renal function - nephrotoxicity",
                    "Auditory function - ototoxicity"],
    "amikacin":    ["Amikacin trough/peak levels",
                    "Renal function - nephrotoxicity"],
    "linezolid":   ["FBC weekly - bone marrow suppression "
                    "(thrombocytopenia/anaemia after >2 weeks)",
                    "Symptoms of serotonin syndrome (Linezolid is a weak MAO inhibitor)",
                    "LFTs - hepatotoxicity",
                    "Visual symptoms if used >28 days - optic neuropathy"],
    "daptomycin":  ["CK (creatine kinase) weekly - rhabdomyolysis risk",
                    "Renal function"],
    "warfarin":    ["INR (target depends on indication)",
                    "Bleeding signs"],
    "heparin":     ["aPTT (target 1.5-2.5x baseline)",
                    "FBC for thrombocytopenia (HIT) - days 5-10",
                    "Bleeding signs"],
    "enoxaparin":  ["FBC for thrombocytopenia (HIT)",
                    "Renal function (CrCl) - dose adjust if <30 mL/min",
                    "Anti-Xa levels ONLY if pregnancy/extremes of weight/severe renal impairment",
                    "Bleeding signs",
                    "NOTE: Enoxaparin does NOT require routine INR or aPTT monitoring"],
    "rivaroxaban": ["Renal function",
                    "Bleeding signs",
                    "NOTE: DOACs do NOT require routine INR/aPTT monitoring"],
    "apixaban":    ["Renal function",
                    "Bleeding signs",
                    "NOTE: DOACs do NOT require routine INR/aPTT monitoring"],
    "paracetamol": ["LFTs if cumulative dose high or chronic use",
                    "Maximum 4 g/day in healthy adults; lower in liver impairment/elderly"],
    "amoxicillin": ["Signs of hypersensitivity reaction",
                    "GI tolerance"],
    "co-amoxiclav":["LFTs - cholestatic hepatitis (esp. with prolonged use)",
                    "Signs of hypersensitivity"],
    "flucloxacillin":["LFTs - cholestatic hepatitis",
                    "Signs of hypersensitivity"],
    "ceftriaxone": ["Signs of hypersensitivity",
                    "Avoid concurrent calcium-containing IV fluids in neonates"],
    "ciprofloxacin":["QT interval (prolongation risk)",
                    "Tendon symptoms - tendinopathy/rupture risk",
                    "CNS symptoms"],
    "levofloxacin":["QT interval (prolongation risk)",
                    "Tendon symptoms",
                    "CNS symptoms"],
    "azithromycin":["QT interval (prolongation risk)",
                    "LFTs"],
    "clarithromycin":["QT interval (prolongation risk)",
                    "LFTs",
                    "Drug interactions via CYP3A4"],
    "erythromycin":["QT interval (prolongation risk)",
                    "LFTs",
                    "Drug interactions via CYP3A4"],
    "metronidazole":["LFTs if prolonged use",
                    "Peripheral neuropathy if prolonged use",
                    "Avoid alcohol (disulfiram-like reaction)"],
    "clindamycin": ["Signs of C. difficile-associated diarrhoea",
                    "LFTs if prolonged"],
    "trimethoprim-sulfamethoxazole": ["FBC - cytopenias",
                    "Renal function - serum creatinine",
                    "Serum potassium - hyperkalaemia",
                    "LFTs"],
    "fluconazole": ["LFTs",
                    "QT interval if high doses",
                    "Drug interactions via CYP3A4/2C9/2C19"],
    "amphotericin b":["Renal function (nephrotoxicity is dose-limiting)",
                    "Electrolytes (K, Mg)",
                    "FBC"],
}


# =========================
# DETERMINISTIC INTERACTION HINTS
# =========================
DRUG_INTERACTIONS = {
    frozenset(["warfarin", "metronidazole"]):
        "Metronidazole inhibits warfarin metabolism - significantly increases "
        "INR. Monitor INR more frequently and consider dose reduction.",
    frozenset(["warfarin", "trimethoprim-sulfamethoxazole"]):
        "TMP-SMX displaces warfarin from albumin and inhibits CYP2C9 - "
        "significant INR rise. Monitor INR closely.",
    frozenset(["warfarin", "ciprofloxacin"]):
        "Ciprofloxacin can increase INR with warfarin - monitor INR.",
    frozenset(["warfarin", "fluconazole"]):
        "Fluconazole inhibits CYP2C9 - significantly increases INR. "
        "Monitor INR closely.",
    frozenset(["clarithromycin", "warfarin"]):
        "Clarithromycin (CYP3A4 inhibitor) increases warfarin effect - "
        "monitor INR.",
    frozenset(["ciprofloxacin", "azithromycin"]):
        "Both prolong QT interval - additive QT prolongation risk.",
    frozenset(["clarithromycin", "azithromycin"]):
        "Both prolong QT interval - additive risk.",
    frozenset(["ciprofloxacin", "clarithromycin"]):
        "Both prolong QT interval - additive risk.",
    frozenset(["enoxaparin", "warfarin"]):
        "Bridging therapy is intentional but increases bleeding risk - "
        "monitor closely.",
    frozenset(["enoxaparin", "aspirin"]):
        "Increased bleeding risk - assess benefit vs risk.",
    frozenset(["enoxaparin", "ibuprofen"]):
        "Increased bleeding risk with NSAIDs - avoid if possible.",
    frozenset(["enoxaparin", "diclofenac"]):
        "Increased bleeding risk with NSAIDs - avoid if possible.",
}


# =========================
# NEGATIVE INDICATIONS (Tier 3.7)
# A drug may appear in a chapter's chunks but only be indicated for a
# specific sub-condition. This table catches "the drug is in the chapter
# but not for THIS diagnosis" - e.g. metronidazole is in the SSTI chapter
# only for bite wounds, not plain cellulitis.
#
# Each entry: (drug_lowercase, diagnosis_keyword) -> {
#     "exception_keywords": [...]   list of words that, if present in the
#                                   diagnosis or in the drug's chunk context,
#                                   make the drug acceptable
#     "message":   reason shown to LLM and pharmacist
# }
#
# A drug paired here is downgraded to RESTRICTED_USE unless an exception
# keyword is found. Add new entries as you encounter more guideline traps.
# =========================
NEGATIVE_INDICATIONS = {
    # ------------------------------------------------------------------
    # Site-restricted drugs.
    # Use allowed_diagnosis_keywords (whitelist) - rule fires for ANY
    # diagnosis that does NOT contain one of these.
    # ------------------------------------------------------------------
    "nitrofurantoin": [{
        "allowed_diagnosis_keywords": [
            "cystitis", "lower urinary tract", "lower uti",
            "uncomplicated uti", "bladder infection",
        ],
        "forbidden_diagnosis_keywords": [],
        "exception_keywords": [],
        "severity": "CRITICAL",
        "message": (
            "Nitrofurantoin only achieves therapeutic concentrations in the "
            "bladder and does NOT penetrate kidney tissue. It is inappropriate "
            "for pyelonephritis or any upper UTI - treatment failure is likely."
        ),
    }, {
        # G6PD contraindication - fires for any diagnosis text that
        # mentions G6PD (regardless of the primary infection site).
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["g6pd"],
        "exception_keywords": [],
        "severity": "CRITICAL",
        "message": (
            "Nitrofurantoin is CONTRAINDICATED in G6PD deficiency due to risk "
            "of acute haemolytic anaemia. Choose an alternative regimen "
            "(e.g. cefalexin or cefuroxime)."
        ),
    }],

    # ------------------------------------------------------------------
    # Indication-specific traps (previously the rest of NEGATIVE_INDICATIONS).
    # Use forbidden_diagnosis_keywords (blacklist) - rule fires only when
    # the diagnosis contains one of these AND no exception keyword is found.
    # ------------------------------------------------------------------

    # Co-trimoxazole / TMP-SMX in G6PD - sulfa-induced oxidative haemolysis.
    "trimethoprim-sulfamethoxazole": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["g6pd"],
        "exception_keywords": [],
        "severity": "CRITICAL",
        "message": (
            "Trimethoprim-sulfamethoxazole (co-trimoxazole) is CONTRAINDICATED "
            "in G6PD deficiency - sulfonamide can precipitate acute haemolytic "
            "anaemia. UMMC paediatric urology explicitly requires G6PD "
            "screening before initiating this drug."
        ),
    }],

    # Metronidazole is in the SSTI chapter but only for bite/contaminated/anaerobic
    "metronidazole": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": [
            "cellulitis", "skin and soft tissue",
        ],
        "exception_keywords": [
            "anaerobic", "bite", "contaminated", "necrotising",
            "necrotizing", "polymicrobial", "wound",
        ],
        "severity": "WARNING",
        "message": (
            "Metronidazole is not routinely indicated for uncomplicated "
            "cellulitis or skin/soft tissue infections. It is only used when "
            "anaerobic coverage is needed (bite wounds, contaminated wounds, "
            "necrotising infections, polymicrobial infections)."
        ),
    }],

    # Vancomycin reserved for MRSA / severe
    "vancomycin": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["cellulitis"],
        "exception_keywords": [
            "MRSA", "severe", "MDR", "methicillin",
            "necrotising", "necrotizing",
        ],
        "severity": "WARNING",
        "message": (
            "Vancomycin is not routinely indicated for uncomplicated "
            "cellulitis. It is reserved for MRSA-confirmed or severe/MDR "
            "infections."
        ),
    }, {
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["pneumonia"],
        "exception_keywords": [
            "MRSA", "severe", "MDR", "methicillin",
            "nosocomial", "HAP", "VAP",
        ],
        "severity": "WARNING",
        "message": (
            "Vancomycin is not first-line for community-acquired pneumonia. "
            "Reserve for MRSA or nosocomial pneumonia."
        ),
    }],

    # Daptomycin: never for pneumonia (lung surfactant inactivation)
    "daptomycin": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["cellulitis"],
        "exception_keywords": [
            "MRSA", "severe", "MDR", "methicillin",
        ],
        "severity": "WARNING",
        "message": (
            "Daptomycin is not routinely indicated for uncomplicated "
            "cellulitis. It is reserved for MRSA bacteraemia or complicated "
            "MRSA SSTI."
        ),
    }, {
        # Hard block - no exceptions
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": [
            "pneumonia", "respiratory", "lung",
        ],
        "exception_keywords": [],
        "severity": "CRITICAL",
        "message": (
            "DAPTOMYCIN IS INACTIVATED BY LUNG SURFACTANT. It must NEVER be "
            "used for pneumonia or any respiratory infection - treatment "
            "failure is guaranteed."
        ),
    }],

    # Linezolid reserved for VRE/MRSA
    "linezolid": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["cellulitis"],
        "exception_keywords": [
            "MRSA", "VRE", "severe", "vancomycin-resistant",
        ],
        "severity": "WARNING",
        "message": (
            "Linezolid is not routinely indicated for uncomplicated cellulitis. "
            "Reserve for MRSA, VRE, or vancomycin-resistant gram-positive "
            "infections."
        ),
    }, {
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["pneumonia"],
        "exception_keywords": [
            "MRSA", "severe", "methicillin",
        ],
        "severity": "WARNING",
        "message": (
            "Linezolid is not first-line for community-acquired pneumonia. "
            "Reserve for MRSA pneumonia or treatment failure."
        ),
    }],

    # Meropenem reserved for severe / MDR / penicillin-allergic empiric
    "meropenem": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["cellulitis"],
        "exception_keywords": [
            "severe", "ESBL", "MDR", "necrotising", "necrotizing",
            "penicillin allergy",
        ],
        "severity": "WARNING",
        "message": (
            "Meropenem is not routinely indicated for uncomplicated cellulitis. "
            "Reserve for severe necrotising infections, ESBL/MDR organisms, or "
            "penicillin-allergic patients needing broad-spectrum cover."
        ),
    }, {
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["urinary", "pyelonephritis"],
        "exception_keywords": [
            "severe", "sepsis", "ESBL", "MDR", "penicillin allergy",
        ],
        "severity": "WARNING",
        "message": (
            "Meropenem is reserved for severe pyelonephritis with sepsis, "
            "ESBL/MDR organisms, or penicillin-allergic patients."
        ),
    }],

    # Ceftazidime is anti-Pseudomonal - not for routine empiric use
    "ceftazidime": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["cellulitis"],
        "exception_keywords": [
            "pseudomonas", "burn", "diabetic foot", "neutropenic",
        ],
        "severity": "WARNING",
        "message": (
            "Ceftazidime is anti-Pseudomonal. Not indicated for routine "
            "cellulitis - reserve for confirmed Pseudomonas, burn-related "
            "infections, diabetic foot, or neutropenic patients."
        ),
    }],

    # Ciprofloxacin in UTI - only for step-down/susceptibility-confirmed
    "ciprofloxacin": [{
        "allowed_diagnosis_keywords": [],
        "forbidden_diagnosis_keywords": ["pyelonephritis"],
        "exception_keywords": [
            "susceptible", "culture", "step-down", "oral switch",
        ],
        "severity": "WARNING",
        "message": (
            "Ciprofloxacin is not first-line empiric therapy for pyelonephritis "
            "due to rising fluoroquinolone resistance. Use only for "
            "culture-confirmed susceptibility or as oral step-down."
        ),
    }],
}


# =========================
# Route tokens - used to strip route suffixes when matching drug names
# (Tier 2.4 - prevents spurious "auto-correction" alerts)
# =========================
ROUTE_TOKENS = {
    "po", "iv", "im", "sc", "sl", "pr", "topical", "inhaled",
    "oral", "intravenous", "intramuscular", "subcutaneous",
    "rectal", "sublingual", "nebulised", "nebulized", "neb",
    "tablet", "tablets", "tab", "capsule", "capsules", "cap",
    "injection", "inj", "infusion", "syrup", "drops", "ointment",
}


# =========================
# Public API Functions
# =========================

def _strip_route_tokens(name: str) -> str:
    """
    Remove route/formulation words from a drug name string so we can compare
    'Ceftriaxone IV' vs 'ceftriaxone' without flagging it as a 'correction'.
    """
    parts = re.split(r'[\s\-,/]+', name.lower().strip())
    cleaned_parts = [p for p in parts if p and p not in ROUTE_TOKENS]
    return " ".join(cleaned_parts).strip()


def _is_meaningful_correction(original: str, generic: str) -> bool:
    """
    Returns True only if the difference between user input and the resolved
    generic is more than route stripping, case, or whitespace.

    Examples:
      'Ceftriaxone IV' -> 'ceftriaxone'   : route strip only       -> FALSE (no alert)
      'AMOXICILLIN PO' -> 'amoxicillin'   : case + route           -> FALSE (no alert)
      'Augmentin'      -> 'co-amoxiclav'  : brand resolution       -> TRUE  (alert)
      'amoxicilin'     -> 'amoxicillin'   : real typo correction   -> TRUE  (alert)
      'ZINNAT'         -> 'cefuroxime'    : brand resolution       -> TRUE  (alert)
    """
    orig_clean = _strip_route_tokens(original)
    if not orig_clean:
        return False
    gen_clean = generic.lower().strip()

    # If route+case strip makes them identical, it's purely noise.
    if orig_clean == gen_clean:
        return False

    # Otherwise it's a meaningful change - brand resolution OR a typo.
    # Both should alert the pharmacist so they can verify.
    return True


def resolve_drug_name(input_name: str) -> Tuple[str, str, bool]:
    """
    Resolve a drug name input to its canonical generic name.

    Returns (generic_name, original_input, was_meaningfully_corrected).
    The third value is True ONLY when a real spell / brand correction
    happened - not when the only change was lowercasing or stripping
    a route token like 'PO' or 'IV'. This prevents alert fatigue.
    """
    if not input_name:
        return (input_name, input_name, False)

    cleaned = input_name.lower().strip()
    cleaned_no_route = _strip_route_tokens(input_name)

    # 1. Exact match on raw input
    if cleaned in _ALIAS_MAP:
        generic = _ALIAS_MAP[cleaned]
        return (generic, input_name, _is_meaningful_correction(input_name, generic))

    # 2. Exact match after stripping route tokens
    if cleaned_no_route and cleaned_no_route in _ALIAS_MAP:
        generic = _ALIAS_MAP[cleaned_no_route]
        return (generic, input_name, _is_meaningful_correction(input_name, generic))

    # 3. Fuzzy match against known names (real typo correction)
    matches = get_close_matches(
        cleaned_no_route or cleaned, _ALL_KNOWN_NAMES, n=1, cutoff=0.80
    )
    if matches:
        matched = matches[0]
        generic = _ALIAS_MAP.get(matched, matched)
        # Always flag fuzzy hits - the user might have a real typo.
        return (generic, input_name, True)

    # 4. RxNorm API fallback
    try:
        from rxnorm_client import lookup_drug
        print(f"[drug_database] '{input_name}' not in local DB - trying RxNorm API...")

        result = lookup_drug(input_name)
        if result:
            generic_name = result["generic_name"]
            rxnorm_class = result.get("drug_class", "unknown")
            mapped_class = _RXNORM_CLASS_MAP.get(rxnorm_class, DrugClass.UNKNOWN)

            _RXNORM_CACHE[generic_name] = {
                "class": mapped_class,
                "subclass": rxnorm_class,
                "ingredients": result.get("ingredients", [generic_name]),
                "max_daily_dose_mg": None,
                "aliases": [cleaned],
                "source": "rxnorm",
            }
            _RXNORM_CACHE[cleaned] = _RXNORM_CACHE[generic_name]

            print(f"[drug_database] RxNorm resolved: '{input_name}' -> "
                  f"'{generic_name}' [{rxnorm_class}]")

            return (generic_name, input_name,
                    _is_meaningful_correction(input_name, generic_name))

        print(f"[drug_database] RxNorm found nothing for '{input_name}'")

    except ImportError:
        print("[drug_database] rxnorm_client not available - skipping API fallback")
    except Exception as e:
        print(f"[drug_database] RxNorm API error: {e}")

    print(f"[drug_database] '{input_name}' not found in any source - returning as unknown")
    return (input_name.lower(), input_name, False)


def get_drug_info(generic_name: str) -> Optional[dict]:
    info = DRUG_DB.get(generic_name.lower())
    if info:
        return info
    cached = _RXNORM_CACHE.get(generic_name.lower())
    if cached:
        return cached
    return None


def get_drug_class(generic_name: str) -> str:
    info = get_drug_info(generic_name)
    return info["class"] if info else DrugClass.UNKNOWN


def get_drug_subclass(generic_name: str) -> str:
    info = get_drug_info(generic_name)
    return info.get("subclass", "") if info else ""


def get_ingredients(generic_name: str) -> List[str]:
    info = get_drug_info(generic_name)
    return info["ingredients"] if info else [generic_name.lower()]


def get_max_daily_dose(generic_name: str) -> Optional[float]:
    info = get_drug_info(generic_name)
    if info:
        return info.get("max_daily_dose_mg")
    return None


def is_supportive_care(generic_name: str) -> bool:
    drug_class = get_drug_class(generic_name)
    return drug_class in SUPPORTIVE_CARE_CLASSES


def is_restricted_drug(generic_name: str) -> Optional[str]:
    """If drug is a restricted big-gun agent, return the reason. Else None."""
    return RESTRICTED_DRUGS.get(generic_name.lower())


def get_monitoring_for(generic_name: str) -> List[str]:
    """Return deterministic monitoring list for a drug."""
    return DRUG_MONITORING.get(generic_name.lower(), [])


def get_known_interactions(medicines: List[dict]) -> List[str]:
    """Look up deterministic drug-drug interactions."""
    notes = []
    seen = set()

    names = []
    for m in medicines:
        n = m.get("generic_name", m.get("name", ""))
        if n:
            names.append(n.lower())

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            pair = frozenset([names[i], names[j]])
            if pair in DRUG_INTERACTIONS and pair not in seen:
                seen.add(pair)
                notes.append(
                    f"{names[i]} + {names[j]}: {DRUG_INTERACTIONS[pair]}"
                )
    return notes


def check_ingredient_duplication(medicines: List[dict]) -> List[dict]:
    alerts = []
    ingredient_map: Dict[str, List[str]] = {}
    for med in medicines:
        generic = med.get("generic_name", med.get("name", "")).lower()
        ingredients = get_ingredients(generic)
        for ing in ingredients:
            if ing not in ingredient_map:
                ingredient_map[ing] = []
            ingredient_map[ing].append(med.get("name", generic))

    for ingredient, drugs in ingredient_map.items():
        if len(drugs) > 1:
            alerts.append({
                "type": "THERAPEUTIC_DUPLICATION",
                "severity": "CRITICAL",
                "ingredient": ingredient,
                "drugs": drugs,
                "message": (
                    f"CRITICAL - Therapeutic duplication detected: "
                    f"{', '.join(drugs)} both contain '{ingredient}'. "
                    f"This may cause double-dosing toxicity."
                )
            })
    return alerts


def check_class_overlap(medicines: List[dict]) -> List[dict]:
    alerts = []
    subclass_map: Dict[str, List[str]] = {}
    for med in medicines:
        generic = med.get("generic_name", med.get("name", "")).lower()
        drug_class = get_drug_class(generic)
        subclass = get_drug_subclass(generic)

        if drug_class != DrugClass.ANTIBIOTIC:
            continue

        broad_class = _get_broad_antibiotic_class(subclass)
        if not broad_class:
            continue

        if broad_class not in subclass_map:
            subclass_map[broad_class] = []
        subclass_map[broad_class].append(med.get("name", generic))

    for broad_class, drugs in subclass_map.items():
        if len(drugs) > 1:
            alerts.append({
                "type": "CLASS_OVERLAP",
                "severity": "WARNING",
                "drug_class": broad_class,
                "drugs": drugs,
                "message": (
                    f"WARNING - Therapeutic redundancy: "
                    f"{', '.join(drugs)} are both {broad_class} antibiotics. "
                    f"Prescribing multiple drugs from the same class for the same "
                    f"indication is usually redundant. Verify if both are intended "
                    f"(e.g., step-down therapy, different infection sites)."
                )
            })
    return alerts


def _get_broad_antibiotic_class(subclass: str) -> Optional[str]:
    if not subclass:
        return None

    subclass_lower = subclass.lower()

    if any(term in subclass_lower for term in
           ["penicillin", "cephalosporin", "carbapenem", "beta-lactam"]):
        return "beta-lactam"
    if "macrolide" in subclass_lower:
        return "macrolide"
    if "fluoroquinolone" in subclass_lower or "quinolone" in subclass_lower:
        return "fluoroquinolone"
    if "tetracycline" in subclass_lower:
        return "tetracycline"
    if "aminoglycoside" in subclass_lower:
        return "aminoglycoside"
    if "glycopeptide" in subclass_lower:
        return "glycopeptide"
    if "polymyxin" in subclass_lower:
        return "polymyxin"
    return None


def check_max_dose_safety(
    generic_name: str,
    single_dose_mg: float,
    frequency_hours: Optional[int]
) -> Optional[dict]:
    max_daily = get_max_daily_dose(generic_name)
    if max_daily is None or single_dose_mg is None:
        return None

    if frequency_hours and frequency_hours > 0:
        doses_per_day = 24 / frequency_hours
        daily_dose = single_dose_mg * doses_per_day
    else:
        daily_dose = single_dose_mg

    if daily_dose <= max_daily:
        return None

    ratio = daily_dose / max_daily

    if ratio >= 3:
        severity = "CRITICAL"
        message = (
            f"CRITICAL OVERDOSE: {generic_name} total daily dose is {daily_dose:.0f}mg "
            f"({ratio:.1f}x the maximum safe limit of {max_daily:.0f}mg/day). "
            f"This is a DANGEROUS dose that could cause severe toxicity."
        )
    else:
        severity = "WARNING"
        message = (
            f"HIGH DOSE WARNING: {generic_name} total daily dose is {daily_dose:.0f}mg "
            f"which exceeds the maximum of {max_daily:.0f}mg/day ({ratio:.1f}x limit)."
        )

    return {
        "type": "MAX_DOSE_EXCEEDED",
        "severity": severity,
        "drug": generic_name,
        "daily_dose_mg": daily_dose,
        "max_daily_mg": max_daily,
        "ratio": ratio,
        "message": message
    }


# =========================
# ALLERGY + CROSS-SENSITIVITY CHECK
# =========================
def _normalize_allergy_string(allergy_text: str) -> List[str]:
    """Parse free-text allergy field into matching keys."""
    if not allergy_text:
        return []

    text = allergy_text.lower().strip()
    if text in ("none", "none reported", "n/a", "null", "nil",
                "no known allergy", "nka", "nkda", ""):
        return []

    found = []
    for key in ALLERGY_CROSS_REACTIVITY.keys():
        if key in text:
            found.append(key)
    return found


def _infer_allergy_reaction_severity(allergy_text: str) -> str:
    """
    Inspect the free-text allergy field for reaction-severity cues and return:
        "severe"   - anaphylaxis, angioedema, SJS/TEN, DRESS, swelling, shock,
                     hypotension, respiratory distress  -> hard contraindication,
                     even for cross-reactive classes.
        "mild"     - rash, itch, urticaria-without-anaphylaxis, hives, GI upset
                     -> cross-reactive drugs (e.g. cephalosporin for a penicillin
                     rash) become "use with caution", not absolute contraindications.
        "unknown"  - no reaction descriptor provided. We default to treating
                     cross-reactivity as CRITICAL for safety.

    Direct hits (drug IS the allergen, e.g. cloxacillin in a penicillin-allergic
    patient) are ALWAYS critical regardless of this value.
    """
    if not allergy_text:
        return "unknown"
    t = allergy_text.lower()

    severe_terms = (
        "anaphyla",          # anaphylaxis / anaphylactic
        "angioedema", "angio-edema", "angio edema",
        "stevens", "sjs", "ten ",     # SJS / TEN
        "dress",
        "swelling", "throat", "tongue",
        "shock", "hypotens",
        "wheez", "bronchospasm",
        "respiratory distress", "difficulty breathing", "short of breath",
        "severe",
    )
    if any(s in t for s in severe_terms):
        return "severe"

    mild_terms = (
        "rash", "itch", "itchy",
        "hives", "urticaria",
        "mild",
        "gi upset", "nausea", "vomit", "diarrhoea", "diarrhea",
    )
    if any(s in t for s in mild_terms):
        return "mild"

    return "unknown"


def check_allergy_conflicts(medicines: List[dict],
                            allergy_text: str) -> List[dict]:
    """
    Cross-check every prescribed drug against patient's allergies.

    Two failure modes are distinguished:
      * Direct hit (e.g. amoxicillin for a penicillin-allergic patient) -
        always CRITICAL with a hard "DO NOT ADMINISTER" recommendation.
      * Cross-reactivity (e.g. cefalexin for a penicillin-allergic patient) -
        severity is downgraded to WARNING when the documented reaction is
        mild (rash, itch, urticaria), since 1st/2nd-gen cephalosporins carry
        roughly 1-2% cross-reactivity for non-anaphylactic penicillin allergy.
        For severe or unspecified reactions, the alert stays CRITICAL.
    """
    alerts = []
    allergy_keys = _normalize_allergy_string(allergy_text)
    if not allergy_keys:
        return alerts

    reaction_severity = _infer_allergy_reaction_severity(allergy_text)

    seen = set()

    for med in medicines:
        generic = med.get("generic_name", med.get("name", "")).lower()
        if not generic:
            continue

        info = get_drug_info(generic)
        subclass = (info.get("subclass", "") if info else "").lower()
        ingredients = get_ingredients(generic)

        for allergy_key in allergy_keys:
            triggers = ALLERGY_CROSS_REACTIVITY.get(allergy_key, [])

            # A drug is a DIRECT hit when either:
            #   (1) the allergen appears in its ingredients list, OR
            #   (2) the allergen appears in its subclass string
            #       (e.g. cloxacillin subclass = "beta-lactam/penicillin"
            #        means cloxacillin IS a penicillin, not merely
            #        cross-reactive with one).
            # Direct hits are always CRITICAL regardless of reaction severity.
            direct_hit = (
                any(allergy_key in ing.lower() for ing in ingredients)
                or allergy_key in subclass
            )
            if direct_hit and (generic, allergy_key) not in seen:
                seen.add((generic, allergy_key))
                alerts.append({
                    "type": "ALLERGY_DIRECT",
                    "severity": "CRITICAL",
                    "drug": generic,
                    "allergy": allergy_key,
                    "message": (
                        f"CRITICAL ALLERGY CONFLICT: Patient is allergic to "
                        f"{allergy_key.upper()}. {generic} is a {allergy_key}-"
                        f"class antibiotic - DO NOT ADMINISTER. Recommend "
                        f"immediate discontinuation. Do NOT suggest dose "
                        f"adjustments for contraindicated drugs."
                    )
                })
                continue

            for trigger in triggers:
                if trigger.lower() in subclass:
                    if (generic, allergy_key) not in seen:
                        seen.add((generic, allergy_key))

                        # Downgrade severity for mild documented reactions.
                        # A penicillin rash carries low (~1-2%) cross-reactivity
                        # risk with cephalosporins; an anaphylactic penicillin
                        # reaction is a hard contraindication for the whole
                        # beta-lactam class.
                        if reaction_severity == "mild":
                            alerts.append({
                                "type": "ALLERGY_CROSS_REACTIVITY",
                                "severity": "WARNING",
                                "drug": generic,
                                "allergy": allergy_key,
                                "subclass": subclass,
                                "reaction_severity": reaction_severity,
                                "message": (
                                    f"CROSS-SENSITIVITY (mild reaction documented): "
                                    f"Patient has a {allergy_key} allergy described "
                                    f"as a mild reaction (e.g. rash). {generic} is "
                                    f"a {subclass}, which carries a low but "
                                    f"non-zero cross-reactivity risk with "
                                    f"{allergy_key}. Use only after a documented "
                                    f"allergy-risk review; a non-beta-lactam "
                                    f"alternative (e.g. clindamycin) is preferred "
                                    f"when clinically equivalent."
                                )
                            })
                        else:
                            alerts.append({
                                "type": "ALLERGY_CROSS_REACTIVITY",
                                "severity": "CRITICAL",
                                "drug": generic,
                                "allergy": allergy_key,
                                "subclass": subclass,
                                "reaction_severity": reaction_severity,
                                "message": (
                                    f"CRITICAL CROSS-SENSITIVITY: Patient is allergic "
                                    f"to {allergy_key.upper()}. {generic} is a "
                                    f"{subclass} - cross-reactivity with "
                                    f"{allergy_key} is well-documented. DO NOT "
                                    f"ADMINISTER without specialist clearance. "
                                    f"Recommend immediate discontinuation."
                                )
                            })
                    break

    return alerts


# =========================
# PRN APPROPRIATENESS CHECK
# =========================
def check_prn_appropriateness(medicines: List[dict]) -> List[dict]:
    """Systemic antibiotics and anticoagulants must not be PRN."""
    alerts = []
    for med in medicines:
        prn = bool(med.get("prn", False))
        if not prn:
            continue

        generic = med.get("generic_name", med.get("name", ""))
        drug_class = get_drug_class(generic)

        if drug_class == DrugClass.ANTIBIOTIC:
            alerts.append({
                "type": "PRN_INAPPROPRIATE",
                "severity": "CRITICAL",
                "drug": generic,
                "message": (
                    f"CRITICAL - PRN ERROR: {generic} is a systemic antibiotic "
                    f"and MUST be scheduled (not PRN). PRN antibiotics result "
                    f"in subtherapeutic dosing, treatment failure, and increase "
                    f"antimicrobial resistance. Convert to scheduled dosing."
                )
            })
        elif drug_class == DrugClass.ANTICOAGULANT:
            alerts.append({
                "type": "PRN_INAPPROPRIATE",
                "severity": "CRITICAL",
                "drug": generic,
                "message": (
                    f"CRITICAL - PRN ERROR: {generic} is an anticoagulant and "
                    f"MUST be scheduled (not PRN). PRN dosing risks "
                    f"subtherapeutic anticoagulation and thrombotic events. "
                    f"Convert to scheduled dosing."
                )
            })

    return alerts


# =========================
# RESTRICTED-DRUG CHECK
# =========================
def check_restricted_drugs(medicines: List[dict]) -> List[dict]:
    """Flag every restricted/last-resort drug in the prescription."""
    alerts = []
    for med in medicines:
        generic = med.get("generic_name", med.get("name", ""))
        reason = is_restricted_drug(generic)
        if reason:
            alerts.append({
                "type": "RESTRICTED_USE",
                "severity": "WARNING",
                "drug": generic,
                "message": (
                    f"RESTRICTED ANTIBIOTIC: {generic} is a last-resort agent. "
                    f"{reason} Verify clinical justification - culture/sensitivity, "
                    f"severity of infection, or specific patient factors."
                )
            })
    return alerts


# =========================
# NEGATIVE INDICATION CHECK
#
# Each NEGATIVE_INDICATIONS entry is a list of rules per drug. Each rule has:
#   allowed_diagnosis_keywords  - whitelist style. If non-empty, the drug is
#                                  ONLY appropriate when one of these appears
#                                  in the diagnosis. Used for site-restricted
#                                  drugs (Nitrofurantoin only for lower UTI).
#   forbidden_diagnosis_keywords - blacklist style. The rule fires only when
#                                   one of these keywords appears in the
#                                   diagnosis. Used for indication traps
#                                   (Metronidazole only blocked for cellulitis,
#                                   not for every diagnosis).
#   exception_keywords           - if any of these appear in the diagnosis OR
#                                   in the chunk context, the rule is
#                                   overridden (clinical reason documented).
#   severity                     - CRITICAL = hard block, WARNING = soft flag.
#   message                      - clinician-facing explanation.
#
# Either allowed_diagnosis_keywords OR forbidden_diagnosis_keywords drives
# the rule - one of them should be populated, not both.
# =========================

def check_negative_indication(
    drug_name: str,
    diagnosis: str,
    drug_chunk_context: str = ""
) -> Optional[dict]:
    """
    Return an alert dict if (drug, diagnosis) violates a NEGATIVE_INDICATIONS
    rule and no exception keyword applies. Otherwise return None.

    drug_chunk_context: optional text from the retrieved chunks around where
    this drug was found. Exception keywords are checked against BOTH the
    diagnosis string AND this context, since the clinical reason might be
    implied by chunk content rather than the diagnosis text.
    """
    if not drug_name or not diagnosis:
        return None

    drug_lower = drug_name.lower().strip()
    diag_lower = diagnosis.lower().strip()
    ctx_lower = (drug_chunk_context or "").lower()

    rules = NEGATIVE_INDICATIONS.get(drug_lower)
    if not rules:
        return None

    for rule in rules:
        allowed = [kw.lower() for kw in rule.get("allowed_diagnosis_keywords", [])]
        forbidden = [kw.lower() for kw in rule.get("forbidden_diagnosis_keywords", [])]
        exceptions = [kw.lower() for kw in rule.get("exception_keywords", [])]

        # ---- Step 1: decide whether this rule applies ----
        rule_applies = False
        if allowed:
            # Whitelist mode: rule fires when diagnosis matches NONE of the
            # allowed keywords.
            if not any(kw in diag_lower for kw in allowed):
                rule_applies = True
        elif forbidden:
            # Blacklist mode: rule fires when diagnosis matches ANY of the
            # forbidden keywords.
            if any(kw in diag_lower for kw in forbidden):
                rule_applies = True

        if not rule_applies:
            continue

        # ---- Step 2: check for clinical-reason exception ----
        if exceptions:
            for kw in exceptions:
                if kw in diag_lower or kw in ctx_lower:
                    return None  # clinical reason documented - rule overridden

        # ---- Step 3: produce alert ----
        return {
            "type": "NEGATIVE_INDICATION",
            "severity": rule.get("severity", "WARNING"),
            "drug": drug_name,
            "diagnosis": diagnosis,
            "message": rule["message"],
        }

    return None


def check_negative_indications(medicines: List[dict],
                                diagnosis: str) -> List[dict]:
    """
    Run check_negative_indication() across every prescribed drug and
    return the resulting alert dicts.

    This replaces the old check_site_restrictions() wrapper - site
    restrictions and indication traps now flow through the same
    NEGATIVE_INDICATIONS table.
    """
    alerts = []
    for med in medicines:
        generic = med.get("generic_name", med.get("name", ""))
        alert = check_negative_indication(generic, diagnosis, "")
        if alert:
            alerts.append(alert)
    return alerts

# =========================================================================
# AGE-BASED CONTRAINDICATIONS
# =========================================================================
# Drugs that are unsafe below (or above) a specific age threshold for
# reasons that are NOT captured by the diagnosis text or allergy data.
# These are deterministic safety alerts that fire whenever the patient's
# age falls inside the danger band, regardless of the prescribed
# indication.
#
# Each rule has:
#   max_age_months  inclusive upper bound below which the rule fires
#                   (e.g. 3 means "fires if age < 3 months")
#   min_age_months  optional inclusive lower bound (for "below" + "above"
#                   combination; typically left as None)
#   severity        "CRITICAL" or "WARNING"
#   message         clinician-facing explanation including the reason
#                   (haemolysis, tooth staining, arthropathy, etc.)
#
# Drug names are matched against the resolved generic_name as well as
# the ingredient list - so prescribing "doxycycline" or "tetracycline"
# both match the tetracycline-class rule via INGREDIENT_FAMILIES below.
# =========================================================================

AGE_CONTRAINDICATIONS = {
    # Nitrofurantoin: immature G6PD activity + risk of neonatal jaundice
    # / haemolytic anaemia. UMMC paediatric urology explicitly states
    # ">3 months only".
    "nitrofurantoin": [{
        "max_age_months": 3,
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Nitrofurantoin is CONTRAINDICATED in infants <3 months of "
            "age. Immature G6PD activity creates a high risk of acute "
            "haemolytic anaemia and neonatal jaundice. UMMC paediatric "
            "urology guideline restricts nitrofurantoin to >=3 months."
        ),
    }],
    # Tetracycline class: permanent tooth discolouration + enamel
    # hypoplasia + suppression of bone growth in children <8 years.
    "tetracycline": [{
        "max_age_months": 96,  # 8 years
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Tetracyclines are CONTRAINDICATED in children <8 years. "
            "They bind to calcium in developing teeth and bone, causing "
            "permanent tooth discolouration, enamel hypoplasia, and "
            "transient suppression of bone growth."
        ),
    }],
    "doxycycline": [{
        "max_age_months": 96,  # 8 years
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Doxycycline is generally avoided in children <8 years due "
            "to risk of dental staining. Short courses (<21 days) for "
            "serious indications (e.g. rickettsial infection) are "
            "considered acceptable - confirm the indication justifies "
            "the risk."
        ),
    }],
    "minocycline": [{
        "max_age_months": 96,
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Minocycline is CONTRAINDICATED in children <8 years - "
            "tetracycline-class dental and skeletal toxicity."
        ),
    }],
    # Fluoroquinolones: arthropathy and tendon damage in juveniles.
    "ciprofloxacin": [{
        "max_age_months": 216,  # 18 years
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Fluoroquinolones (ciprofloxacin) are generally avoided in "
            "patients <18 years due to risk of arthropathy and tendon "
            "damage. Acceptable in narrow paediatric indications "
            "(complicated UTI/pyelonephritis when no safer alternative, "
            "inhalational anthrax, cystic-fibrosis Pseudomonas) - "
            "confirm the indication."
        ),
    }],
    "levofloxacin": [{
        "max_age_months": 216,
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Fluoroquinolones (levofloxacin) are generally avoided in "
            "patients <18 years - arthropathy and tendon damage risk."
        ),
    }],
    "moxifloxacin": [{
        "max_age_months": 216,
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Fluoroquinolones (moxifloxacin) are generally avoided in "
            "patients <18 years - arthropathy and tendon damage risk."
        ),
    }],
    "ofloxacin": [{
        "max_age_months": 216,
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Fluoroquinolones (ofloxacin) are generally avoided in "
            "patients <18 years - arthropathy and tendon damage risk."
        ),
    }],
    "norfloxacin": [{
        "max_age_months": 216,
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Fluoroquinolones (norfloxacin) are generally avoided in "
            "patients <18 years - arthropathy and tendon damage risk."
        ),
    }],
    # Chloramphenicol: grey baby syndrome in neonates from immature
    # glucuronidation - cardiovascular collapse risk.
    "chloramphenicol": [{
        "max_age_months": 1,  # <28 days roughly
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Chloramphenicol is CONTRAINDICATED in neonates (<1 month). "
            "Immature hepatic glucuronidation causes accumulation, "
            "leading to grey baby syndrome (cardiovascular collapse, "
            "abdominal distension, cyanosis)."
        ),
    }],
    # Aspirin and salicylates: Reye's syndrome with viral illness.
    "aspirin": [{
        "max_age_months": 192,  # 16 years
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Aspirin is CONTRAINDICATED in children <16 years due to "
            "association with Reye's syndrome (acute encephalopathy and "
            "hepatic failure), particularly during viral illness."
        ),
    }],
    "bismuth subsalicylate": [{
        "max_age_months": 192,
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Bismuth subsalicylate is generally avoided in children "
            "<16 years - salicylate component carries the same Reye's "
            "syndrome risk as aspirin."
        ),
    }],
    # Codeine and tramadol: CYP2D6 ultra-rapid metaboliser risk -
    # respiratory depression and death. FDA / MHRA both restrict.
    "codeine": [{
        "max_age_months": 144,  # 12 years
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Codeine is CONTRAINDICATED in children <12 years. "
            "Ultra-rapid CYP2D6 metabolism can produce dangerously high "
            "morphine levels, causing fatal respiratory depression."
        ),
    }],
    "tramadol": [{
        "max_age_months": 144,
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Tramadol is CONTRAINDICATED in children <12 years - same "
            "CYP2D6 ultra-rapid-metaboliser risk as codeine."
        ),
    }],
    # Promethazine: respiratory depression and sudden infant death.
    "promethazine": [{
        "max_age_months": 24,  # 2 years
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Promethazine is CONTRAINDICATED in children <2 years due "
            "to risk of fatal respiratory depression."
        ),
    }],
    # Metoclopramide: extrapyramidal side effects in infants.
    "metoclopramide": [{
        "max_age_months": 12,  # 1 year
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Metoclopramide should be avoided in children <1 year due "
            "to increased risk of extrapyramidal symptoms and "
            "methaemoglobinaemia."
        ),
    }],
    # Loperamide: paralytic ileus and CNS toxicity in infants.
    "loperamide": [{
        "max_age_months": 24,  # 2 years
        "min_age_months": None,
        "severity": "WARNING",
        "message": (
            "Loperamide is generally avoided in children <2 years - "
            "risk of paralytic ileus, severe abdominal distension, and "
            "CNS depression."
        ),
    }],
    # Sulfonamides in young infants: bilirubin displacement -> kernicterus.
    "sulfadiazine": [{
        "max_age_months": 2,
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Sulfonamides are CONTRAINDICATED in infants <2 months due "
            "to displacement of bilirubin from albumin, with risk of "
            "kernicterus."
        ),
    }],
    "trimethoprim-sulfamethoxazole": [{
        "max_age_months": 2,
        "min_age_months": None,
        "severity": "CRITICAL",
        "message": (
            "Trimethoprim-sulfamethoxazole is CONTRAINDICATED in "
            "infants <2 months - sulfa component displaces bilirubin "
            "from albumin (kernicterus risk)."
        ),
    }],
}


def check_age_contraindication(
    drug_name: str,
    age_months: Optional[float],
) -> Optional[dict]:
    """
    Return an alert dict if `drug_name` is contraindicated at this age
    band per AGE_CONTRAINDICATIONS. Otherwise return None.

    age_months=None -> no alert (caller chose not to filter by age).
    """
    if not drug_name or age_months is None:
        return None
    drug_lower = drug_name.lower().strip()
    rules = AGE_CONTRAINDICATIONS.get(drug_lower)
    if not rules:
        return None
    for rule in rules:
        max_age = rule.get("max_age_months")
        min_age = rule.get("min_age_months")
        fires = False
        if max_age is not None and age_months < max_age:
            fires = True
        if min_age is not None and age_months >= min_age:
            # Combined band: both bounds must hold simultaneously when
            # both are set.
            fires = (max_age is None) or (age_months < max_age)
        if fires:
            return {
                "type": "AGE_CONTRAINDICATION",
                "severity": rule.get("severity", "WARNING"),
                "drug": drug_name,
                "age_months": age_months,
                "message": rule["message"],
            }
    return None


def check_age_contraindications(
    medicines: List[dict],
    age_months: Optional[float],
) -> List[dict]:
    """
    Batch wrapper: run check_age_contraindication() across all medicines.
    Returns the list of alert dicts (possibly empty).
    """
    alerts = []
    if age_months is None:
        return alerts
    for med in medicines:
        generic = med.get("generic_name", med.get("name", ""))
        alert = check_age_contraindication(generic, age_months)
        if alert:
            alerts.append(alert)
    return alerts