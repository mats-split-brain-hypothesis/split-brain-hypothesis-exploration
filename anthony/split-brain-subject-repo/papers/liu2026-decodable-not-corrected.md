# Decodable but Not Corrected by Fixed Residual-Stream Linear Steering: Evidence from Medical LLM Failure Regimes

Ming Liu

## Abstract

Can linearly decodable failure signals in LLM hidden states be leveraged to correct those failures? We investigate this *classification-correction gap* via *Overthinking* (OT)—a stable behavioral regime (Jaccard $\geq 0.81$, 94% inter-annotator agreement) in medical QA where models answer correctly under resampling yet fail in extended chain-of-thought. OT is linearly decodable at 71.6% balanced accuracy ($p\approx 10^{-16}$). Yet five families of fixed linear steering (29 configurations, $n=1{,}273$) all yield $\Delta\approx 0$, with identical null results cross-architecture (Qwen2.5-7B) and cross-domain (MMLU-STEM). Three convergent lines of evidence suggest *representational entanglement*: the OT direction has 85–88% overlap with task-critical computation (specificity ratio $\leq 0.152$); non-targeted shared-direction steering damages accuracy ($-$12.1pp); and LEACE concept erasure damages accuracy ($-$3.6pp, $p=0.01$), while 10 random erasures produce $\Delta=+0.3$pp. The per-instance probe–steering correlation is $r=-0.002$ ($p=0.97$). Positively, the same probe enables selective abstention (held-out AUROC = 0.610, exceeding all five uncertainty baselines, $p=0.009$): decodable failure structure supports post-generation reliability estimation even when the fixed linear steering family cannot exploit it for correction.

## 1 Introduction

Activation steering—adding directions in activation space to modify model behavior—succeeds for binary behavioral properties like refusal (Arditi et al., 2024) and sentiment (Turner et al., 2024). But does this extend to correcting multi-step reasoning failures? Chain-of-thought prompting (Wei et al., 2022; Kojima et al., 2022) enables multi-step reasoning but also introduces failure modes tied to extended generation (Turpin et al., 2023; Lanham et al., 2023); indeed, Huang et al. (2024) show that LLMs cannot self-correct reasoning without external feedback. We use medical question answering as a controlled testbed: it demands multi-step reasoning, failures carry distinct semantic signatures, and the multiple-choice format provides an unambiguous evaluation endpoint.

We focus on a specific empirical question: *when models frequently answer correctly yet sometimes fail through extended reasoning, can the representational structure underlying this behavioral regime be leveraged for activation steering?*

We address this question through a systematic investigation with four contributions:

1. 1. Behavioral regime identification. We identify *Overthinking* (OT)—where models frequently answer correctly under alternative sampled traces but produce incorrect long-reasoning outputs—as a robust behavioral construct, stable under threshold perturbation, length regression, and prompt-end probing (Section 3).

2. 2. Geometric analysis. Binary OT-vs-non-OT classification achieves 71.6% (modest but highly reliable; $p\approx 10^{-16}$), with supporting evidence on Qwen2.5-7B and cross-domain transfer to MMLU-STEM (decodability and steering failure). The OT-specific specificity ratio is only 0.119 (88% of the signal is shared with task-relevant directions), and concept erasure damages accuracy ($-3.6$pp, $p=0.01$), providing causal evidence that the decodable signal is entangled with task computation rather than merely correlational.

3. 3. An empirical classification-correction gap. Five families of fixed linear steering (contrastive, probe-guided, multi-layer, prompt-end, and subspace; 29 configurations total, $n=1{,}273$) on Llama-3.1-8B produce $\Delta\approx 0$, while shared-direction steering ($-$12.1pp) and mean-difference concept erasure ($-$3.6pp, $p=0.01$; direction-specific vs. random erasures) damage accuracy—consistent with failure-mode information co-occurring with task-relevant computation. Qwen2.5-7B (9 configurations), MMLU-STEM (4 configurations), and ten prompt baselines including self-refinement and verbalized confidence are consistent with this pattern. A refusal-steering control verifies the implementation ($p=0.008$, one-sided).

4. 4. Post-generation reliability estimation. The same structure enables selective abstention after a single generation: a correctness probe (layer 21, selected via held-out AUROC from a 32-layer scan) achieves held-out split AUROC = 0.716 (held-out test: 0.610; generalization gap is primarily temperature-driven), outperforming all five tested single-forward-pass uncertainty baselines ($\Delta$AUROC = 0.041, $p=0.009$; Holm rank-1 threshold = 0.010). *Reading* representations has operational value even when linear *writing* to them does not—probing success, even when robust and cross-domain transferable, does not imply steerability.

## 2 Related Work

### Linear directions can steer binary behavioral attributes—but unreliably.

Representation engineering (Zou et al., 2023) shows that linear directions correspond to interpretable concepts. Inference-time intervention (Li et al., 2023), activation addition (Turner et al., 2024), contrastive activation addition (Panickssery et al., 2023), mean-centred variants (Jorgensen et al., 2023), and feature clamping via sparse autoencoders (Templeton et al., 2024; Cunningham et al., 2023) demonstrate successful steering for binary behavioral traits (refusal, sentiment, sycophancy (Sharma et al., 2024)) and in-context task identity (Todd et al., 2024), while model editing (Meng et al., 2022) modifies localized factual associations. Layer-contrast decoding (Chuang et al., 2024) provides an alternative inference-time intervention that improves factuality by exploiting layer-wise knowledge maturation. Representation finetuning (Wu et al., 2024) instead *learns* targeted interventions on frozen representations. However, growing evidence reveals systematic steering failures: Da Silva et al. (2025) find substantial variability across 36 models from 14 families; Braun et al. (2025) document concepts that remain unsteerable across all layers; McKenzie et al. (2026) identify endogenous resistance circuits that actively counteract interventions; and Zur et al. (2025) show steering fails once a model has committed to a reasoning path—even when hidden states still encode uncertainty. Jafari et al. (2026) propose mechanistic indicators for predicting effectiveness a priori, and Billa (2026) formalize a three-regime framework in which some concepts are provably beyond any linear intervention’s reach.

### But probed information need not be causally effective.

The linear representation hypothesis (Park et al., 2024; Marks and Tegmark, 2024; Nanda et al., 2023; Hernandez et al., 2024) and probing methods (Alain and Bengio, 2017; Belinkov, 2022; Hewitt and Liang, 2019) establish that LLMs encode rich structure—including correctness signals (Azaria and Mitchell, 2023; Burns et al., 2023)—but whether probed information is *causally* used remains contested (Elazar et al., 2021; Ravfogel et al., 2022). Deng et al. (2025) argue confounding bias can cause probes to find correlational rather than causal directions; however, our LEACE erasure result ($-3.6$pp damage, direction-specific) rules out the purely correlational account in our setting, instead supporting causal entanglement with task computation. Concept erasure methods—INLP (Ravfogel et al., 2020), RLACE (Ravfogel et al., 2022), LEACE (Belrose et al., 2023)—and causal mediation (Vig et al., 2020; Geiger et al., 2024) test this distinction. Hase et al. (2023) show that localizing facts does not predict editing success, foreshadowing the gap we observe.

The decodability–steerability gap is now documented across multiple domains. Wu et al. (2025) benchmark this at scale: on Gemma-2, difference-of-means probes achieve best concept detection while prompting outperforms all representation-based steering methods. Basu et al. (2026) find 98% AUROC internal hazard representations in clinical triage that four mechanistic interventions fail to exploit. Sanyal et al. (2025) and Cox et al. (2026) report analogous gaps in math solvability and factual reasoning. Wang et al. (2026) coin “representation-behavior gap” for the same phenomenon in tool-calling agents (99% probe AUC, model still fails to act). Mishra et al. (2026) prove steered activations leave the prompt-reachable set; Nadaf (2026) document the inverse (steerability without decodability). Theoretically, Gao et al. (2026) extend the linear representation hypothesis to show that concept overlap creates intrinsically unpredictable “sensitive sectors,” while Wollschläger et al. (2025) prove that geometric orthogonality does not guarantee interventional independence. When representations are encoded in superposition (Elhage et al., 2022)—sharing directions across features—additive steering along one feature’s direction inevitably perturbs others.

### Our contribution: mechanistic explanation, not just documentation.

While the gap’s existence is now established across several concurrent works (Wu et al., 2025; Basu et al., 2026; Wang et al., 2026), none provides: (a) systematic geometric characterization of *why* steering fails in a specific domain—we show the OT-specific specificity ratio is only 0.119, meaning 88% of the contrastive signal is shared with task-relevant computation, and concept erasure *damages* accuracy ($-3.6$pp, $p=0.01$), confirming the entanglement is causal rather than merely correlational; (b) per-instance analysis showing probe confidence and steering effect are completely uncorrelated ($r=-0.002$, $p=0.97$); or (c) an operational positive—redirecting decodable structure toward selective abstention. We test the commonly assumed probing-to-steering move in multi-step medical reasoning (Jin et al., 2021; Singhal et al., 2023; Nori et al., 2023)—a domain where overthinking degrades accuracy (Chen et al., 2024; Wang et al., 2025) and chain-of-thought benefits remain limited compared to symbolic tasks (Sprague et al., 2024)—with five method families (29 configurations), and provide convergent geometric evidence (low specificity, directional damage, cross-domain subspace degradation) that the gap arises from representational entanglement with task computation, consistent with the structurally unreachable regime of Billa (2026). This contrasts with domains where steering succeeds (factual recall (Li et al., 2023), refusal (Arditi et al., 2024))—where target directions have higher specificity ratios (refusal: 0.999 vs. OT: $\leq$0.21; a $4.7\times$ gap that is predictive of steerability in our two-point comparison).

## 3 Failure Characterization

We characterize failures along two axes. Axis A (primary): Behavioral regime (OT vs. non-OT), defined by cross-trace statistics and carrying our strongest claims. Axis B (exploratory): Error mechanism (KD vs. RCB, within non-OT only), defined by semantic judgment with lower inter-annotator agreement. Core findings do not depend on the KD/RCB boundary.

### Primary construct: Overthinking (OT).

We use “Overthinking” as a behavioral label for a sampling-level pattern, not as a claim about internal cognitive mechanism; cf. Chen et al. (2024) on excessive computation in o1-like models and Muennighoff et al. (2025) on budget forcing. Operationally: the model answers correctly in $\geq$60% of sampled traces (Wang et al., 2023)—a conservative majority threshold—but produces incorrect answers in long-reasoning traces ($>$200 tokens). The length threshold is nearly redundant ($>$99% of incorrect traces exceed 200 tokens), so the effective OT boundary is determined by the correct-rate threshold. OT is defined by *observable behavioral statistics*, yielding high reproducibility: 94% expert agreement, 100% within-question purity, and Jaccard $\geq$0.81 under threshold perturbation (Section 4). Length regression and prompt-end probing (54.4% vs. 50% chance) confirm OT reflects a generation-time regime rather than question difficulty or response length alone. Our research question is whether representational structure tracking this regime can support correction, regardless of what mechanism produces it (Turpin et al., 2023).

### Exploratory sub-classification: KD and RCB.

Within non-OT failures, *Knowledge Deficit* (KD) denotes factual errors and *Reasoning Chain Break* (RCB) denotes valid-fact/invalid-logic errors. This distinction requires semantic judgment ($\kappa=0.61$ expert-expert, $\kappa=0.30$ LLM; Section 3.3).

### 3.1 Annotation Pipeline

Annotation proceeds in two phases: (1) heuristic OT detection—if $\geq$60% of 10 sampled traces are correct, incorrect traces $>$200 tokens are labeled OT; (2) LLM-based KD/RCB classification of remaining traces via Claude Haiku (Anthropic, 2024) following the LLM-as-judge paradigm (Zheng et al., 2023). Full prompt and pipeline details are in Appendix A.5.

### 3.2 Annotation Statistics

|  | KD | RCB | OT | Unclear |
|---|---|---|---|---|
| Llama-3.1-8B | 7,419 | 11,895 | 10,713 | 4,505 |
|  | (21.5%) | (34.5%) | (31.0%) | (13.0%) |
| Qwen2.5-7B | 12,960 | 13,629 | 6,306 | 6,967 |
|  | (32.5%) | (34.2%) | (15.8%) | (17.5%) |

*Table 1: Failure mode annotation distribution. Values show count and percentage of all incorrect traces. Llama annotations are over 34,532 traces from 10,178 MedQA questions (10 traces/question). Qwen annotations are over 39,862 traces from the same questions.*

Table 1 shows the annotation distribution. RCB is the most common failure mode (34.5%), followed by OT (31.0%) and KD (21.5%), with consistent proportions across architectures. Unclear cases (13.0%/17.5%) are excluded from subsequent analysis.

### 3.3 Annotation Validation

Domain expert validation ($n=500$ gold set, two blinded 4th-year clinical students) yields 94% agreement on OT, with expert-expert $\kappa=0.61$ on the three-way task; the KD/RCB boundary is the primary source of disagreement. Within-question OT purity is 100% (all incorrect traces from an OT question receive the same label). Simulating 37% KD/RCB label noise (matching observed LLM disagreement) drops three-way classification only 2.9pp while leaving the binary OT-vs-non-OT result (71.6%) unaffected. Full validation details (LLM cross-validation, multi-model comparison, within-question consistency analysis) are in Appendix A.6.

### 3.4 Behavioral Validation

OT shows a steep negative length-accuracy gradient ($\rho=-0.164$, $p<0.001$), confirming that extended reasoning is associated with lower accuracy, while KD/RCB show weak slopes ($\rho=-0.044,-0.082$ respectively). OT has 78.3% base accuracy vs. $\sim$28% for KD/RCB, confirming a clean two-way behavioral split. Self-consistency (Wang et al., 2023) (majority vote, 10 traces) achieves AUROC = 0.804 for correctness prediction and—by construction of the $\geq$60% threshold—corrects 100% of OT-incorrect questions, yielding $+10.6$pp on training and $+7.4$pp overall on the held-out test ($p<10^{-10}$; Section 6). A single-forward-pass correctness probe achieves AUROC = 0.716 (held-out 30% split; 5-fold CV: 0.721 $\pm$ 0.005; independent test set: 0.610) using a geometrically different signal (Section 4), substantially exceeding surface uncertainty baselines (all $\leq 0.530$ on training, $\leq 0.569$ on test; $\Delta$AUROC = 0.041, $p=0.009$; Tables 6–7).

## 4 Geometric Analysis of Failure Modes

### 4.1 Hidden State Extraction

We extract hidden states from Llama-3.1-8B-Instruct (Grattafiori et al., 2024) for 12,000 traces: 2,000 per failure mode (KD, RCB, OT) plus 6,000 matched correct traces (2,000 correct traces from the same questions as each failure mode). For each trace, we construct the full conversation (system prompt + question + model response), extract the last-token hidden state at all 32 layers in fp32 precision, yielding a tensor of shape $(12000,32,4096)$.

### 4.2 Contrastive Vectors

Following the representation engineering framework, we compute contrastive vectors:

$$ \mathbf{v}_{m}^{(l)}=\frac{\bar{\mathbf{h}}_{\text{correct}}^{(l)}-\bar{\mathbf{h}}_{m}^{(l)}}{\|\bar{\mathbf{h}}_{\text{correct}}^{(l)}-\bar{\mathbf{h}}_{m}^{(l)}\|} $$

where $\bar{\mathbf{h}}_{\text{correct}}^{(l)}$ and $\bar{\mathbf{h}}_{m}^{(l)}$ are the mean hidden states at layer $l$ for correct traces and mode $m$ traces, respectively.

*Figure 1: Layer-wise classification accuracy profiles. (a) Exploratory three-way classification (KD/RCB/OT) using PCA-50 + logistic regression, peaking at 51.5% (chance = 33.3%). (b) Binary classification (correct vs. mode) showing mode-specific layer profiles: OT peaks at layer 17 (81.5%), providing the strongest and most annotation-robust signal.*

### 4.3 Statistical Analysis Suite

#### Classification.

Three-way KD/RCB/OT classification reaches 51.5% at layer 16 (chance = 33.3%; Figure 1a). Per-mode correct-vs-incorrect probes peak at 76–82% with mode-specific layer profiles (Figure 1b). Binary OT-vs-non-OT classification achieves 71.6% accuracy (balanced accuracy = 62.3%, AUROC = 0.672; majority baseline = 66.7%, $p\approx 10^{-16}$). The effect size is modest (4.9pp above majority baseline): the probe achieves high specificity (90% non-OT recall) but low sensitivity (34% OT recall), reflecting moderate but statistically reliable separability. Contrastive vectors show high pairwise cosine similarity (mean 0.820; Figure 2), indicating substantial overlap across modes. The observed pairwise distance (3.38) is 2.4$\times$ the permutation null ($p<0.001$); shuffled labels yield chance-level classification (34.6%), ruling out data artifacts.

*Figure 2: Pairwise cosine similarity between contrastive vectors across layers. Early layers show low similarity (mode-specific information), while later layers converge to high similarity ($>$0.9), reflecting the dominance of the shared component.*

### 4.4 Robustness Controls

The 71.6% binary classification is robust to six potential confounds (full details in Appendix B): random labels yield chance (33.2%); length regression leaves OT-vs-non-OT unaffected (71.3%); threshold sweeps produce Jaccard $\geq$0.81; GroupKFold rules out question-identity leakage ($<$1pp drop). Prompt-end probing achieves only 54.4% (vs. 71.6% at last-token), confirming the probe detects a generation-time regime rather than question difficulty.

### 4.5 Direction Ablation Analysis

Removing 3 contrastive directions (from 4096) drops in-sample classification from 51.4% to 25.8% (below chance), while removing random directions has zero effect. However, cross-validated ablation (directions fit on split A, evaluated on split B) shows no significant drop ($\Delta=-0.2$pp), indicating that the in-sample effect reflects probe-direction overfitting rather than a uniquely necessary subspace. These directions produce no reliable behavioral change under additive steering (Section 5)—necessity for a probe’s classification does not entail causal involvement in the model’s generation process.

### 4.6 Shared-Specific Decomposition

The average specificity ratio is only 0.119: 88% of each contrastive vector aligns with a shared “incorrect-vs-correct” direction, confirmed under binary OT-vs-non-OT framing (bypassing KD/RCB entirely). A permutation test (10,000 label shuffles among incorrect traces) yields null specificity mean = 0.370; observed = 0.119 is significantly *below* all permuted values ($p<0.0001$), confirming anomalously high alignment with the shared axis rather than an artifact of set-subset structure. To further rule out circularity (since OT traces are a subset of incorrect traces), we compute $\mathbf{d}_{\text{OT vs KD}}=\bar{\mathbf{h}}_{\text{OT}}-\bar{\mathbf{h}}_{\text{KD}}$—a direction that makes no reference to correct traces—and find $\cos(\mathbf{d}_{\text{OT vs KD}},\mathbf{d}_{\text{correctness}})=0.86$, demonstrating that the entanglement persists even when the correct class is removed from the computation. Uniform steering using this shared component is harmful ($\Delta=-12.1$pp; Table 3), consistent with the failure-mode direction sharing representational subspace with task-relevant computation.

### 4.7 Probe-Based Analysis

Probe weight vectors are geometrically dissociated from contrastive vectors (cosine 0.23–0.54 vs. 0.82), yet achieve comparable classification (51.2% vs. 51.5%). This dissociation—same accuracy, different directions—illustrates that decodability does not uniquely identify an intervention target (Appendix F). Non-linear probes (MLP, SVM-RBF) perform at or below linear on classification tasks ($\Delta\leq-0.2$pp for MLP); SVM-RBF gains +1.4pp on correctness AUROC (0.734 vs. 0.720), a marginal improvement confirming the signal ceiling is close to what linear probes capture.

### 4.8 Cross-Architecture Validation

We repeat the full geometric analysis suite on Qwen2.5-7B-Instruct (Yang et al., 2024) (28 layers, 3584 hidden dimensions), sampling 12,000 traces (2,000 per mode + 6,000 correct) from 39,862 annotated failures.

#### Consistent classification signal.

Three-way classification reaches 46.9% at layer 18 (chance = 33.3%, $p<0.001$), consistent with cross-architecture generalization. Randomized labels produce 34.0% ($\approx$ chance).

#### Divergent geometry.

The geometry differs substantially: Qwen’s average pairwise cosine is 0.339 (vs. 0.820), average specificity ratio 0.414 (vs. 0.119), and layer profiles diverge (Table 2). The elevated Qwen average is driven by KD geometry (0.662); OT-specific specificity is comparable across architectures (Qwen: 0.152, Llama: 0.119), suggesting the OT encoding is similarly entangled in both models. A steering test on Qwen ($n=1{,}273$, nine configurations spanning layers 5–18, amplitudes $\alpha\in[0.5,3.0]$, and mode-specific/uniform/multi-layer variants; Section 5) yields $\Delta\in[-0.9,+0.8]$pp (all $p>0.05$), providing consistent evidence for the cross-architecture steering null across diverse hyperparameter settings.

| Metric | Llama-3.1-8B | Qwen2.5-7B |
|---|---|---|
| Layers / Hidden dim | 32 / 4096 | 28 / 3584 |
| 3-way accuracy | 51.5% | 46.9% |
| Permutation $p$-value | $<$0.001 | $<$0.001 |
| Random control | 34.6% | 34.0% |
| Avg pairwise cosine | 0.820 | 0.339 |
| Specificity ratio | 0.119 | 0.414 |
| Peak layer (KD) | 17 | 24 |
| Peak layer (RCB) | 15 | 9 |
| Peak layer (OT) | 17 | 5 |

*Table 2: Cross-architecture comparison. Both models show significant failure mode structure ($p<0.001$), but the underlying geometry varies substantially: Qwen has more distinct modes (lower cosine, higher specificity) with different layer localization, suggesting the encoding is architecture-dependent.*

### 4.9 Cross-Domain Validation: MMLU-STEM

To test domain generality, we replicate the core pipeline on MMLU-STEM (Hendrycks et al., 2021) (300 questions, 18 subjects, 10 traces each, same OT criteria). OT prevalence is comparable (33.7% vs. 31.0%; 223 traces), and an in-domain probe reaches 70.0%. A MedQA-trained probe transfers zero-shot at 61.4% balanced accuracy ($z=6.15$, $p<10^{-9}$; permutation test with 1,000 label shuffles, $n=446$ traces: 223 OT + 223 matched correct). Dimensionality analysis reveals the geometric basis: in the top-3 PCA subspace (fit on MedQA), cross-domain cosine is 0.87 at the peak transfer layer 18 (mean 0.89, layers 10–24; notably lower at the primary steering layers 16–17: 0.67/0.65), while the full 4096-dim cosine is only 0.44. This alignment increases monotonically with subspace rank (PCA-3: 0.87, PCA-5: 0.94, PCA-10: 0.97 at layer 18), confirming that the OT signal occupies a genuinely shared low-rank subspace rather than reflecting an artifact of low-dimensional projection; the moderate raw-space alignment reflects dilution by noise dimensions.

## 5 Activation Steering Experiments

Given the weak but statistically reliable geometric structure identified in Section 4, we investigate whether it enables effective activation steering to correct failures.

### 5.1 Experimental Setup

We evaluate on the full MedQA test set (1,273 questions) using Llama-3.1-8B-Instruct, with a sanity check on Qwen2.5-7B-Instruct. Steering vectors are applied via forward hooks adding $\alpha\cdot\mathbf{v}$ to the residual stream (Elhage et al., 2021) at target layers. At $\alpha=1.5$, perturbation norm is $\sim$17% of residual stream norm at peak layers 15–17, comparable to prior work (Turner et al., 2024).

### 5.2 Methods

We test a broad family of linear additive interventions motivated directly by the decodable geometry; we do not claim to exhaust all possible intervention families (see Limitations).

#### Contrastive Steering.

We add $\alpha\cdot\mathbf{v}_{m}^{(l)}$ to the hidden state at the mode’s peak layer during generation, using either *mode-specific* vectors (detected via cosine projection) or the *uniform* shared component; confidence-gated variants steer only above a detection threshold.

#### Probe-Guided Steering.

We replace the contrastive vector with the probe weight vector ($n=1{,}175$ questions with valid outputs).

#### Multi-layer Steering.

We apply mode-specific vectors simultaneously at 1, 3, or 5 layers centered on the peak layer.

#### Rank-$k$ Subspace Steering.

We construct rank-$k$ bases ($k\in\{1,3,5\}$) via SVD of stacked direction matrices (probe and combined), testing whether rank-1 vectors are too restrictive (details in Appendix E).

#### Prompt-End Steering.

We extract contrastive vectors from *prompt-end* hidden states—the last token before generation, causally independent of the response—which are near-orthogonal to last-token vectors (cosine 0.01–0.17).

### 5.3 Results

| Method | Acc. | $\Delta$ | $p$ | Corr. | Dmg. |
|---|---|---|---|---|---|
| Baseline (no steering) | 65.1 | — | — | — | — |
| *Contrastive Steering (n=1,273)* |  |  |  |  |  |
| Uniform (shared, $\alpha$=1.5) | 53.0 | $-$12.1 | $<$.001 | 28.2 | 33.7 |
| Mode-specific ($\alpha$=1.5) | 65.0 | $-$0.2 | .953 | 32.0 | 17.4 |
| Mode-specific ($\alpha$=3.0) | 65.3 | +0.2 | .952 | 31.1 | 16.4 |
| *Probe-Guided Steering (n=1,175)* |  |  |  |  |  |
| Probe-uniform ($\alpha$=0.5) | 66.0 | $-$0.4 | .806 | 33.0 | 17.3 |
| Probe-mode ($\alpha$=0.5) | 64.8 | $-$1.7 | .233 | 29.7 | 17.5 |
| Probe-mode ($\alpha$=1.0) | 65.1 | $-$1.4 | .361 | 32.2 | 18.3 |
| *Multi-layer Contrastive (n=1,273)* |  |  |  |  |  |
| 3 layers (L13–17) | 64.6 | +0.2 | .956 | 36.4 | 19.9 |
| 5 layers (L11–19) | 62.8 | $-$1.6 | .280 | 35.5 | 22.2 |
| *Prompt-End Vectors (n=1,273)* |  |  |  |  |  |
| Uniform (shared, $\alpha$=1.5) | 65.3 | +0.5 | .735 | 35.6 | 18.6 |
| Mode-specific ($\alpha$=1.5) | 66.4 | +1.6 | .241 | 34.7 | 16.4 |
| Mode-specific ($\alpha$=3.0) | 65.0 | +0.2 | .912 | 37.0 | 19.8 |
| Full composite ($\alpha$=1.5) | 65.7 | +0.9 | .542 | 37.6 | 19.1 |
| *Strong Probe Steering (n=1,273)* |  |  |  |  |  |
| OT probe (L17, $\alpha$=1.5) | 66.7 | +1.5 | .296 | 36.0 | 15.8 |
| OT probe (L17, $\alpha$=3.0) | 61.4 | $-$3.8 | .010 | 33.7 | 22.4 |
| OT probe (L14, $\alpha$=1.5) | 65.4 | +0.2 | .953 | 33.3 | 16.4 |
| *Cross-architecture: Qwen (n=1,273)* |  |  |  |  |  |
| Mode-specific ($\alpha$=1.5) | 61.3 | $-$0.1 | 1.00 | 18.5 | 11.8 |
| Uniform ($\alpha$=1.5) | 61.9 | +0.5 | .677 | 21.7 | 12.8 |
| Mode-specific ($\alpha$=3.0) | 61.0 | $-$0.4 | .778 | 19.9 | 13.2 |
| *Concept Erasure (n=1,273)* |  |  |  |  |  |
| Mean-diff erasure (L16) | 63.5 | $-$3.6 | .010 | 31.3 | 20.7 |

*Table 3: Steering results on MedQA test set. All values in %. Acc. = accuracy; $\Delta$ = change vs. baseline (pp); $p$ = McNemar two-sided; Corr. = % of baseline-incorrect questions corrected; Dmg. = % of baseline-correct questions damaged. Prompt-end vectors are constructed from pre-generation hidden states and are near-orthogonal to last-token vectors (cosine $\leq$ 0.17). All experiments use temperature 0.1 with do_sample=True, introducing run-to-run variability; baseline varies across independent runs (Llama: 64.0–67.4%; Qwen: 61.4%). Each $\Delta$ is computed against its own run’s paired baseline (not cross-run). For context, majority vote ($k=10$, $10\times$ cost, evaluated at $T{=}0.8$) achieves $\Delta=+10.6$pp on training data and $+7.4$pp on the test set ($p<10^{-10}$); note the temperature difference from steering experiments.*

*Figure 3: Steering experiment results. (a) Accuracy delta vs baseline: uniform shared steering damages performance ($-$12.1pp), while all targeted methods produce $\Delta\approx 0$. (b) Correction vs damage trade-off: all methods lie near or above the net-zero diagonal, meaning corrections are offset by comparable damage.*

Table 3 and Figure 3 present the results. No steering method reliably improves accuracy. On the full test set ($n$=1,273), mode-specific steering produces $\Delta=-0.2$pp (95% CI: [$-2.8$, $+2.4$]pp; TOST equivalence (Lakens, 2017) within $\pm 2.5$pp—chosen a priori as half the 5pp minimal clinically important difference (Walker and Nowacki, 2011, following non-inferiority trial conventions where the margin is $\leq$50% of the established effect;)—$p=0.039$; TOST uses 90% CI $[-2.4,+2.0]$pp, which falls within bounds at $\alpha=0.05$; power is approximately 20% per individual test at this sample size; however, the joint evidence across all 29 configurations is far more decisive—were the true effect $\geq$2.5pp, observing all configurations near zero would occur with probability $<10^{-15}$). Uniform shared steering severely damages performance ($\Delta=-12.1$pp). Multi-layer steering produces $\Delta\approx 0$: 3-layer $+0.2$pp ($p=0.956$), 5-layer $-1.6$pp ($p=0.280$). Prompt-end steering—using vectors near-orthogonal to last-token directions (cosine $\leq$ 0.17)—also yields $\Delta\approx 0$ across all four conditions ($+0.2$ to $+1.6$pp, all 95% CIs including zero). Qwen2.5-7B (nine configurations spanning layers 5–18, $\alpha\in[0.5,3.0]$, mode-specific and uniform vectors) yields $\Delta\in[-0.9,+0.8]$pp (all $p>0.05$; all deltas fall well within the pre-specified $\pm 2.5$pp equivalence margin), strengthening the cross-architecture steering null. Supplementary experiments confirm these findings across temperature settings. Same-temperature evaluation at $T=0.8$ ($n=300$; Appendix K) produces *larger* damage ($\Delta=-6.7$pp, $p=0.031$), making temperature mismatch an unlikely sole explanation for the steering null. The full sweep tested $\alpha\in\{0.5,1.0,1.5,2.0,3.0\}$ per method family (Appendix L); all omitted configurations also yield $\Delta\approx 0$. Because we evaluate multiple configurations, no individual positive $\Delta$ survives Holm correction; the negative conclusion rests on the full sweep, not any single null test.

Nine validity threats to the steering null are addressed by targeted controls (Appendix C): broken hooks (refusal control, one-sided $p=0.008$), vector position (prompt-end $\Delta\approx 0$), rank limitation (rank-$k\leq 5$, $\Delta\approx 0$), temperature mismatch ($T{=}0.8$ more harmful), metric insensitivity (38–56% answers change), non-linear learned intervention ($\Delta=+2.8$pp, $p=0.025$; Appendix D), random artifact (10 random directions $\approx 0$; OT harmful), prompt fixability (7 variants, all $p>0.5$), and single-layer limitation (multi-layer $\Delta\approx 0$).

#### Behavioral readouts.

Re-running three conditions with full text ($n=1{,}273$) confirms steering substantially alters behavior: 38–56% of answers change (Jaccard 0.47). Changes are systematically harmful—damages outnumber corrections 2–3.6:1 for uniform and OT-specific steering—and the answer distribution shifts toward a dominant option (33–52%), indicating systematic bias rather than targeted correction. A refusal-steering positive control confirms the hooks operate correctly (Appendix C).

#### Rank-$k$ subspace steering.

To rule out that rank-1 vectors are too restrictive, we test rank-$k$ subspace steering ($k\in\{1,3,5\}$) on the full test set ($n=1{,}273$; Table 5 in Appendix E). Per-mode steering produces $\Delta\approx 0$ at all ranks (TOST-equivalent within $\pm 3$pp); correctness-uniform steering damages performance at all ranks ($\Delta=-2.6$ to $-6.2$pp). This eliminates “rank-1 too restrictive” as an explanation.

#### Concept erasure.

As an alternative intervention family, we apply mean-difference concept erasure—projecting *out* failure-mode directions ($\mathbf{P}=\mathbf{I}-\hat{\mathbf{d}}\hat{\mathbf{d}}^{T}$, where $\hat{\mathbf{d}}=\Delta\mu/\|\Delta\mu\|$) on the full test set ($n=1{,}273$). Erasing the OT direction at layer 16 damages accuracy ($\Delta=-3.6$pp, $p=0.010$, McNemar; 131 corrections vs. 177 damages, ratio 1.4:1). This damage is direction-specific: 10 random directions of equal rank produce $\Delta_{\text{rand}}=+0.3$pp ($\sigma=1.8$pp; Appendix H), confirming that the OT direction specifically co-occurs with task-relevant computation rather than encoding a separable error signal ($\Delta_{\text{OT}}-\overline{\Delta}_{\text{rand}}=-3.9$pp, $p<0.02$ vs. random distribution). An alternative interpretation—that the OT direction is causally required for correct reasoning, so erasure damages the computation it supports—is equally consistent (Appendix H). Even under oracle centroid displacement, only 58% of OT traces move closer to the correct class, confirming that within-class variance structurally limits linear intervention.

*Figure 4: Selective abstention using a binary correctness probe, evaluated on balanced held-out traces (50% correct, 50% incorrect). (a) Accuracy increases monotonically as the probe abstains on low-confidence predictions. (b) At key coverage levels, accuracy gains range from +3.6pp (90% coverage) to +14.0pp (60% coverage) above the 50% balanced baseline. In deployment where the model’s prior accuracy differs, absolute gains would scale accordingly; the AUROC (0.716) provides a prevalence-independent measure.*

## 6 Discussion

### The classification-correction gap.

A modest but statistically reliable linearly decodable signal—robust across replications, with evidence on one additional architecture (9 configurations) and one additional domain (decodability and steering failure)—is insufficient for correction under the tested family of fixed linear interventions. This is not a universal impossibility claim. The core mismatch is between *what is decodable* and *what needs to change*: failure *mode identity* is largely pre-determined before generation, but failure *occurrence* accumulates dynamically during reasoning. The gap between prompt-end and last-token probing (54.4% vs. 71.6%) confirms that the probe reads a signal generated *during* the response—which is why it supports post-generation abstention but not pre-emptive steering.

We identify four descriptive correlates (compatible explanations, not causally identified mechanisms; equally consistent with an alternative account in which the OT direction is causally required for correct reasoning, so perturbation damages it): (i) *observation-intervention asymmetry*: probes exploit any statistical regularity, while steering requires a causally effective perturbation (Hase et al., 2023); (ii) *low specificity*: 88% of the contrastive signal is shared (OT-specific specificity: 0.119 Llama, 0.152 Qwen—comparable across architectures despite differing average ratios), with within-class variance exceeding the inter-centroid gap by 2–4$\times$; (iii) *cross-model variation*: architectures encode failure modes differently (cosine 0.339 vs. 0.820) yet steering fails on both; (iv) *cross-domain subspace degradation at steering layers*: PCA-3 cosine is 0.87–0.96 at most layers but drops to a local trough at the primary steering layers 16–17 (0.67/0.65), suggesting the shared subspace degrades precisely at the intervention point. These correlates are consistent with—but do not uniquely establish—representational superposition (Elhage et al., 2022) as the underlying mechanism: when the OT signal shares directions with task-relevant computation, probes can extract the OT component (compatible with decodability), but additive steering along this direction perturbs the task computation (compatible with both the steering null for targeted methods and the $-12.1$pp/$-3.6$pp damage for shared/erasure methods). Current data cannot distinguish this from the alternative account that the OT direction is itself a necessary component of correct reasoning (Section 5). The gap persists across decodability strengths: the strong correct-vs-OT probe (81.5%) yields $\Delta=+1.5$pp ($p=0.296$), and increasing $\alpha$ reverses the effect ($-3.8$pp, $p=0.010$). Instance-adaptive methods (K-CAST (Valentino et al., 2026), DAS (Geiger et al., 2024), ReFT (Wu et al., 2024)) could succeed by learning to disentangle shared directions. Preliminary evidence supports this: a learned non-linear residual MLP (4096$\to$64$\to$4096 bottleneck, trained on the same correct/OT supervision as linear methods) achieves $\Delta=+2.8$pp ($p=0.025$, McNemar; 140 corrections, 104 damages; Appendix D). The MLP reduces centroid distance by 50.6% yet produces only modest behavioral gain—consistent with partial but incomplete disentanglement of the shared subspace. This suggests the entanglement is a matter of degree: non-linear transforms can partially navigate around task-critical directions that linear perturbations inevitably disrupt.

### Pre-intervention diagnostics.

The four correlates suggest candidate pre-checks before attempting activation steering: (i) specificity ratio, (ii) within-class variance relative to inter-centroid gap, (iii) cross-architecture stability, and (iv) cross-domain subspace alignment at the intervention layer (Jafari et al., 2026, cf.). In our setting all four were unfavorable and steering failed; refusal—our positive control (Appendix C)—satisfies the first three and responds to contrastive activation addition (CAA). Quantitatively, the refusal direction has specificity ratio 0.999 (under the three-mode shared decomposition; 95% CI for OT: [0.075, 0.119])—nearly all of its variance is mode-specific, compared to only 12–21% for OT. The refusal direction is near-orthogonal to the failure-mode directions ($\cos(\mathbf{d}_{\text{refusal}},\mathbf{d}_{\text{OT}})=-0.008$; $\cos(\mathbf{d}_{\text{refusal}},\bar{\mathbf{v}}_{\text{shared}})=0.014$), confirming it occupies a geometrically distinct subspace. The specificity gap is $4.7\times$ (refusal vs. OT under the same three-mode decomposition), providing a quantitative two-point calibration: directions with specificity $\geq 0.99$ are steerable (refusal: sign test $p=0.008$), while directions with specificity $\leq 0.21$ are not (29 configurations, all $\Delta\approx 0$). A Linear Accessibility Profile (LAP) analysis (Billa, 2026, adapting the framework of) independently confirms the diagnosis: projecting the OT direction through the unembedding matrix yields semantically incoherent top tokens at all layers, with logit-lens classification accuracy (58.6%) far below probe accuracy (81.5%)—a gap of $\Delta=0.23$ indicating the signal is present but not output-aligned (Appendix M). These diagnostics are hypothesis-generating checks based on a two-point comparison (refusal vs. OT), not validated predictors; however, the $4.7\times$ specificity gap provides a concrete quantitative threshold for future work.

### Generality beyond medical QA.

MMLU-STEM replication (Section 4) provides evidence that the classification-correction gap extends beyond MedQA: comparable OT prevalence (33.7%), in-domain probes at 70.0%, zero-shot MedQA probe transfer ($z=6.15$) in a shared low-rank subspace (top-3 PCA cosine 0.87 at peak transfer layer 18; mean 0.89 across layers 10–24, though lower at primary steering layers 16–17: 0.67/0.65), and—critically—the same steering failure pattern ($n=300$): mode-specific steering $\Delta=0.0$pp ($p=1.0$), uniform steering $\Delta=-7.0$pp ($p=0.017$), multi-layer $\Delta=-6.7$pp ($p=0.040$). These results provide evidence that the gap extends beyond MedQA, though broader domain coverage is needed to establish full generality.

### Self-consistency as a correction baseline.

The 100% OT correction by majority vote is definitional: OT requires $\geq$60% correct traces, so MV@10 necessarily selects the correct answer for every OT question. The substantive empirical finding is the *overall* test-set gain: MV@10 achieves 72.7% ($+7.4$pp; $p<10^{-10}$, $n=1{,}273$, $T{=}0.8$), correcting OT errors while fixing only 18.6% of non-OT errors ($+10.6$pp on training data). Best-of-$N$ probe selection at $k{=}10$ achieves 70.7% ($+5.3$pp; $p<10^{-4}$), competitive with MV@10 ($-2.0$pp, $p=0.053$). Notably, at $k{=}3$ (same generation cost as MV@3), the probe achieves 70.6% vs. MV@3’s 69.2% ($+1.4$pp; $p=0.17$), suggesting complementary signal at small $N$; at $k{=}5$, BoN (71.3%) trails MV@5 (71.8%) by only 0.5pp. The resulting hierarchy—oracle (94.2%, $T{=}0.8$, 10 passes) $>$ MV@10 (72.7%) $\approx$ best-of-$N$ (70.7%) $\gg$ steering ($\Delta\leq+1.5$pp, $T{=}0.1$, single-pass) $\approx$ prompt baselines ($\Delta\leq+0.6$pp)—shows the OT problem is solvable at $10\times$ cost but not via single-pass interventions.

### Prompt-based baselines.

We test ten prompt variants ($n=1{,}273$, $T{=}0.1$; Table 4), including few-shot prompting ($k\in\{1,3,5\}$; answer-only format without reasoning chains), self-refinement (Madaan et al., 2023, iterative self-critique within a single generation;), and verbalized confidence. None reliably improves: removing explicit CoT instruction achieves $+0.6$pp ($p=0.68$), 3-shot achieves $+0.5$pp ($p=0.74$), and self-refinement *significantly degrades* accuracy to 63.0% ($\Delta=-5.9$pp vs. its paired baseline of 68.9%, McNemar $p<0.001$; 208 questions damaged, 133 corrected). Verbalized confidence similarly degrades to 63.2% ($\Delta=-5.7$pp, $p<0.001$), though the model’s self-reported confidence retains discriminative value for abstention (AUROC = 0.635; Figure 4). Short-generation catastrophically fails (2.5%, 90% parse failure due to conflicting length constraint and CoT instruction). These results show that OT persists across tested prompt variants, extending the classification-correction gap beyond activation steering to input-level modifications. Untested strategies (MedPrompt, budget forcing) remain open.

| Prompt variant | Acc. | $\Delta$ | $p$ |
|---|---|---|---|
| Baseline CoT (0-shot) | 67.2 | — | — |
| *Zero-shot variants* |  |  |  |
| Concise | 66.1 | $-$1.0 | .51 |
| Answer-first | 66.5 | $-$0.7 | .64 |
| No-CoT | 67.8 | +0.6 | .68 |
| Short-generation (100 tok) | 2.5 | $-$64.7 | $<$.001 |
| *Few-shot variants (separate run, baseline 65.4%)* |  |  |  |
| 1-shot | 65.2 | $-$0.2 | .95 |
| 3-shot | 65.9 | +0.5 | .74 |
| 5-shot | 65.7 | +0.3 | .87 |
| *Self-refinement (paired baseline 68.9%)* |  |  |  |
| Self-refine (self-critique) | 63.0 | $-$5.9 | $<$.001 |
| Verbalized confidence | 63.2 | $-$5.7 | $<$.001 |

*Table 4: Prompt baselines ($n=1{,}273$, temperature 0.1). All values in %. Zero-shot variants share a baseline (67.2%); few-shot variants use a separate independent run (baseline 65.4%) due to different prompt construction. Self-refinement and verbalized confidence use a dedicated paired baseline (68.9%) with identical tokenization (add_special_tokens=False). All $\Delta$ values are McNemar-tested against the run-matched baseline.*

### Selective abstention.

The same structure that fails to support correction enables post-generation reliability estimation (Geifman and El-Yaniv, 2017). A correctness probe (layer 21, selected via held-out AUROC from a 32-layer scan on 70/30 training split) achieves held-out split AUROC = 0.716 on training traces (Figure 4), with held-out test-set AUROC = 0.610 (95% CI: [0.577, 0.642]; $n=1{,}273$). The generalization gap (0.716 $\to$ 0.610) primarily reflects distributional shift between training traces (balanced, temperature 0.8) and test-set evaluation (natural prevalence, temperature 0.1); evidence for this includes: (a) 5-fold GroupKFold CV on training data yields AUROC = 0.727 (higher than the held-out estimate), and (b) the gap aligns with the cross-temperature vector cosine of 0.41 (Appendix J). Despite this shift, the held-out probe exceeds all five tested single-forward-pass uncertainty baselines on both training traces (AUROC $\leq$ 0.530; Table 6) and the test set (best baseline = 0.569; $\Delta$AUROC = 0.041, $p=0.009$, paired bootstrap; Holm-corrected rank-1 threshold = 0.010; Table 7). Verbalized confidence—where the model self-reports a confidence percentage via a modified prompt—achieves comparable AUROC (0.635, 97.4% parseable) but requires prompt modification that alters the generation itself; the probe operates post-hoc on unmodified outputs. At 60% coverage, selective abstention yields 72.3% accuracy (+5.5pp) on the test set; at 70% coverage, gains are comparable (+5.7pp with lower abstention cost). On balanced training data, gains are +14.0pp at 60% coverage (relative to the 50% balanced baseline). Proper 5-fold stratified CV on training data confirms probe quality (best layer L14: AUROC = 0.730 $\pm$ 0.006; L21: AUROC = 0.721 $\pm$ 0.005). Self-consistency achieves higher AUROC (0.804) but at $10\times$ cost; the probe provides a cost-effective single-pass alternative. Unlike process reward models (Lightman et al., 2023), it requires no per-step annotation. The contribution is demonstrating that decodable structure has operational value for reliability estimation even when the tested steering family cannot exploit it for correction.

## 7 Conclusion

We demonstrate an empirical classification-correction gap: OT is linearly decodable ($p\approx 10^{-16}$), robust across confounds with evidence on one additional architecture (Qwen2.5-7B, 9 configs, all $\Delta<1$pp) and cross-domain steering failure (MMLU-STEM, $n=300$: targeted $\Delta=0$pp, uniform $\Delta=-7.0$pp), yet five families of fixed linear steering (29 configurations) and ten prompt baselines produce $\Delta\leq 0$ while non-targeted shared-direction steering and concept erasure damage accuracy (consistent with direction overlap with task computation). The same decodable structure supports selective abstention (held-out test AUROC = 0.610, exceeding all five tested uncertainty baselines; $p=0.009$) and best-of-$N$ probe selection competitive with majority vote (BoN@3 exceeds MV@3 by +1.4pp at identical generation cost, though $p=0.17$), demonstrating operational value for reliability estimation even when the tested steering family cannot exploit it for correction. Four candidate pre-intervention diagnostics (based on a two-point comparison with a refusal control, not validated as predictors) are consistent with this failure pattern. A learned non-linear MLP intervention provides preliminary evidence that the gap is partially closeable ($\Delta=+2.8$pp, $p=0.025$; Appendix D), suggesting the entanglement is partial rather than absolute. Whether more sophisticated learned interventions—Distributed Alignment Search, representation finetuning, or instance-adaptive methods like K-CAST—can fully close the gap remains the central open question; our correct/incorrect supervision pairs provide the requisite training signal for these methods.

## Limitations

### Scale, scope, and generalizability.

We evaluate two 7–8B models on MedQA; at larger scales, higher baseline accuracy likely reduces OT prevalence (though superposition may intensify with more features competing for shared directions). Cross-architecture steering on Qwen uses nine configurations spanning layers 5–18 and amplitudes $\alpha\in[0.5,3.0]$; the absence of Qwen concept-erasure experiments leaves open whether Qwen’s distinct geometry (specificity 0.414 vs. Llama’s 0.119) reflects a qualitatively different encoding. MMLU-STEM confirms both decodability transfer and steering failure ($n=300$, same pattern as MedQA). The 60% correct-rate threshold is empirically motivated (Jaccard $\geq$0.81 under 50–70% sweeps) but the MV@10 correction rate of 100% is definitional. Prompt baselines do not include MedPrompt or budget-forcing strategies; the no-CoT condition does not enforce short generation, so implicit reasoning may persist.

### Intervention scope.

The primary negative result covers *fixed*-direction residual-stream linear interventions: five method families (29 additive configurations) plus mean-difference concept erasure (rank-1 projection and a whitened variant; see footnote in Section 5). The full oblique LEACE projector of Belrose et al. (2023) ($\Sigma_{w}^{+1/2}P\Sigma_{w}^{-1/2}$) remains untested. A probe-gated dynamic variant was tested on $n=300$ (Appendix I) but produced no significant improvement (all $p>0.3$). A learned non-linear MLP (4096$\to$64$\to$4096 residual adapter; Appendix D) achieves $\Delta=+2.8$pp ($p=0.025$), providing preliminary evidence that non-linear learned interventions can partially close the gap—though the damage rate remains high (104/1273 = 8.2%) and the gain is modest relative to the 50.6% centroid-distance reduction, consistent with only partial disentanglement of the shared subspace. Full DAS (Geiger et al., 2024), ReFT (Wu et al., 2024), and instance-adaptive methods (K-CAST (Valentino et al., 2026)) remain untested; our correct/incorrect supervision pairs provide the requisite training signal. Other untested families include path patching (Goldowsky-Dill et al., 2023) and parameter-efficient fine-tuning (Hu et al., 2022). Qwen concept erasure experiments were not conducted.

### Temperature mismatch and annotation validity.

Annotation uses $T{=}0.8$, steering evaluation $T{=}0.1$. Same-temperature steering produces *larger* damage ($-6.7$pp, $p=0.031$; Appendix K), directly falsifying temperature mismatch as an explanation for the steering null; the probe’s generalization gap (0.716 $\to$ 0.610) reflects this distributional shift (cross-temperature vector cosine = 0.41; Appendix J). KD/RCB annotation shows moderate agreement ($\kappa=0.30$) from two 4th-year clinical students; the core binary OT finding bypasses this boundary and is robust to 37% simulated label noise.

## Ethics Statement

This research analyzes model failures on a public benchmark (MedQA) with no patient data or human subjects. LLM annotations use Claude models via the Anthropic API. Llama-3.1 and Qwen2.5 are used under their open-weight licenses. The selective abstention result may inform research on post-generation reliability estimation under benchmark conditions, though it is not sufficient as a standalone clinical safeguard.

## Reproducibility

All experiments use publicly available models (Llama-3.1-8B-Instruct, Qwen2.5-7B-Instruct) and data (MedQA, MMLU-STEM). Steering and evaluation experiments were run on NVIDIA A10G GPUs (24GB); full test-set evaluation ($n=1{,}273$) takes approximately 4 hours per configuration. Generation uses do_sample=True with $T{=}0.1$, introducing run-to-run variability (baseline range: 64.0–67.4%); all deltas are computed within-run against paired baselines. Appendix A provides annotation prompts, probe training hyperparameters, PCA settings, decoding parameters, and data split details. Code and processed annotations will be released upon publication.

## References

- Alain and Bengio (2017) Guillaume Alain and Yoshua Bengio. 2017. Understanding intermediate layers using linear classifier probes. *arXiv preprint arXiv:1610.01644*.

- Anthropic (2024) Anthropic. 2024. The Claude 3 model family: Opus, Sonnet, Haiku. Technical report, Anthropic. We use Claude Haiku 4.5 (claude-haiku-4-5-20251001).

- Arditi et al. (2024) Andy Arditi, Oscar Obber, Ajeya Shlegeris, and Nicholas Schiefer. 2024. Refusal in language models is mediated by a single direction. *arXiv preprint arXiv:2406.11717*.

- Azaria and Mitchell (2023) Amos Azaria and Tom Mitchell. 2023. The internal state of an LLM knows when it’s lying. In *Findings of the Association for Computational Linguistics: EMNLP 2023*, pages 967–976.

- Basu et al. (2026) Sanjay Basu, Sadiq Y. Patel, Parth Sheth, Bhairavi Muralidharan, Namrata Elamaran, Aakriti Kinra, John Morgan, and Rajaie Batniji. 2026. Interpretability without actionability: Mechanistic methods cannot correct language model errors despite near-perfect internal representations. *arXiv preprint arXiv:2603.18353*.

- Belinkov (2022) Yonatan Belinkov. 2022. Probing classifiers: Promises, shortcomings, and advances. *Computational Linguistics*, 48(1):207–219.

- Belrose et al. (2023) Nora Belrose, David Schneider-Joseph, Shauli Ravfogel, Ryan Cotterell, Edward Raff, and Stella Biderman. 2023. LEACE: Perfect linear concept erasure in closed form. In *Advances in Neural Information Processing Systems*, volume 36.

- Billa (2026) Jayadev Billa. 2026. Predicting where steering vectors succeed. *arXiv preprint arXiv:2604.15557*.

- Braun et al. (2025) Joschka Braun, Dmitrii Krasheninnikov, Usman Anwar, Robert Kirk, Daniel Tan, and David Scott Krueger. 2025. A sober look at steering vectors for LLMs. *arXiv preprint*.

- Burns et al. (2023) Collin Burns, Haotian Ye, Dan Klein, and Jacob Steinhardt. 2023. Discovering latent knowledge in language models without supervision. In *International Conference on Learning Representations*.

- Chen et al. (2024) Xingyu Chen, Jiahao Xu, Tian Liang, Zhiwei He, Jianhui Pang, Dian Yu, Linfeng Song, Qiuzhi Liu, Mengfei Zhou, Zhuosheng Zhang, Rui Wang, Zhaopeng Tu, Haitao Mi, and Dong Yu. 2024. Do NOT think that much for 2+3=? on the overthinking of o1-like LLMs. *arXiv preprint arXiv:2412.21187*.

- Chuang et al. (2024) Yung-Sung Chuang, Yujia Xie, Hongyin Luo, Yoon Kim, James Glass, and Pengcheng He. 2024. DoLa: Decoding by contrasting layers improves factuality in large language models. In *Proceedings of the 12th International Conference on Learning Representations (ICLR)*.

- Cox et al. (2026) Kyle Cox, Darius Kianersi, and Adria Garriga-Alonso. 2026. Decoding answers before chain-of-thought: Evidence from pre-CoT probes and activation steering. *arXiv preprint arXiv:2603.01437*.

- Cunningham et al. (2023) Hoagy Cunningham, Aidan Ewart, Logan Riggs, Robert Huben, and Lee Sharkey. 2023. Sparse autoencoders find highly interpretable features in language models. *arXiv preprint arXiv:2309.08600*.

- Da Silva et al. (2025) Patrick Queiroz Da Silva, Hari Sethuraman, Dheeraj Rajagopal, Hannaneh Hajishirzi, and Sachin Kumar. 2025. Steering off course: Reliability challenges in steering language models. *arXiv preprint arXiv:2504.04635*.

- Deng et al. (2025) Zhihong Deng, Jing Jiang, Guodong Long, and Chengqi Zhang. 2025. Rethinking the reliability of representation engineering in large language models. *arXiv preprint arXiv:2409.15726*.

- Elazar et al. (2021) Yanai Elazar, Shauli Ravfogel, Alon Jacovi, and Yoav Goldberg. 2021. Amnesic probing: Behavioral explanation with amnesic counterfactuals. *Transactions of the Association for Computational Linguistics*, 9:160–175.

- Elhage et al. (2022) Nelson Elhage, Tristan Hume, Catherine Olsson, Nicholas Schiefer, Tom Henighan, Shauna Kravec, Zac Hatfield-Dodds, Robert Lasenby, Dawn Drain, Carol Chen, and 1 others. 2022. Toy models of superposition. *Transformer Circuits Thread*.

- Elhage et al. (2021) Nelson Elhage, Neel Nanda, Catherine Olsson, Tom Henighan, Nicholas Joseph, Ben Mann, Amanda Askell, Yuntao Bai, Anna Chen, Tom Conerly, and 1 others. 2021. A mathematical framework for transformer circuits. *Transformer Circuits Thread*.

- Gao et al. (2026) Lang Gao, Jinghui Zhang, Wei Liu, Fengxian Ji, Chenxi Wang, Zirui Song, Akash Ghosh, Youssef Mohamed, Preslav Nakov, and Xiuying Chen. 2026. The cylindrical representation hypothesis for language model steering. *arXiv preprint arXiv:2605.01844*.

- Geifman and El-Yaniv (2017) Yonatan Geifman and Ran El-Yaniv. 2017. Selective classification for deep neural networks. In *Advances in Neural Information Processing Systems*, volume 30.

- Geiger et al. (2024) Atticus Geiger, Zhengxuan Wu, Christopher Potts, Thomas Icard, and Noah D. Goodman. 2024. Finding alignments between interpretable causal variables and distributed neural representations. *arXiv preprint arXiv:2303.02536*.

- Goldowsky-Dill et al. (2023) Nicholas Goldowsky-Dill, Chris MacLeod, Lucas Sato, and Aryaman Arora. 2023. Localizing model behavior with path patching. *arXiv preprint arXiv:2304.05969*.

- Grattafiori et al. (2024) Aaron Grattafiori, Abhimanyu Dubey, Abhinav Jauhri, and 1 others. 2024. The Llama 3 herd of models. *arXiv preprint arXiv:2407.21783*.

- Guo et al. (2017) Chuan Guo, Geoff Pleiss, Yu Sun, and Kilian Q Weinberger. 2017. On calibration of modern neural networks. In *International Conference on Machine Learning*, pages 1321–1330.

- Hase et al. (2023) Peter Hase, Mohit Bansal, Been Kim, and Asma Ghandeharioun. 2023. Does localization inform editing? surprising differences in causality-based localization vs. knowledge editing in language models. In *Advances in Neural Information Processing Systems*, volume 36.

- Hendrycks et al. (2021) Dan Hendrycks, Collin Burns, Steven Basart, Andy Zou, Mantas Mazeika, Dawn Song, and Jacob Steinhardt. 2021. Measuring massive multitask language understanding. In *International Conference on Learning Representations*.

- Hernandez et al. (2024) Evan Hernandez, Arnab Sen Sharma, Tal Haklay, Kevin Meng, Martin Wattenberg, Jacob Andreas, Yonatan Belinkov, and David Bau. 2024. Linearity of relation decoding in transformer language models. In *International Conference on Machine Learning*.

- Hewitt and Liang (2019) John Hewitt and Percy Liang. 2019. Designing and interpreting probes with control tasks. In *Proceedings of EMNLP*, pages 2733–2743.

- Hu et al. (2022) Edward J Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, and Weizhu Chen. 2022. LoRA: Low-rank adaptation of large language models. In *International Conference on Learning Representations*.

- Huang et al. (2024) Jie Huang, Xinyun Chen, Swaroop Mishra, Huaixiu Steven Zheng, Adams Wei Yu, Xinying Song, and Denny Zhou. 2024. Large language models cannot self-correct reasoning yet. In *Proceedings of the 12th International Conference on Learning Representations (ICLR)*.

- Jafari et al. (2026) Amir Jafari, Aryaman Gangopadhyay, Jeffrey Long, and Ekdeep Singh Lubana. 2026. Mechanistic indicators of steering effectiveness in large language models. *arXiv preprint arXiv:2602.01716*.

- Jin et al. (2021) Di Jin, Eileen Pan, Nassim Oufattole, Wei-Hung Weng, Hanyi Fang, and Peter Szolovits. 2021. What disease does this patient have? a large-scale open domain question answering dataset from medical exams. *Applied Sciences*, 11(14):6421.

- Jorgensen et al. (2023) Ole Jorgensen, Dylan Cope, Nandi Schoots, and Murray Shanahan. 2023. Improving activation steering in language models with mean-centring. *arXiv preprint arXiv:2312.03813*.

- Kadavath et al. (2022) Saurav Kadavath, Tom Conerly, Amanda Askell, Tom Henighan, Dawn Drain, Ethan Perez, Nicholas Schiefer, Zac Hatfield-Dodds, Nova DasSarma, Eli Tran-Johnson, and 1 others. 2022. Language models (mostly) know what they know. *arXiv preprint arXiv:2207.05221*.

- Kojima et al. (2022) Takeshi Kojima, Shixiang Shane Gu, Machel Reid, Yutaka Matsuo, and Yusuke Iwasawa. 2022. Large language models are zero-shot reasoners. In *Advances in Neural Information Processing Systems*, volume 35.

- Kuhn et al. (2023) Lorenz Kuhn, Yarin Gal, and Sebastian Farquhar. 2023. Semantic uncertainty: Linguistic invariances for uncertainty estimation in natural language generation. In *International Conference on Learning Representations*.

- Lakens (2017) Daniel Lakens. 2017. Equivalence tests: A practical primer for t tests, correlations, and meta-analyses. *Social Psychological and Personality Science*, 8(4):355–362.

- Lanham et al. (2023) Tamera Lanham, Anna Chen, Ansh Radhakrishnan, Benoit Steiner, Carson Denison, Danny Hernandez, Dustin Li, Esin Durmus, Evan Hubinger, Jackson Kernion, KamilL̇ukić, Karina Nguyen, Newton Schiefer, Catherine Olsson, Tom Henighan, Andy Jones, Karina Ndousse, Oliver Bloom, Nelson Elhage, and 6 others. 2023. Measuring faithfulness in chain-of-thought reasoning. *arXiv preprint arXiv:2307.13702*.

- Li et al. (2023) Kenneth Li, Oam Patel, Fernanda Viégas, Hanspeter Pfister, and Martin Wattenberg. 2023. Inference-time intervention: Eliciting truthful answers from a language model. *Advances in Neural Information Processing Systems*, 36.

- Lightman et al. (2023) Hunter Lightman, Vineet Kosaraju, Yuri Burda, Harri Edwards, Bowen Baker, Teddy Lee, Jan Leike, John Schulman, Ilya Sutskever, and Karl Cobbe. 2023. Let’s verify step by step. *arXiv preprint arXiv:2305.20050*.

- Lin et al. (2022) Stephanie Lin, Jacob Hilton, and Owain Evans. 2022. Truthfulqa: Measuring how models mimic human falsehoods. In *Proceedings of the 60th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, pages 3214–3252.

- Madaan et al. (2023) Aman Madaan, Niket Tandon, Prakhar Gupta, Skyler Hallinan, Luyu Gao, Sarah Wiegreffe, Uri Alon, Nouha Dziri, Shravya Prabhumoye, Yiming Yang, Shashank Gupta, Bodhisattwa Prasad Majumder, Katherine Hermann, Sean Welleck, Amir Yazdanbakhsh, and Peter Clark. 2023. Self-refine: Iterative refinement with self-feedback. In *Advances in Neural Information Processing Systems*, volume 36.

- Marks and Tegmark (2024) Samuel Marks and Max Tegmark. 2024. The geometry of truth: Emergent linear structure in large language model representations of true/false datasets. In *Conference on Language Modeling*.

- McKenzie et al. (2026) Alex McKenzie, Keenan Pepper, Stijn Servaes, Martin Leitgab, Murat Cubuktepe, Mike Vaiana, Diogo de Lucena, Judd Rosenblatt, and Michael S. A. Graziano. 2026. Endogenous resistance to activation steering in language models. *arXiv preprint arXiv:2602.06941*.

- Meng et al. (2022) Kevin Meng, David Bau, Alex Andonian, and Yonatan Belinkov. 2022. Locating and editing factual associations in GPT. In *Advances in Neural Information Processing Systems*, volume 35, pages 17359–17372.

- Mishra et al. (2026) Aayush Mishra, Daniel Khashabi, and Anqi Liu. 2026. Steered LLM activations are non-surjective. *arXiv preprint arXiv:2604.09839*.

- Muennighoff et al. (2025) Niklas Muennighoff, Zitong Yang, Weijia Shi, Xiang Lisa Li, Li Fei-Fei, Hannaneh Hajishirzi, Luke Zettlemoyer, Percy Liang, Emmanuel Candela, and Dirk Groeneveld. 2025. s1: Simple test-time scaling. *arXiv preprint arXiv:2501.19393*.

- Nadaf (2026) Mohammed Suhail B Nadaf. 2026. Steerable but not decodable: Function vectors operate beyond the logit lens. *arXiv preprint arXiv:2604.02608*.

- Nanda et al. (2023) Neel Nanda, Andrew Lee, and Martin Wattenberg. 2023. Emergent linear representations in world models of self-supervised sequence models. In *Proceedings of the Annual Meeting of the Association for Computational Linguistics: BlackboxNLP Workshop*.

- Nori et al. (2023) Harsha Nori, Yin Tat Lee, Sheng Zhang, Dean Carignan, Richard Edgar, Nicolo Fusi, Nicholas King, Jonathan Larson, Yuanzhi Li, Weishung Liu, Renqian Luo, Scott Mayer McKinney, Robert Osazuwa Morrow, Tristan Nguyen, Hoifung Poon, Qiufeng Wei, and 1 others. 2023. Can generalist foundation models outcompete special-purpose tuning? Case study in medicine. *arXiv preprint arXiv:2311.16452*.

- Panickssery et al. (2023) Nina Panickssery, Nick Gabrieli, Julian Schulz, Meg Tong, Evan Hubinger, and Alexander Matt Turner. 2023. Steering Llama 2 via contrastive activation addition. *arXiv preprint arXiv:2312.06681*.

- Park et al. (2024) Kiho Park, Yo Joong Choe, and Victor Veitch. 2024. The linear representation hypothesis and the geometry of large language models. In *International Conference on Machine Learning*.

- Pedregosa et al. (2011) Fabian Pedregosa, Gaël Varoquaux, Alexandre Gramfort, Vincent Michel, Bertrand Thirion, Olivier Grisel, Mathieu Blondel, Peter Prettenhofer, Ron Weiss, Vincent Dubourg, and 1 others. 2011. Scikit-learn: Machine learning in Python. *Journal of Machine Learning Research*, 12:2825–2830.

- Ravfogel et al. (2020) Shauli Ravfogel, Yanai Elazar, Hila Gonen, Michael Twiton, and Yoav Goldberg. 2020. Null it out: Guarding protected attributes by iterative nullspace projection. In *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics*, pages 7237–7256. Association for Computational Linguistics.

- Ravfogel et al. (2022) Shauli Ravfogel, Michael Twiton, Yoav Goldberg, and Ryan Cotterell. 2022. Linear adversarial concept erasure. In *Proceedings of ICML*, pages 18400–18421.

- Sanyal et al. (2025) Debdeep Sanyal, Manya Pandey, Dhruv Kumar, Saurabh Deshpande, and Murari Mandal. 2025. Confidence is not competence: Probing vs steering LLM solvability beliefs. *arXiv preprint arXiv:2510.24772*.

- Sharma et al. (2024) Mrinank Sharma, Meg Tong, Tomasz Korbak, David Duvenaud, Amanda Askell, Samuel R Bowman, Newton Cheng, Esin Durmus, Zac Hatfield-Dodds, Scott R Johnston, and 1 others. 2024. Towards understanding sycophancy in language models. *arXiv preprint arXiv:2310.13548*.

- Singhal et al. (2023) Karan Singhal, Shekoofeh Azizi, Tao Tu, S Sara Mahdavi, Jason Wei, Hyung Won Chung, Nathan Scales, Ajay Tanwani, Heather Cole-Lewis, Stephen Pfohl, and 1 others. 2023. Large language models encode clinical knowledge. *Nature*, 620(7972):172–180.

- Sprague et al. (2024) Zayne Sprague, Fangcong Yin, Juan Diego Rodriguez, Dongwei Jiang, Manya Wadhwa, Prasann Singhal, Xinyu Zhao, Xi Ye, Kyle Mahowald, and Greg Durrett. 2024. To CoT or not to CoT? chain-of-thought helps mainly on math and symbolic reasoning. *arXiv preprint arXiv:2409.12183*.

- Templeton et al. (2024) Adly Templeton, Tom Conerly, Jonathan Marcus, Jack Lindsey, Trenton Bricken, Brian Chen, Adam Pearce, Craig Citro, Emmanuel Amezcua, Andy Jones, Hoagy Cunningham, Nicholas L Turner, Callum McDougall, Monte MacDiarmid, C Daniel Freeman, Theodore R Sumers, Edward Rees, Joshua Batson, Adam Jermyn, and 3 others. 2024. Scaling monosemanticity: Extracting interpretable features from Claude 3 Sonnet. *Anthropic Technical Report*.

- Todd et al. (2024) Eric Todd, Millicent L Li, Arnab Sen Sharma, Aaron Mueller, Byron C Wallace, and David Bau. 2024. Function vectors in large language models. In *International Conference on Learning Representations*.

- Turner et al. (2024) Alexander Matt Turner, Lisa Thiergart, Gavin Leech, David Udell, Juan J. Vazquez, Ulisse Mini, and Monte MacDiarmid. 2024. Steering language models with activation engineering. *arXiv preprint arXiv:2308.10248*.

- Turpin et al. (2023) Miles Turpin, Julian Michael, Ethan Perez, and Samuel R. Bowman. 2023. Language models don’t always say what they think: Unfaithful explanations in chain-of-thought prompting. In *Advances in Neural Information Processing Systems*, volume 36.

- Valentino et al. (2026) Marco Valentino, Mokanarangan Thayaparan, Tom Sherborne, and André Freitas. 2026. Mitigating content effects on reasoning in language models through fine-grained activation steering. In *Proceedings of the AAAI Conference on Artificial Intelligence*.

- Vig et al. (2020) Jesse Vig, Sebastian Gehrmann, Yonatan Belinkov, Sharon Qian, Daniel Nevo, Yaron Singer, and Stuart Shieber. 2020. Investigating gender bias in language models using causal mediation analysis. In *Advances in Neural Information Processing Systems*, volume 33, pages 12388–12401.

- Walker and Nowacki (2011) Esteban Walker and Amy S Nowacki. 2011. Understanding equivalence and noninferiority testing. *Journal of General Internal Medicine*, 26(2):192–196.

- Wang et al. (2023) Xuezhi Wang, Jason Wei, Dale Schuurmans, Quoc Le, Ed Chi, Sharan Narang, Aakanksha Chowdhery, and Denny Zhou. 2023. Self-consistency improves chain of thought reasoning in language models. In *International Conference on Learning Representations*.

- Wang et al. (2026) Youjin Wang, Run Zhou, Rong Fu, Shuaishuai Cao, Hongwei Zeng, Jiaxuan Lu, Sicheng Fan, Jiaqiao Zhao, and Liangming Pan. 2026. ASA: Training-free representation engineering for tool-calling agents. *arXiv preprint arXiv:2602.04935*.

- Wang et al. (2025) Yue Wang, Qiuzhi Liu, Jiahao Xu, Tian Liang, Xingyu Chen, Zhiwei He, Linfeng Song, Dian Yu, Juntao Li, Zhuosheng Zhang, Rui Wang, Zhaopeng Tu, Haitao Mi, and Dong Yu. 2025. Thoughts are all over the place: On the underthinking of o1-like LLMs. *arXiv preprint arXiv:2501.18585*.

- Wei et al. (2022) Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, and Denny Zhou. 2022. Chain-of-thought prompting elicits reasoning in large language models. In *Advances in Neural Information Processing Systems*, volume 35.

- Wollschläger et al. (2025) Tom Wollschläger, Jannes Elstner, Simon Geisler, Vincent Cohen-Addad, Stephan Günnemann, and Johannes Gasteiger. 2025. The geometry of refusal in large language models: Concept cones and representational independence. *arXiv preprint arXiv:2502.17420*.

- Wu et al. (2025) Zhengxuan Wu, Aryaman Arora, Atticus Geiger, Zheng Wang, Jing Huang, Dan Jurafsky, Christopher D. Manning, and Christopher Potts. 2025. AxBench: Steering LLMs? even simple baselines outperform sparse autoencoders. In *International Conference on Machine Learning*.

- Wu et al. (2024) Zhengxuan Wu, Aryaman Arora, Zhitao Wang, Atticus Geiger, Dan Jurafsky, Christopher D. Manning, and Christopher Potts. 2024. ReFT: Representation finetuning for language models. In *International Conference on Machine Learning*.

- Xiong et al. (2024) Miao Xiong, Zhiyuan Hu, Xinyang Lu, Yifei Li, Jie Fu, Junxian He, and Bryan Hooi. 2024. Can LLMs express their uncertainty? an empirical evaluation of confidence elicitation in LLMs. In *International Conference on Learning Representations*.

- Yang et al. (2024) An Yang, Baosong Yang, Beichen Zhang, and 1 others. 2024. Qwen2.5 technical report. *arXiv preprint arXiv:2412.15115*.

- Zheng et al. (2023) Lianmin Zheng, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu, Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, and 1 others. 2023. Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. In *Advances in Neural Information Processing Systems*, volume 36.

- Zou et al. (2023) Andy Zou, Long Phan, Sarah Chen, James Campbell, Phillip Guo, Richard Ren, Alexander Pan, Xuwang Yin, Mantas Mazeika, Ann-Kathrin Dombrowski, Shashwat Goel, Nathaniel Li, Michael J Byun, Zifan Wang, Alex Mallen, Steven Basart, Sanmi Koyejo, Dawn Song, Matt Fredrikson, and 2 others. 2023. Representation engineering: A top-down approach to AI transparency. *arXiv preprint arXiv:2310.01405*.

- Zur et al. (2025) Amir Zur, Atticus Geiger, Ekdeep Singh Lubana, and Eric Bigelow. 2025. Are language models aware of the road not taken? token-level uncertainty and hidden state dynamics. *arXiv preprint arXiv:2511.04527*.
