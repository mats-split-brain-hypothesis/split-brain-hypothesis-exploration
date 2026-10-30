"""Refined imagery contrasts: constructive mental imagery vs low-engagement copying.
Goal: a working direction framed as imagery-enrichment, not thought-suppression."""
from novel2 import _CONCEPTS, _CARRIERS

def make(A_instr, B_instr):
    A,B=[],[]
    for i,c in enumerate(_CONCEPTS):
        car=_CARRIERS[i%len(_CARRIERS)]
        A.append({"user":A_instr.format(c=c,car=car),"assistant":car})
        B.append({"user":B_instr.format(c=c,car=car),"assistant":car})
    return A,B

IM_VARIANTS = {
 # original working
 "v_orig": ("Picture the object {c} vividly in your mind as you write. Now write exactly this sentence: \"{car}\"",
            "Simply transcribe this sentence without thinking of anything: \"{car}\""),
 # mechanical B
 "v_mech": ("Form a vivid mental image of the object {c} as you write. Now write exactly this sentence: \"{car}\"",
            "Copy this sentence in a purely mechanical way, attending only to the letters: \"{car}\""),
 # autopilot B
 "v_auto": ("Build a detailed mental picture of the object {c} as you write. Now write exactly this sentence: \"{car}\"",
            "Write this sentence on autopilot, without forming any mental pictures: \"{car}\""),
 # sensory A, plain B
 "v_sens": ("Call to mind the color, texture and shape of the object {c} as you write. Now write exactly this sentence: \"{car}\"",
            "Write this sentence as plain text, with nothing in mind: \"{car}\""),
 # imagery of scene vs transcription
 "v_scene": ("Visualize the object {c} sitting before you as you write. Now write exactly this sentence: \"{car}\"",
             "Transcribe this sentence as dictation, with your mind empty: \"{car}\""),
}
