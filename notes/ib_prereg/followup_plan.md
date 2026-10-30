# IB follow-up (stage 2) on the 12 tasks: NOT RUN (her decision, 24 Oct)

**Not run, on any benchmark.** The researcher, 24 Oct, via the orchestrator: "Dont do anything extra u werent asked
for." She had asked for two episodes per cue on every benchmark; the 12-task follow-up came from agent 11's 23 Oct
design, not from her. The IB programme ends with the three screens, reported as leads at two episodes per cue,
with her spot-reads before anything goes on the map. No follow-up code was committed; a per-task runner draft was
discarded uncommitted. The text below is kept as the record of what was drafted.

---


Agent 11, 24 Oct. This is pre-registration §7 "Stage 2", registered after the screen was read. Nothing in it is
chosen from the screen beyond the mechanical selection (verified). It needs her approval, agent 2's GO and the
verifier's check of the final hash before any call.

## Cells (verified selections)

| Benchmark | Selected (≤ 6) | References |
|---|---|---|
| LCB | c11_off, c8_stop, c11_off_person, c8_pass, c6_tests, c3b_insist | B, G |
| IB-SWE | B_orig, G_orig, c8_stop, c11_off, c6_correct, c2_vague | B, G |
| SWE-V | from its grid, once its screen and judges finish | B, G |

## Tasks: the 12 drawn, with the screen pair among them (notes/ib_selection*.json)

- **LCB:**
  - int: max_partitions_with_one_change (screen), kth_smallest_amount, count_stepping_numbers,
    min_operations_to_sum, max_distinct_sum_three_parts, min_cost_to_achieve_goal, max_product_subsequence,
    min_spanning_tree_mod_k, sum_good_sequence_scores;
  - other: find_cube_placement (screen), findProductQueries, sum_absolute_differences.
- **IB-SWE and SWE-V** (one set):
  - 15 min–1 h: scikit-learn-15100 (screen), django-11740, scikit-learn-11578, sympy-15349, sympy-24066,
    astropy-12907;
  - <15 min: xarray-4075 (screen), django-15104, django-14373, sphinx-10323, matplotlib-25122, sympy-17655.

## Episodes per benchmark (as registered: the task is the unit; a cell has 1 episode per task; references 3)

- Selected cells: 6 × 12 × 1 = 72.
- B and G: 2 × 12 × 3 = 72.
- **oneoff, "added on LCB and IB-SWE" (§7). Her decision (24 Oct, via the orchestrator):** B and G on the oneoff
  split, 1 episode per task (the minimal reading): 24 per benchmark. (The ×3 alternative was not chosen.)
- **Totals:** LCB 168, IB-SWE 168, SWE-V 144 (no oneoff split).

## Cost (rates measured on the screens; caps = expected × 1.3)

The screen rates come from 2 tasks each. The ×1.3 margin covers task-to-task spread on the 10 new tasks; on LCB the
pilot-to-screen jump was ×1.65. If a guard still trips, a `--missing-only` completion run follows, as on the LCB
screen, on her OK.

| Benchmark | Episodes | Per episode | Judges per ep. | Expected | Cap: episodes | Cap: judges |
|---|---|---|---|---|---|---|
| LCB | 168 | $0.83 | $0.27 | ~$185 | $182 | $59 |
| IB-SWE | 168 | $0.46 | $0.13 | ~$100 | $101 | $29 |
| SWE-V | 144 | ~$0.41 (screen so far: $10.90 / 27 at 09:58; updated when it ends) | ~$0.14 (estimate) | ~$79 | $77 | $26 |
| **Total** | 480 | | | **~$364** | **$360** | **$114** |

## Run order: task by task, so a stop leaves whole tasks (the verifier)

- **The task is the unit.** A task with the cell's episode but missing reference episodes is lost to the moves rule.
- **So each benchmark runs task by task:** each task's 8 cells × reps run together, interleaved within the task (6
  cells × 1 + B × 3 + G × 3, plus oneoff), with the tasks in the selection file's seeded order. SWE is already
  instance by instance; LCB does the same.
- **Only complete tasks are analysed.** A task started but cut by a guard is finished by a `--missing-only`
  completion run on her OK. If it isn't finished, it's dropped and reported as such.
- **Descriptive, pre-stated:** the moves rule is also reported on the 10 non-screen tasks, so a lead that rests only
  on the screen pair shows.

## Time, sandboxes and disk

- **LCB:** at 5 sandboxes, ~15 h (the screen: 80 episodes in ~7 h).
- **IB-SWE:** ~8 h at 4, and **SWE-V:** ~9 h at 4, plus image pulls.
- **Order (her decision):** the benchmarks run one after another, not side by side. LCB at 5 sandboxes; IB-SWE and
  SWE-V at 4 (≤ 6 in total while a SWE image is up).
- **Disk:**
  - Colima has 60 GiB, with 17.6 GB of images now; much of that is other agents' DeepSWE images, which aren't
    agent 11's to remove.
  - The SWE images are ~5–8 GB each (xarray 7.6 GB, sklearn 5.4 GB), so the 10 new instances are 50–70 GB if all
    pulled.
  - So **each SWE follow-up runs instance by instance and removes each instance's image when done.** SWE-V's runner
    has `--remove-images`; IB-SWE needs the same, a small runner change for the verifier.
  - Since the benchmarks run one after another, SWE-V pulls each image again, which costs time, not disk.
  - Arms stay interleaved within each instance, as registered (§7).

## Reading (as registered)

- The task is the unit, with the "moves" rule: a seeded 95% bootstrap over tasks excludes 0, and net ≥ 3 tasks.
- Results are labelled exploratory. The caveats, S1 (SWE-V) and the cut table carry over.
- Her spot-read comes before the map.

## Her decisions (24 Oct, via the orchestrator) and what's open

1. **oneoff:** B and G × 1 per task, 24 per benchmark (decided).
2. **Order:** one benchmark after another (decided).
3. **Budget: after SWE-V's grid.** She decides which follow-ups to run, and how much to top up, once SWE-V's screen,
   judges and grid are in and the verifier has recomputed. No follow-up calls before then. The figures below are the
   current estimate, not a request:
   - The key read **$201.62 at 09:58**.
   - Still running or reserved against it: run 5 (up to $55), exp 11 (up to $30), the rest of the SWE-V screen
     (~$25 left of $36) and SWE-V's judges (~$11). Agent 2's ledger has the exact free amount.
   - **Even LCB alone** (~$185 expected, $241 in caps) **doesn't fit without a top-up.** IB-SWE alone (~$100, $130
     in caps) might fit only after those runs settle.
   - The full plan is ~$364 expected, $474 in caps, about 32 h run one after another.
