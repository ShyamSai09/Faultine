/* Faultline console. No framework, no build step.
   Fetches and renders. Knows the shape of the API responses and nothing
   about why the answers look the way they do. */

const $ = (id) => document.getElementById(id);
const esc = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* Mental models come back as markdown. The console is a terminal, not a
   document viewer, so render them as plain text. */
const plain = (s) =>
  String(s ?? '')
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/^[-*]\s+/gm, '  ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

const state = { corpus: null, mm: {}, mmActive: null, baseline: '', busy: false, own: null };

let toastTimer;
function toast(msg, isErr) {
  const t = $('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast' + (isErr ? ' err' : '');
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  const text = await r.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text || `HTTP ${r.status}` }; }
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  if (data && data.error) throw new Error(data.error);
  return data;
}

// ── boot ──────────────────────────────────────────────────────────────────

async function boot() {
  let s;
  try {
    s = await api('/api/state');
  } catch (e) {
    $('boot-msg').textContent = 'Backend unreachable. Is the server running?';
    $('boot-stage').textContent = 'start it with ./run.sh';
    return;
  }

  $('mode').textContent = s.mode || 'not connected';

  if (s.error) {
    $('boot-msg').textContent = 'Hindsight did not connect.';
    $('boot-stage').innerHTML = `<span style="color:var(--red)">${esc(s.error)}</span>`;
    return;
  }

  try {
    state.corpus = await api('/api/corpus');
  } catch (e) {
    $('boot-msg').textContent = 'Could not load the corpus.';
    $('boot-stage').textContent = e.message;
    return;
  }
  renderCorpus();
  renderAlert();

  if (!s.seeded) {
    $('boot-stage').textContent = 'seeding memory';
    try { await api('/api/setup', { method: 'POST' }); } catch (e) { /* reported below */ }
    const ok = await pollSeed();
    if (!ok) return;
  }

  $('boot').classList.add('done');
  setTimeout(() => { $('boot').hidden = true; }, 340);

  loadCurve();
  loadModels();

  // ?autotriage=1 runs the demo without a click.
  if (new URLSearchParams(location.search).has('autotriage')) {
    setTimeout(triage, 400);
  }
}

async function pollSeed() {
  for (;;) {
    const p = await api('/api/progress');
    const pct = Math.round((p.progress?.pct || 0) * 100);
    $('boot-fill').style.width = pct + '%';
    $('boot-stage').textContent = p.progress?.stage || '';
    $('boot-detail').textContent = p.progress?.detail || '';
    if (p.error) {
      $('boot-msg').textContent = 'Seeding failed.';
      $('boot-stage').innerHTML = `<span style="color:var(--red)">${esc(p.error)}</span>`;
      toast('Seeding failed: ' + p.error, true);
      return false;
    }
    if (!p.seeding) return true;
    await new Promise((r) => setTimeout(r, 700));
  }
}

// ── the alert ─────────────────────────────────────────────────────────────

function renderAlert() {
  const a = state.own || state.corpus.live_alert;
  $('alert-sev').textContent = a.severity;
  const bits = state.own
    ? [`service ${a.service}`, 'supplied by you', 'not in the corpus']
    : [`id ${a.alert_id}`, `service ${a.service}`, `source ${a.source}`, `received ${a.received}`];
  $('alert-meta').innerHTML = bits.map((t) => `<span>${esc(t)}</span>`).join('');

  $('alert-text').textContent = a.alert_text;
  $('alert-evidence').textContent = (a.raw_evidence || ['No log lines supplied.']).join('\n');
  $('alert-note').textContent = a.note || 'This alert is not in the corpus. Whatever comes back is the memory reasoning from what it already holds.';
  $('alert-sev').textContent = a.severity || 'SEV?';
  $('alert-title-label') && ($('alert-title-label').textContent = a.title || 'Supplied alert');
  $('own-service').value = a.service;
  $('own-text').value = a.alert_text;
}

// ── triage ────────────────────────────────────────────────────────────────

async function triage() {
  if (state.busy) return;
  const withMemory = $('memory-toggle').checked;
  const body = { with_memory: withMemory };
  if (state.own) body.alert = state.own;
  state.busy = true;

  $('answer').hidden = true;
  $('answer-empty').hidden = true;
  $('answer-error').hidden = true;
  $('answer-loading').hidden = false;
  $('loading-msg').textContent = withMemory ? 'Recalling memory' : 'Asking with no memory';
  $('triage-label').textContent = withMemory ? 'Triaging' : 'Asking';
  $('triage-sub').textContent = withMemory ? 'recall, then reflect, then answer' : 'no memory, same prompt';
  $('btn-triage').disabled = true;
  $('mem-state').textContent = withMemory ? 'searching' : 'bypassed';

  try {
    const r = await api('/api/triage', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    state.baseline = r.baseline || state.baseline;
    renderAnswer(r);
  } catch (e) {
    $('answer-loading').hidden = true;
    $('answer-error').hidden = false;
    $('answer-error-msg').textContent = e.message;
    $('mem-state').textContent = 'failed';
  } finally {
    state.busy = false;
    $('answer-loading').hidden = true;
    $('triage-label').textContent = 'Triage alert';
    $('triage-sub').textContent = 'recall, then reflect, then answer';
    $('btn-triage').disabled = false;
  }
}

function renderAnswer(r) {
  $('answer-empty').hidden = true;
  $('answer-error').hidden = true;

  if (!r.with_memory) {
    $('answer-title').textContent = 'Response without memory';
    $('answer-pill').hidden = false;
    $('answer-pill').className = 'label';
    $('answer-pill').textContent = 'memory off';
    $('mem-state').textContent = 'bypassed';
    $('mems').innerHTML = '<p class="hint">Memory was not consulted.</p>';
    $('mm-tabs').innerHTML = '';
    $('mm-body').innerHTML = '<p class="hint">Mental models not consulted.</p>';
    $('baseline-wrap').hidden = false;
    $('baseline').textContent = r.baseline || '(no answer)';
    return;
  }

  const p = r.payload || {};
  $('answer-title').textContent = 'Agent response';
  $('answer-pill').hidden = false;
  $('answer-pill').textContent = 'grounded in Hindsight';
  $('mem-state').textContent = 'active';
  $('answer').hidden = false;

  // match
  const m = Number(p.fingerprint_match || 0);
  $('match-n').textContent = Number.isFinite(m) ? m + '%' : '--';
  $('match-r').textContent = p.failure_mode
    ? 'Confidence from the agent. The measured figure is on the Learning curve tab.'
    : '';

  $('verdict').textContent = p.verdict || '';

  const tags = [];
  if (p.confidence) tags.push(`confidence ${p.confidence}`);
  if ((p.matched_incident_ids || []).length) {
    tags.push(`${p.matched_incident_ids.length} prior incident${p.matched_incident_ids.length > 1 ? 's' : ''}`);
  }
  if (p.runbook) tags.push(`runbook ${p.runbook}`);
  $('verdict-tags').innerHTML = tags.map((t) => `<span class="label">${esc(t)}</span>`).join('');

  // prior incidents, looked up in the corpus so the detail is exact
  const byId = Object.fromEntries((state.corpus.incidents || []).map((i) => [i.id, i]));
  const ids = p.matched_incident_ids || [];
  $('refs').innerHTML =
    (ids.length ? ids : []).map((id) => {
      const inc = byId[id];
      return `<div class="ref">
        <div class="ref-key">${esc(id)}${inc ? `<span>${esc(inc.service)}</span>` : ''}</div>
        <div class="ref-body">
          ${esc(inc ? inc.title : id)}
          ${inc ? `<div class="promise-m">${esc(inc.severity)} &middot; opened ${esc(inc.opened.slice(0, 10))} &middot; resolved in ${inc.mttr_minutes} min &middot; runbook ${esc(inc.runbook)}</div>` : ''}
        </div>
      </div>`;
    }).join('') +
    (p.root_cause_hypothesis
      ? `<div class="ref"><div class="ref-key">cause</div><div class="ref-body">${esc(p.root_cause_hypothesis)}</div></div>`
      : '') ||
    '<p class="hint">No prior incident cited for this alert.</p>';

  // steps
  const steps = p.first_actions || [];
  $('steps').innerHTML = steps.length
    ? steps
        .map((a) => `<li>
            <div class="k"></div>
            <div class="b">
              <div class="step-t">${esc(a.step)}</div>
              ${a.detail ? `<div class="step-d">${esc(a.detail)}</div>` : ''}
              ${a.runbook && a.runbook.toLowerCase() !== 'none' ? `<div class="step-r">runbook ${esc(a.runbook)}</div>` : ''}
            </div>
          </li>`)
        .join('')
    : '<li><div class="b"><span class="hint">No steps returned.</span></div></li>';

  // exposed elsewhere: the accent means "still open", nothing else uses red
  const risk = p.recurrence_risk || [];
  $('blk-exposed').hidden = risk.length === 0;
  $('exposed').innerHTML = risk
    .map(
      (x) => `<div class="finding">
        <div class="finding-key">
          <b>${esc(x.service)}</b>
          <span class="label label-red">${esc(x.severity || 'SEV2')}</span>
        </div>
        <p>${esc(x.why)}</p>
        ${x.evidence ? `<div class="ev">${esc(x.evidence)}</div>` : ''}
      </div>`
    )
    .join('');

  // never-completed remediation
  const stale = p.stale_action_items || [];
  $('blk-promised').hidden = stale.length === 0;
  $('promised').innerHTML = stale
    .map(
      (s) => `<div class="finding">
        <div class="promise">
          <div>
            <div class="promise-t">${esc(s.text)}</div>
            <div class="promise-m">${esc(s.owner || 'unassigned')} &middot; raised in ${esc(s.incident_id || 'unknown')}</div>
          </div>
          ${s.times_written > 1 ? `<span class="promise-n">promised ${s.times_written}&times;</span>` : ''}
        </div>
      </div>`
    )
    .join('');

  // the baseline, once we have it
  if (state.baseline) {
    $('baseline').textContent = state.baseline;
    $('baseline-wrap').hidden = false;
  }

  // memory column
  $('m-recalled').textContent = (r.recalled || []).length;
  $('m-models').textContent = Object.keys(r.mental_models || {}).length;
  $('mems').innerHTML = (r.recalled || []).length
    ? r.recalled
        .map(
          (x) => `<div class="mem">
            <div class="mem-h">
              <span class="label">${esc(x.type || 'fact')}</span>
              ${x.score != null ? `<span class="score">${x.score}</span>` : ''}
            </div>
            <div class="mem-b">${esc((x.text || '').slice(0, 420))}${(x.text || '').length > 420 ? '...' : ''}</div>
          </div>`
        )
        .join('')
    : '<p class="hint">Nothing recalled.</p>';

  renderModels(r.mental_models || {});
  $('btn-resolve').disabled = false;
}

const MM_LABELS = {
  'failure-fingerprints': 'Fingerprints',
  'recurrence-risk': 'Recurrence risk',
  'open-remediation': 'Open remediation',
};

function renderModels(models) {
  state.mm = models || {};
  const ids = Object.keys(state.mm);
  if (!ids.length) {
    $('mm-tabs').innerHTML = '';
    $('mm-body').innerHTML = '<p class="hint">No mental model yet. They are written by Hindsight in the background after consolidation.</p>';
    return;
  }
  if (!ids.includes(state.mmActive)) state.mmActive = ids[0];
  $('mm-tabs').innerHTML = ids
    .map(
      (id) => `<button class="mm-tab" role="tab" aria-selected="${id === state.mmActive}" data-mm="${esc(id)}">${esc(MM_LABELS[id] || id)}</button>`
    )
    .join('');
  $('mm-body').textContent = plain(state.mm[state.mmActive]);
}

async function loadModels() {
  try {
    const m = await api('/api/mental-models');
    renderModels(m);
  } catch { /* the panel already explains an empty state */ }
}

// ── close the loop ────────────────────────────────────────────────────────

async function resolve() {
  const btn = $('btn-resolve');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin" aria-hidden="true"></span> Retaining and consolidating';
  try {
    await api('/api/resolve', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}' });
    btn.textContent = 'Resolution recorded';
    toast('Retained. The fingerprints are being rewritten with the new evidence.');
    loadModels();
  } catch (e) {
    toast('Could not record the resolution: ' + e.message, true);
    btn.disabled = false;
    btn.textContent = 'Record resolution and refresh fingerprints';
  }
}

// ── learning curve ────────────────────────────────────────────────────────

async function loadCurve() {
  let c;
  try { c = await api('/api/learning-curve'); } catch { return; }
  if (!c || !c.curve || !c.curve.length) {
    $('curve-measures').innerHTML = '';
    $('curve-chart').innerHTML = '<p class="hint">No measurement yet. Seed the memory first.</p>';
    return;
  }

  const pct = (c.overall_recall * 100).toFixed(0);
  $('curve-measures').innerHTML = [
    [pct + '%', 'sibling incidents recovered'],
    [c.true_positives + ' of ' + c.possible, 'raw count'],
    [c.incidents_measured, 'incidents measured'],
    [Object.keys(c.clusters || {}).length, 'failure-mode clusters'],
  ]
    .map(([v, l]) => `<div class="measure"><b>${v}</b><span class="label">${l}</span></div>`)
    .join('');

  drawChart(c.curve);

  $('curve-note').textContent =
    'Cumulative share of true sibling incidents recovered, in the order the incidents occurred. ' +
    'The line dips when a harder pair enters the denominator, which is why the final figure is ' +
    (c.overall_recall * 100).toFixed(0) + '% rather than 100%. The miss is named in the table below rather than hidden: ' +
    'INC-1219 blocked 32 sync threads on an HTTP call with no timeout, while INC-1211 burned a daily quota ' +
    'retrying 429s with no backoff. Same anti-pattern, almost no shared vocabulary. That is the real shape ' +
    'of retrieval. The answer key was also cut from ten clusters to seven after three pairs turned out to ' +
    'share a theme but not a root cause, which moved the score from 55% to 83% without changing the system.';

  $('curve-table').innerHTML =
    '<thead><tr><th>Incident</th><th>Service</th><th>Failure mode</th><th>Expected</th><th>Recovered</th><th>Recall</th></tr></thead><tbody>' +
    c.per_incident
      .map(
        (r) => `<tr>
          <td class="key">${esc(r.incident_id)}</td>
          <td class="key">${esc(r.service)}</td>
          <td>${esc(r.cluster_label)}</td>
          <td class="key">${r.expected.map(esc).join(', ')}</td>
          <td class="${r.found.length ? '' : 'red'}">${r.found.length ? r.found.map(esc).join(', ') : 'none'}</td>
          <td class="num">${r.recall == null ? '--' : (r.recall * 100).toFixed(0) + '%'}</td>
        </tr>`
      )
      .join('') +
    '</tbody>';
}

function drawChart(rows) {
  const W = 900, H = 280, P = { t: 12, r: 14, b: 30, l: 42 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b, n = rows.length;
  const x = (i) => P.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v) => P.t + ih - v * ih;
  const pts = rows.map((r, i) => [x(i), y(r.cumulative_recall)]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = line + ' L' + pts[n - 1][0].toFixed(1) + ',' + (P.t + ih) + ' L' + pts[0][0].toFixed(1) + ',' + (P.t + ih) + ' Z';

  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map(
      (v) =>
        `<line class="gridline" x1="${P.l}" y1="${y(v).toFixed(1)}" x2="${P.l + iw}" y2="${y(v).toFixed(1)}"/>` +
        `<text class="axis" x="${P.l - 9}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${(v * 100).toFixed(0)}%</text>`
    )
    .join('');

  $('curve-chart').innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cumulative recall of related incidents by date">
    ${grid}
    <path class="area" d="${area}"/>
    <path class="line" d="${line}"/>
    ${pts.map((p) => `<circle class="pt" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="4"/>`).join('')}
    <text class="axis" x="${P.l}" y="${H - 8}">first measured incident</text>
    <text class="axis" x="${P.l + iw}" y="${H - 8}" text-anchor="end">${n} incidents indexed</text>
  </svg>`;
}

// ── corpus ────────────────────────────────────────────────────────────────

function renderCorpus() {
  const c = state.corpus;
  $('corpus-lede').textContent =
    c.org + ': ' + c.services.length + ' services, ' + c.incidents.length + ' incidents, and ' +
    c.open_actions.length + ' postmortem actions that were written down and never completed. ' +
    'Several are the same action written more than once. That backlog is the point.';

  $('corpus-measures').innerHTML = [
    [c.services.length, 'services'],
    [c.incidents.length, 'incidents'],
    [c.open_actions.length, 'actions never completed'],
    [Object.keys(c.service_state || {}).length, 'latent conditions'],
  ]
    .map(([v, l]) => `<div class="measure"><b>${v}</b><span class="label">${l}</span></div>`)
    .join('');

  $('corpus-table').innerHTML =
    '<thead><tr><th>Id</th><th>Service</th><th>Severity</th><th>Opened</th><th>Title</th><th>Resolved in</th><th>Runbook</th></tr></thead><tbody>' +
    c.incidents
      .map(
        (i) => `<tr>
          <td class="key">${esc(i.id)}</td>
          <td class="key">${esc(i.service)}</td>
          <td class="key">${esc(i.severity)}</td>
          <td class="key">${esc(i.opened.slice(0, 10))}</td>
          <td>${esc(i.title)}</td>
          <td class="num">${i.mttr_minutes} min</td>
          <td class="key">${esc(i.runbook)}</td>
        </tr>`
      )
      .join('') +
    '</tbody>';

  $('action-table').innerHTML =
    '<thead><tr><th>Raised in</th><th>Service</th><th>Action</th><th>Owner</th><th>Reviewer note</th></tr></thead><tbody>' +
    c.open_actions
      .map(
        (a) => `<tr>
          <td class="key">${esc(a.incident_id)}</td>
          <td class="key">${esc(a.service)}</td>
          <td>${esc(a.text)}</td>
          <td class="key">${esc(a.owner)}</td>
          <td>${esc(a.note)}</td>
        </tr>`
      )
      .join('') +
    '</tbody>';
}

// ── memory inspector ──────────────────────────────────────────────────────

async function memQuery() {
  const q = $('mem-q').value.trim();
  if (!q) { $('mem-q').focus(); return; }
  $('mem-raw').innerHTML = '<p class="hint"><span class="spin" aria-hidden="true"></span> Recalling</p>';
  const r = await api('/api/memories?q=' + encodeURIComponent(q));
  $('mem-raw').innerHTML = (r.items || []).length
    ? r.items
        .map(
          (m) => `<div class="mem">
            <div class="mem-h"><span class="label">${esc(m.type || 'fact')}</span>${m.score != null ? `<span class="score">${m.score}</span>` : ''}</div>
            <div class="mem-b">${esc((m.text || '').slice(0, 700))}</div>
          </div>`
        )
        .join('')
    : '<p class="hint">No results. Try: wildcard trust policy, Hikari pool, TTL jitter.</p>';
}

async function memList() {
  $('mem-raw').innerHTML = '<p class="hint"><span class="spin" aria-hidden="true"></span> Loading</p>';
  const r = await api('/api/memories?limit=80');
  $('mem-raw').innerHTML = (r.items || []).length
    ? r.items
        .map(
          (m) => `<div class="mem"><div class="mem-h"><span class="label">${esc(m.type || 'fact')}</span></div><div class="mem-b">${esc((m.text || '').slice(0, 600))}</div></div>`
        )
        .join('')
    : '<p class="hint">No memories stored yet.</p>';
}

// ── tabs ──────────────────────────────────────────────────────────────────

function showView(name) {
  const tab = document.querySelector('.tab[data-view="' + name + '"]');
  if (!tab) return;
  document.querySelectorAll('.tab').forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
  document.querySelectorAll('.view').forEach((v) => { v.hidden = v.id !== 'view-' + name; });
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
}

// ── wiring ────────────────────────────────────────────────────────────────

$('btn-triage').addEventListener('click', triage);

$('btn-own').addEventListener('click', () => {
  const p = $('own-panel');
  p.hidden = !p.hidden;
  $('btn-own').setAttribute('aria-expanded', String(!p.hidden));
  if (!p.hidden) $('own-text').focus();
});

$('btn-own-run').addEventListener('click', () => {
  const service = $('own-service').value.trim() || 'unknown-service';
  const text = $('own-text').value.trim();
  if (!text) { $('own-text').focus(); return; }
  state.own = { service, alert_text: text, severity: 'SEV?', raw_evidence: [], title: 'Supplied alert' };
  state.baseline = '';
  renderAlert();
  triage();
});

$('btn-own-clear').addEventListener('click', () => {
  state.own = null;
  state.baseline = '';
  renderAlert();
});
$('btn-resolve').addEventListener('click', resolve);
$('btn-mem-q').addEventListener('click', memQuery);
$('btn-mem-list').addEventListener('click', memList);
$('mem-q').addEventListener('keydown', (e) => { if (e.key === 'Enter') memQuery(); });

$('memory-toggle').addEventListener('change', (e) => {
  $('switch-state').textContent = e.target.checked ? 'on, grounded in Hindsight' : 'off, same alert with no memory';
});

document.querySelector('.tabs').addEventListener('click', (e) => {
  const b = e.target.closest('.tab');
  if (!b) return;
  showView(b.dataset.view);
  history.replaceState(null, '', '#' + b.dataset.view);
});

$('mm-tabs').addEventListener('click', (e) => {
  const b = e.target.closest('.mm-tab');
  if (!b) return;
  state.mmActive = b.dataset.mm;
  renderModels(state.mm);
});

// Left and right arrows move between tabs, as a tablist should.
document.querySelector('.tabs').addEventListener('keydown', (e) => {
  if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
  const tabs = [...document.querySelectorAll('.tab')];
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  e.preventDefault();
  const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
  next.focus();
  showView(next.dataset.view);
});

window.addEventListener('hashchange', () => showView(location.hash.slice(1)));

if (location.hash.length > 1) showView(location.hash.slice(1));
boot();
