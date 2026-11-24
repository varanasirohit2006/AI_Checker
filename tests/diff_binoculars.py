"""Stage 5 differential test — Binoculars (Repo #1).

Compares upstream `research/Binoculars` (editable install, exact clone) against
the clean rebuild `detectors/binoculars.py` on 50 diverse text samples.

Pass conditions (rea/binoculars/01-target.md, 04-spec.md):
  * abs(score_upstream - score_rebuild) <= 0.001 for every sample
  * identical predict() labels
  * batch-of-2 outputs identical in order
  * edge behaviours replicated: "" -> RuntimeError, 1 token -> nan,
    change_mode("bogus") -> ValueError

Model pair on this CPU-only machine: gpt2 (observer) / distilgpt2 (performer),
fp32, max_token_observed=512. Thresholds are Falcon-tuned upstream constants;
label agreement (not label correctness) is what this test asserts.

Run:  .venv/Scripts/python.exe tests/diff_binoculars.py
"""

from __future__ import annotations

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import torch

import binoculars as upstream_pkg
from binoculars import Binoculars as UpstreamBinoculars

from detectors.binoculars import (
    BINOCULARS_ACCURACY_THRESHOLD,
    BINOCULARS_FPR_THRESHOLD,
    BinocularsDetector,
)

TOL = 1e-3
OBSERVER = "gpt2"
PERFORMER = "distilgpt2"
MAX_TOKENS = 512

# --------------------------------------------------------------------------
# 50 diverse samples
# --------------------------------------------------------------------------

HUMAN = [
    ("human_bike", "My bike commute takes about twenty minutes on a good day, though honestly the "
     "lights along Cedar Avenue conspire against me. Last Tuesday I got caught behind a garbage "
     "truck for three blocks and arrived at work smelling like a landfill. My boss made a face. "
     "I told him it was the new cologne I was testing. He didn't laugh, but the intern did, and "
     "that's basically all I need to keep going. Some mornings the lake path is foggy and quiet "
     "and I remember why I stopped taking the bus in the first place."),
    ("human_kitchen", "Grandma never measured anything. Flour went in until the dough looked right, "
     "and when I asked how much that was she'd say 'until it looks right' like I was the slow one. "
     "I spent two years trying to reverse engineer her Sunday rolls and got close, but not close "
     "enough. The secret, I think, was the old oven that ran hot and the fact that she let the "
     "dough rise twice while she watched her shows. Mine taste fine. Hers tasted like being eight "
     "years old and taller than the counter."),
    ("human_work", "The printer jammed again during the quarterly review, which felt almost poetic. "
     "Dave from accounting tried to fix it and ended up with toner on his tie, and nobody said "
     "anything for a solid ten seconds because we were all pretending to be professional. Then "
     "Priya snorted and the whole room lost it. We presented the numbers off a laptop screen "
     "crowded around like it was a campfire. Honestly the best meeting we've had all year, and "
     "the printer has been 'temporarily out of service' ever since."),
    ("human_book", "I wanted to hate that book. Everyone at work kept quoting it, and the cover "
     "looked like it was designed by a committee of motivational speakers. But around chapter "
     "four something clicked, and by the end I was sitting in my car in the driveway just "
     "staring at the steering wheel. It's not great literature. The middle drags and the "
     "dialogue gets preachy. Still, I keep lending my copy out, and I keep buying new ones "
     "when people don't give it back. Make of that what you will."),
    ("human_garden", "Tomatoes are a gamble and I keep losing. This year I planted six, babied "
     "them through the frost scare in April, built a whole cage system out of scrap wire, and "
     "then the hornworms showed up in July like they'd been waiting for an invitation. My "
     "neighbor Walt says I should've picked them off by hand at dawn. Walt is seventy-eight "
     "and grows tomatoes the size of softballs, so I nod and take notes. Next year: dawn "
     "patrols, apparently. The basil, at least, is thriving out of pure spite."),
    ("human_soccer", "We lost the rec league final 4-2 and our goalie, who is normally the most "
     "mild-mannered guy alive, kicked the post so hard he limped for a week. The other team "
     "was genuinely better, faster, younger, all of it. But on the drive home someone put on "
     "that song from the '98 World Cup and by the second chorus we were all shouting along "
     "with the windows down. Nobody talked about the score. We stopped for tacos. It was, "
     "and I mean this sincerely, a pretty great night."),
    ("human_coffee", "There's a guy at the coffee shop on 5th who types with two fingers, "
     "extremely fast, and glares at anyone who walks behind his screen. I've decided he's "
     "writing a novel, or possibly witness protection paperwork. The barista calls him 'the "
     "professor' even though nobody knows his name. Today he ordered a flat white, sat in "
     "the corner, and typed for three hours without blinking. I respect the commitment. "
     "Meanwhile I've written two emails and refreshed my phone forty times. Different "
     "species, honestly."),
    ("human_moving", "Moving apartments at thirty-two hits different than at twenty-two. Back "
     "then it was two trips in a friend's hatchback and pizza on the floor. This time there "
     "was a couch that wouldn't fit through the stairwell, a security deposit dispute, and "
     "a very patient mover named Andrei who said 'we will make it fit' and then, somehow, "
     "made it fit. I found a box of college notebooks I hadn't opened in a decade. Read "
     "half of one, felt my soul leave my body, and put it straight in the recycling."),
    ("human_guitar", "Six months of guitar and my neighbors have opinions. I can play exactly "
     "four songs, three of which share the same chords, and my F barre still sounds like a "
     "cat being stepped on. But last week my kid asked me to play 'her song' at bedtime and "
     "I did, badly, and she sang the whole thing like it was the radio. So the neighbors can "
     "file their complaints. The instructor says my wrist is too stiff. My daughter says I'm "
     "the best guitarist in the world. I know which review I trust."),
    ("human_dentist", "The dentist asked if I'd been flossing and I said 'regularly,' which is "
     "technically true if you define regular as 'the week before this appointment.' She gave "
     "me the look. You know the look. My hygienist, bless her, narrated the whole cleaning "
     "like a nature documentary: 'and here we see the molar in its natural habitat.' I "
     "laughed with a suction tube in my mouth, which is a mistake I recommend to nobody. "
     "Two cavities. Worth it? Ask me again when the novocaine wears off."),
    ("human_hike", "The trail map said 'moderate, 6 miles' and the trail map is a liar. Mile "
     "three was a vertical scramble over wet roots, and my friend Jess kept saying 'the "
     "view is worth it' in the voice of someone who had also been deceived. The view was "
     "worth it. We sat on a warm rock eating squished sandwiches and watched hawks ride "
     "the ridge wind, and neither of us checked our phones once. On the way down my knees "
     "filed a formal complaint. I'd do it again next month. Probably. Ask me tomorrow."),
    ("human_letter", "It's strange what you miss after a year away. Not the big things — the "
     "skyline, the restaurants, those I can visit. It's the sound of the 7 train rattling "
     "past my old window at 6:15, the specific creak of the third stair, the bodega cat "
     "who hated everyone but tolerated me. I told myself I'd outgrown the city. Turns out "
     "the city just quietly became part of how I measure quiet. My new place is peaceful. "
     "Some nights peace feels a lot like a room where someone stopped talking."),
]

AI = [
    ("ai_productivity", "In today's fast-paced world, productivity has become a cornerstone of "
     "personal and professional success. By leveraging effective time-management strategies, "
     "individuals can optimize their daily routines and achieve their goals more efficiently. "
     "Furthermore, prioritization plays a pivotal role in ensuring that high-impact tasks "
     "receive the attention they deserve. Ultimately, cultivating a productive mindset enables "
     "individuals to unlock their full potential and thrive in an increasingly competitive "
     "landscape."),
    ("ai_climate", "Climate change represents one of the most pressing challenges of our time. "
     "Rising global temperatures, shifting weather patterns, and increasing frequency of extreme "
     "events underscore the urgent need for coordinated action. Governments, businesses, and "
     "individuals must work collaboratively to reduce carbon emissions and transition toward "
     "sustainable energy sources. Moreover, investing in green infrastructure not only "
     "mitigates environmental damage but also fosters economic growth. In conclusion, addressing "
     "climate change is essential for safeguarding the planet for future generations."),
    ("ai_remote", "Remote work has revolutionized the modern workplace, offering unprecedented "
     "flexibility and autonomy. Studies indicate that employees who work remotely often "
     "experience increased job satisfaction and improved work-life balance. Additionally, "
     "organizations benefit from reduced overhead costs and access to a broader talent pool. "
     "However, it is important to acknowledge potential challenges, such as communication "
     "barriers and feelings of isolation. By implementing robust collaboration tools and "
     "fostering a strong virtual culture, companies can maximize the benefits of this "
     "transformative shift."),
    ("ai_healthcare", "Artificial intelligence is transforming the healthcare industry in "
     "profound ways. From diagnostic imaging to personalized treatment plans, AI-powered "
     "systems enhance accuracy, efficiency, and patient outcomes. Machine learning algorithms "
     "can analyze vast datasets to identify patterns that may elude human practitioners. "
     "Furthermore, AI-driven chatbots and virtual assistants streamline administrative tasks, "
     "allowing medical professionals to focus on patient care. As these technologies continue "
     "to evolve, they hold immense promise for revolutionizing healthcare delivery worldwide."),
    ("ai_exercise", "Regular exercise offers numerous benefits for both physical and mental "
     "well-being. Engaging in consistent physical activity strengthens the cardiovascular "
     "system, improves muscular endurance, and supports healthy weight management. Moreover, "
     "exercise has been shown to reduce stress, alleviate symptoms of anxiety, and enhance "
     "cognitive function. It is recommended that adults engage in at least 150 minutes of "
     "moderate-intensity activity per week. In conclusion, incorporating exercise into one's "
     "daily routine is a vital step toward achieving a healthier, more balanced lifestyle."),
    ("ai_social", "Social media plays a pivotal role in contemporary communication and "
     "information dissemination. Platforms enable users to connect across geographical "
     "boundaries, share experiences, and engage with diverse perspectives. Nevertheless, "
     "the proliferation of misinformation and the impact on mental health warrant careful "
     "consideration. Users must develop critical digital literacy skills to navigate online "
     "content responsibly. Ultimately, social media remains a powerful tool that, when used "
     "mindfully, can foster meaningful connections and drive positive societal change."),
    ("ai_education", "Education serves as the cornerstone of societal progress and individual "
     "empowerment. Access to quality learning opportunities equips individuals with the "
     "knowledge and skills necessary to navigate an ever-changing world. Furthermore, "
     "education promotes critical thinking, creativity, and civic engagement. Innovations "
     "such as online learning platforms have democratized access to knowledge, breaking down "
     "traditional barriers. In conclusion, investing in education is not merely an economic "
     "imperative but a moral obligation that shapes the trajectory of future generations."),
    ("ai_blockchain", "Blockchain technology has emerged as a groundbreaking innovation with "
     "applications extending far beyond cryptocurrency. Its decentralized architecture "
     "ensures transparency, security, and immutability of records. Industries ranging from "
     "supply chain management to healthcare are exploring blockchain solutions to enhance "
     "traceability and reduce fraud. Additionally, smart contracts automate agreements, "
     "eliminating intermediaries and reducing costs. As adoption continues to grow, blockchain "
     "has the potential to fundamentally reshape how organizations establish trust and "
     "conduct transactions."),
    ("ai_timemgmt", "Time management is an essential skill for achieving success in both "
     "personal and professional domains. Effective techniques, such as the Pomodoro method "
     "and time blocking, enable individuals to structure their day with intention and focus. "
     "Furthermore, setting clear priorities helps minimize distractions and prevent burnout. "
     "It is also important to schedule regular breaks, as they enhance productivity and "
     "creativity. By mastering time management, individuals can accomplish more while "
     "maintaining a healthy balance between work and personal life."),
    ("ai_mental", "The importance of mental health cannot be overstated in today's demanding "
     "society. Awareness campaigns and open conversations have helped reduce stigma, "
     "encouraging individuals to seek support when needed. Employers are increasingly "
     "recognizing the value of mental wellness programs, which contribute to higher "
     "engagement and reduced absenteeism. Moreover, practices such as mindfulness, adequate "
     "sleep, and social connection play crucial roles in maintaining psychological "
     "well-being. Prioritizing mental health is fundamental to building resilient "
     "communities and thriving workplaces."),
    ("ai_sustain", "Sustainable living has become increasingly important as environmental "
     "concerns continue to escalate. Simple actions, such as reducing single-use plastics, "
     "conserving water, and choosing renewable energy, collectively make a significant "
     "difference. Furthermore, supporting local and eco-conscious businesses encourages "
     "responsible production practices. Education and community initiatives also empower "
     "individuals to adopt greener habits. In conclusion, embracing sustainability is a "
     "shared responsibility that ensures a healthier planet for generations to come."),
    ("ai_network", "Networking is a crucial skill for career advancement and professional "
     "growth. Building genuine relationships opens doors to opportunities, mentorship, and "
     "collaboration. Attending industry events, participating in online communities, and "
     "maintaining consistent communication are effective strategies for expanding one's "
     "network. Additionally, offering value to others strengthens connections and fosters "
     "mutual trust. Ultimately, a robust professional network serves as a powerful asset "
     "that can accelerate career trajectories and enrich one's professional journey."),
]

MIXED = [
    ("mixed_review", "I bought this blender because my old one sounded like a helicopter "
     "dying. First impression: it's shiny, it's loud, and the manual is written for people "
     "who already understand blenders. That said, the product delivers exceptional "
     "performance across a wide range of blending tasks. Its powerful motor ensures smooth, "
     "consistent results, while the durable construction guarantees long-term reliability. "
     "Overall, this blender represents an excellent investment for any kitchen."),
    ("mixed_email", "Hey team, quick heads up that Thursday's sync is moved to 2pm because "
     "the conference room got double-booked again (shocking, I know). Going forward, we will "
     "leverage a centralized scheduling framework to optimize room utilization and ensure "
     "seamless coordination across all stakeholders. Please update your calendars "
     "accordingly and confirm receipt of this communication at your earliest convenience."),
    ("mixed_essay", "My hometown had one traffic light and everybody knew everybody's car. "
     "When the factory closed, Main Street emptied out like a theater after the credits "
     "roll. Urban economic diversification is essential for fostering resilience in "
     "post-industrial communities. By investing in small-business incubators, workforce "
     "retraining programs, and broadband infrastructure, municipalities can stimulate "
     "sustainable growth and revitalize local economies for the long term."),
    ("mixed_blog", "Confession: I have killed every houseplant I've ever owned except one "
     "plastic fern my sister gave me as a joke. Caring for indoor plants offers numerous "
     "benefits, including improved air quality, reduced stress levels, and enhanced "
     "aesthetic appeal. By selecting low-maintenance species and establishing a consistent "
     "watering schedule, even novice gardeners can cultivate a thriving indoor garden."),
    ("mixed_note", "Grandpa's workshop smells like sawdust and old coffee and I'd bottle it "
     "if I could. He still writes every measurement on the wall in pencil, forty years of "
     "numbers layered over each other like tree rings. Documenting institutional knowledge "
     "through systematic record-keeping ensures operational continuity and facilitates "
     "effective knowledge transfer across generations of practitioners."),
]

SHORT = [
    ("short_hello", "Hello world"),
    ("short_cat", "The cat sat on the mat."),
    ("short_disagree", "I disagree."),
    ("short_list", "Buy milk, eggs, and bread."),
    ("short_surprise", "What a wonderful surprise!"),
    ("short_python", "Python is fun."),
]

# Paragraph pool used to build long samples near/over the 512-token cap.
P1 = ("My bike commute takes about twenty minutes on a good day, though honestly the lights "
      "along Cedar Avenue conspire against me. Last Tuesday I got caught behind a garbage truck "
      "for three blocks and arrived at work smelling like a landfill. My boss made a face. I told "
      "him it was the new cologne I was testing. He didn't laugh, but the intern did, and that's "
      "basically all I need to keep going. Some mornings the lake path is foggy and quiet and I "
      "remember why I stopped taking the bus in the first place. ")
P2 = ("Remote work has revolutionized the modern workplace, offering unprecedented flexibility "
      "and autonomy. Studies indicate that employees who work remotely often experience increased "
      "job satisfaction and improved work-life balance. Additionally, organizations benefit from "
      "reduced overhead costs and access to a broader talent pool. However, it is important to "
      "acknowledge potential challenges, such as communication barriers and feelings of isolation. "
      "By implementing robust collaboration tools and fostering a strong virtual culture, "
      "companies can maximize the benefits of this transformative shift. ")
P3 = ("Grandma never measured anything. Flour went in until the dough looked right, and when I "
      "asked how much that was she'd say 'until it looks right' like I was the slow one. I spent "
      "two years trying to reverse engineer her Sunday rolls and got close, but not close enough. "
      "The secret, I think, was the old oven that ran hot and the fact that she let the dough rise "
      "twice while she watched her shows. Mine taste fine. Hers tasted like being eight years old "
      "and taller than the counter. ")
P4 = ("Climate change represents one of the most pressing challenges of our time. Rising global "
      "temperatures, shifting weather patterns, and increasing frequency of extreme events "
      "underscore the urgent need for coordinated action. Governments, businesses, and individuals "
      "must work collaboratively to reduce carbon emissions and transition toward sustainable "
      "energy sources. Moreover, investing in green infrastructure not only mitigates environmental "
      "damage but also fosters economic growth. In conclusion, addressing climate change is "
      "essential for safeguarding the planet for future generations. ")
P5 = ("The trail map said 'moderate, 6 miles' and the trail map is a liar. Mile three was a "
      "vertical scramble over wet roots, and my friend Jess kept saying 'the view is worth it' in "
      "the voice of someone who had also been deceived. The view was worth it. We sat on a warm "
      "rock eating squished sandwiches and watched hawks ride the ridge wind, and neither of us "
      "checked our phones once. On the way down my knees filed a formal complaint. I'd do it again "
      "next month. Probably. Ask me tomorrow. ")
P6 = ("Education serves as the cornerstone of societal progress and individual empowerment. "
      "Access to quality learning opportunities equips individuals with the knowledge and skills "
      "necessary to navigate an ever-changing world. Furthermore, education promotes critical "
      "thinking, creativity, and civic engagement. Innovations such as online learning platforms "
      "have democratized access to knowledge, breaking down traditional barriers. In conclusion, "
      "investing in education is not merely an economic imperative but a moral obligation that "
      "shapes the trajectory of future generations. ")

LONG = [
    ("long_near512", P1 + P2 + P3 + P4 + P5),
    ("long_over512_a", P1 + P2 + P3 + P4 + P5 + P6),
    ("long_mid", P4 + P5 + P6 + P1),
    ("long_over512_b", P2 + P5 + P1 + P6 + P3 + P4),
    ("long_over512_c", P3 + P6 + P2 + P5 + P1 + P4),
]

NON_ASCII = [
    ("nonascii_fr", "Le marché du samedi matin est mon endroit préféré dans tout le quartier. "
     "Les vendeurs crient les prix, les enfants courent entre les étals, et l'odeur du fromage "
     "frais se mélange à celle des fraises. J'achète toujours trop de pain, mais je ne regrette "
     "jamais. C'est dans ces petits moments que je me sens vraiment chez moi, loin du bureau "
     "et des écrans, les mains pleines de sacs et le cœur léger."),
    ("nonascii_de", "Am Sonntagmorgen fahre ich mit dem Fahrrad zum See, auch wenn es regnet. "
     "Die Ruhe dort ist etwas Besonderes, das man in der Stadt nicht findet. Manchmal treffe "
     "ich Herrn Weber, der seit dreißig Jahren jeden Sonntag dieselbe Bank benutzt. Wir "
     "schweigen gemeinsam und schauen auf das Wasser. Das klingt seltsam, aber es ist die "
     "beste Unterhaltung, die ich seit Langem hatte."),
    ("nonascii_es", "Mi abuela decía que la cocina era el corazón de la casa, y tenía razón. "
     "Cuando preparo su receta de lentejas, el olor me transporta a las tardes de invierno en "
     "su casa, con la radio encendida y la mesa llena de primos. No uso nunca la olla a "
     "presión, aunque tardo el doble. Hay cosas que no se pueden acelerar sin perder algo "
     "importante por el camino."),
    ("nonascii_ru", "Каждое утро я гуляю по набережной, даже зимой, когда ветер обжигает лицо. "
     "В это время город ещё спит, и только дворники шуршат метлами по асфальту. Однажды я "
     "встретил там старого рыбака, который сказал мне, что клёв зависит не от погоды, а от "
     "терпения. Я не рыбачу, но почему-то запомнил эту фразу на всю жизнь."),
    ("nonascii_hi", "हर रविवार की सुबह मैं अपने दादाजी के साथ बाजार जाता था। वे हमेशा मोलभाव "
     "करते थे और मैं शर्म से लाल हो जाता था। लेकिन अब जब वे नहीं हैं, तो मुझे उनकी आवाज़ "
     "याद आती है — कैसे वे सब्जी वाले से हँसकर बात करते थे और हर दुकानदार को नाम से जानते "
     "थे। उस बाजार की भीड़ में मुझे आज भी अपनापन महसूस होता है।"),
    ("nonascii_zh", "我小时候住在外婆家的小院里，院子里有一棵枣树。每到秋天，外婆就会用竹竿打枣，"
     "我在树下捡，装满整整一篮子。如今我住在城市的高楼里，超市里的枣子又大又甜，却再也吃不出"
     "当年的味道。去年回去看老院子，枣树还在，只是外婆已经不在了。我站在树下很久，什么也没说。"),
    ("nonascii_ja", "毎朝、駅前の小さな喫茶店でコーヒーを飲むのが習慣になっている。マスターは"
     "無口な人で、注文を言わなくても出してくれる。先月、店が閉店すると聞いて驚いた。三十年"
     "続いた店だという。最終日、常連客がみんな集まって、マスターは少し照れたように笑っていた。"
     "私も何か言いたかったのに、結局「ありがとう」しか言えなかった。😊 また会えるといいな。"),
]

SPECIAL = [
    ("special_code", "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n"
     "    return a\n\n# quick sanity check\nprint([fib(i) for i in range(10)])\n"
     "assert fib(10) == 55\n# TODO: memoize if n gets large\n"),
    ("special_recipe", "Weeknight pasta, serves 2: 1) Boil salted water, cook 200g spaghetti "
     "one minute short of the box time. 2) Meanwhile, warm 3 tbsp olive oil, add 4 sliced "
     "garlic cloves and a pinch of chili flakes; do NOT brown the garlic. 3) Add a ladle of "
     "pasta water, then the drained pasta; toss hard for 60 seconds. 4) Off heat: lemon "
     "zest, parsley, parmesan. 5) Eat standing up if you must, no judgment."),
    ("special_punct", "BREAKING: the so-called 'update' (v2.3.1??) broke EVERYTHING --- "
     "login: 500; search: 404; billing: ??? Check https://status.example.com/incidents/4821 "
     "for details... or don't, because the status page is ALSO down. #devlife "
     "¯\\_(ツ)_/¯ Email support@example.com if you dare. P.S. 'it works on my machine' "
     "is not a fix, Kevin."),
]

SAMPLES: list[tuple[str, str]] = HUMAN + AI + MIXED + SHORT + LONG + NON_ASCII + SPECIAL
assert len(SAMPLES) == 50, f"expected 50 samples, got {len(SAMPLES)}"


def scores_match(a: float, b: float) -> bool:
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= TOL


def main() -> int:
    print("=" * 78)
    print("Stage 5 differential test: Binoculars")
    print(f"  upstream : {upstream_pkg.__file__}")
    assert "research" in Path(upstream_pkg.__file__).parts, "upstream must resolve to the clone"
    print(f"  rebuild  : {ROOT / 'detectors' / 'binoculars.py'}")
    print(f"  pair     : observer={OBSERVER} performer={PERFORMER} "
          f"dtype=fp32 device=cpu max_token_observed={MAX_TOKENS}")
    print(f"  tolerance: +/-{TOL} on scores; exact label equality; batch order preserved")
    print("=" * 78)

    torch.set_num_threads(4)
    failures: list[str] = []
    max_diff = 0.0

    t0 = time.time()
    upstream = UpstreamBinoculars(
        observer_name_or_path=OBSERVER, performer_name_or_path=PERFORMER,
        use_bfloat16=False, max_token_observed=MAX_TOKENS, mode="low-fpr",
    )
    print(f"[load] upstream loaded in {time.time() - t0:.1f}s")
    t0 = time.time()
    rebuild = BinocularsDetector(
        observer_name_or_path=OBSERVER, performer_name_or_path=PERFORMER,
        use_bfloat16=False, max_token_observed=MAX_TOKENS, mode="low-fpr",
    )
    print(f"[load] rebuild  loaded in {time.time() - t0:.1f}s")

    assert rebuild.threshold == upstream.threshold == BINOCULARS_FPR_THRESHOLD

    # Phase A: single-string scores on all 50 samples (like-for-like, no padding).
    print("\n--- Phase A: compute_score, single strings (50 samples) ---")
    single_up: list[float] = []
    single_rb: list[float] = []
    for i, (name, text) in enumerate(SAMPLES):
        u = upstream.compute_score(text)
        r = rebuild.compute_score(text)
        single_up.append(u)
        single_rb.append(r)
        ok = scores_match(u, r)
        diff = abs(u - r)
        if not math.isnan(diff):
            max_diff = max(max_diff, diff)
        if not ok:
            failures.append(f"A[{i}] {name}: upstream={u!r} rebuild={r!r}")
        print(f"  [{i + 1:2d}/50] {name:<20s} up={u:.9f} rb={r:.9f} "
              f"diff={diff:.2e} {'OK' if ok else 'FAIL'}")

    # Phase B: batches of 2 (padding='longest' path), order preserved.
    print("\n--- Phase B: compute_score, batches of 2 (25 batches) ---")
    batch_up: list[list[float]] = []
    batch_rb: list[list[float]] = []
    for j in range(0, 50, 2):
        texts = [SAMPLES[j][1], SAMPLES[j + 1][1]]
        u = upstream.compute_score(texts)
        r = rebuild.compute_score(texts)
        batch_up.append(u)
        batch_rb.append(r)
        for k in range(2):
            ok = scores_match(u[k], r[k])
            order_ok = scores_match(u[k], single_up[j + k])
            diff = abs(u[k] - r[k])
            if not math.isnan(diff):
                max_diff = max(max_diff, diff)
            if not ok:
                failures.append(f"B[{j + k}] {SAMPLES[j + k][0]} batch: up={u[k]!r} rb={r[k]!r}")
            if not order_ok:
                failures.append(f"B[{j + k}] order: batch={u[k]!r} single={single_up[j + k]!r}")
        print(f"  batch {j // 2 + 1:2d}/25 ({SAMPLES[j][0]}, {SAMPLES[j + 1][0]}): "
              f"up={[round(x, 7) for x in u]} rb={[round(x, 7) for x in r]}")

    # Phase C: predict() labels, low-fpr mode, same batches of 2.
    print("\n--- Phase C: predict labels, low-fpr (25 batches) ---")
    labels_up: list[str] = []
    labels_rb: list[str] = []
    for j in range(0, 50, 2):
        texts = [SAMPLES[j][1], SAMPLES[j + 1][1]]
        u = upstream.predict(texts)
        r = rebuild.predict(texts)
        labels_up.extend(u)
        labels_rb.extend(r)
        if u != r:
            failures.append(f"C[{j}:{j + 2}] labels: up={u} rb={r}")
        for k in range(2):
            expected = ("Most likely AI-generated"
                        if batch_up[j // 2][k] < BINOCULARS_FPR_THRESHOLD
                        else "Most likely human-generated")
            if u[k] != expected or r[k] != expected:
                failures.append(f"C[{j + k}] label vs threshold: up={u[k]} rb={r[k]} exp={expected}")
    n_ai = sum(l == "Most likely AI-generated" for l in labels_up)
    print(f"  labels identical on all 50: {labels_up == labels_rb} "
          f"(AI={n_ai}, human={50 - n_ai}; small CPU pair is not Falcon-calibrated)")

    # Phase D: accuracy mode switch on both implementations.
    print("\n--- Phase D: change_mode('accuracy') + predict on 4 samples ---")
    upstream.change_mode("accuracy")
    rebuild.change_mode("accuracy")
    assert rebuild.threshold == upstream.threshold == BINOCULARS_ACCURACY_THRESHOLD
    for idx in (0, 12, 30, 40):
        name, text = SAMPLES[idx]
        u = upstream.predict(text)
        r = rebuild.predict(text)
        ok = u == r and isinstance(u, str) and isinstance(r, str)
        if not ok:
            failures.append(f"D[{idx}] {name}: up={u!r} rb={r!r}")
        print(f"  {name:<20s} up={u!r} rb={r!r} {'OK' if ok else 'FAIL'}")
    upstream.change_mode("low-fpr")
    rebuild.change_mode("low-fpr")

    # Phase E: edge behaviours must match upstream exactly.
    print("\n--- Phase E: edge cases ---")
    for label, fn in (
        ("empty string -> RuntimeError", lambda d: d.compute_score("")),
        ("1-token 'Hello' -> nan", lambda d: d.compute_score("Hello")),
        ("1-token 'a' -> nan", lambda d: d.compute_score("a")),
        ("change_mode('bogus') -> ValueError", lambda d: d.change_mode("bogus")),
    ):
        def outcome(det):
            try:
                v = fn(det)
                return ("value", v)
            except Exception as exc:  # noqa: BLE001 - comparing exception types is the point
                return ("error", type(exc).__name__)
        u_out, r_out = outcome(upstream), outcome(rebuild)
        if u_out[0] == "value" and r_out[0] == "value":
            ok = scores_match(u_out[1], r_out[1])
        else:
            ok = u_out == r_out
        if not ok:
            failures.append(f"E {label}: up={u_out} rb={r_out}")
        print(f"  {label:<40s} up={u_out} rb={r_out} {'OK' if ok else 'FAIL'}")
    upstream.change_mode("low-fpr")
    rebuild.change_mode("low-fpr")

    # Phase F: rebuild-only extras (score_window consistency + extension guards).
    print("\n--- Phase F: score_window consistency + extension guards (rebuild only) ---")
    for idx in (0, 36, 41):
        name, text = SAMPLES[idx]
        w = rebuild.score_window(text)
        n_tok = len(rebuild.tokenizer.encode(text))
        checks = {
            "score==single": scores_match(w["score"], single_rb[idx]),
            "label==predict": w["label"] == labels_rb[idx],
            "ppl/x_ppl==score": scores_match(w["ppl"] / w["x_ppl"], w["score"]),
            "n_tokens": w["n_tokens"] == min(n_tok, MAX_TOKENS),
        }
        if not all(checks.values()):
            failures.append(f"F[{idx}] {name} score_window: {w} checks={checks}")
        print(f"  {name:<20s} score={w['score']:.9f} ppl={w['ppl']:.6f} "
              f"x_ppl={w['x_ppl']:.6f} n_tokens={w['n_tokens']} "
              f"{'OK' if all(checks.values()) else 'FAIL'}")
    try:
        BinocularsDetector(observer_name_or_path=OBSERVER, performer_name_or_path=PERFORMER,
                           use_bfloat16=True)
        failures.append("F: bfloat16-on-CPU was not refused")
        print("  bfloat16-on-CPU refusal: FAIL")
    except ValueError:
        print("  bfloat16-on-CPU refusal: OK (ValueError)")
    try:
        BinocularsDetector(observer_name_or_path=OBSERVER, performer_name_or_path=PERFORMER,
                           use_bfloat16=False, quantize="2bit")
        failures.append("F: invalid quantize option was not refused")
        print("  invalid quantize refusal: FAIL")
    except ValueError:
        print("  invalid quantize refusal: OK (ValueError)")

    # Summary
    print("\n" + "=" * 78)
    print(f"Samples: 50 | single checks: 50 | batch-of-2 checks: 50 | "
          f"label checks: 50 (low-fpr) + 4 (accuracy) | edge checks: 4 | extras: 5")
    print(f"Max |score diff| across all single+batch comparisons: {max_diff:.3e} "
          f"(tolerance {TOL})")
    if failures:
        print(f"RESULT: FAIL ({len(failures)} failures)")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: PASS — all outputs match within +/-0.001, labels identical, "
          "batch order preserved, edge behaviours replicated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())