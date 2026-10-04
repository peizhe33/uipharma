"""
SmartPharma RAGAS Evaluation Script
====================================
Evaluates the RAG retrieval pipeline using LLM-as-judge metrics:
  - Faithfulness
  - Answer Relevancy
  - Context Precision
  - Context Recall (requires ground_truth)

Requirements:
  pip install requests    (you already have this)

Usage:
  1. Ensure Ollama is running (port 11434) with your Qwen model
  2. Ensure Flask backend is running (port 5009): python app.py
  3. Run:  python ragas_eval.py
  4. Optional:  python ragas_eval.py --cases TC01 TC03

Output:
  - Console table with per-case and aggregate scores
  - ragas_results.csv
"""

import argparse
import json
import sys
import time
import csv
from datetime import datetime

import requests


# ---------------------------------------------------------------------------
# Configuration  (matched to your config.py)
# ---------------------------------------------------------------------------
FLASK_BASE_URL = "http://127.0.0.1:5009"
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:7b-instruct-q4_K_M"

OUTPUT_CSV = "ragas_results.csv"


# ---------------------------------------------------------------------------
# Test cases  — uses the EXACT payload format your /ask endpoint expects
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "id": "TC01",
        "description": "CAP adult - correct amoxicillin/clavulanate",
        "ground_truth": (
            "Amoxicillin/clavulanate 1.2g IV every 8 hours for 5-7 days is the "
            "recommended first-line treatment for community-acquired pneumonia "
            "(suspected bacterial) according to the UMMC antimicrobial guidelines."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 45, "k": 5,
            "patient": {"name": "Test A", "id": "RAGAS_TC01", "ward_room": "A101", "gender": "Male", "height": "170", "weight": "70", "blood_type": "O+"},
            "vitals": {"date": "2026-06-10", "temperature": "38.5", "blood_pressure": "120/80", "heart_rate": "90", "spo2": "95", "urine_output": "50", "allergy_details": "NKDA", "renal_function": "Normal"},
            "labs": {"creatinine": "0.9", "egfr": "90", "wbc": "14"},
            "diagnosis": "Community acquired pneumonia, suspected bacterial",
            "prescribed_medicines": [
                {"name": "Amoxicillin/clavulanate", "dose": "1.2", "unit": "g", "frequency": "Every 8 hours", "route": "IV", "prn": False}
            ]
        }
    },
    {
        "id": "TC02",
        "description": "UTI adult - wrong drug (amoxicillin mono)",
        "ground_truth": (
            "Amoxicillin monotherapy is not a recommended first-line treatment "
            "for acute uncomplicated cystitis. The UMMC guidelines recommend "
            "nitrofurantoin 100mg twice daily for 5 days or fosfomycin 3g single dose."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 30, "k": 5,
            "patient": {"name": "Test B", "id": "RAGAS_TC02", "ward_room": "B201", "gender": "Female", "height": "160", "weight": "55", "blood_type": "A+"},
            "vitals": {"date": "2026-06-10", "temperature": "37.2", "blood_pressure": "110/70", "heart_rate": "78", "spo2": "98", "urine_output": "60", "allergy_details": "NKDA", "renal_function": "Normal"},
            "labs": {"creatinine": "0.7", "egfr": "110", "wbc": "11"},
            "diagnosis": "Acute uncomplicated cystitis",
            "prescribed_medicines": [
                {"name": "Amoxicillin", "dose": "500", "unit": "mg", "frequency": "Three times a day", "route": "PO", "prn": False}
            ]
        }
    },
    {
        "id": "TC03",
        "description": "CAP - penicillin allergy (anaphylaxis)",
        "ground_truth": (
            "Amoxicillin/clavulanate is contraindicated in patients with severe "
            "penicillin allergy (anaphylaxis) due to cross-reactivity risk. "
            "Alternative regimens should be considered."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 50, "k": 5,
            "patient": {"name": "Test C", "id": "RAGAS_TC03", "ward_room": "C301", "gender": "Male", "height": "175", "weight": "75", "blood_type": "B+"},
            "vitals": {"date": "2026-06-10", "temperature": "38.8", "blood_pressure": "130/85", "heart_rate": "100", "spo2": "93", "urine_output": "45", "allergy_details": "Penicillin (anaphylaxis)", "renal_function": "Normal"},
            "labs": {"creatinine": "1.0", "egfr": "85", "wbc": "16"},
            "diagnosis": "Community acquired pneumonia, suspected bacterial",
            "prescribed_medicines": [
                {"name": "Amoxicillin/clavulanate", "dose": "1.2", "unit": "g", "frequency": "Every 8 hours", "route": "IV", "prn": False}
            ]
        }
    },
    {
        "id": "TC04",
        "description": "Pyelonephritis - renal impairment eGFR 20",
        "ground_truth": (
            "Ceftriaxone does not require dose adjustment in renal impairment. "
            "2g IV once daily is appropriate for acute pyelonephritis."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 65, "k": 5,
            "patient": {"name": "Test D", "id": "RAGAS_TC04", "ward_room": "D401", "gender": "Female", "height": "155", "weight": "60", "blood_type": "AB+"},
            "vitals": {"date": "2026-06-10", "temperature": "39.0", "blood_pressure": "100/65", "heart_rate": "110", "spo2": "94", "urine_output": "30", "allergy_details": "NKDA", "renal_function": "Impaired"},
            "labs": {"creatinine": "3.2", "egfr": "20", "wbc": "18"},
            "diagnosis": "Acute pyelonephritis",
            "prescribed_medicines": [
                {"name": "Ceftriaxone", "dose": "2", "unit": "g", "frequency": "Once a day", "route": "IV", "prn": False}
            ]
        }
    },
    {
        "id": "TC05",
        "description": "SSTI cellulitis - correct cloxacillin",
        "ground_truth": (
            "Cloxacillin 1g IV every 6 hours is appropriate for non-purulent "
            "cellulitis according to UMMC skin and soft tissue infection guidelines."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 40, "k": 5,
            "patient": {"name": "Test E", "id": "RAGAS_TC05", "ward_room": "E501", "gender": "Male", "height": "175", "weight": "80", "blood_type": "O-"},
            "vitals": {"date": "2026-06-10", "temperature": "38.2", "blood_pressure": "125/80", "heart_rate": "88", "spo2": "97", "urine_output": "55", "allergy_details": "NKDA", "renal_function": "Normal"},
            "labs": {"creatinine": "0.8", "egfr": "100", "wbc": "13"},
            "diagnosis": "Cellulitis / skin and soft tissue infection",
            "prescribed_medicines": [
                {"name": "Cloxacillin", "dose": "1", "unit": "g", "frequency": "Every 6 hours", "route": "IV", "prn": False}
            ]
        }
    },
    {
        "id": "TC06",
        "description": "Paediatric UTI - nitrofurantoin + G6PD",
        "ground_truth": (
            "Nitrofurantoin is contraindicated in patients with G6PD deficiency "
            "due to the risk of haemolytic anaemia."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 5, "k": 5,
            "patient": {"name": "Test F", "id": "RAGAS_TC06", "ward_room": "P101", "gender": "Male", "height": "110", "weight": "18", "blood_type": "O+"},
            "vitals": {"date": "2026-06-10", "temperature": "38.0", "blood_pressure": "90/60", "heart_rate": "120", "spo2": "97", "urine_output": "30", "allergy_details": "NKDA", "renal_function": "Normal", "g6pd_status": "Deficient"},
            "labs": {"creatinine": "0.3", "egfr": "120", "wbc": "12"},
            "diagnosis": "Acute cystitis",
            "prescribed_medicines": [
                {"name": "Nitrofurantoin", "dose": "50", "unit": "mg", "frequency": "Twice a day", "route": "PO", "prn": False}
            ]
        }
    },
    {
        "id": "TC07",
        "description": "CAP multi-drug with supportive care",
        "ground_truth": (
            "For community-acquired pneumonia, the UMMC guidelines recommend "
            "amoxicillin/clavulanate 1.2g IV every 8 hours or ceftriaxone 2g IV "
            "once daily. Azithromycin may be added for atypical cover. "
            "Paracetamol is appropriate supportive care."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 22, "k": 5,
            "patient": {"name": "See Seng Hong", "id": "RAGAS_TC07", "ward_room": "A101", "gender": "Male", "height": "160", "weight": "78", "blood_type": "O+"},
            "vitals": {"date": "2026-06-10", "temperature": "38.6", "blood_pressure": "118/76", "heart_rate": "105", "spo2": "92", "urine_output": "40", "allergy_details": "NKDA", "renal_function": "Normal"},
            "labs": {"creatinine": "1.2", "egfr": "75", "lactate": "1.8", "wbc": "15"},
            "diagnosis": "Community acquired pneumonia, suspected bacterial",
            "prescribed_medicines": [
                {"name": "Ceftriaxone", "dose": "1", "unit": "g", "frequency": "Once a day", "route": "IV", "prn": False},
                {"name": "Azithromycin", "dose": "500", "unit": "mg", "frequency": "Once a day", "route": "PO", "prn": False},
                {"name": "Paracetamol", "dose": "1000", "unit": "mg", "frequency": "Every 6 hours", "route": "PO", "prn": True}
            ]
        }
    },
    {
        "id": "TC08",
        "description": "Meningitis - ceftriaxone 2g q12H",
        "ground_truth": (
            "Ceftriaxone 2g IV every 12 hours is the recommended empiric therapy "
            "for suspected bacterial meningitis in adults per UMMC CNS guidelines."
        ),
        "payload": {
            "question": "Verify the safety and appropriateness of the prescribed medications for this patient based on UMMC Antimicrobial Guidelines.",
            "age": 35, "k": 5,
            "patient": {"name": "Test G", "id": "RAGAS_TC08", "ward_room": "ICU", "gender": "Female", "height": "165", "weight": "65", "blood_type": "A-"},
            "vitals": {"date": "2026-06-10", "temperature": "39.5", "blood_pressure": "90/60", "heart_rate": "115", "spo2": "96", "urine_output": "35", "allergy_details": "NKDA", "renal_function": "Normal"},
            "labs": {"creatinine": "0.9", "egfr": "95", "wbc": "20"},
            "diagnosis": "Suspected bacterial meningitis",
            "prescribed_medicines": [
                {"name": "Ceftriaxone", "dose": "2", "unit": "g", "frequency": "Every 12 hours", "route": "IV", "prn": False}
            ]
        }
    },
]


# ---------------------------------------------------------------------------
# Call SmartPharma /ask endpoint
# ---------------------------------------------------------------------------
def call_smartpharma(payload):
    url = f"{FLASK_BASE_URL}/ask"
    try:
        resp = requests.post(url, json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        answer = data.get("answer", "")
        retrieved = data.get("retrieved", [])
        contexts = [item["text"] for item in retrieved if item.get("text")]
        return {"answer": answer, "contexts": contexts, "raw": data}
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot connect to {url}. Is app.py running?")
        return {"answer": "", "contexts": [], "raw": {}}
    except Exception as e:
        print(f"  [ERROR] API call failed: {e}")
        return {"answer": "", "contexts": [], "raw": {}}


# ---------------------------------------------------------------------------
# Ollama helper
# ---------------------------------------------------------------------------
def call_ollama(prompt, temperature=0.0):
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": temperature, "num_predict": 512}},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        print(f"  [ERROR] Ollama call failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# RAGAS metrics (LLM-as-judge via Ollama)
# ---------------------------------------------------------------------------
def evaluate_faithfulness(answer, contexts):
    if not answer or not contexts:
        return 0.0
    context_block = "\n---\n".join(contexts[:5])
    claims_text = call_ollama(
        "Extract all factual claims from the following medical verification "
        "response. List each claim on a separate numbered line. Only include "
        "factual assertions, not transitional phrases.\n\n"
        f"Response:\n{answer[:2000]}\n\nClaims:"
    )
    claims = [l.strip() for l in claims_text.strip().split("\n")
              if l.strip() and any(c.isalpha() for c in l)]
    if not claims:
        return 1.0
    supported = 0
    for claim in claims:
        verdict = call_ollama(
            "Determine whether the following claim is supported by the "
            "provided context. Answer ONLY 'SUPPORTED' or 'NOT SUPPORTED'.\n\n"
            f"Context:\n{context_block}\n\nClaim: {claim}\n\nVerdict:"
        ).strip().upper()
        if "SUPPORTED" in verdict and "NOT" not in verdict:
            supported += 1
    return supported / len(claims)


def evaluate_answer_relevancy(question, answer):
    if not answer:
        return 0.0
    score_text = call_ollama(
        "On a scale of 0.0 to 1.0, rate how relevant the following "
        "prescription verification answer is to the clinical question. "
        "1.0 means it directly addresses the prescription safety check. "
        "0.0 means completely off-topic. "
        "Respond with ONLY a decimal number.\n\n"
        f"Question: {question}\n\nAnswer: {answer[:2000]}\n\nRelevancy score:"
    ).strip()
    try:
        score = float(score_text.split()[0].strip(".,;:"))
        return max(0.0, min(1.0, score))
    except (ValueError, IndexError):
        return 0.5


def evaluate_context_precision(question, contexts):
    if not contexts:
        return 0.0
    relevant_at = []
    for i, chunk in enumerate(contexts):
        verdict = call_ollama(
            "Is the following retrieved guideline chunk relevant to answering "
            "the clinical question? Answer ONLY 'RELEVANT' or 'NOT RELEVANT'.\n\n"
            f"Question: {question}\n\nRetrieved chunk:\n{chunk[:800]}\n\nVerdict:"
        ).strip().upper()
        if "RELEVANT" in verdict and "NOT" not in verdict:
            relevant_at.append(i + 1)
    if not relevant_at:
        return 0.0
    precisions, relevant_count = [], 0
    for k in range(1, len(contexts) + 1):
        if k in relevant_at:
            relevant_count += 1
            precisions.append(relevant_count / k)
    return sum(precisions) / len(precisions) if precisions else 0.0


def evaluate_context_recall(ground_truth, contexts):
    if not ground_truth or not contexts:
        return 0.0
    context_block = "\n---\n".join(contexts[:5])
    gt_sentences = [s.strip() for s in ground_truth.replace(". ", ".\n").split("\n") if s.strip()]
    if not gt_sentences:
        return 1.0
    attributed = 0
    for sentence in gt_sentences:
        verdict = call_ollama(
            "Can the following ground-truth statement be attributed to or "
            "supported by the retrieved context? Answer ONLY 'YES' or 'NO'.\n\n"
            f"Context:\n{context_block}\n\nStatement: {sentence}\n\nAnswer:"
        ).strip().upper()
        if verdict.startswith("YES"):
            attributed += 1
    return attributed / len(gt_sentences)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="SmartPharma RAGAS Evaluation")
    parser.add_argument("--cases", nargs="*", default=None,
                        help="Run only specific test case IDs (e.g. TC01 TC03)")
    args = parser.parse_args()

    cases = TEST_CASES
    if args.cases:
        cases = [tc for tc in TEST_CASES if tc["id"] in args.cases]
        if not cases:
            print(f"[ERROR] No matching test cases for: {args.cases}")
            sys.exit(1)

    print("=" * 78)
    print("  SmartPharma RAGAS Evaluation")
    print(f"  Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Test cases: {len(cases)}")
    print(f"  LLM judge:  {OLLAMA_MODEL}")
    print("=" * 78)

    # Pre-flight checks
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"  Ollama models: {models}")
    except Exception:
        print(f"  [ERROR] Cannot connect to Ollama at {OLLAMA_BASE_URL}")
        sys.exit(1)

    try:
        resp = requests.get(f"{FLASK_BASE_URL}/health", timeout=5)
        resp.raise_for_status()
        h = resp.json()
        print(f"  Flask backend: OK ({h.get('docs', '?')} docs, model={h.get('model', '?')})")
    except Exception:
        print(f"  [ERROR] Cannot connect to Flask at {FLASK_BASE_URL}")
        print(f"  Start it first:  python app.py")
        sys.exit(1)

    # Step 1: Collect responses
    print("\n--- Step 1: Sending test prescriptions to /ask ---")
    results = []
    for tc in cases:
        print(f"\n  [{tc['id']}] {tc['description']}")
        t0 = time.time()
        response = call_smartpharma(tc["payload"])
        elapsed = time.time() - t0
        answer = response["answer"]
        contexts = response["contexts"]
        print(f"    Response time: {elapsed:.1f}s | Answer: {len(answer)} chars | Contexts: {len(contexts)}")
        if not answer:
            print("    [WARN] Empty answer - check Flask terminal for errors")
        if not contexts:
            print("    [WARN] No contexts - faithfulness/precision will score 0")

        diag = tc["payload"].get("diagnosis", "")
        drugs = ", ".join(
            f"{m['name']} {m['dose']}{m['unit']} {m['route']} {m['frequency']}"
            for m in tc["payload"].get("prescribed_medicines", [])
        )
        results.append({
            "id": tc["id"], "description": tc["description"],
            "question": f"Verify the safety of prescribing {drugs} for {diag}",
            "ground_truth": tc["ground_truth"],
            "answer": answer, "contexts": contexts,
        })

    # Step 2: Evaluate
    print("\n--- Step 2: Running RAGAS evaluation (LLM-as-judge) ---")
    print("  ~2-5 min per case depending on your GPU...\n")
    metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    for r in results:
        print(f"  [{r['id']}] {r['description']}")
        t0 = time.time()
        r["faithfulness"] = evaluate_faithfulness(r["answer"], r["contexts"])
        print(f"    Faithfulness:       {r['faithfulness']:.4f}")
        r["answer_relevancy"] = evaluate_answer_relevancy(r["question"], r["answer"])
        print(f"    Answer Relevancy:   {r['answer_relevancy']:.4f}")
        r["context_precision"] = evaluate_context_precision(r["question"], r["contexts"])
        print(f"    Context Precision:  {r['context_precision']:.4f}")
        r["context_recall"] = evaluate_context_recall(r["ground_truth"], r["contexts"])
        print(f"    Context Recall:     {r['context_recall']:.4f}")
        print(f"    Eval time: {time.time() - t0:.1f}s\n")

    # Step 3: Display
    print("=" * 78)
    print("  RAGAS EVALUATION RESULTS")
    print("=" * 78)
    header = f"{'ID':<6} {'Description':<42} {'Faith':>7} {'Relev':>7} {'Prec':>7} {'Recall':>7}"
    print(header)
    print("-" * 78)
    for r in results:
        print(f"{r['id']:<6} {r['description'][:40]:<42} "
              f"{r.get('faithfulness',0):>7.4f} {r.get('answer_relevancy',0):>7.4f} "
              f"{r.get('context_precision',0):>7.4f} {r.get('context_recall',0):>7.4f}")
    print("-" * 78)
    avgs = {m: sum(r.get(m,0) for r in results)/len(results) for m in metrics}
    print(f"{'AVG':<6} {'':42} {avgs['faithfulness']:>7.4f} {avgs['answer_relevancy']:>7.4f} "
          f"{avgs['context_precision']:>7.4f} {avgs['context_recall']:>7.4f}")
    overall = sum(avgs.values()) / len(avgs)
    print(f"\n  Overall RAGAS Score (mean of 4 metrics): {overall:.4f}")

    # Step 4: CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Case ID", "Description", "Faithfulness", "Answer Relevancy",
                     "Context Precision", "Context Recall", "Overall"])
        for r in results:
            co = sum(r.get(m,0) for m in metrics) / len(metrics)
            w.writerow([r["id"], r["description"],
                        f"{r.get('faithfulness',0):.4f}", f"{r.get('answer_relevancy',0):.4f}",
                        f"{r.get('context_precision',0):.4f}", f"{r.get('context_recall',0):.4f}",
                        f"{co:.4f}"])
        w.writerow(["AVERAGE", "", f"{avgs['faithfulness']:.4f}", f"{avgs['answer_relevancy']:.4f}",
                     f"{avgs['context_precision']:.4f}", f"{avgs['context_recall']:.4f}",
                     f"{overall:.4f}"])
    print(f"\n  Results saved to: {OUTPUT_CSV}")
    print("=" * 78)


if __name__ == "__main__":
    main()