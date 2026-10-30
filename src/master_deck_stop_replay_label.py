"""Orchestrator + verifier: the without-STOP quote on ib-stop was generated in a replay of one episode's decision turn
(row 2o: turn 2 of round1f H_neither lcbhard_101, which is one of row 1g's 12 time-matched no-STOP episodes). Say so on
the face in plain words (verifier's wording, no run id) and give the trace in the notes. Usage: stop_replay_label.py <ib-stop.html>"""
import sys

p = sys.argv[1]
t = open(p).read()
SERIF = "<p style=\"font-family:'Source Serif 4', Georgia, serif; font-size:26px; font-style:italic; line-height:1.3; color:#3d3833\">"
a = "Qwen’s reasoning</p>\n        " + SERIF + "“Then decide about a hack"
b = ("Qwen’s reasoning · from a replay of one episode’s decision turn, not the episode itself</p>\n        " + SERIF
     + "“Then decide about a hack")
assert t.count(a) == 1, t.count(a)
t = t.replace(a, b)
a2 = "the reasoning at the replayed decision turn)."
b2 = ("the reasoning at the replayed decision turn; the replayed context is turn 2 of round1f H_neither lcbhard_101, one of "
      "the 12 time-matched no-STOP episodes, but the quoted text was generated in the replay).")
assert t.count(a2) == 1, t.count(a2)
t = t.replace(a2, b2)
open(p, "w").write(t)
print("ok")
