import json
layers=[18,20,21,22,23,24,26]
# Self-authored think/don't-think pairs using the bench's exact verb-pair structure and
# "the {category} {concept}" phrasing, but my OWN concepts and carrier sentences.
# Verb pairs (matched think/dont-think):
verbs = [
    ("Keep the {cat} {c} in your thoughts as you write.", "Keep the {cat} {c} out of your thoughts as you write."),
    ("Hold the {cat} {c} in mind as you write.", "Put the {cat} {c} out of your mind as you write."),
    ("Concentrate on the {cat} {c} while you write.", "Avoid thinking about the {cat} {c} while you write."),
    ("Think about the {cat} {c} while you write.", "Do not think about the {cat} {c} while you write."),
    ("Try to focus on the {cat} {c} as you write the sentence.", "Try hard not to think about the {cat} {c} as you write the sentence."),
]
# (category, concept, carrier) -- my own
items = [
    ("instrument","clarinet","The quarterly figures were sent to the board."),
    ("animal","badger","Please submit your timesheet by Thursday."),
    ("body part","radius","The budget review was postponed until Monday."),
    ("vehicle","gondola","Our flight to the conference leaves at noon."),
    ("fruit","papaya","The training session will be recorded for later."),
    ("metal","cobalt","The parking garage will close early on Friday."),
    ("vegetable","kale","The shipment arrived two days ahead of schedule."),
    ("planet","Saturn","The new policy takes effect next month."),
    ("shape","trapezoid","The draft was shared with the whole team."),
    ("gemstone","garnet","The server maintenance window starts at midnight."),
    ("dessert","macaron","The survey results will be published next week."),
    ("boat","trimaran","The printer on the third floor needs new toner."),
    ("chess piece","rook","The committee approved the minutes without changes."),
    ("footwear","moccasin","All staff must complete the training by Friday."),
    ("emotion","envy","The contract was signed by both parties today."),
    ("sea creature","octopus","The elevator is out of service until further notice."),
    ("word","thunder","The results exceeded our expectations this quarter."),
    ("bird","falcon","The meeting was moved to the larger conference room."),
    ("color","indigo","The database backup completed successfully overnight."),
    ("tool","wrench","The application deadline has been extended one week."),
    ("flower","dahlia","The new software update will deploy on Sunday."),
    ("tree","willow","The invoice was processed and paid last week."),
    ("country","Bhutan","The presentation slides are in the shared folder."),
    ("sport","fencing","The weather forecast predicts rain all weekend."),
    ("dance","tango","The keys are in the drawer by the front desk."),
    ("fabric","linen","The report needs to be reformatted before sending."),
]
TAIL = ' Now write exactly this sentence: "{carrier}"'
A=[]; B=[]
for i,(cat,c,carrier) in enumerate(items):
    vp, vn = verbs[i % len(verbs)]
    a = vp.format(cat=cat,c=c) + TAIL.format(carrier=carrier)
    b = vn.format(cat=cat,c=c) + TAIL.format(carrier=carrier)
    A.append({"user": a, "assistant": carrier})
    B.append({"user": b, "assistant": carrier})
json.dump({"layers":layers,"prompts":A,"positions":"assistant"}, open("work/spec_self_A.json","w"), ensure_ascii=False)
json.dump({"layers":layers,"prompts":B,"positions":"assistant"}, open("work/spec_self_B.json","w"), ensure_ascii=False)
print("self pairs", len(items))
