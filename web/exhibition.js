/* Exhibition page: run, follow, load and display a pipeline run (API: exhibition_api.py) */

document.addEventListener('DOMContentLoaded', () => {

const $ = id => document.getElementById(id);
const els = {
  country: $('exCountry'), yearFrom: $('exYearFrom'), yearTo: $('exYearTo'),
  review: $('exReview'), factCheck: $('exFactCheck'), run: $('exRun'), stop: $('exStop'),
  saved: $('exSaved'), load: $('exLoad'), replay: $('exReplay'), latest: $('exLatest'),
  status: $('exStatus'), placeholder: $('exPlaceholder'), result: $('exResult'),
  meta: $('exMeta'), title: $('exTitle'), concept: $('exConcept'), missing: $('exMissing'),
  sections: $('exSections'), reviewBox: $('exReviewBox'), agents: $('exAgents'),
  vision: $('exVision'), gallery: $('exGallery'),
  museum: $('exMuseum'), museumNav: $('exMuseumNav'), museumHalls: $('exMuseumHalls'),
};
if (!els.run) return;

const AGENT_LABELS = {
  historian: '📜 Historian', sociologist: '👥 Sociologist', technology: '⚙️ Technology',
  culture_art: '🎨 Culture & Art', visual: '🖼️ Visual',
};
const POLL_MS = 5000;
let pollTimer = null;
let currentRun = null;
let shownRun = null;

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function safeUrl(url) {
  return /^https?:\/\//i.test(url || '') ? url : '';
}
function setStatus(kind, html) {
  els.status.className = `ex-status ex-status-${kind}`;
  els.status.innerHTML = html;
  els.status.classList.remove('hidden');
}
function setBusy(busy) {
  [els.run, els.replay].forEach(b => { b.disabled = busy; });
  els.stop.classList.toggle('hidden', !busy);
  els.stop.disabled = false;
  els.run.innerHTML = busy ? '<span class="spinner"></span> Run en cours…' : '<span class="btn-icon">▶</span> Lancer un run';
}
async function api(path, options) {
  const res = await fetch(path, options);
  let body = {};
  try { body = await res.json(); } catch (_) { /* empty */ }
  return { status: res.status, body };
}

function runLabel(r) {
  const when = (r.started_at || r.run_id).replace('T', ' ').slice(0, 16);
  const what = r.complete ? (r.title || 'Exposition') : 'incomplet (sans exposition)';
  const extra = [r.country, r.model && r.model.split('/').pop(), r.from_run && 'rejoué'].filter(Boolean).join(' · ');
  return `${when} — ${what}${extra ? ` (${extra})` : ''}`;
}

async function loadSaved(select) {
  const { status, body } = await api('/api/exhibitions');
  if (status !== 200) return;
  const keep = select || els.saved.value;
  els.saved.innerHTML = (body.runs || []).length
    ? body.runs.map(r => `<option value="${esc(r.run_id)}">${esc(runLabel(r))}</option>`).join('')
    : '<option value="">Aucun run sauvegardé</option>';
  if (keep && [...els.saved.options].some(o => o.value === keep)) els.saved.value = keep;
  if (body.running && !pollTimer) follow(body.running);
}

function follow(runId, replay = false) {
  const started = Date.now();
  currentRun = runId;
  const steps = replay
    ? 'curateur puis fact-check, sur les analyses sauvegardées'
    : 'les 5 agents, puis la revue, le curateur et le fact-check';
  setBusy(true);
  clearInterval(pollTimer);
  const tick = async () => {
    const { status, body } = await api(`/api/exhibition/${encodeURIComponent(runId)}`);
    if (status === 200 && body.status === 'running') {
      const secs = Math.round((Date.now() - started) / 1000);
      const what = body.cancelling ? 'arrêt en cours…' : steps;
      setStatus('running', `<span class="spinner"></span> Run <code>${esc(runId)}</code> en cours… ${secs} s
        <span class="ex-muted">(${what})</span>`);
      return;
    }
    clearInterval(pollTimer);
    pollTimer = null;
    currentRun = null;
    setBusy(false);
    if (status !== 200) {
      setStatus('error', `Run <code>${esc(runId)}</code> introuvable (${status}).`);
      return;
    }
    body.openMuseum = Boolean(body.exhibition);
    render(body);
    loadSaved(runId);
  };
  pollTimer = setInterval(tick, POLL_MS);
  tick();
}

async function start(payload) {
  const { status, body } = await api('/api/exhibition', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (status === 202 || status === 200) return follow(body.run_id, Boolean(payload.from_run));
  if (status === 409) {
    setStatus('running', 'Un run est déjà en cours : affichage de son avancement.');
    return follow(body.run_id);
  }
  const msg = status === 401 ? 'Ce serveur exige un token (EXHIBITION_API_TOKEN).' : (body.error || `Erreur ${status}`);
  setStatus('error', esc(msg));
}

els.run.addEventListener('click', () => {
  const year = el => (el.value === '' ? null : Number(el.value));
  start({
    country: els.country.value.trim() || null, year_from: year(els.yearFrom), year_to: year(els.yearTo),
    review: els.review.checked, fact_check: els.factCheck.checked,
  });
});

els.stop.addEventListener('click', async () => {
  if (!currentRun) return;
  els.stop.disabled = true;
  const { status, body } = await api(`/api/exhibition/${encodeURIComponent(currentRun)}/cancel`, { method: 'POST' });
  if (status !== 202) { els.stop.disabled = false; setStatus('error', esc(body.error || `Erreur ${status}`)); }
});

els.replay.addEventListener('click', () => {
  if (!els.saved.value) return setStatus('error', 'Choisissez d\'abord un run sauvegardé.');
  start({ from_run: els.saved.value, fact_check: els.factCheck.checked });
});

els.load.addEventListener('click', async () => {
  if (!els.saved.value) return;
  await loadRun(els.saved.value, { openMuseum: true });
});

els.latest.addEventListener('click', async () => {
  const { status, body } = await api('/api/exhibition/latest');
  if (status === 200) {
    body.openMuseum = true;
    render(body);
    loadSaved(body.run_id);
  } else setStatus('error', esc(body.error || `Erreur ${status}`));
});

function citeLinks(text, refs) {
  return esc(text).replace(/\[([^\[\]]+)\]/g, (whole, inner) => {
    const ids = inner.split(',').map(s => s.trim());
    if (!ids.every(id => refs.has(id))) return whole;
    return ids.map(id => `<a class="ex-cite" href="#ex-art-${esc(id)}">${refs.get(id)}</a>`).join('');
  });
}

function factBadge(verdict) {
  if (!verdict) return '<span class="ex-badge ex-badge-off">Fact-check non exécuté</span>';
  if (verdict.supported === true) return '<span class="ex-badge ex-badge-ok">✓ Vérifié</span>';
  if (verdict.supported === false) {
    const claims = (verdict.unsupported_claims || []).map(c => `<li>${esc(c)}</li>`).join('');
    return `<details class="ex-badge ex-badge-warn"><summary>⚠ ${(verdict.unsupported_claims || []).length || ''} non soutenue(s)</summary><ul>${claims}</ul></details>`;
  }
  return '<span class="ex-badge ex-badge-off">? Non vérifiable</span>';
}

function plainVision(text) {
  return text.replace(/\*\*|^#+\s*/gm, '').replace(/^\s*[-*]\s+/gm, '• ').replace(/\n{2,}/g, '\n').trim();
}

function artifactCard(a, n) {
  const url = safeUrl(a.url);
  const img = safeUrl(a.image_url);
  const meta = [a.source, a.category, a.year].filter(v => v !== undefined && v !== null && v !== '').join(' · ');
  const text = (a.content || '').length > 240 ? `${a.content.slice(0, 240)}…` : (a.content || '');
  return `
    <article class="ex-artifact" id="ex-art-${esc(a.id)}">
      ${img ? `<img class="ex-art-img" src="${esc(img)}" alt="${esc(a.title || '')}" loading="lazy" onerror="this.remove()">` : ''}
      <div class="ex-art-body">
        <div class="ex-art-head"><span class="ex-art-num">${n}</span><span class="ex-art-title">${esc(a.title || 'Source sans titre')}</span></div>
        ${meta ? `<div class="ex-art-meta">${esc(meta)}</div>` : ''}
        ${text ? `<p class="ex-art-text">${esc(text)}</p>` : ''}
        ${a.vision ? `<details class="ex-vision"><summary>👁 Ce que l'IA voit</summary><p>${esc(plainVision(a.vision))}</p></details>` : ''}
        ${url ? `<a class="ex-art-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Voir la source ↗</a>` : ''}
      </div>
    </article>`;
}

function renderSections(sections) {
  els.sections.innerHTML = sections.map((s, i) => {
    const refs = new Map(s.artifacts.map((a, k) => [a.id, k + 1]));
    return `
      <section class="card ex-section">
        <div class="ex-section-head">
          <span class="ex-section-num">${i + 1}</span>
          <h3 class="ex-section-title">${esc(s.title)}</h3>
          ${factBadge(s.fact_check)}
        </div>
        <p class="ex-narrative">${citeLinks(s.narrative, refs)}</p>
        <div class="ex-artifacts">${s.artifacts.map((a, k) => artifactCard(a, k + 1)).join('')}</div>
      </section>`;
  }).join('');
}

/** One curator section → one museum hall; wall shows corpus images already on artifacts. */
function renderMuseumHalls(sections) {
  if (!els.museum || !els.museumHalls) return;
  const rooms = (sections || []).map((s, i) => {
    const withImg = [...new Map(
      (s.artifacts || []).filter(a => safeUrl(a.image_url)).map(a => [a.id, a]),
    ).values()];
    return { index: i + 1, title: s.title || `Salle ${i + 1}`, narrative: s.narrative || '', items: withImg, fact: s.fact_check };
  });
  const withArt = rooms.filter(r => r.items.length);
  if (!withArt.length) {
    els.museum.classList.add('hidden');
    els.museumHalls.innerHTML = '';
    els.museumNav.innerHTML = '';
    return;
  }
  els.museum.classList.remove('hidden');
  els.museumNav.innerHTML = rooms.map(r =>
    `<a class="ex-museum-nav-item${r.items.length ? '' : ' is-empty'}" href="#ex-hall-${r.index}">
      Salle ${r.index}<span>${esc(r.title)}</span>
      <em>${r.items.length ? `${r.items.length} œuvre(s)` : 'sans image'}</em>
    </a>`).join('');
  els.museumHalls.innerHTML = rooms.map(r => {
    const wall = r.items.length
      ? `<div class="ex-hall-wall">${r.items.map(a => `
          <figure class="ex-hall-frame">
            <a href="#ex-art-${esc(a.id)}">
              <img src="${esc(safeUrl(a.image_url))}" alt="${esc(a.title || '')}" loading="lazy"
                   onerror="this.closest('figure').remove()">
            </a>
            <figcaption>${esc(a.title || 'Sans titre')}${a.year != null ? ` · ${esc(a.year)}` : ''}</figcaption>
          </figure>`).join('')}</div>`
      : `<p class="ex-hall-empty">Aucune image dans cette salle — le récit reste dans la section ci-dessous.</p>`;
    const plaque = (r.narrative || '').slice(0, 220);
    return `
      <article class="ex-hall" id="ex-hall-${r.index}">
        <header class="ex-hall-door">
          <span class="ex-hall-num">Salle ${r.index}</span>
          <h4 class="ex-hall-name">${esc(r.title)}</h4>
          ${factBadge(r.fact)}
        </header>
        ${wall}
        ${plaque ? `<p class="ex-hall-plaque">${esc(plaque)}${r.narrative.length > 220 ? '…' : ''}</p>` : ''}
      </article>`;
  }).join('');
}

function scrollToMuseum() {
  if (!els.museum || els.museum.classList.contains('hidden')) return;
  requestAnimationFrame(() => els.museum.scrollIntoView({ behavior: 'smooth', block: 'start' }));
}

function agentChips(agents) {
  return (agents || []).map(a => `<span class="ex-chip">${esc(AGENT_LABELS[a] || a)}</span>`).join('');
}

function renderReview(review) {
  const block = (title, items, line) => items.length
    ? `<h4 class="ex-subhead">${title}</h4><ul class="ex-list">${items.map(line).join('')}</ul>` : '';
  const html =
    block('Accords', review.agreements, r => `<li>${agentChips(r.agents)} ${esc(r.point)}</li>`) +
    block('Tensions', review.tensions, r => `<li>${agentChips(r.agents)} ${esc(r.issue)}</li>`) +
    block('Constats fragiles', review.weak_findings,
      r => `<li>${agentChips([r.agent])} ${esc(r.reason)}</li>`);
  els.reviewBox.innerHTML = html || '<p class="ex-muted">Pas de revue croisée pour ce run.</p>';
}

function renderAgents(insights) {
  const names = Object.keys(AGENT_LABELS).filter(n => insights[n]).concat(
    Object.keys(insights).filter(n => !AGENT_LABELS[n]));
  els.agents.innerHTML = names.map(name => {
    const ins = insights[name];
    const badge = ins.status === 'ok' ? `<span class="ex-badge ex-badge-ok">${(ins.key_findings || []).length} constat(s)</span>`
      : ins.status === 'abstained' ? '<span class="ex-badge ex-badge-off">abstention</span>'
      : '<span class="ex-badge ex-badge-err">erreur</span>';
    const findings = (ins.key_findings || []).map(f => `<li>${esc(f)}</li>`).join('');
    return `
      <details class="ex-agent">
        <summary>${esc(AGENT_LABELS[name] || name)} ${badge}</summary>
        ${ins.perspective ? `<p class="ex-agent-persp">${esc(ins.perspective)}</p>` : ''}
        ${findings ? `<ul class="ex-list">${findings}</ul>` : `<p class="ex-muted">${esc(ins.reason || 'Aucun constat.')}</p>`}
      </details>`;
  }).join('') || '<p class="ex-muted">Aucun agent enregistré.</p>';
}

function render(view) {
  els.placeholder.classList.add('hidden');
  els.result.classList.remove('hidden');
  const cfg = view.config || {};
  const years = (cfg.years || []).map(y => y ?? '…').join('–');
  els.meta.innerHTML = [
    `run <code>${esc(view.run_id)}</code>`, cfg.country && esc(cfg.country), years && esc(years),
    cfg.model && esc(cfg.model), cfg.from_run && `rejoué depuis <code>${esc(cfg.from_run)}</code>`,
    view.timings && view.timings.total && `${Math.round(view.timings.total)} s`,
  ].filter(Boolean).join(' · ');

  const ex = view.exhibition;
  shownRun = ex ? view.run_id : null;
  const images = ex ? ex.sections.flatMap(s => s.artifacts).filter(a => a.image_url) : [];
  const seen = images.filter(a => a.vision).length;
  const unique = [...new Map(images.filter(a => safeUrl(a.image_url)).map(a => [a.id, a])).values()];
  els.gallery.innerHTML = unique.length
    ? `<div class="ex-gallery-label">🖼️ Plan rapide · ${unique.length} œuvre(s) — voir les salles ci-dessous</div><div class="ex-gallery-grid">` +
      unique.map(a => `<a class="ex-gallery-item" href="#ex-art-${esc(a.id)}" title="${esc(a.title || '')}">
        <img src="${esc(safeUrl(a.image_url))}" alt="${esc(a.title || '')}" loading="lazy" onerror="this.parentElement.remove()">
        <span>${esc(a.title || '')}</span></a>`).join('') + '</div>'
    : '';
  els.vision.classList.toggle('hidden', !images.length);
  els.vision.disabled = images.length > 0 && seen === images.length;
  els.vision.textContent = els.vision.disabled
    ? `👁 ${seen}/${images.length} images analysées` : `👁 Analyser les images (IA) · ${seen}/${images.length}`;

  if (ex) {
    els.title.textContent = ex.title;
    els.concept.textContent = ex.concept;
    els.missing.innerHTML = ex.missing_perspectives.length
      ? `Perspectives absentes : ${agentChips(ex.missing_perspectives)}` : '';
    renderMuseumHalls(ex.sections);
    renderSections(ex.sections);
    const ok = ex.sections.filter(s => s.fact_check && s.fact_check.supported === true).length;
    const checked = ex.sections.some(s => s.fact_check);
    const halls = (ex.sections || []).filter(s => (s.artifacts || []).some(a => a.image_url)).length;
    setStatus('ok', `Exposition chargée : ${ex.sections.length} section(s)` +
      (halls ? `, ${halls} salle(s) avec images` : '') +
      (checked ? `, ${ok}/${ex.sections.length} entièrement vérifiée(s).` : '.'));
    if (view.openMuseum) scrollToMuseum();
  } else {
    els.title.textContent = 'Pas d\'exposition pour ce run';
    els.concept.textContent = 'Sélectionnez ce run et cliquez sur « Rejouer le curateur ».';
    els.missing.innerHTML = '';
    els.sections.innerHTML = '';
    if (els.museum) { els.museum.classList.add('hidden'); els.museumHalls.innerHTML = ''; }
    if (view.run_id) els.saved.value = view.run_id;
    setStatus('error', view.cancelled
      ? 'Run arrêté. Les analyses déjà terminées sont sauvegardées.'
      : esc(view.error || 'Le run s\'est arrêté avant l\'exposition.'));
  }
  renderReview(view.review || { agreements: [], tensions: [], weak_findings: [] });
  renderAgents(view.insights || {});
}

async function loadRun(runId, { openMuseum = false } = {}) {
  const { status, body } = await api(`/api/exhibition/${encodeURIComponent(runId)}`);
  if (status !== 200) {
    setStatus('error', esc(body.error || `Erreur ${status}`));
    return;
  }
  body.openMuseum = openMuseum;
  render(body);
  loadSaved(runId);
}

els.vision.addEventListener('click', async () => {
  if (!shownRun) return;
  els.vision.disabled = true;
  els.vision.innerHTML = '<span class="spinner"></span> Analyse des images…';
  const { status, body } = await api(`/api/exhibition/${encodeURIComponent(shownRun)}/vision`, { method: 'POST' });
  if (status !== 200) {
    els.vision.disabled = false;
    els.vision.textContent = '👁 Analyser les images (IA)';
    return setStatus('error', esc(status === 401 ? 'Token requis.' : (body.error || `Erreur ${status}`)));
  }
  render(body);
  setStatus('ok', `${body.vision_added || 0} image(s) décrite(s). Ouvrez « Ce que l'IA voit » sous chaque image.`);
});

document.querySelectorAll('.nav-item[data-section="exhibition"]').forEach(a =>
  a.addEventListener('click', () => loadSaved()));
loadSaved();

// Deep links from n8n:
//   halls board: http://127.0.0.1:5000/?run=<id>&museum=1#exhibition
//   3D visit:    http://127.0.0.1:5000/virtual?run=<id>
(async () => {
  const params = new URLSearchParams(location.search);
  const runId = params.get('run');
  const openMuseum = params.get('museum') === '1' || params.get('museum') === 'true';
  if (!runId) return;
  const nav = document.querySelector('.nav-item[data-section="exhibition"]');
  if (nav) nav.click();
  else location.hash = 'exhibition';
  await loadRun(runId, { openMuseum });
})();

});
