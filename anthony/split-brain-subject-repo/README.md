# j-lens-mean 

J_l (h_l - mu_l)

Properties we want:
Generalizable
Ideally cheap
‘Fair’ (not cheating)
Principled (not cheating)

How the lens gets read out -> the mean might be either position dependent or depend on the type of token you are reading out (e.g. “:” might be different from “hello”)

Look into positional embeddings

Model mu_l:
Spectrum of how sophisticated the methodology is e.g. mathematically speaking
Spectrum of how empirical vs theoretical the construction is 
Random vector (control)
Representation of the most abstract word you can think of to represent the category (e.g., bunch of typos -> typo), also steering vectors (magnitude of the steering vector would probably have to be tuned)
Mean across similar, neutral contexts to extract the thing at the top of the model’s mind (which isn’t background noise, but also not polluted by prompt content)
Reconstructing the ‘optimal’ mean from what we want the model to surface… (from the targets of e.g. of Workspace Bench, of e.g. lying/truthful-related concepts in the Liar’s Bench)
Mean could depend directly on the recent activations in the given context (e.g. g(h_l(t), h_l(t-1), …)
Activation clusters -> taking a mean per cluster + 

Basic science:
Want development/validation sets for the Workspace Bench (should be pretty easy to generate with agents + J++ released some)
Use various fits of the J-lens to make sure 
Look at how averaging changes when averaged over n = 1, 5, 10, 100, … etc



The way the lens is read out -> with/without norm (something to control for). (Smaller details to check for)


