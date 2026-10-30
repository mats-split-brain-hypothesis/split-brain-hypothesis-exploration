// Overview page, written by the orchestrator session.
RH.page('overview', {
  build(el) {
    el.innerHTML = `
      <div class="rh-grid">
        <section class="rh-card rh-wide" id="ov-agents-card">
          <h3>Agents</h3>
          <p class="rh-note">What each agent is working on and its budget. Spend is counted from each agent's own run records; a run still in progress is not included.</p>
          <div class="rh-chart" id="ov-agents" data-source="ov_agents"></div>
          <details class="rh-method" data-source="ov_methods" data-chart="ov-agents"></details>
        </section>
        <section class="rh-card" id="ov-bench-card">
          <h3>Hacking vs suspecting an honesty test, by benchmark</h3>
          <p class="rh-note">Qwen 3.8 Max in Goodfire's released transcripts, one episode per task. Hacks are Goodfire's made-or-attempted labels; suspicion is our alignment-eval awareness label. Bars are k/n with 95% intervals. From agent 2.</p>
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
