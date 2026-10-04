from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-7B-Instruct")

# ─────────────────────────────────────────────
# FULL OUTPUT (includes overhead: Clinical Flags,
# Verification line, References list)
# ─────────────────────────────────────────────
full_output_with_overhead = """
AI Explanation & Citations

Assessment: CRITICAL safety issues detected (1). Review alerts and consider immediate intervention.
Diagnosis: Cellulitis / skin and soft tissue infection

Clinical Flags:
- ALLERGY: CRITICAL ALLERGY CONFLICT: Patient is allergic to PENICILLIN. cloxacillin contains/IS penicillin - DO NOT ADMINISTER. Recommend immediate discontinuation. Do NOT suggest dose adjustments for contraindicated drugs.
- ALLERGY: CROSS-SENSITIVITY (mild reaction documented): Patient has a penicillin allergy described as a mild reaction (e.g. rash). cefalexin is a cephalosporin (1st gen), which carries a low but non-zero cross-reactivity risk with penicillin. Use only after a documented allergy-risk review; a non-beta-lactam alternative (e.g. clindamycin) is preferred when clinically equivalent.
- Metronidazole is not routinely indicated for uncomplicated cellulitis or skin/soft tissue infections. It is only used when anaerobic coverage is needed (bite wounds, contaminated wounds, necrotising infections, polymicrobial infections).
- CLASS OVERLAP: WARNING - Therapeutic redundancy: cloxacillin, cefalexin are both beta-lactam antibiotics. Prescribing multiple drugs from the same class for the same indication is usually redundant. Verify if both are intended (e.g., step-down therapy, different infection sites).

--- cloxacillin ---
Assessment: Unsafe
Issues:
- CRITICAL ALLERGY CONFLICT: Patient is allergic to PENICILLIN. cloxacillin contains/IS penicillin - DO NOT ADMINISTER. Recommend immediate discontinuation. Do NOT suggest dose adjustments for contraindicated drugs.
- WARNING - Therapeutic redundancy: cloxacillin, cefalexin are both beta-lactam antibiotics. Prescribing multiple drugs from the same class for the same indication is usually redundant. Verify if both are intended (e.g., step-down therapy, different infection sites).
Recommendation: It is recommended to discontinue cloxacillin due to the safety alert above and consult the prescriber for an alternative [1][2].

--- clindamycin ---
Assessment: Safe
Issues: None
Recommendation: Continue

--- cefalexin ---
Assessment: Needs Review
Issues:
- CROSS-SENSITIVITY (mild reaction documented): Patient has a penicillin allergy described as a mild reaction (e.g. rash). cefalexin is a cephalosporin (1st gen), which carries a low but non-zero cross-reactivity risk with penicillin. Use only after a documented allergy-risk review; a non-beta-lactam alternative (e.g. clindamycin) is preferred when clinically equivalent.
- WARNING - Therapeutic redundancy: cloxacillin, cefalexin are both beta-lactam antibiotics. Prescribing multiple drugs from the same class for the same indication is usually redundant. Verify if both are intended (e.g., step-down therapy, different infection sites).
Recommendation: It is recommended to review cefalexin with the prescriber given the alert(s) above [1][2].

--- metronidazole ---
Assessment: Unsafe
Issues:
- Metronidazole is not routinely indicated for 'Cellulitis / skin and soft tissue infection'. Metronidazole is not routinely indicated for uncomplicated cellulitis or skin/soft tissue infections. It is only used when anaerobic coverage is needed (bite wounds, contaminated wounds, necrotising infections, polymicrobial infections).
Recommendation: It is recommended to discontinue metronidazole and switch to a guideline-recommended alternative, since metronidazole is not routinely indicated for 'Cellulitis / skin and soft tissue infection' [5].

Monitoring:
clindamycin:
    * Signs of C. difficile-associated diarrhoea
    * LFTs if prolonged

metronidazole:
    * LFTs if prolonged use
    * Peripheral neuropathy if prolonged use
    * Avoid alcohol (disulfiram-like reaction)

Verification: AI-generated analysis based on UMMC Antimicrobial Guidelines 3rd Edition, MOH Anticoagulant Quick Guide 1st Edition, and clinical knowledge. Clinical judgment required before acting on these recommendations.

References:
[1] 4.10 Skin and Soft Tissue Infections_3rd Ed (pg 1)
[2] 3.10 Skin and Soft Tissue Infections_3rd Ed (pg 4)
[3] 3.10 Skin and Soft Tissue Infections_3rd Ed (pg 7)
[4] 3.10 Skin and Soft Tissue Infections_3rd Ed (pg 6)
[5] 3.10 Skin and Soft Tissue Infections_3rd Ed (pg 11)
"""

# ─────────────────────────────────────────────
# PER-DRUG SECTIONS ONLY (no overhead)
# ─────────────────────────────────────────────
per_drug_sections_only = """
--- cloxacillin ---
Assessment: Unsafe
Issues:
- CRITICAL ALLERGY CONFLICT: Patient is allergic to PENICILLIN. cloxacillin contains/IS penicillin - DO NOT ADMINISTER. Recommend immediate discontinuation. Do NOT suggest dose adjustments for contraindicated drugs.
- WARNING - Therapeutic redundancy: cloxacillin, cefalexin are both beta-lactam antibiotics. Prescribing multiple drugs from the same class for the same indication is usually redundant. Verify if both are intended (e.g., step-down therapy, different infection sites).
Recommendation: It is recommended to discontinue cloxacillin due to the safety alert above and consult the prescriber for an alternative [1][2].

--- clindamycin ---
Assessment: Safe
Issues: None
Recommendation: Continue

--- cefalexin ---
Assessment: Needs Review
Issues:
- CROSS-SENSITIVITY (mild reaction documented): Patient has a penicillin allergy described as a mild reaction (e.g. rash). cefalexin is a cephalosporin (1st gen), which carries a low but non-zero cross-reactivity risk with penicillin. Use only after a documented allergy-risk review; a non-beta-lactam alternative (e.g. clindamycin) is preferred when clinically equivalent.
- WARNING - Therapeutic redundancy: cloxacillin, cefalexin are both beta-lactam antibiotics. Prescribing multiple drugs from the same class for the same indication is usually redundant. Verify if both are intended (e.g., step-down therapy, different infection sites).
Recommendation: It is recommended to review cefalexin with the prescriber given the alert(s) above [1][2].

--- metronidazole ---
Assessment: Unsafe
Issues:
- Metronidazole is not routinely indicated for 'Cellulitis / skin and soft tissue infection'. Metronidazole is not routinely indicated for uncomplicated cellulitis or skin/soft tissue infections. It is only used when anaerobic coverage is needed (bite wounds, contaminated wounds, necrotising infections, polymicrobial infections).
Recommendation: It is recommended to discontinue metronidazole and switch to a guideline-recommended alternative, since metronidazole is not routinely indicated for 'Cellulitis / skin and soft tissue infection' [5].

"""

# ─────────────────────────────────────────────
# COMPACT FORM (single Safe drug)
# ─────────────────────────────────────────────
compact_sample = """
--- ceftriaxone ---
Assessment: Safe
Issues:
- None
Recommendation: Continue
"""

# ─────────────────────────────────────────────
# MEASUREMENTS
# ─────────────────────────────────────────────
full_with_overhead_tokens = len(tokenizer.encode(full_output_with_overhead))
per_drug_tokens           = len(tokenizer.encode(per_drug_sections_only))
overhead_tokens           = full_with_overhead_tokens - per_drug_tokens
compact_tokens            = len(tokenizer.encode(compact_sample))
num_drugs                 = 4
per_drug_average          = round(per_drug_tokens / num_drugs)

print("=" * 50)
print(f"Full output (with overhead) : {full_with_overhead_tokens} tokens")
print(f"Per-drug sections only      : {per_drug_tokens} tokens")
print(f"Overhead (flags + refs etc) : {overhead_tokens} tokens")
print(f"Compact form (single drug)  : {compact_tokens} tokens")
print("-" * 50)
print(f"Number of drugs in sample   : {num_drugs}")
print(f"Average tokens per drug     : {per_drug_average} tokens")
print("-" * 50)
print(f"Worst-case observed output  : {full_with_overhead_tokens} tokens")
print(f"Budget set to               : 1500 tokens")
print(f"Safety margin               : {1500 - full_with_overhead_tokens} tokens")
print(f"Safety margin percentage    : {round((1500 - full_with_overhead_tokens) / 1500 * 100)}%")
print("=" * 50)