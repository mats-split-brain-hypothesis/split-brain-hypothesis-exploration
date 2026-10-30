import json
layers = [18,20,21,22,23,24,26]

# Concrete-noun-ness vs function-word-ness contrast (self-written).
# Condition A: assistant is a concrete noun (varied). Condition B: assistant is a function word (varied).
# The difference of last-token residuals captures a broad "concrete concept" direction, not any one concept.
nouns = ["volleyball","chess","cycling","tennis","baseball","golf","piano","violin","flood","volcano",
         "avalanche","storm","desert","forest","library","kitchen","opera","ballet","poker","archery",
         "submarine","lighthouse","rain","fire","bridge","market","cathedral","harbor","anvil","compass",
         "kayak","accordion","telescope","harvest","glacier","meadow","canyon","temple","carnival","trellis",
         "forge","kennel","atelier","regatta","orchard","aqueduct","observatory","mill","bazaar","vineyard",
         "campfire","river","mountain","ocean","castle","garden","factory","hospital","airport","stadium"]
funcw = ["the","of","and","to","a","in","that","it","is","was","for","on","with","as","by","at","this","from",
         "or","an","be","but","not","are","if","so","than","into","about","over","after","also","just","very",
         "some","such","each","both","which","their","other","more","most","only","same","any","new","now","well"]

UA = "Complete the list with one more item of the same kind:"
# A: concrete nouns ; B: function words
A = [{"user": f"{UA}", "assistant": f" {n}"} for n in nouns]
B = [{"user": f"{UA}", "assistant": f" {w}"} for w in funcw]
json.dump({"layers": layers, "prompts": A, "positions": "last"}, open("work/spec_noun_A.json","w"), ensure_ascii=False)
json.dump({"layers": layers, "prompts": B, "positions": "last"}, open("work/spec_noun_B.json","w"), ensure_ascii=False)
print("nouns", len(A), "func", len(B))
