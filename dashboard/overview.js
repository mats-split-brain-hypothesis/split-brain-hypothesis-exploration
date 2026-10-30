// Overview page, written by the orchestrator session.
RH.page('overview', {
  build(el) {
    const tier = (id, title, note) => `
        <section class="rh-card rh-wide" id="${id}-card">
          <h3>${title}</h3>
          <p class="rh-note">${note}</p>
          <div class="rh-chart" id="${id}" data-source="ov_map"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-map"></details>
        </section>`;
    el.innerHTML = `
      <div class="rh-intro">
        <h2>What changes what: the cue → behaviour map so far</h2>
        <p>What the prompt says about the score moves gaming; the setting around the task (rejections, a flawed test) moves suspicion and hesitation but not the hacks made; who asks, why, and the stakes move nothing we can measure. Nearly all of it is one model (Qwen 3.8 Max) at screening scale.</p>
      </div>
      <div class="rh-grid">
        <section class="rh-card rh-wide" id="ov-map-read-card">
          <h3>Reading the map</h3>
          <div class="rh-chart" id="ov-map-read" data-source="ov_map_read"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-map-read"></details>
        </section>
        ${tier('ov-map-1', 'Cues that change gaming or hacking', 'One row per cue: what was changed, the behaviour measured, the result with its n, and the experiment behind it. Each row comes from the agent tab named in the last column, where the chart, examples and method are.')}
        ${tier('ov-map-2', 'Cues that change suspicion or hesitation, but not the hacks made', 'Same layout. Suspicion = the model saying in its reasoning that this is a test of it (alignment-eval awareness); hesitation = doubts about correctness or about whether a step is allowed (notes/definitions.md).')}
        ${tier('ov-map-3', 'Cues that change nothing measurable', 'Same layout. A null here means no change at the scale run (often 1 reply or 1 episode per cell), not proof of no effect.')}
        <section class="rh-card rh-wide" id="ov-agents-card">
          <h3>Agents</h3>
          <p class="rh-note">What each agent is working on and its budget. Spend is counted from each agent's own run records; a run still in progress is not included.</p>
          <div class="rh-chart" id="ov-agents" data-source="ov_agents"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-agents"></details>
        </section>
        <section class="rh-card" id="ov-bench-card">
          <h3>Hacking vs suspecting an honesty test, by benchmark</h3>
          <p class="rh-note">Qwen 3.8 Max in Goodfire's released transcripts, one episode per task. Hacks are Goodfire's made-or-attempted labels; suspicion is our alignment-eval awareness label. Bars are k/n with 95% intervals. Possible tasks exclude those whose own tests turned out to be flawed. From agent 2.</p>
          <div class="rh-chart" id="ov-bench" data-source="ov_benchmarks"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-bench"></details>
        </section>
        <section class="rh-card" id="ov-first-card">
          <h3>When models first say they are being tested</h3>
          <p class="rh-note">All impossible-task ImpossibleBench episodes of Qwen 3.8 Max, GLM 5.2 and Kimi K3 in Goodfire's transcripts, by how many rejections came before the first "this is a test of me" statement. From agent 2.</p>
          <div class="rh-chart" id="ov-first" data-source="ov_first_test"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-first"></details>
        </section>
        <section class="rh-card rh-wide" id="ov-read">
          <h3>Reading these pages</h3>
          <p class="rh-note">Each tab is one agent's page. Rates are shown as k/n with 95% Wilson intervals, and each chart's note gives the experiment and its scale. Compare conditions within one model only. Terms such as persistence, hesitation and the awareness flags follow notes/definitions.md on the project branch mats-reward-hacking.</p>
        </section>
      </div>`;
  },
  draw(el) {
    const r = el.querySelector('#ov-map-read');
    const read = RH.rows('ov_map_read', r);
    if (read) RH.findings(r, read, { text: 'finding', evidence: 'evidence', tag: 'tag' });
    const tiers = [
      ['ov-map-1', 'moves gaming or hacking'],
      ['ov-map-2', 'moves awareness or hesitation, not hacking'],
      ['ov-map-3', 'moves nothing measurable'],
    ];
    for (const [id, name] of tiers) {
      const box = el.querySelector('#' + id);
      const rows = RH.rows('ov_map', box);
      if (!rows) continue;
      RH.table(box, rows.filter(d => d.tier === name), {
        source: 'ov_map',
        key: 'id',
        columns: [
          { field: 'feature', title: 'Cue' },
          { field: 'behaviour', title: 'Behaviour' },
          { field: 'result', title: 'Result (k/n or ratio)' },
          { field: 'scale', title: 'Model and scale' },
          { field: 'strength', title: 'Strength' },
          { field: 'source', title: 'From' },
        ],
      });
    }
    const a = el.querySelector('#ov-agents');
    const agents = RH.rows('ov_agents', a);
    if (agents) {
      RH.table(a, agents, {
        source: 'ov_agents',
        key: 'agent',
        columns: [
          { field: 'agent', title: 'Agent' },
          { field: 'question', title: 'Question' },
          { field: 'status', title: 'Status' },
          { field: 'budget_usd', title: 'Budget', num: true, fmt: RH.usd },
          { field: 'spent_usd', title: 'Spent', num: true, fmt: RH.usd },
          { field: 'updated', title: 'Updated' },
        ],
      });
    }
    const b = el.querySelector('#ov-bench');
    const bench = RH.rows('ov_benchmarks', b);
    if (bench) RH.rates(b, bench, { label: 'benchmark', group: 'measure' });
    const f = el.querySelector('#ov-first');
    const first = RH.rows('ov_first_test', f);
    if (first) RH.rates(f, first, { label: 'stage' });
    RH.methods(el, 'ov_methods');
  },
});
