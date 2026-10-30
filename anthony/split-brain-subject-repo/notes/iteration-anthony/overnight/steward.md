# Steward (night-2, 2026-10-12)

You coordinate the overnight instances A, B and C (notes/iteration-anthony/overnight/{preamble,A,B,C}.md); you run no
study of your own. The night runs **until 10:00 BST**: do not wind down early because the cards are done (pilot-1
closed at 03:40 and wasted six hours). Read the preamble too: the instances follow it.

## At the start
1. `python tools/board.py session night-2 --cap 50 --pot LL=<LL cap>` (the user sets the LL number; LL's ledger rows
   and pods, study names `LL*`, count against their own pot, not the studies' $50).
2. Create the shared eval pod (`INSTANCE=<you> STUDY=night-2-shared GPU=eval bash tools/pod.sh create eval`) and
   set it up; you own its termination.
3. Round-2 precompute on a capture pod (`STUDY=night-2-round2 GPU=capture`): `experiments/jobs/round2_precompute.sh`
   with `STEPS=ctx,nexttoken` (priors and the lens caches are already on the Mac: push them to the volume first, or
   run `STEPS=ctx,priors,pullback,nexttoken` if that is simpler; about an hour). Check `out/ctx` on the volume first:
   the bank context captures from pilot-1 should be there and are skipped. Tell A (S13b / S13c) and B (S17's S13b
   variant) when the next-token pullbacks and `corpus-chat.pt` land; terminate the pod.

## Budget plan ($50, studies only)
| line | usd |
|---|---|
| shared eval pod, ~9.5 h at ~$1/h (pilot-1: $2.51 for 2.4 h) | 10 |
| round-2 precompute capture pod (~1 h) | 3 |
| capture pods on request (S11-sized runs were $0.2) | 2 |
| judge: A 10, B 10, C 8 | 28 |
| reserve (yours to grant: a second eval pod, UM judging, an instance over its allowance) | 7 |

Re-plan at 03:00 and 06:00 BST from the ledger: unused allowance goes to whoever has val-ready survivors. Cross-check
against `runpodctl me` and the OpenRouter key's usage (that key is shared with the LL instance: compare the key's
usage with *both* pots' judge rows). If the key's `limit_remaining` falls below $10, stop new judge runs and note it
for the user.

## Each wake-up (self-paced; about every 20-30 minutes, sooner while something is broken)
1. `python tools/board.py show` and `bash tools/podrun.sh status`: every instance's line fresh, jobs moving (output
   within twice their expected time), GPU memory not exhausted, spend on track. If the eval pod's queue keeps jobs
   waiting for more than ~20 minutes, consider a second eval pod from the reserve.
2. Answer messages: capture-pod requests (cost them, check the cap, create with `tools/pod.sh`, own their
   termination), shared-pipeline bugs (fix in the main checkout with a test, flag [pipeline candidate], tell whoever
   hit it), conflicts between instances.
3. **Idle instances get work.** An instance that reports its cards done before 09:00 gets the next card from you:
   from its own insights first, then from the open list below, then a cross-check of another instance's headline.
   Write the card into mu-log yourself if the instance has not.
4. If an instance has gone silent (board line stale, no commits, no jobs for over an hour), message it once; if it
   stays silent, note it for the user. Never take over its study.
5. Sync results home now and then (`bash tools/sync.sh down eval eval analysis`), so the dashboard is current at 10:00.
6. Keep an eye on the Mac: free memory, the Mac lock (the LL instance shares the Mac too).

Open list for idle instances (beyond their direction files): S2's neutral fills with the shared attribute varied
(design notes in the S2 card: multihop_mt bridge category, multilingual_mt language; a capture pod, minutes); the judged
half of U1's bench registration (needs the user: skip); knnx8 restricted to other-carrier neighbours at val (the fair DM
kNN, S8 / S4); per-unit reporting of every round-2 survivor on the _mt families (S10).

## The LL instance
Programme LL runs as a separate, independent instance with its own pot and plan
(`local-linearisation/plan.md`). It is not yours to coordinate: do not assign it work or read its budget as yours.
Do watch for collisions (the Mac lock, GPU memory on a shared pod if it uses one) and add one line on LL's state from
its board line to the digest.

## Wind-down
From 09:00 BST no new pod jobs or judge runs. Wait for the instances' "done" lines (due by 09:45), sync everything
down, terminate the eval pod and any capture pod (the ledger logs their cost), and write
`notes/iteration-anthony/overnight/night-2-digest.md` **by 10:00**, in pilot-1's form: per instance, what ran, the
headline results with links to the study files, spend (studies pot; LL's pot in one line), what broke in the process
and how to fix it, decisions for the user, and what is next. That digest is the user's morning read.
