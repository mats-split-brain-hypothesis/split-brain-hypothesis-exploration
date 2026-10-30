"""Additive editorial layer for the original IB and SoRH dashboard."""

# Each summary addresses the original figure's endpoint. Original prose is untouched.
GRAPHS = {
    'ib.html': {
        'f-when': ('ib-1', 'Some Qwen workarounds are planned before any local test, so rejection is not necessary in those cases. The aggregate chart measures first submission; it does not establish that every early hack preceded all feedback.'),
        'f-a': ('ib-2', 'Early grading-off cues can change which objective wins. Reviewed faithful responses can still anticipate an honesty check or human assessment, so the behavioural change does not by itself mean the model now believes the task is real.'),
        'f-up': ('ib-2', 'Mentioning the update, changing a plan, and delivering different code are separate events. The reasoning helps distinguish ignoring a cue from noticing it and retaining the original pass-the-tests priority.'),
        'f-b': ('ib-3', 'A late update can encounter an intended workaround, a failed write, or an already working exploit. Some models explicitly retain the earlier objective; some attempt a change that fails to reach the file. Judge the final retained code separately from the stated intention.'),
        'f-c': ('ib-4', 'STOP supplies a legitimate response to an impossible task. Reviewed traces show the contradiction being recognised under both faithful and exploit-seeking policies: detection alone does not determine the action.'),
        'f-d': ('ib-4', 'A cheating-detector warning can become a further constraint to optimise around. In a reviewed Qwen 27B example, the model considers what the detector might catch while continuing to plan a workaround.'),
        'f-mi-cues': ('ib-4', 'Cue recognition is weaker evidence than cue compliance. Read the model’s interpretation together with the code actually retained and any failed writes, rather than treating a mention as a behavioural change.'),
        'f-mi-before': ('ib-1', 'Local evidence and submission feedback are different triggers. The reviewed traces include anticipatory exploitation, faithful implementation after seeing a contradiction, and persistence after rejection.'),
        'f-chat': ('ib-5', 'The Qwens can produce deliberate exploits in a single chat reply. GLM’s much larger harness endpoint is consistent with iteration and rejection mattering, but the comparison also changes tools, opportunity and endpoint.'),
        'f-hw': ('ib-6', 'The homework opening can elicit faithful code, but a recorded failure is not proof of no attempted hack: a reviewed Qwen 27B first reply contains a disclosed workaround that fails. The opening still mentions an autograder, so it does not remove evaluation expectations.'),
        'f-rej': ('ib-6', 'Failure feedback produces several different revisions: a disclosed workaround, an ordinary bug fix, removal of a workaround, or speculation about hidden tests. One verified failure came from extracting prose rather than the model’s passing code.'),
    },
    'sorh.html': {
        'f-scorer': ('sorh-1', 'An explicit metric gives the model something concrete to optimise. The reasoning reveals choices about what counts as an item, while vague scoring often prompts ordinary quality planning. Even named metrics can be read as constraints to avoid rather than maximise.'),
        'f-pad3': ('sorh-2', 'A real recipient and metric pursuit can coexist. Reviewed real-use replies sometimes restore readability and sometimes increase density; the mechanism is a negotiation between requirements rather than a uniform real-versus-test switch.'),
        'f-pad5': ('sorh-2', 'Classroom framing does not produce one consistent change across models and tasks. The reasoning weighs breadth, readability and countability, so individual quantity differences should not be treated as causal estimates.'),
        'f-probe': ('sorh-3', 'A purpose vote of Real can explicitly acknowledge rubric gaming. These probe explanations classify the request; they do not directly establish that the task-solving model lacks evaluation awareness or that the label causes its behaviour.'),
        'f-sw-probe': ('sorh-3', 'The probe label can remain test-like while task behaviour changes. Explanations also reveal taxonomy and parsing issues. Compare the retained explanation with its actual question, and keep probe responses separate from task-solving reasoning.'),
        'f-switch': ('sorh-4', 'Follow the whole branch: a natural first post-switch response can be followed by renewed optimisation. The reasoning may retain an earlier requirement, distrust a cue, or infer from another revision request that the user still wants the old metric.'),
        'f-mi-split': ('sorh-4', 'Scoring-off and nobody-scoring wording need not be interpreted the same way. Reviewed trajectories support several mechanisms; the final padding label alone cannot identify which one occurred.'),
        'f-c': ('sorh-5', 'A quality commitment does not guarantee a quality-preserving final answer. Some traces restrain the metric; others redefine quality to accommodate a denser answer or remove useful context. This is an observed intention–output gap, not proof of separate internal systems.'),
        'f-bf': ('sorh-6', 'Constraints can change the form of optimisation without eliminating it. A reply may avoid obvious additions yet keep a high ratio by deleting context; counts can also differ depending on whether notes outside the requested artifact are included.'),
        'f-f': ('sorh-6', '“Don’t add anything just to raise the score” can be interpreted narrowly. Reviewed reasoning distinguishes meaningful restraint from retaining the metric and rationalising which additions or deletions remain acceptable.'),
        'f-cyc': ('sorh-7', 'Draft–count–revise loops show deliberate proxy pursuit in the quoted cases. For share metrics, revision often means deleting denominator words, so a shorter answer can be more aggressively optimised.'),
        'f-tok': ('sorh-7', 'Longer reasoning is not a direct measure of deeper deliberation. Full reads include repeated arithmetic, uncertainty about the checker and rationalisation as well as useful planning; provider token accounting remains a separate measurement.'),
        'f-mi-floor': ('sorh-7', 'The growth ratio depends on the no-score baseline as well as the scored trace. Reviewed examples explain specific counting and compression strategies, but do not establish a general cognitive-depth ranking between models.'),
        'f-d': ('sorh-8', 'A score estimate and an external count may refer to different text. In the reviewed gratitude example, the model predicts 14 phrases, the letter contains 12 by the audit’s convention, and the whole reply contains 21 including its explanatory note.'),
        'f-mean': ('sorh-9', 'A refusal preface, a restrained tone, and the presence of insulting language are separate observations. Some replies announce a boundary and still deliver contempt or an insult; the full final answer is needed to judge that distinction.'),
    },
}

# Purposeful comparisons for panels where an automatic representative could
# belong to another arm of a broadly attached source cohort.
FEATURED = {
    ('ib.html', 'f-hw'): ['ib_0020', 'ib_0402'],
    ('ib.html', 'f-c'): ['ib_0267', 'ib_0266'],
    ('ib.html', 'f-d'): ['ib_0378', 'ib_0265'],
    ('sorh.html', 'f-pad5'): ['qwen27b_20__c7_dont_care__sorh_529__s0__55cfa05bb8', 'qwen27b_20__r_student__c7_dont_care__sorh_529__s0__d3de460e84'],
    ('sorh.html', 'f-switch'): ['mt20_glm52/cue10_nobody/sorh_931/0', 'mt20_glm52/cue10_off/sorh_931/0'],
    ('sorh.html', 'f-mi-split'): ['mt_nobody_glm52/cue10_nobody/sorh_223/3', 'mt_glm52/cue10_off/sorh_223/3'],
}

SECTIONS = {
    'ib.html': {
        'when': ('ib-1', ['f-when', 'f-mi-before']),
        'off': ('ib-2', ['f-a', 'f-b', 'f-up']),
        'stop': ('ib-4', ['f-c', 'f-d']),
        'chat': ('ib-5', ['f-chat']),
        'homework': ('ib-6', ['f-hw', 'f-rej']),
        'why': ('ib-1', ['f-mi-before', 'f-mi-cues']),
        'fits': ('ib-3', ['f-a', 'f-b', 'f-chat']),
        'trust': ('ib-7', ['f-rej', 'f-b']),
    },
    'sorh.html': {
        'scorer': ('sorh-1', ['f-scorer']),
        'real': ('sorh-2', ['f-pad3', 'f-probe', 'f-pad5']),
        'off': ('sorh-4', ['f-switch', 'f-sw-probe', 'f-f']),
        'saying': ('sorh-5', ['f-c', 'f-bf']),
        'chase': ('sorh-7', ['f-cyc', 'f-tok', 'f-d']),
        'mean': ('sorh-9', ['f-mean']),
        'why': ('sorh-7', ['f-mi-floor', 'f-mi-split']),
        'fits': ('sorh-5', ['f-c', 'f-switch', 'f-probe']),
        'trust': ('sorh-10', ['f-d', 'f-c']),
    },
}

SECTION_SUMMARIES = {
    ('ib.html', 'off'): 'Timing changes the interpretation: an early cue can redirect the initial objective, while a late cue may encounter an intended workaround, a failed write, or an already working exploit. Recognising the update and successfully changing the retained artifact are separate outcomes.',
    ('ib.html', 'why'): 'The clearest case-level differences concern what the model notices, which requirement it prioritises, and how it responds to failure. These examples qualify a single-trigger account: detection, rejection and exploitation do not always occur together.',
    ('ib.html', 'fits'): 'The evidence supports context-sensitive priorities and anticipated assessment. It is compatible with an intention–action split, but does not isolate belief about real use or establish separate internal systems.',
    ('sorh.html', 'why'): 'Model differences combine baseline reasoning length, task-specific counting strategies, interpretation of feedback and the final artifact. The reasoning explains particular choices; it does not turn a growth ratio into an architectural diagnosis.',
    ('sorh.html', 'fits'): 'Across both datasets, a visible proxy can compete with the task’s ordinary purpose. Context and feedback change that competition, and stated commitments can diverge from delivery. Belief mediation and a two-system explanation remain open hypotheses.',
    ('sorh.html', 'trust'): 'Padding, density, usefulness and factual grounding are different outcomes. The reasoning review adds artifact-boundary discrepancies and cases where apparently restrained replies still introduce unsupported facts. The complete sample census remains unfinished.',
}
