"""Card S2: neutral-context fills (notes/iteration-anthony/studies/S2.md).

Builds ``data/dev/<family>/s2.json`` for multihop_mt, typo, association and multilingual_mt: prompts in the family's
form (same template, read at the final token by the bench's own plan) whose content does **not** share what the
family's items share (S6 / S10: a mean over cells that share X removes X). Each item carries ``condition``:

* ``neutral``  the shared attribute varied away: multihop_mt bridges that are not famous people / works / landmarks
  (elements, organs, tools, planets ...); typo sentences ending in a correctly spelled word; association scene
  sentences that evoke nothing nameable; multilingual_mt descriptions of general concepts in the family's 12 languages;
* ``matched``  (multihop_mt only, the negative control) the family's shared attribute kept: two-hop facts whose bridge
  is a famous person or work, none of them a bridge or target of any split.

Authored by hand (instance C, 2026-10-11), no LLM, no targets: the fills are reference cells only, never scored.
``--check`` lists collisions with any split's targets / intermediates (a leak guard; colliding fills are dropped).

  python experiments/s2_bank.py [--check]
  python experiments/s2_bank.py --capture --device cuda     # read-cell captures -> out/captures/<family>-s2.pt
"""

import argparse
import json
import re

from jlm import REPO_ROOT

DEV = REPO_ROOT / "data" / "dev"

FILLS: dict[str, dict[str, list[str]]] = {
    "multihop_mt": {
        "neutral": [
            "Fact: the metal with the highest melting point, once used for light-bulb filaments, has the chemical symbol",
            "Fact: the organ that produces insulin in the human body sits just behind the",
            "Fact: the gas that makes up about 78 percent of Earth's atmosphere was first isolated by the Scottish physician",
            "Fact: the longest bone in the human body runs from the hip to the",
            "Fact: the unit of electrical resistance is named after the German physicist",
            "Fact: the programming language created at Bell Labs in the early 1970s was used to rewrite the operating system",
            "Fact: the mineral rated 10 on the Mohs hardness scale is a crystal form of the element",
            "Fact: the planet with the most prominent ring system has a largest moon called",
            "Fact: the kitchen tool with a perforated bowl used to drain pasta is called a",
            "Fact: the weather instrument that measures air pressure was invented in the 17th century by",
            "Fact: the tree whose sap is boiled down into a sweet syrup in Canada also gives its leaf to the national",
            "Fact: the shape with eight equal sides is used on the road sign that tells drivers to",
            "Fact: the protein that carries oxygen in red blood cells is built around atoms of the element",
            "Fact: the insect that makes honey lives in a colony headed by a single",
            "Fact: the currency used in Japan is issued by the central bank headquartered in the city of",
            "Fact: the process by which plants turn light into chemical energy takes place in the organelle called the",
            "Fact: the fastest land animal hunts mostly on the open grasslands of the continent of",
            "Fact: the vitamin the skin makes in sunlight helps the body absorb the mineral",
            "Fact: the river that flows through Baghdad joins the Euphrates to form the waterway called the",
            "Fact: the lightest element in the periodic table is fused into helium in the core of the",
            "Fact: the disease caused by a lack of vitamin C was once common among long-voyage",
            "Fact: the device that turns alternating current into direct current in a phone charger is called a",
            "Fact: the color made by mixing blue and yellow paint is also the color of the leaf pigment called",
            "Fact: the frozen water that floats at the top of the Arctic Ocean shrinks every summer because of rising",
        ],
        "matched": [
            "Fact: the Dutch painter of The Night Watch lived and worked for most of his life in the city of",
            "Fact: the English playwright who wrote Hamlet was born in the market town of",
            "Fact: the German composer who went deaf yet wrote the Ninth Symphony was born in the city of",
            "Fact: the physicist who formulated the laws of motion and universal gravitation held a chair at the University of",
            "Fact: the novel narrated by the whaling sailor Ishmael was written by the American author",
            "Fact: the clock tower at the north end of the Palace of Westminster houses the great bell nicknamed",
            "Fact: the Polish-born scientist who won Nobel Prizes in physics and chemistry named an element after her homeland, whose capital is",
            "Fact: the Spanish painter of Guernica co-founded the art movement called",
            "Fact: the iron lattice tower built for the 1889 World's Fair in Paris was designed by the firm of the engineer",
            "Fact: the Scottish scientist who discovered penicillin made the discovery at a hospital in the city of",
            "Fact: the composer of the opera La Traviata was born in the Duchy of",
            "Fact: the Serbian-American inventor of the alternating-current induction motor was born in the village of",
            "Fact: the Russian novelist who wrote War and Peace lived on the family estate called",
            "Fact: the leader of India's independence movement known for nonviolent resistance was assassinated in the city of",
            "Fact: the Dutch painter of Girl with a Pearl Earring spent his whole life in the city of",
            "Fact: the medieval Italian poet who wrote the Divine Comedy was exiled from his native city of",
            "Fact: the Greek philosopher who tutored Alexander the Great founded a school in Athens called the",
            "Fact: the composer of The Four Seasons violin concertos was ordained a priest in the city of",
            "Fact: the Egyptian queen who allied with Mark Antony was the last ruler of the dynasty known as the",
            "Fact: the American novel narrated by Scout Finch was written by the Alabama author",
            "Fact: the prehistoric stone circle on Salisbury Plain stands in the English county of",
            "Fact: the French sculptor of The Thinker first made it as part of a monumental bronze portal called",
            "Fact: the explorer who led the first expedition to sail around the world was born in the kingdom of",
            "Fact: the German author of Faust was a leading figure of the literary movement called",
        ],
    },
    "typo": {
        "neutral": [
            "The boys tossed a soft foam toy", "She sliced a fresh green pepper",
            "Every week volunteers gathered supplies to donate", "She refilled the empty metal can",
            "He tightened the loose wooden chair", "The farmer planted a row of tall corn",
            "They painted the old wooden shed", "The baby dropped her small plastic spoon",
            "We watched the slow muddy stream", "He polished the silver serving tray",
            "The coach handed out the new jerseys", "My neighbor repaired his broken bicycle",
            "The cat chased a tiny gray mouse", "She folded the clean cotton towel",
            "The chef stirred the thick tomato sauce", "Our team celebrated the hard-won victory",
            "He opened the heavy front door", "The wind scattered the dry brown needles",
            "She wrapped the small cardboard box", "The students solved the difficult puzzle",
            "They hiked to the snowy rocky ridge", "He measured the width of the desk",
            "The bakery sold fresh warm bread", "She lit a small scented candle",
        ],
    },
    "association": {
        "neutral": [
            "She set the cup down on the table and looked out of the window for a while.",
            "He walked slowly along the corridor, counting the doors as he passed them.",
            "They sat together on the bench and talked about nothing in particular.",
            "The light in the room changed as the afternoon turned into evening.",
            "She opened the drawer, took out a pen, and closed it again.",
            "He waited by the door, listening to the sound of footsteps upstairs.",
            "The papers on the desk were stacked neatly in three uneven piles.",
            "She turned the page and kept reading until her eyes grew tired.",
            "They carried the boxes from the car into the hallway one by one.",
            "He looked at the clock, then back at the empty street outside.",
            "The water in the glass trembled slightly when the door slammed.",
            "She wrote a short note, folded it twice, and left it by the lamp.",
            "He stood up, stretched his arms, and sat back down again.",
            "The two of them walked in silence until they reached the corner.",
            "A faint breeze moved the curtains as the room grew quiet.",
            "She rearranged the chairs around the table before anyone arrived.",
            "He rinsed the plate, dried it, and put it back on the shelf.",
            "They agreed to meet again at the same place the following week.",
            "The phone rang twice and then stopped before anyone could answer.",
            "She tied her shoes, picked up her bag, and stepped outside.",
            "He tapped his fingers on the armrest while he thought it over.",
            "The room smelled faintly of dust and old paper.",
            "They laughed at something one of them had said earlier that day.",
            "She switched off the light and the room went dark.",
        ],
    },
    "multilingual_mt": {
        "neutral": [
            "Прибор для измерения температуры тела называется",
            "Фигура с тремя сторонами и тремя углами называется",
            "Ngọn núi có miệng phun ra dung nham nóng chảy được gọi là",
            "Dải màu xuất hiện trên bầu trời sau cơn mưa khi có nắng được gọi là",
            "Alat yang digunakan untuk menentukan arah utara disebut",
            "Benda yang dipakai untuk melindungi diri dari hujan saat berjalan disebut",
            "Uzaktaki yıldızları büyüterek gösteren aletin adı",
            "Yüksek yerlere çıkmak için kullanılan basamaklı aracın adı",
            "العضو الذي ينقي الدم من الفضلات في جسم الإنسان يسمى",
            "قطعة المعدن التي تجذب الحديد إليها تسمى",
            "Η μεγάλη μάζα πάγου που κινείται αργά στις πλαγιές των βουνών λέγεται",
            "Το όργανο που μετρά την ατμοσφαιρική πίεση λέγεται",
            "Sairauksilta suojaava, ihoon pistettävä valmiste on nimeltään",
            "Laite, jolla hyvin pieniä asioita katsotaan suurennettuina, on nimeltään",
            "Urządzenie, które pokazuje aktualną godzinę, nazywa się",
            "Najmniejsza cząstka pierwiastka chemicznego to",
            "המכשיר שמשמש לחישוב מספרים נקרא",
            "הכוכב שסביבו מסתובב כדור הארץ נקרא",
            "물이 얼어서 생긴 단단한 고체를 부르는 말은",
            "높은 곳에서 물이 아래로 떨어지는 곳을 부르는 말은",
            "A szívből a test felé vért szállító eret úgy hívják, hogy",
            "Az a szerszám, amellyel szöget verünk a falba, a",
            "Kifaa kinachotumika kupima uzito wa vitu kinaitwa",
            "Chombo kinachotumika kupima joto la hewa kinaitwa",
        ],
    },
}


def build(family: str) -> dict:
    header = {k: v for k, v in json.loads((DEV / family / "fit.json").read_text()).items() if k != "items"}
    items = [{"name": f"s2-{family}-{cond}-{i:02d}", "prompt": p, "condition": cond, "split": "s2"}
             for cond, ps in FILLS[family].items() for i, p in enumerate(ps)]
    return header | {"split": "s2", "source": "experiments/s2_bank.py (hand-authored neutral fills)", "items": items}


def path(family: str):
    return DEV / family / "s2.json"


def load(family: str):
    """The S2 bank of ``family`` as a ``jlm.banks.Bank`` (split "s2": not one of the loader's splits)."""
    from wsbench.banks import load_bank

    from jlm.banks import Bank

    header, items = load_bank(path(family))
    return Bank(family, "s2", path(family), header, items)


def check() -> list[str]:
    """Fills whose text contains any split's target or intermediate (case-insensitive): a leak guard."""
    from jlm import banks

    hits = []
    for family, conds in FILLS.items():
        words = set()
        for split in banks.SPLITS:
            for it in banks.load(family, split).items:
                for w in [it.get("target"), *it.get("target_alts", []), *it.get("intermediates", []), *banks.targets(it)]:
                    if isinstance(w, str) and len(w) >= 4:
                        words.add(w.casefold())
        for cond, ps in conds.items():
            hits += [f"{family}/{cond}: {p!r} contains {w!r}" for p in ps for w in words
                     if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", p.casefold())]
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--capture", action="store_true")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    if args.check:
        print("\n".join(check()) or "no collisions")
        return
    if args.capture:
        from jlm import capture

        for family in FILLS:
            print(capture.run(load(family), args.device), flush=True)
        return
    for family in FILLS:
        path(family).write_text(json.dumps(build(family), ensure_ascii=False, indent=1) + "\n")
        print(f"{path(family)}: {len(build(family)['items'])} items")


if __name__ == "__main__":
    main()
