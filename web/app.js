/* ── AI Museum of the Future — Dashboard JS ─────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {

// ── Navigation ──────────────────────────────────────────────────────────────
const navItems    = document.querySelectorAll('.nav-item');
const sections    = document.querySelectorAll('.section');
const pageTitle   = document.getElementById('page-title');

const sectionTitles = {
  overview: 'Vue d\'ensemble',
  pipeline: 'Pipeline S5',
  corpus:   'Corpus',
  data:     'Données',
  agents:   'Agents',
  prompts:  'Prompts V1',
  tests:    'Tests',
};

function activateSection(id) {
  navItems.forEach(n => n.classList.toggle('active', n.dataset.section === id));
  sections.forEach(s => s.classList.toggle('active', s.id === `section-${id}`));
  pageTitle.textContent = sectionTitles[id] || id;
}

navItems.forEach(item => {
  item.addEventListener('click', e => {
    e.preventDefault();
    activateSection(item.dataset.section);
  });
});

// ── Validation ──────────────────────────────────────────────────────────────
const btnValidate   = document.getElementById('btnValidate');
const statusBanner  = document.getElementById('statusBanner');
const statusText    = document.getElementById('statusText');
const pipelineSteps = document.querySelectorAll('.pipeline-step');
const pipelineResultsEl = document.getElementById('pipelineResults');
const crossRefsVal  = document.getElementById('crossRefsVal');

// KPIs
const kpiCorpus  = document.getElementById('kpi-corpus-val');
const kpiChunks  = document.getElementById('kpi-chunks-val');
const kpiAgents  = document.getElementById('kpi-agents-val');
const kpiPrompts = document.getElementById('kpi-prompts-val');

const stepIcons = ['📂', '✂️', '🔍', '🤖', '💬', '🖼️'];

function setBanner(cls, icon, text) {
  statusBanner.className = `status-banner status-${cls}`;
  statusBanner.querySelector('.status-icon').textContent = icon;
  statusText.textContent = text;
}

function resetSteps() {
  pipelineSteps.forEach(s => {
    s.className = 'pipeline-step idle';
    s.querySelector('.step-detail').textContent = '—';
  });
}

async function runValidation() {
  btnValidate.disabled = true;
  btnValidate.innerHTML = '<span class="spinner"></span> Validation en cours…';
  setBanner('loading', '⏳', 'Validation du pipeline en cours…');
  resetSteps();
  pipelineResultsEl.innerHTML = '';

  try {
    const res  = await fetch('/api/validate');
    const data = await res.json();

    // Update banner
    const allOk = data.status === 'ok';
    setBanner(allOk ? 'ok' : 'warning', allOk ? '✅' : '⚠️', data.summary);

    // Update pipeline steps
    data.steps.forEach((step, i) => {
      const el = pipelineSteps[i];
      if (!el) return;
      el.className = `pipeline-step ${step.ok ? 'ok' : 'fail'}`;
      el.querySelector('.step-detail').textContent = step.detail;
    });

    // Update KPIs
    const corpusStep  = data.steps[0];
    const chunkStep   = data.steps[1];
    const agentsStep  = data.steps[3];
    const promptsStep = data.steps[4];

    kpiCorpus.textContent  = corpusStep  ? (corpusStep.detail.match(/\d+/) || ['—'])[0] : '—';
    kpiChunks.textContent  = chunkStep   ? (chunkStep.detail.match(/\d+/)  || ['—'])[0] : '—';
    kpiPrompts.textContent = promptsStep ? (promptsStep.detail.match(/\d+/) || ['—'])[0] : '—';

    if (data.cross_references) {
      kpiAgents.textContent = data.cross_references.length;
      crossRefsVal.textContent = data.cross_references.length
        ? data.cross_references.join(', ')
        : 'Aucune (agents non encore exécutés avec données réelles)';
    } else if (agentsStep) {
      const m = agentsStep.detail.match(/\[([^\]]*)\]/);
      const refs = m ? m[1].split(',').map(s => s.trim()).filter(Boolean) : [];
      kpiAgents.textContent = refs.length;
      crossRefsVal.textContent = refs.length ? refs.join(', ') : 'Aucune';
    }

    // Detailed results (pipeline section)
    pipelineResultsEl.innerHTML = '';
    data.steps.forEach((step, i) => {
      const item = document.createElement('div');
      item.className = `result-item ${step.ok ? 'ok' : 'fail'}`;
      item.innerHTML = `
        <div class="result-icon">${step.ok ? '✅' : '❌'}</div>
        <div class="result-body">
          <div class="result-name">${stepIcons[i] || ''} ${step.name}</div>
          <div class="result-detail">${step.detail}</div>
        </div>
      `;
      pipelineResultsEl.appendChild(item);
    });

    // Corpus files
    populateCorpus(data.corpus_files || []);

    // Prompts
    populatePrompts(data.prompt_files || []);

  } catch (err) {
    setBanner('error', '❌', `Erreur: ${err.message}`);
  } finally {
    btnValidate.disabled = false;
    btnValidate.innerHTML = '<span class="btn-icon">▶</span> Relancer la validation S5';
  }
}

// ── Corpus section ───────────────────────────────────────────────────────────
function populateCorpus(files) {
  const el = document.getElementById('corpusFiles');
  if (!files.length) {
    el.innerHTML = '<p class="empty-state">Aucun fichier JSON dans data/processed/. Lancez d\'abord fetch_all.py.</p>';
    return;
  }
  el.innerHTML = files.map(f => `
    <div class="corpus-file-item">
      <span class="corpus-file-icon">📄</span>
      <span class="corpus-file-name">${f.name}</span>
      <span class="corpus-file-meta">${f.size_kb} KB · ${f.records} enregistrement(s)</span>
    </div>
  `).join('');
}

// ── Prompts section ──────────────────────────────────────────────────────────
const promptIcons = {
  'system.md':     '⚙️',
  'historian.md':  '📜',
  'sociologist.md':'👥',
  'technology.md': '⚙️',
  'culture_art.md':'🎨',
  'visual.md':     '🖼️',
  'curator.md':    '🏛️',
};

function populatePrompts(files) {
  const el = document.getElementById('promptsList');
  const allFiles = [
    'system.md', 'historian.md', 'sociologist.md',
    'technology.md', 'culture_art.md', 'visual.md', 'curator.md',
  ];
  el.innerHTML = allFiles.map(name => {
    const info   = files.find(f => f.name === name);
    const found  = !!info;
    return `
      <div class="prompt-card ${found ? 'found' : 'missing'}">
        <div class="prompt-icon">${promptIcons[name] || '💬'}</div>
        <div class="prompt-name">${name}</div>
        <div class="prompt-version">${found ? (info.version || 'v1') : '—'}</div>
        <div class="prompt-status">${found ? '✓ Présent' : '✗ Manquant'}</div>
      </div>
    `;
  }).join('');
}

// ── Init ─────────────────────────────────────────────────────────────────────
btnValidate.addEventListener('click', runValidation);

// Seed prompts section with file list (static — always known)
populatePrompts([]);

// ── Data explorer ─────────────────────────────────────────────────────────────
let allRecords   = [];
let filteredRecs = [];
let currentPage  = 1;
const PAGE_SIZE  = 20;

const dataSearch         = document.getElementById('dataSearch');
const dataFilterSource   = document.getElementById('dataFilterSource');
const dataFilterCategory = document.getElementById('dataFilterCategory');
const dataCountEl        = document.getElementById('dataCount');
const dataTableBody      = document.getElementById('dataTableBody');
const dataPrev           = document.getElementById('dataPrev');
const dataNext           = document.getElementById('dataNext');
const dataPageEl         = document.getElementById('dataPage');
const dataModal          = document.getElementById('dataModal');
const modalBackdrop      = document.getElementById('modalBackdrop');
const modalClose         = document.getElementById('modalClose');
const modalTitle         = document.getElementById('modalTitle');
const modalBody          = document.getElementById('modalBody');

const sourceBadgeClass = {
  arxiv:     'source-arxiv',
  wikimedia: 'source-wikimedia',
  gdelt:     'source-gdelt',
  wikipedia: 'source-wikipedia',
  wikidata:  'source-wikidata',
};

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderTable() {
  const start = (currentPage - 1) * PAGE_SIZE;
  const page  = filteredRecs.slice(start, start + PAGE_SIZE);
  const total = filteredRecs.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  dataCountEl.textContent = `${total.toLocaleString()} enregistrement(s)`;
  dataPageEl.textContent  = `Page ${currentPage} / ${totalPages}`;
  dataPrev.disabled = currentPage <= 1;
  dataNext.disabled = currentPage >= totalPages;

  if (!page.length) {
    dataTableBody.innerHTML = '<tr><td colspan="6" class="empty-state">Aucun résultat.</td></tr>';
    return;
  }

  dataTableBody.innerHTML = page.map((r, i) => {
    const cls   = sourceBadgeClass[r.source] || 'source-default';
    const tags  = (r.tags || []).filter(Boolean).slice(0, 3)
      .map(t => `<span class="tag-chip">${escHtml(t)}</span>`).join('');
    return `
      <tr data-idx="${start + i}">
        <td><span class="source-badge ${cls}">${escHtml(r.source)}</span></td>
        <td><span class="cat-badge">${escHtml(r.category)}</span></td>
        <td class="title-cell" title="${escHtml(r.title)}">${escHtml(r.title) || '<em style="color:var(--muted)">sans titre</em>'}</td>
        <td style="white-space:nowrap;color:var(--muted);font-size:.8rem">${escHtml(r.date) || '—'}</td>
        <td><div class="tags-cell">${tags}</div></td>
        <td><button class="btn-detail" data-idx="${start + i}">Voir</button></td>
      </tr>`;
  }).join('');

  // Row click → modal
  dataTableBody.querySelectorAll('tr[data-idx]').forEach(row => {
    row.addEventListener('click', e => {
      if (e.target.classList.contains('btn-detail')) return;
      openModal(filteredRecs[+row.dataset.idx]);
    });
  });
  dataTableBody.querySelectorAll('.btn-detail').forEach(btn => {
    btn.addEventListener('click', () => openModal(filteredRecs[+btn.dataset.idx]));
  });
}

function applyFilters() {
  const q    = (dataSearch.value || '').toLowerCase();
  const src  = dataFilterSource.value;
  const cat  = dataFilterCategory.value;
  filteredRecs = allRecords.filter(r => {
    if (src && r.source   !== src)  return false;
    if (cat && r.category !== cat)  return false;
    if (q) {
      const hay = `${r.title} ${r.text} ${r.source} ${r.category} ${(r.tags||[]).join(' ')}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  currentPage = 1;
  renderTable();
}

async function loadDataRecords() {
  try {
    const res  = await fetch('/api/data');
    const data = await res.json();
    allRecords = data.records || [];
    applyFilters();
  } catch (e) {
    dataTableBody.innerHTML = `<tr><td colspan="6" style="color:var(--red)">Erreur: ${e.message}</td></tr>`;
  }
}

function openModal(rec) {
  modalTitle.textContent = rec.title || 'Enregistrement';
  const cls = sourceBadgeClass[rec.source] || 'source-default';
  const tags = (rec.tags||[]).filter(Boolean).map(t => `<span class="tag-chip">${escHtml(t)}</span>`).join(' ');
  const img  = rec.image_url ? `<img src="${escHtml(rec.image_url)}" style="max-width:100%;border-radius:8px;margin-bottom:12px" onerror="this.style.display='none'">` : '';

  modalBody.innerHTML = `
    ${img}
    <div class="modal-field"><div class="modal-label">ID</div><div class="modal-value" style="font-family:monospace;font-size:.8rem">${escHtml(rec.id)}</div></div>
    <div class="modal-field">
      <div class="modal-label">Source / Catégorie</div>
      <div class="modal-value"><span class="source-badge ${cls}">${escHtml(rec.source)}</span> &nbsp; <span class="cat-badge">${escHtml(rec.category)}</span></div>
    </div>
    ${rec.url ? `<div class="modal-field"><div class="modal-label">URL</div><div class="modal-value"><a href="${escHtml(rec.url)}" target="_blank" rel="noopener">${escHtml(rec.url)}</a></div></div>` : ''}
    ${rec.date ? `<div class="modal-field"><div class="modal-label">Date</div><div class="modal-value">${escHtml(rec.date)}</div></div>` : ''}
    ${rec.lang ? `<div class="modal-field"><div class="modal-label">Langue</div><div class="modal-value">${escHtml(rec.lang)}</div></div>` : ''}
    ${tags ? `<div class="modal-field"><div class="modal-label">Tags</div><div class="modal-value" style="display:flex;gap:4px;flex-wrap:wrap">${tags}</div></div>` : ''}
    ${rec.text ? `<div class="modal-field"><div class="modal-label">Texte</div><div class="modal-text">${escHtml(rec.text)}</div></div>` : ''}
  `;
  dataModal.classList.remove('hidden');
}

function closeModal() { dataModal.classList.add('hidden'); }

modalClose.addEventListener('click', closeModal);
modalBackdrop.addEventListener('click', closeModal);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

dataPrev.addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderTable(); } });
dataNext.addEventListener('click', () => {
  const totalPages = Math.ceil(filteredRecs.length / PAGE_SIZE);
  if (currentPage < totalPages) { currentPage++; renderTable(); }
});

dataSearch.addEventListener('input',         applyFilters);
dataFilterSource.addEventListener('change',  applyFilters);
dataFilterCategory.addEventListener('change',applyFilters);

// Load data when user navigates to the data section
navItems.forEach(item => {
  item.addEventListener('click', () => {
    if (item.dataset.section === 'data' && allRecords.length === 0) {
      loadDataRecords();
    }
  });
});

// Auto-run on load
runValidation();

}); // end DOMContentLoaded
