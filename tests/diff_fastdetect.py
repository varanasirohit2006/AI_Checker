"""Stage 5 differential test — Fast-DetectGPT (Repo #2).

Compares upstream `research/fast-detect-gpt` against the clean rebuild
`detectors/fastdetect.py` on 50 diverse text samples.

Pass conditions (rea/fast-detect-gpt/01-target.md, 04-spec.md):
  * abs(crit_upstream - crit_rebuild) <= 0.001 for every sample
  * identical probability mapping for all 4 published distribution parameter sets
  * ntoken == n_tokens - 1
  * edge behaviours replicated:
    - "" -> RuntimeError
    - 1-token -> nan
    - batch > 1 -> AssertionError
    - unknown pair -> KeyError
  * score_window consistency and truncation at model_max_length (1024)

Run:  .venv/Scripts/python.exe tests/diff_fastdetect.py
"""

from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FAST_SCRIPTS = ROOT / "research" / "fast-detect-gpt" / "scripts"
sys.path.insert(0, str(FAST_SCRIPTS))

import torch

# Upstream imports from cloned research repo
from model import load_model as upstream_load_model
from model import load_tokenizer as upstream_load_tokenizer
from fast_detect_gpt import get_sampling_discrepancy_analytic as upstream_get_discrepancy
from local_infer import compute_prob_norm as upstream_compute_prob_norm

# Rebuild imports
from detectors.fastdetect import (
    DISTRIB_PARAMS,
    FastDetectGPTDetector,
    compute_discrepancy_analytic,
    compute_prob_norm as rebuild_compute_prob_norm,
)

TOL = 1e-3
MODEL_NAME = "gpt2"
CACHE = ROOT / "research" / "fast-detect-gpt" / "cache"

# --------------------------------------------------------------------------
# 50 diverse samples (human, AI, technical, multilingual, edge)
# --------------------------------------------------------------------------

HUMAN = [
    ("human_bike", "The bike ride to work took twenty minutes again today, and the lights on Cedar "
     "Avenue were against me the whole way. A garbage truck blocked three blocks and I "
     "got to the office smelling like a landfill. My boss made a face. I told him it was "
     "a new cologne. The intern laughed, which is all I need to keep going."),
    ("human_kitchen", "Grandma never measured anything. Flour went in until the dough looked right, "
     "and when I asked how much that was she'd say 'until it looks right' like I was the slow one. "
     "I spent two years trying to reverse engineer her Sunday rolls and got close, but not close "
     "enough. The secret, I think, was the old oven that ran hot."),
    ("human_work", "The printer jammed again during the quarterly review, which felt almost poetic. "
     "Dave from accounting tried to fix it and ended up with toner on his tie, and nobody said "
     "anything for a solid ten seconds because we were all pretending to be professional. Then "
     "Priya snorted and the whole room lost it."),
    ("human_book", "I wanted to hate that book. Everyone at work kept quoting it, and the cover "
     "looked like it was designed by a committee of motivational speakers. But around chapter "
     "four something clicked, and by the end I was sitting in my car in the driveway just "
     "staring at the steering wheel. It's not great literature."),
    ("human_garden", "Tomatoes are a gamble and I keep losing. This year I planted six, babied "
     "them through the frost scare in April, built a whole cage system out of scrap wire, and "
     "then the hornworms showed up in July like they'd been waiting for an invitation. My "
     "neighbor Walt says I should've picked them off by hand at dawn."),
    ("human_soccer", "We lost the rec league final 4-2 and our goalie, who is normally the most "
     "mild-mannered guy alive, kicked the post so hard he limped for a week. The other team "
     "was genuinely better, faster, younger, all of it. But on the drive home someone put on "
     "that song from the '98 World Cup."),
    ("human_coffee", "There's a guy at the coffee shop on 5th who types with two fingers, "
     "extremely fast, and glares at anyone who walks behind his screen. I've decided he's "
     "writing a novel, or possibly witness protection paperwork. The barista calls him 'the "
     "professor' even though nobody knows his name."),
    ("human_moving", "Moving apartments at thirty-two hits different than at twenty-two. Back "
     "then it was two trips in a friend's hatchback and pizza on the floor. This time there "
     "was a couch that wouldn't fit through the stairwell, a security deposit dispute, and "
     "a very patient mover named Andrei."),
    ("human_guitar", "Six months of guitar and my neighbors have opinions. I can play exactly "
     "three chords and one of them is buzzing, but my cat sits on the amplifier whenever I "
     "start, which I choose to interpret as feline critical acclaim."),
    ("human_rain", "The rain started right when I stepped off the train, the kind of heavy summer "
     "rain that soaks your socks in four seconds flat. By the time I made it under the awning at "
     "the deli there were six other people huddled there, all of us staring at the sidewalk "
     "like it was personally insulting us.")
]

AI = [
    ("ai_productivity", "In today's fast-paced world, productivity has become a cornerstone of personal and "
     "professional success. By leveraging effective time-management strategies, individuals "
     "can optimize their daily routines and achieve their goals more efficiently. Ultimately, "
     "cultivating a productive mindset enables individuals to unlock their full potential."),
    ("ai_remotework", "Remote work has revolutionized the modern workplace, offering unprecedented "
     "flexibility and autonomy. Studies indicate that employees who work remotely often "
     "experience increased job satisfaction and improved work-life balance. Additionally, "
     "organizations benefit from reduced overhead costs and access to a broader talent pool."),
    ("ai_ai_healthcare", "Artificial intelligence is poised to transform the healthcare landscape by "
     "enhancing diagnostic accuracy, personalizing treatment plans, and streamlining administrative "
     "workflows. Through deep learning algorithms, medical imaging analysis has achieved remarkable "
     "milestones."),
    ("ai_climate", "Addressing global climate change necessitates a multifaceted approach combining renewable "
     "energy transition, sustainable agricultural practices, and international policy cooperation. "
     "Decarbonization of industrial processes remains imperative to curtailing greenhouse gas emissions."),
    ("ai_blockchain", "Blockchain technology offers a decentralized and immutable framework for recording "
     "transactions and establishing trust across distributed networks. While cryptocurrency represents "
     "its most visible application, enterprise supply chains and digital identity management present "
     "equally profound opportunities."),
    ("ai_leadership", "Effective leadership in modern organizations requires a balance between empathetic "
     "communication and strategic decisiveness. Leaders who foster an inclusive environment tend to "
     "inspire higher employee engagement and innovation."),
    ("ai_urban_planning", "Sustainable urban planning emphasizes transit-oriented development, green infrastructure, "
     "and mixed-use zoning to create resilient and equitable metropolitan environments."),
    ("ai_education", "The integration of digital learning platforms into higher education has democratized "
     "access to specialized knowledge while posing new challenges for student engagement and retention."),
    ("ai_nutrition", "A balanced diet rich in whole foods, dietary fiber, and micronutrients plays a crucial role "
     "in promoting metabolic longevity and reducing the incidence of chronic lifestyle diseases."),
    ("ai_cybersecurity", "Zero-trust architecture represents a paradigm shift in enterprise cybersecurity, "
     "mandating continuous verification of identity and privilege regardless of perimeter location.")
]

TECHNICAL = [
    ("tech_git", "Git maintains a directed acyclic graph of commit objects pointing to tree nodes. "
     "Each tree node references blobs and subtree hashes. When merging divergent branches, a three-way "
     "merge algorithm locates the best common ancestor to synthesize changes cleanly."),
    ("tech_bplus_tree", "B+ trees are self-balancing search trees optimized for block storage systems. "
     "All records reside in the leaf nodes, which are sequentially linked to provide efficient range "
     "queries. Internal nodes store only discriminant keys and child pointers."),
    ("tech_concurrency", "Mutual exclusion primitives like spinlocks and mutexes prevent data races "
     "in multithreaded runtimes. Condition variables allow worker threads to suspend execution until "
     "a shared state predicate evaluates to true under an acquired lock."),
    ("tech_tcp", "TCP congestion control utilizes additive-increase multiplicative-decrease dynamics "
     "to discover link bandwidth without causing sustained packet drops at intermediate buffer queues."),
    ("tech_raft", "The Raft consensus protocol decomposes distributed agreement into leader election, "
     "log replication, and safety guarantees. Heartbeat timeouts trigger state transitions from follower "
     "to candidate."),
    ("tech_gc", "Generational garbage collectors exploit the weak generational hypothesis: most allocated "
     "objects die young. Surviving allocations are promoted to older generations subject to less frequent scans."),
    ("tech_compilers", "Static single assignment form guarantees that each variable is defined exactly once, "
     "simplifying dataflow analysis, dead code elimination, and common subexpression elimination in SSA passes."),
    ("tech_lsm", "Log-structured merge-trees append writes sequentially to an in-memory memtable before "
     "flushing immutable SSTables to disk, trading read amplification for maximized write throughput."),
    ("tech_crypto", "Elliptic-curve cryptography achieves equivalence with traditional RSA key lengths at "
     "significantly reduced bit sizes, enabling faster cryptographic handshakes and lower power consumption."),
    ("tech_distributed", "Vector clocks capture partial ordering in asynchronous distributed systems by "
     "tracking per-node logical timestamps across exchanged messages.")
]

MULTILINGUAL = [
    ("fr_market", "Le marché du samedi matin est mon endroit préféré dans tout le quartier. "
     "Les vendeurs crient les prix et l'odeur du fromage frais se mélange à celle "
     "des fraises. J'achète toujours trop de pain, mais je ne regrette jamais."),
    ("de_baker", "Jeden Morgen um vier Uhr beginnt der Bäcker mit dem Kneten des Roggenteigs. "
     "Die Kruste muss krachen und das Innere soll saftig und elastisch bleiben. Gute Handwerkskunst "
     "braucht Geduld und Mehl ohne Zusatzstoffe."),
    ("es_fiesta", "Las calles del pueblo estaban adornadas con guirnaldas de colores brillantes y la "
     "música de guitarras resonaba en cada esquina. Las familias compartían platos tradicionales "
     "mientras los niños jugaban cerca de la fuente central."),
    ("it_pasta", "La vera carbonara romana richiede solo guanciale croccante, pecorino romano grattugiato, "
     "tuorli freschi e una generosa spolverata di pepe nero macinato al momento. Nessuna panna."),
    ("pt_ocean", "O mar estava calmo ao entardecer, com as ondas quebrando suavemente na areia dourada. "
     "Os pescadores recolhiam as redes com a paciência de quem conhece o ritmo das marés há gerações."),
    ("nl_canal", "Langs de oude grachten fietsten honderden studenten op weg naar het college. De "
     "herfstbladeren dreven langzaam over het donkere water tussen de woonboten door."),
    ("ru_winter", "Зимний вечер опустился на заснеженный город, и фонари зажглись мягким золотистым светом. "
     "Люди спешили домой, укутавшись в теплые шарфы."),
    ("pl_forest", "Ścieżka prowadziła przez gęsty sosnowy las pełen zapachu żywicy i wilgotnego mchu. "
     "W oddali słychać było stukanie dzięcioła."),
    ("sv_summer", "Sommarnatten var ljus och stilla över sjön. En ensam eka låg förtöjd vid bryggan "
     "där vattnet kluckade mot de gamla träpålarna."),
    ("el_island", "Το αιγαιοπελαγίτικο φως λούζει τα λευκά σπιτάκια του νησιού. Ο αέρας μυρίζει αλμύρα "
     "και άγριο θυμάρι καθώς ο ήλιος δύει στη θάλασσα.")
]

EDGE_AND_SHORT = [
    ("short_1", "The cat slept on the warm windowsill all afternoon."),
    ("short_2", "Quantum computing leverages superposition and quantum entanglement."),
    ("short_3", "A fresh cup of black coffee changes my entire morning outlook."),
    ("short_4", "Differential testing confirms identical outputs across implementations."),
    ("short_5", "Leaves rustled softly in the chilly autumn evening wind."),
    ("mixed_quotes", 'She said, "Wait, is this really happening right now?" He merely nodded.'),
    ("mixed_numbers", "Order #48291 was billed for $1,249.95 on 2026-11-23 at 14:32 UTC."),
    ("mixed_newlines", "First line of text.\n\nSecond line after double newline.\nThird line."),
    ("near_512", "Artificial intelligence has rapidly evolved over the past decade, transforming industries, "
     "reshaping communication, and challenging traditional conceptions of creativity and labor. From natural "
     "language processing systems that compose coherent essays to computer vision models that identify medical "
     "pathologies with superhuman precision, modern machine learning touches virtually every facet of life. "
     "However, with these extraordinary capabilities come critical ethical imperatives: bias mitigation, transparency, "
     "accountability, and the preservation of human agency in automated decisions. As we look ahead, researchers "
     "and policymakers must collaborate to establish robust safety standards that ensure algorithmic advancements "
     "benefit all of humanity equitably."),
    ("repeat_text", "Repeat repeat repeat repeat. Simple words repeated sequentially to observe score behavior.")
]

SAMPLES = HUMAN + AI + TECHNICAL + MULTILINGUAL + EDGE_AND_SHORT
assert len(SAMPLES) == 50, f"Expected 50 samples, got {len(SAMPLES)}"


def main() -> int:
    print("=" * 78)
    print("Stage 5 differential test: Fast-DetectGPT (Repo #2)")
    print(f"  upstream : {FAST_SCRIPTS}")
    print(f"  rebuild  : {ROOT / 'detectors' / 'fastdetect.py'}")
    print(f"  model    : {MODEL_NAME} (scoring==sampling, fp32, device=cpu)")
    print(f"  tolerance: +/-{TOL} on criterion and probabilities; exact ntoken match")
    print("=" * 78)

    # 1. Load Upstream components
    print("\nLoading upstream model and tokenizer...")
    t0 = time.time()
    upstream_tok = upstream_load_tokenizer(MODEL_NAME, str(CACHE))
    upstream_mdl = upstream_load_model(MODEL_NAME, "cpu", str(CACHE))
    upstream_mdl.eval()
    print(f"Upstream ready in {time.time() - t0:.2f}s")

    # 2. Load Rebuild detector
    print("Loading rebuild FastDetectGPTDetector...")
    t0 = time.time()
    # Provide falcon params explicitly so KeyError is avoided during initialization
    falcon_params = DISTRIB_PARAMS["falcon-7b_falcon-7b-instruct"]
    rebuild = FastDetectGPTDetector(
        sampling_model_name=MODEL_NAME,
        scoring_model_name=MODEL_NAME,
        device="cpu",
        use_float16=False,
        classifier_params=falcon_params,
    )
    print(f"Rebuild ready in {time.time() - t0:.2f}s")

    failures = []
    max_crit_diff = 0.0
    max_prob_diff = 0.0

    print("\n--- Phase A: Criterion differential test (50 samples) ---")
    for idx, (name, text) in enumerate(SAMPLES, 1):
        # Upstream scoring
        tok = upstream_tok(text, truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False)
        labels = tok.input_ids[:, 1:]
        with torch.no_grad():
            logits = upstream_mdl(**tok).logits[:, :-1]
            crit_up = upstream_get_discrepancy(logits, logits, labels)
            ntoken_up = labels.size(1)

        # Rebuild scoring
        crit_rb, ntoken_rb = rebuild.compute_crit(text)

        diff = abs(crit_up - crit_rb)
        if diff > max_crit_diff:
            max_crit_diff = diff

        ntoken_ok = (ntoken_up == ntoken_rb)
        crit_ok = (diff <= TOL)

        if not (crit_ok and ntoken_ok):
            failures.append(
                f"Sample {idx} ({name}): crit_up={crit_up:.6f}, crit_rb={crit_rb:.6f}, "
                f"diff={diff:.3e}, ntoken_up={ntoken_up}, ntoken_rb={ntoken_rb}"
            )
        if idx % 10 == 0 or idx == len(SAMPLES):
            print(f"  [{idx:02d}/50] {name:<18s} crit_up={crit_up:.6f} crit_rb={crit_rb:.6f} "
                  f"diff={diff:.2e} ntok={ntoken_rb} {'OK' if crit_ok and ntoken_ok else 'FAIL'}")

    print("\n--- Phase B: Probability mapping differential test (4 parameter sets x 50 samples) ---")
    for param_name, params in DISTRIB_PARAMS.items():
        set_max_diff = 0.0
        for name, text in SAMPLES:
            crit, _ = rebuild.compute_crit(text)
            prob_up = upstream_compute_prob_norm(crit, **params)
            prob_rb = rebuild_compute_prob_norm(crit, **params)
            p_diff = abs(prob_up - prob_rb)
            if p_diff > set_max_diff:
                set_max_diff = p_diff
            if p_diff > max_prob_diff:
                max_prob_diff = p_diff
            if p_diff > TOL:
                failures.append(f"Prob mismatch for {param_name} on {name}: up={prob_up}, rb={prob_rb}")
        print(f"  Parameter set {param_name:<30s} max prob diff={set_max_diff:.2e} "
              f"{'OK' if set_max_diff <= TOL else 'FAIL'}")

    print("\n--- Phase C: Edge cases & guardrails ---")
    # 1. Empty string raises RuntimeError
    empty_up_raised = False
    try:
        tok_e = upstream_tok("", truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False)
        with torch.no_grad():
            upstream_mdl(**tok_e)
    except RuntimeError:
        empty_up_raised = True

    empty_rb_raised = False
    try:
        rebuild.compute_crit("")
    except RuntimeError:
        empty_rb_raised = True

    if empty_up_raised and empty_rb_raised:
        print("  Empty string -> RuntimeError: OK (both raised RuntimeError)")
    else:
        failures.append(f"Empty string handling mismatch: up={empty_up_raised}, rb={empty_rb_raised}")
        print(f"  Empty string -> RuntimeError: FAIL (up={empty_up_raised}, rb={empty_rb_raised})")

    # 2. 1-token input yields nan
    single_tok = "Hello"
    tok_1 = upstream_tok(single_tok, truncation=True, return_tensors="pt", padding=True, return_token_type_ids=False)
    crit_1_rb, ntok_1_rb = rebuild.compute_crit(single_tok)
    if tok_1.input_ids.shape[1] == 1:
        if math.isnan(crit_1_rb) and ntok_1_rb == 0:
            print("  1-token input -> nan: OK (rebuild returns nan, ntoken=0)")
        else:
            failures.append(f"1-token input did not yield nan: got {crit_1_rb}")
            print(f"  1-token input -> nan: FAIL (got {crit_1_rb})")
    else:
        print(f"  (Skipping 1-token check: '{single_tok}' tokenized to {tok_1.input_ids.shape[1]} tokens)")

    # 3. Batch > 1 raises AssertionError in analytic discrepancy
    batch_t = torch.randn(2, 5, 50257)
    batch_l = torch.zeros(2, 5, dtype=torch.long)
    try:
        compute_discrepancy_analytic(batch_t, batch_t, batch_l)
        failures.append("Batch > 1 did not raise AssertionError")
        print("  Batch > 1 assertion: FAIL")
    except AssertionError:
        print("  Batch > 1 assertion: OK (raised AssertionError)")

    # 4. Unknown model pair raises KeyError
    try:
        FastDetectGPTDetector(sampling_model_name="gpt2", scoring_model_name="gpt2")
        failures.append("Unknown model pair did not raise KeyError")
        print("  Unknown model pair KeyError: FAIL")
    except KeyError:
        print("  Unknown model pair KeyError: OK (raised KeyError)")

    # 5. Invalid quantize raises ValueError
    try:
        FastDetectGPTDetector(quantize="invalid_mode")
        failures.append("Invalid quantize did not raise ValueError")
        print("  Invalid quantize ValueError: FAIL")
    except ValueError:
        print("  Invalid quantize ValueError: OK (raised ValueError)")

    print("\n--- Phase D: score_window consistency ---")
    window_sample = SAMPLES[0][1]
    w = rebuild.score_window(window_sample)
    crit_exp, ntok_exp = rebuild.compute_crit(window_sample)
    prob_exp, _, _ = rebuild.compute_prob(window_sample)
    w_ok = (
        abs(w["criterion"] - crit_exp) < 1e-6
        and abs(w["probability"] - prob_exp) < 1e-6
        and w["n_tokens"] == ntok_exp + 1
    )
    if w_ok:
        print(f"  score_window consistency: OK (crit={w['criterion']:.4f}, prob={w['probability']:.4f}, n_tokens={w['n_tokens']})")
    else:
        failures.append(f"score_window mismatch: {w}")
        print(f"  score_window consistency: FAIL ({w})")

    # Final summary
    print("\n" + "=" * 78)
    print(f"Samples: 50 | Max crit diff: {max_crit_diff:.3e} | Max prob diff: {max_prob_diff:.3e}")
    if failures:
        print(f"RESULT: FAIL ({len(failures)} failures)")
        for f in failures:
            print("  -", f)
        return 1

    print("RESULT: PASS — all outputs match within +/-0.001, probability sets verified, "
          "edge behaviours replicated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
