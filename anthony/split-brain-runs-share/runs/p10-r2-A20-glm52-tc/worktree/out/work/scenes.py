# Self-authored scenes evoking concepts NOT in the association fit target set.
# Each scene implies a concept without naming it.
SCENES = [
 ("chess", "She castled early and sacrificed a bishop to spring the mating trap on his king."),
 ("ballet", "She rose onto her toes and spun through three turns before landing in a silent fifth position."),
 ("soccer", "The striker chested down the cross and volleyed it past the keeper into the top corner."),
 ("fishing", "He tied a fly to the leader and false-cast twice before laying the line on the glassy current."),
 ("skiing", "She planted her poles and arced parallel turns down the groomed face, carving clean tracks."),
 ("archery", "She drew the bowstring to her cheek, held, and loosed; the shaft thudded into the gold ring."),
 ("opera", "The soprano held the high note through the crescendo as the chorus swelled behind her."),
 ("guitar", "He fretted a barre chord and strummed, then bent the high string up a whole step."),
 ("knitting", "She worked the yarn between the needles, slipping stitches to shape the cable pattern."),
 ("pottery", "She centred the clay on the wheel and drew up the walls into a thin, even vessel."),
 ("fencing", "He lunged, extending the blade, and his tip flicked his opponent's guard before the parry."),
 ("yoga", "She folded forward from the hips, pressing her palms flat beside her feet in a steady breath."),
 ("running", "He settled into his stride, arms pumping, as the kilometre markers ticked past on the course."),
 ("swimming", "She rolled to breathe on every third stroke of her freestyle, kicking in a steady flutter."),
 ("climbing", "He flagged his leg to shift his weight and reached for the crimp above the overhang."),
 ("baking", "She folded the dough in thirds, chilled it, and rolled it out again for the third turn."),
 ("judo", "He gripped the lapel and sleeve, stepped in, and threw his partner flat onto the mat with a hip sweep."),
 ("cricket", "The batsman leaned into the drive and sent the red ball racing through the covers for four."),
 ("hockey", "He carried the puck down the wing and wristed a shot over the goalie's glove into the top corner."),
 ("boxing", "He slipped the jab and countered with a sharp right cross that snapped his opponent's head back."),
 ("rowING", "She squared the blades and pulled through the drive, sliding the seat forward as the shell glided."),
 ("camping", "He pitched the fly and gathered dry kindling to lay a small fire beside the tent."),
 ("sculpture", "She chipped the marble away with a chisel, finding the figure hidden inside the block."),
 ("sailing2", "She sheeted in the main as the boat heeled and the wake foam hissed over the leeward rail."),
]
# verify concepts not in association targets
import json
tgts=set(t.lower() for i in json.load(open('data/dev/association/fit.json'))['items'] for t in i['intermediates'])
bad=[c for c,_ in SCENES if c.lower() in tgts]
assert not bad, bad
print(len(SCENES),"scenes, none in targets")
