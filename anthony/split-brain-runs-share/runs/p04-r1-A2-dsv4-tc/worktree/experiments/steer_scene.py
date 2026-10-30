"""Scene-concept vs neutral-prose contrasts (complete sentences, matching association's render)."""
import sys, os, torch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import metric
LAYERS = [26, 28, 30]

SCENE = [
 "She swung the racquet and watched the ball clear the net.",
 "He dipped the brush in paint and stroked the canvas.",
 "The children built towers of sand near the crashing waves.",
 "She read the sheet music and pressed the ivory keys.",
 "He laced up his skates and stepped onto the frozen pond.",
 "The dough rose slowly under the warm cloth.",
 "She wrapped the gift and tied a bow on top.",
 "He turned the wrench until the pipe stopped leaking.",
 "The seeds sprouted into rows of green shoots.",
 "She shuffled the deck and dealt five cards to each player.",
 "He strapped on the mask and dove under the surface.",
 "The actors took their places as the curtain rose.",
 "She pressed the shutter and the flash went off.",
 "He pedaled harder as the hill grew steeper.",
 "The conductor raised his baton and the orchestra began.",
 "She threaded the needle and pulled the cloth taut.",
 "He threw the clay onto the wheel and shaped it with wet hands.",
 "The keys clattered as her fingers flew across the board.",
 "She rolled the dough flat and spread sauce across the top.",
 "He climbed the ladder and hammered the shingle into place.",
 "The ball arced high and dropped through the metal hoop.",
 "She trimmed the stems and arranged the blooms in a vase.",
 "He cast the line and waited for a tug on the rod.",
 "The chef whisked the eggs and folded in the flour.",
 "She glided down the slope, poles planted, snow spraying behind.",
 "He lifted the barbell and pushed it high above his chest.",
 "The plane taxied down the runway and lifted into the sky.",
 "She measured the planks and sawed along the penciled line.",
 "He stirred the pot and tasted the simmering broth.",
 "The horse galloped down the track toward the finish.",
 "She applied the brush strokes and blended the colors on the canvas.",
 "He strummed the strings and hummed along with the melody.",
 "The referee's whistle stopped play as the crowd roared.",
 "She punched the dough down and let it rest a second time.",
 "He loaded the reel and flicked the lure toward the reeds.",
 "The climber chalked his hands and reached for the next hold.",
 "She spun the wheel and guided the car around the corner.",
 "He blew into the mouthpiece and pressed the valves in turn.",
 "The waiter balanced the tray and wove between the tables.",
 "She set the anchor and furled the sail against the wind.",
]
NEUTRAL = [
 "The weather was pleasant that afternoon.",
 "He arrived at the station just before noon.",
 "The room was quiet for a long moment.",
 "She looked out the window at the street below.",
 "The meeting ran longer than anyone expected.",
 "He put his coat on and reached for the door.",
 "The city looked different in the early light.",
 "She wrote the number down on a piece of paper.",
 "The clock on the wall was two minutes slow.",
 "He poured a glass of water and sat down.",
 "The phone rang twice before it stopped.",
 "She folded the letter and put it in her pocket.",
 "The bus pulled away from the curb.",
 "He checked his watch and quickened his pace.",
 "The lamp cast a soft glow across the desk.",
 "She opened the window to let in some air.",
 "The hallway was dark and quiet.",
 "He finished his coffee and reached for his bag.",
 "The pages of the book were worn at the corners.",
 "She turned the key and the engine started.",
 "The shelf sagged under the weight of the books.",
 "He glanced at the calendar on the wall.",
 "The sidewalk was wet from the morning rain.",
 "She waited at the crosswalk for the light to change.",
 "The kettle began to whistle on the stove.",
 "He tucked the receipt into his wallet.",
 "The trees swayed gently in the breeze.",
 "She tightened the lid on the jar.",
 "The train was delayed by half an hour.",
 "He set the box down beside the door.",
 "The curtains moved slightly in the draft.",
 "She turned off the light and closed the door.",
 "The note was short and to the point.",
 "He adjusted his glasses and cleared his throat.",
 "The floor creaked under her careful steps.",
 "She counted the change into her palm.",
 "The radio played softly in the background.",
 "He hung his keys on the hook by the door.",
 "The shadows lengthened as the day wore on.",
 "She smoothed the blanket and settled in.",
]
QUESTION = [
 "What do you call a baby cat?",
 "What is the capital of France?",
 "How many legs does a spider have?",
 "What colour is a ripe banana?",
 "What planet is closest to the Sun?",
 "What food do bees make?",
 "How many days are in a week?",
 "What is the largest ocean?",
 "What do you call a young dog?",
 "What is the chemical symbol for gold?",
 "What is the square root of one hundred and forty four?",
 "What do birds use to fly?",
 "What is the currency of Japan?",
 "What is the tallest animal on Earth?",
 "What does a chef use to cut vegetables?",
 "What is the colour of fresh snow?",
 "What do you call a group of lions?",
 "What is the fastest land animal?",
 "What is the main ingredient in bread?",
 "What do astronauts travel in?",
 "What is the longest river on Earth?",
 "What do you use to write on a blackboard?",
 "What has two wheels and an engine?",
 "What is the name of Earth's natural satellite?",
 "What season comes after winter?",
 "What is the study of stars called?",
 "What do you wear on your feet?",
 "Where are books kept for borrowing?",
 "What is the opposite of big?",
 "How many continents are there?",
 "What do doctors use to listen to your heart?",
 "What is a common breakfast drink?",
 "What do you call a person who flies a plane?",
 "What covers most of the Earth's surface?",
 "What do fish use to breathe?",
 "What is the tallest mountain in the world?",
 "What do you use to cut paper?",
 "What is the primary source of light on Earth?",
 "What do cows give us to drink?",
 "What is the hardest natural substance?",
]

def cap(name, prompts, positions="last"):
    p = Path(f"out/steer/caps/{name}.pt")
    if p.exists() and not os.environ.get("RECAP"):
        return {int(k): v.float() for k, v in torch.load(p, weights_only=False)["mean"].items()}
    out = metric.capture({"layers": LAYERS, "prompts": [{"user": x} for x in prompts], "positions": positions})
    p.parent.mkdir(parents=True, exist_ok=True); torch.save(out, p)
    print(f"captured {name} n={out['n_prompts']} pos={positions}", flush=True)
    return {int(k): v.float() for k, v in out["mean"].items()}

def fam(name):
    d = torch.load(f"out/steer/caps/{name}.pt", weights_only=False)
    return {int(k): v.float() for k, v in d["mean"].items()}, d["n_prompts"]

def pooled(fams):
    tot = 0; acc = {L: torch.zeros(2560) for L in LAYERS}
    for f in fams:
        m, n = fam(f)
        for L in LAYERS: acc[L] += m[L] * n
        tot += n
    return {L: acc[L] / tot for L in LAYERS}

def test(name, A, B, scales, positions="read", sign=1.0):
    vecs = {int(L): sign * (A[L] - B[L]) for L in LAYERS}
    torch.save(vecs, f"out/steer/{name}.pt")
    print(f"\n=== {name} pos={positions} ===", flush=True)
    for L in LAYERS: print(f"  L{L} ||v||={float(vecs[L].norm()):.2f}")
    for s in scales:
        r = metric.run_metric(vecs, positions, s)
        print(f"  scale {s:+.1f}: pass@10 {r['pass_at_10']:.4f}  meanlog10 {r['mean_log10_rank']:.4f}", flush=True)
        for e in r['examples']:
            print(f"     {e['id']} {e['target']}: {e['baseline_rank']} -> {e['best_rank']}")

if __name__ == "__main__":
    scene = cap("scene", SCENE, "last")
    neutral = cap("neutral", NEUTRAL, "last")
    question = cap("question", QUESTION, "last")
    fampool = pooled(["basic_readout", "typo", "multilingual", "multihop"])
    which = sys.argv[1] if len(sys.argv) > 1 else "scene_neutral"
    if which == "scene_neutral":
        test("scene_minus_neutral", scene, neutral, [1.0, 2.0, 4.0])
        test("neutral_minus_scene", neutral, scene, [1.0, 2.0])
    elif which == "fam_neutral":
        test("fam_minus_neutral", fampool, neutral, [1.0, 2.0, 4.0])
    elif which == "scene_question":
        test("scene_minus_question", scene, question, [1.0, 2.0])
    elif which == "question_neutral":
        test("question_minus_neutral", question, neutral, [1.0, 2.0])
