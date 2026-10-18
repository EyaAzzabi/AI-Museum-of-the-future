document.addEventListener('DOMContentLoaded', () => {
  const exhibitGrid = document.getElementById('exhibitGrid');
  const exhibitCount = document.getElementById('exhibitCount');
  const collectionGrid = document.getElementById('collectionGrid');
  const collectionCount = document.getElementById('collectionCount');
  const collectionSearch = document.getElementById('collectionSearch');
  const collectionFilter = document.getElementById('collectionFilter');
  const collectionMore = document.getElementById('collectionMore');
  const storyChoices = document.getElementById('storyChoices');
  const historianResult = document.getElementById('historianResult');
  const exhibitionForm = document.getElementById('exhibitionForm');
  const exhibitionQuery = document.getElementById('exhibitionQuery');
  const createExhibitionButton = document.getElementById('createExhibition');
  const exhibitionOutput = document.getElementById('exhibitionOutput');
  const museumScene = document.getElementById('museumScene');
  const museumWorld = document.getElementById('museumWorld');
  const scenePosition = document.getElementById('scenePosition');
  const sceneCurrentName = document.getElementById('sceneCurrentName');
  const visitAgentRoom = document.getElementById('visitAgentRoom');
  const guideNumber = document.getElementById('guideNumber');
  const guideIcon = document.getElementById('guideIcon');
  const guideAgent = document.getElementById('guideAgent');
  const guideTitle = document.getElementById('guideTitle');
  const guideDescription = document.getElementById('guideDescription');
  const guideFocus = document.getElementById('guideFocus');
  const guideTeam = document.getElementById('guideTeam');
  const recordDialog = document.getElementById('recordDialog');
  const dialogContent = document.getElementById('dialogContent');
  const menuToggle = document.getElementById('menuToggle');
  const mainNav = document.getElementById('mainNav');
  const chatToggle = document.getElementById('chatToggle');
  const chatWidget = document.getElementById('chatWidget');
  const chatClose = document.getElementById('chatClose');
  const chatMessages = document.getElementById('chatMessages');
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');

  const pageSize = 9;
  const museumRooms = [
    { agent: 'historian', icon: '◷', label: 'Historien', title: 'Le temps long', description: 'Relie les événements d’aujourd’hui aux transformations qui façonneront la mémoire de demain.', focus: 'Événements, mémoire collective et perspectives à cent ans.' },
    { agent: 'sociologist', icon: '◎', label: 'Sociologue', title: 'Vies en mouvement', description: 'Observe comment les sociétés changent, s’organisent et répondent aux défis de leur temps.', focus: 'Identités, modes de vie et transformations sociales.' },
    { agent: 'technology', icon: '⌘', label: 'Technologies', title: 'Le monde de demain', description: 'Explore les innovations qui transforment déjà notre façon de vivre et d’imaginer le futur.', focus: 'Sciences, inventions et effets des technologies.' },
    { agent: 'culture_art', icon: '✳', label: 'Culture & arts', title: 'L’esprit d’une époque', description: 'Met en lumière les œuvres, les symboles et les récits qui donnent forme à notre culture.', focus: 'Arts, médias, expressions et héritages culturels.' },
    { agent: 'visual', icon: '◉', label: 'Agent visuel', title: 'Voir notre monde', description: 'Étudie les images et les objets visuels qui rendent notre époque tangible aux visiteurs.', focus: 'Images, esthétique et culture visuelle.' },
    { agent: 'reviewer', icon: '⇄', label: 'Relecture croisée', title: 'Les idées en dialogue', description: 'Compare les interprétations des spécialistes, leurs accords et leurs désaccords.', focus: 'Points communs, tensions et qualité des preuves.' },
    { agent: 'curator', icon: '⌂', label: 'Conservateur', title: 'Composer le parcours', description: 'Relie les cinq regards en un récit cohérent et transforme les archives en exposition.', focus: 'Curation de récits accessibles et reliés aux sources.' },
    { agent: 'fact_checker', icon: '✓', label: 'Vérificateur', title: 'Vérifier les traces', description: 'Contrôle que les récits du musée restent fidèles aux documents qui les étayent.', focus: 'Vérification des faits et des citations des archives.' },
  ];
  let records = [];
  let filteredRecords = [];
  let presets = [];
  let selectedPreset = null;
  let currentRoom = 0;
  let showAllRecords = false;
  let chatHistory = [];

  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  async function requestJson(url, options) {
    const response = await fetch(url, options);
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError('Le musée ne peut pas lire la réponse du serveur.', response.status);
    }
    if (!response.ok) {
      throw new ApiError(payload.error || 'Une erreur est survenue lors de la requête.', response.status);
    }
    return payload;
  }

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, character => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[character]);
  }

  function safeExternalUrl(value) {
    if (!value) return '';
    try {
      const url = new URL(value, window.location.origin);
      return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch {
      return '';
    }
  }

  function categoryLabel(category) {
    const labels = {
      culture: 'Culture & arts',
      'culture & art': 'Culture & arts',
      image: 'Image',
      news: 'Actualités',
      science: 'Sciences',
      technology: 'Technologie',
      history: 'Histoire',
      politics: 'Société',
      society: 'Société',
    };
    return labels[String(category || '').toLowerCase()] || category || 'Archive';
  }

  function renderMuseumRooms() {
    museumWorld.innerHTML = museumRooms.map((room, index) => `
      <button class="room-card${index === currentRoom ? ' is-current' : ''}" type="button"
        style="--room-index:${index}" data-room="${index}" data-agent="${room.agent}" data-status="idle"
        aria-label="Visiter la salle ${escapeHtml(room.title)}, ${escapeHtml(room.label)}"
        aria-pressed="${index === currentRoom}">
        <span class="room-index">SALLE ${String(index + 1).padStart(2, '0')}</span>
        <span class="room-art" aria-hidden="true"></span>
        <span class="room-title">${escapeHtml(room.title)}</span>
        <span class="room-agent">${escapeHtml(room.label)}</span>
        <span class="room-open" aria-hidden="true">${escapeHtml(room.icon)}</span>
      </button>
    `).join('');

    museumWorld.querySelectorAll('[data-room]').forEach(button => {
      button.addEventListener('click', () => {
        if (suppressRoomClick) {
          suppressRoomClick = false;
          return;
        }
        setCurrentRoom(Number(button.dataset.room));
      });
    });
    setCurrentRoom(currentRoom);
  }

  function setCurrentRoom(index) {
    if (!Number.isInteger(index)) return;
    currentRoom = (index + museumRooms.length) % museumRooms.length;
    const room = museumRooms[currentRoom];
    museumWorld.style.setProperty('--world-rotation', `${-currentRoom * 45}deg`);
    museumWorld.querySelectorAll('[data-room]').forEach(button => {
      const isCurrent = Number(button.dataset.room) === currentRoom;
      button.classList.toggle('is-current', isCurrent);
      button.setAttribute('aria-pressed', String(isCurrent));
    });

    scenePosition.innerHTML = `${String(currentRoom + 1).padStart(2, '0')} <i>/</i> ${String(museumRooms.length).padStart(2, '0')}`;
    sceneCurrentName.textContent = room.title;
    guideNumber.textContent = String(currentRoom + 1).padStart(2, '0');
    guideIcon.textContent = room.icon;
    guideAgent.textContent = room.label.toLocaleUpperCase('fr');
    guideTitle.textContent = room.title;
    guideDescription.textContent = room.description;
    guideFocus.textContent = room.focus;
    guideTeam.dataset.status = 'idle';
    guideTeam.innerHTML = '<span class="guide-team-dot"></span> PRÊT À REJOINDRE LES AUTRES AGENTS';
  }

  function setMuseumAgentStatuses(agents, fallbackStatus) {
    const agentMap = new Map((agents || []).map(agent => [agent.name, agent]));
    museumWorld.querySelectorAll('[data-room]').forEach(button => {
      const room = museumRooms[Number(button.dataset.room)];
      const agent = agentMap.get(room.agent);
      button.dataset.status = agent?.status || fallbackStatus || 'unavailable';
      if (agent) {
        button.setAttribute('aria-label', `Salle ${room.title}, ${room.label} : ${stageState(agent.status)}`);
      }
    });

    const active = agentMap.get(museumRooms[currentRoom].agent);
    if (active) {
      guideTeam.dataset.status = active.status;
      guideTeam.innerHTML = `<span class="guide-team-dot"></span> ${escapeHtml(stageState(active.status).toLocaleUpperCase('fr'))}`;
    } else if (fallbackStatus) {
      guideTeam.dataset.status = fallbackStatus;
      guideTeam.innerHTML = `<span class="guide-team-dot"></span> ${escapeHtml(stageState(fallbackStatus).toLocaleUpperCase('fr'))}`;
    }
  }

  function moveToRoom(direction) {
    setCurrentRoom(currentRoom + direction);
  }

  let dragStartX = null;
  let suppressRoomClick = false;
  museumScene.addEventListener('pointerdown', event => {
    if (event.target.closest('.scene-controls')) return;
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    dragStartX = event.clientX;
  });
  museumScene.addEventListener('pointerup', event => {
    if (dragStartX === null) return;
    const delta = event.clientX - dragStartX;
    dragStartX = null;
    if (Math.abs(delta) > 40) {
      suppressRoomClick = true;
      setTimeout(() => { suppressRoomClick = false; }, 120);
      moveToRoom(delta < 0 ? 1 : -1);
    }
  });
  museumScene.addEventListener('pointercancel', () => { dragStartX = null; });
  museumScene.addEventListener('keydown', event => {
    if (event.target.closest('.scene-controls')) return;
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveToRoom(1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveToRoom(-1);
    }
  });
  document.getElementById('roomPrevious').addEventListener('click', () => moveToRoom(-1));
  document.getElementById('roomNext').addEventListener('click', () => moveToRoom(1));
  visitAgentRoom.addEventListener('click', () => {
    if (!selectedPreset && presets.length) choosePreset(0);
    if (!selectedPreset) {
      exhibitionOutput.innerHTML = '<p class="historian-error" role="alert">Aucun récit documentaire n’est disponible. Importez des archives avant de lancer les agents.</p>';
      exhibitionOutput.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    exhibitionQuery.value = selectedPreset.title;
    exhibitionForm.requestSubmit();
  });

  function addChatMessage(text, role = 'assistant') {
    const message = document.createElement('div');
    message.className = `chat-message ${role}`;
    message.textContent = text;
    chatMessages.appendChild(message);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function askMuseumAssistant(question) {
    chatInput.disabled = true;
    const submitButton = chatForm.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;

    const thinking = document.createElement('div');
    thinking.className = 'chat-message assistant';
    thinking.textContent = 'L’assistant du musée réfléchit…';
    chatMessages.appendChild(thinking);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const result = await requestJson('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: chatHistory.slice(-6) }),
      });
      thinking.textContent = result.answer;
      chatHistory.push({ role: 'user', content: question }, { role: 'assistant', content: result.answer });
    } catch (error) {
      thinking.classList.add('error');
      thinking.textContent = error.status === 503
        ? 'L’assistant IA n’est pas disponible pour le moment (clé LLM manquante).'
        : error.message || 'L’assistant n’a pas pu répondre. Réessayez dans un instant.';
    } finally {
      chatMessages.scrollTop = chatMessages.scrollHeight;
      chatInput.disabled = false;
      if (submitButton) submitButton.disabled = false;
      chatInput.focus();
    }
  }

  function renderExhibitions() {
    if (!presets.length) {
      exhibitGrid.innerHTML = '<div class="loading-card">Les parcours sont momentanément indisponibles.</div>';
      return;
    }

    exhibitGrid.innerHTML = presets.map((preset, index) => {
      const excerpt = preset.chunks?.[0]?.content || 'Un récit à explorer à travers les traces laissées par notre époque.';
      const excerpts = excerpt.length > 145 ? `${excerpt.slice(0, 142).trimEnd()}…` : excerpt;
      return `
        <article class="exhibit-card">
          <span class="exhibit-tag">${escapeHtml(preset.category || 'Récit d’archive')}</span>
          <h3>${escapeHtml(preset.title)}</h3>
          <p>${escapeHtml(excerpts)}</p>
          <button class="exhibit-link" type="button" data-preset="${index}">
            Visiter ce récit <span aria-hidden="true">↗</span>
          </button>
        </article>`;
    }).join('');
    exhibitCount.textContent = `01 — ${String(presets.length).padStart(2, '0')}`;

    exhibitGrid.querySelectorAll('[data-preset]').forEach(button => {
      button.addEventListener('click', () => {
        choosePreset(Number(button.dataset.preset));
        document.getElementById('historien').scrollIntoView({ behavior: 'smooth' });
      });
    });
  }

  function renderStoryChoices() {
    if (!presets.length) {
      storyChoices.innerHTML = '<p class="muted-message">Aucun récit n’est disponible pour le moment.</p>';
      return;
    }

    storyChoices.innerHTML = presets.map((preset, index) => `
      <button class="story-choice" type="button" data-preset="${index}" aria-pressed="false">
        ${escapeHtml(preset.title)}
      </button>
    `).join('');

    storyChoices.querySelectorAll('[data-preset]').forEach(button => {
      button.addEventListener('click', () => choosePreset(Number(button.dataset.preset)));
    });
  }

  function choosePreset(index) {
    selectedPreset = presets[index];
    if (!selectedPreset) return;
    if (!exhibitionQuery.value.trim() || presets.some(preset => preset.title === exhibitionQuery.value.trim())) {
      exhibitionQuery.value = selectedPreset.title;
    }

    storyChoices.querySelectorAll('[data-preset]').forEach(button => {
      button.setAttribute('aria-pressed', String(Number(button.dataset.preset) === index));
    });

    const sources = (selectedPreset.chunks || []).map((chunk, chunkIndex) => `
      <blockquote class="story-evidence">
        “${escapeHtml(chunk.content)}”
        <span class="evidence-source">${escapeHtml(chunk.metadata?.source || 'Archive publique')} · Fragment ${chunkIndex + 1}</span>
      </blockquote>
    `).join('');

    historianResult.innerHTML = `
      <p class="picker-label">FRAGMENTS DE CETTE HISTOIRE</p>
      ${sources || '<p class="result-hint">Aucun fragment documentaire n’est associé à ce récit.</p>'}
      <div class="historian-action">
        <button class="button button-gold" id="analyzeStory" type="button" ${sources ? '' : 'disabled'}>
          Demander le regard de 2126 <span aria-hidden="true">↗</span>
        </button>
      </div>
    `;
    document.getElementById('analyzeStory')?.addEventListener('click', analyzeStory);
  }

  function stageLabel(name) {
    const labels = {
      historian: 'Historien',
      sociologist: 'Sociologue',
      technology: 'Spécialiste des technologies',
      culture_art: 'Culture & arts',
      visual: 'Agent visuel',
      reviewer: 'Relecture croisée',
      curator: 'Conservateur',
      fact_checker: 'Vérification des faits',
    };
    return labels[name] || name;
  }

  function stageState(status) {
    const states = {
      running: 'Travail en cours',
      complete: 'Analyse terminée',
      no_evidence: 'Aucune conclusion sourcée',
      unavailable: 'Étape non exécutée',
      error: 'Échec de l’analyse',
    };
    return states[status] || status;
  }

  function renderExhibition(data) {
    const exhibition = data.exhibition || {};
    const team = data.agents || [];
    const findings = team.filter(agent =>
      ['historian', 'sociologist', 'technology', 'culture_art', 'visual'].includes(agent.name)
      && agent.status === 'complete'
    );
    const sections = (exhibition.sections || []).map((section, index) => `
      <article class="generated-section">
        <span class="generated-number">0${index + 1}</span>
        <div>
          <h4>${escapeHtml(section.title)}</h4>
          <p>${escapeHtml(section.narrative)}</p>
          ${section.artifacts?.length ? `<span class="evidence-source">SOURCES · ${section.artifacts.map(artifact => escapeHtml(typeof artifact === 'string' ? artifact : artifact.id || '')).join(' · ')}</span>` : ''}
        </div>
      </article>
    `).join('');
    const review = exhibition.review || {};
    const reviewItems = [
      ...(review.agreements || []).map(item => item.point),
      ...(review.tensions || []).map(item => item.issue),
    ].filter(Boolean);
    const factChecks = exhibition.fact_check || [];
    exhibitionOutput.innerHTML = `
      <div class="exhibition-result-heading">
        <p class="picker-label">EXPOSITION · ${escapeHtml(data.run_id || '')}</p>
        <h3>${escapeHtml(exhibition.title || 'Exposition du musée')}</h3>
        <p>${escapeHtml(exhibition.concept || '')}</p>
        <span class="evidence-source">${findings.length} regard(s) spécialiste(s) · ${escapeHtml(data.duration_s)} s de recherche</span>
      </div>
      <div class="team-results">
        <p class="picker-label">LES COULISSES DE LA CURATION</p>
        <div class="team-grid">${team.map(agent => `
          <article class="team-member team-${escapeHtml(agent.status)}">
            <span class="team-mark">${agent.status === 'complete' ? '✓' : agent.status === 'no_evidence' ? '—' : '!'}</span>
            <span class="team-name">${escapeHtml(stageLabel(agent.name))}</span>
            <span class="team-status">${escapeHtml(stageState(agent.status))}</span>
            ${agent.perspective ? `<p>${escapeHtml(agent.perspective)}</p>` : ''}
            ${agent.findings?.length ? `<ul>${agent.findings.slice(0, 2).map(finding => `<li>${escapeHtml(finding)}</li>`).join('')}</ul>` : ''}
          </article>
        `).join('')}</div>
      </div>
      <div class="generated-sections">
        <p class="picker-label">PARCOURS DE L’EXPOSITION</p>
        ${sections || '<p class="historian-error">Le conservateur n’a pas pu produire de sections pour cette exposition.</p>'}
      </div>
      ${reviewItems.length ? `<div class="review-notes"><p class="picker-label">ACCORDS & POINTS DE DÉBAT</p><ul>${reviewItems.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>` : ''}
      ${factChecks.length ? `<p class="fact-check-note">${factChecks.filter(item => item.supported).length}/${factChecks.length} récits validés par le vérificateur de faits.</p>` : '<p class="fact-check-note">Le vérificateur de faits n’a pas pu valider les récits de cette exposition.</p>'}
      <p class="builder-note">Les interprétations sont reliées aux archives disponibles. Consultez les sources avant de les reprendre.</p>
    `;
    exhibitionOutput.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function createMultiAgentExhibition(event) {
    event.preventDefault();
    const query = exhibitionQuery.value.trim();
    if (!query) {
      exhibitionQuery.focus();
      return;
    }

    createExhibitionButton.disabled = true;
    createExhibitionButton.setAttribute('aria-busy', 'true');
    createExhibitionButton.innerHTML = '<span class="loading-mark"></span> Les spécialistes travaillent…';
    exhibitionOutput.innerHTML = `
      <div class="pipeline-wait" role="status">
        <span class="loading-mark"></span>
        <div><strong>L’équipe du musée entre en réunion.</strong><p>Les cinq regards analysent les archives, puis les relecteurs vérifient et organisent leurs conclusions. Cette étape peut durer une à deux minutes.</p></div>
      </div>`;
    setMuseumAgentStatuses([], 'running');

    const useSelectedStory = selectedPreset && query === selectedPreset.title;
    try {
      const result = await window.MuseumPipeline.run({
        query,
        chunks: useSelectedStory ? selectedPreset.chunks : [],
        country: 'Tunisia',
        use_rag: !useSelectedStory,
      }, () => {
        const status = exhibitionOutput.querySelector('.pipeline-wait p');
        if (status) status.textContent = 'Une exposition est déjà en cours. Je la suis et afficherai ses résultats dès qu’elle sera terminée.';
      });
      renderExhibition(result);
      setMuseumAgentStatuses(result.agents, null);
    } catch (error) {
      const message = error.message || 'Le musée n’a pas pu terminer cette exposition. Vérifiez la configuration IA et réessayez.';
      exhibitionOutput.innerHTML = `<p class="historian-error" role="alert">${escapeHtml(message)}</p>`;
      setMuseumAgentStatuses([], error.status === 503 ? 'unavailable' : 'error');
    } finally {
      createExhibitionButton.disabled = false;
      createExhibitionButton.removeAttribute('aria-busy');
      createExhibitionButton.innerHTML = 'Créer une exposition avec l’équipe <span aria-hidden="true">↗</span>';
    }
  }

  async function analyzeStory() {
    const button = document.getElementById('analyzeStory');
    if (!selectedPreset || !button) return;
    button.disabled = true;
    button.textContent = 'L’historien réfléchit…';
    button.setAttribute('aria-busy', 'true');

    try {
      const result = await requestJson('/api/historian/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chunks: selectedPreset.chunks || [] }),
      });
      showHistorianResult(result);
    } catch (error) {
      const message = error.status === 503
        ? 'L’historien IA n’est pas disponible pour le moment. Les archives de ce récit restent consultables ci-dessus.'
        : error.status === 502
          ? 'Le service d’analyse n’a pas pu répondre. Réessayez un peu plus tard.'
          : 'La lecture de ce récit a échoué. Vérifiez votre connexion puis réessayez.';
      const notice = document.createElement('p');
      notice.className = 'historian-error';
      notice.setAttribute('role', 'alert');
      notice.textContent = message;
      historianResult.appendChild(notice);
      button.disabled = false;
      button.textContent = 'Réessayer le regard de 2126';
      button.removeAttribute('aria-busy');
    }
  }

  function showHistorianResult(result) {
    const insight = result.insight || {};
    historianResult.innerHTML = `
      <div class="historian-output">
        <p class="picker-label">UNE LECTURE DEPUIS 2126</p>
        <h3>${escapeHtml(insight.agent || 'L’historien du futur')}</h3>
        <p>${escapeHtml(insight.perspective || '')}</p>
        ${insight.key_findings?.length ? `
          <ul>${insight.key_findings.map(finding => `<li>${escapeHtml(finding)}</li>`).join('')}</ul>
        ` : ''}
        <span class="evidence-source">Lecture générée à partir de ${selectedPreset.chunks?.length || 0} fragments sélectionnés</span>
      </div>
      <button class="exhibit-link" id="showStoryAgain" type="button">Revoir les archives <span aria-hidden="true">↑</span></button>
    `;
    document.getElementById('showStoryAgain').addEventListener('click', () => choosePreset(presets.indexOf(selectedPreset)));
  }

  async function loadExhibitions() {
    try {
      const data = await requestJson('/api/historian/presets');
      presets = Array.isArray(data.presets) ? data.presets : [];
      renderExhibitions();
      renderStoryChoices();
      if (!records.length) renderCollection();
    } catch (error) {
      exhibitGrid.innerHTML = '<div class="loading-card load-error" role="alert">Impossible de charger les expositions. Actualisez la page pour réessayer.</div>';
      storyChoices.innerHTML = '<p class="muted-message" role="alert">Les récits sont momentanément indisponibles.</p>';
    }
  }

  function renderCollection() {
    if (!records.length && presets.length) {
      const query = collectionSearch.value.trim().toLocaleLowerCase('fr');
      const category = collectionFilter.value;
      const storyCategories = ['history', 'society', 'culture'];
      const visibleStories = presets.map((preset, index) => ({ preset, index })).filter(({ preset, index }) => {
        const storyCategory = storyCategories[index % storyCategories.length];
        if (category && storyCategory !== category && !(category === 'history' && storyCategory === 'society')) return false;
        const searchable = [preset.title, preset.category, ...(preset.chunks || []).map(chunk => chunk.content)]
          .join(' ').toLocaleLowerCase('fr');
        return searchable.includes(query);
      });
      collectionCount.textContent = `${visibleStories.length} récit${visibleStories.length === 1 ? '' : 's'} à explorer`;
      if (!visibleStories.length) {
        collectionGrid.innerHTML = '<div class="collection-empty"><strong>Aucun récit trouvé.</strong><p>Essayez un autre mot ou choisissez un thème différent.</p></div>';
        collectionMore.replaceChildren();
        return;
      }
      collectionGrid.innerHTML = visibleStories.map(({ preset, index }) => {
        const excerpt = preset.chunks?.[0]?.content || 'Un récit à explorer à travers les traces laissées par notre époque.';
        const themes = ['politics', 'migration', 'culture'];
        return `
          <article class="record-card featured-story">
            <div class="record-image story-cover story-cover-${themes[index % themes.length]}" aria-hidden="true">
              <span>${escapeHtml(categoryLabel(preset.category))}</span>
              <strong>0${index + 1}</strong>
            </div>
            <div class="record-body">
              <div class="record-meta"><span>Récit documentaire</span><span>${escapeHtml(categoryLabel(preset.category))}</span></div>
              <h3>${escapeHtml(preset.title)}</h3>
              <p class="story-excerpt">${escapeHtml(excerpt.slice(0, 150))}${excerpt.length > 150 ? '…' : ''}</p>
              <button class="record-open" type="button" data-story="${index}">Ouvrir le récit <span aria-hidden="true">↗</span></button>
            </div>
          </article>`;
      }).join('');
      collectionGrid.querySelectorAll('[data-story]').forEach(button => {
        button.addEventListener('click', () => {
          choosePreset(Number(button.dataset.story));
          document.getElementById('historien').scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
      });
      collectionMore.replaceChildren();
      return;
    }

    collectionCount.textContent = `${filteredRecords.length.toLocaleString('fr-FR')} archive${filteredRecords.length === 1 ? '' : 's'}`;
    if (!filteredRecords.length) {
      const hasFilters = collectionSearch.value.trim() || collectionFilter.value;
      collectionGrid.innerHTML = hasFilters
        ? '<div class="collection-empty"><strong>Aucune archive trouvée.</strong><p>Essayez un autre mot ou choisissez un thème différent.</p></div>'
        : '<div class="collection-empty"><strong>Les archives se rassemblent.</strong><p>La collection publique se remplit au fil des collectes. En attendant, découvrez les récits sélectionnés dans nos expositions.</p><a class="text-link dark-link" href="#expositions">Explorer les expositions <span aria-hidden="true">↗</span></a></div>';
      collectionMore.replaceChildren();
      return;
    }

    const visibleRecords = showAllRecords ? filteredRecords : filteredRecords.slice(0, pageSize);
    collectionGrid.innerHTML = visibleRecords.map((record, index) => {
      const imageUrl = safeExternalUrl(record.image_url);
      const source = escapeHtml(record.source || 'Archive');
      const date = escapeHtml(record.date || categoryLabel(record.category));
      const image = imageUrl
        ? `<img src="${escapeHtml(imageUrl)}" alt="" loading="lazy" onerror="this.remove()">`
        : '<span class="record-image-placeholder" aria-hidden="true">M</span>';
      return `
        <article class="record-card">
          <div class="record-image">${image}</div>
          <div class="record-body">
            <div class="record-meta"><span>${source}</span><span>${date}</span></div>
            <h3>${escapeHtml(record.title || 'Archive sans titre')}</h3>
            <button class="record-open" type="button" data-record="${index}">Ouvrir l’archive <span aria-hidden="true">↗</span></button>
          </div>
        </article>`;
    }).join('');

    collectionGrid.querySelectorAll('[data-record]').forEach(button => {
      button.addEventListener('click', () => openRecord(visibleRecords[Number(button.dataset.record)]));
    });

    collectionMore.innerHTML = filteredRecords.length > pageSize
      ? `<button class="button-outline" id="toggleRecords" type="button">${showAllRecords ? 'Réduire la collection' : `Voir les ${filteredRecords.length - pageSize} autres archives`}</button>`
      : '';
    document.getElementById('toggleRecords')?.addEventListener('click', () => {
      showAllRecords = !showAllRecords;
      renderCollection();
    });
  }

  function applyCollectionFilters() {
    const query = collectionSearch.value.trim().toLocaleLowerCase('fr');
    const category = collectionFilter.value;
    filteredRecords = records.filter(record => {
      const recordCategory = String(record.category || '').toLocaleLowerCase('fr');
      if (category && recordCategory !== category && !(category === 'history' && ['politics', 'society'].includes(recordCategory))) return false;
      if (!query) return true;
      const searchable = [
        record.title,
        record.text,
        record.source,
        record.category,
        ...(Array.isArray(record.tags) ? record.tags : []),
      ].join(' ').toLocaleLowerCase('fr');
      return searchable.includes(query);
    });
    showAllRecords = false;
    renderCollection();
  }

  async function loadCollection() {
    try {
      const data = await requestJson('/api/data');
      records = Array.isArray(data.records) ? data.records : [];
      applyCollectionFilters();
    } catch {
      collectionCount.textContent = 'Archives indisponibles';
      collectionGrid.innerHTML = '<div class="collection-empty load-error" role="alert"><strong>La collection est momentanément inaccessible.</strong><p>Actualisez la page pour réessayer.</p></div>';
    }
  }

  function openRecord(record) {
    if (!record) return;
    const imageUrl = safeExternalUrl(record.image_url);
    const sourceUrl = safeExternalUrl(record.url);
    const tags = (Array.isArray(record.tags) ? record.tags : []).filter(Boolean);
    dialogContent.innerHTML = `
      <div class="dialog-inner">
        ${imageUrl ? `<img src="${escapeHtml(imageUrl)}" alt="">` : ''}
        <span class="dialog-meta">${escapeHtml(categoryLabel(record.category))} · ${escapeHtml(record.date || 'Date inconnue')}</span>
        <h2 id="dialogTitle">${escapeHtml(record.title || 'Archive')}</h2>
        <p>${escapeHtml(record.text || 'Aucun texte descriptif n’est disponible pour cette archive.')}</p>
        ${tags.length ? `<div class="dialog-tags">${tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}</div>` : ''}
        <p class="dialog-meta">SOURCE · ${escapeHtml(record.source || 'Archive publique')}</p>
        ${sourceUrl ? `<a class="dialog-source" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Consulter la source d’origine ↗</a>` : ''}
      </div>
    `;
    recordDialog.showModal();
  }

  chatToggle.addEventListener('click', () => {
    const isOpen = !chatWidget.hidden;
    chatWidget.hidden = isOpen;
    chatToggle.setAttribute('aria-expanded', String(!isOpen));
    if (!isOpen) {
      chatInput.focus();
    }
  });
  chatClose.addEventListener('click', () => {
    chatWidget.hidden = true;
    chatToggle.setAttribute('aria-expanded', 'false');
  });
  chatForm.addEventListener('submit', event => {
    event.preventDefault();
    const question = chatInput.value.trim();
    if (!question) return;

    addChatMessage(question, 'user');
    chatInput.value = '';
    askMuseumAssistant(question);
  });

  addChatMessage('Bonjour ! Posez une question sur le musée, les expositions ou les thèmes abordés.');

  collectionSearch.addEventListener('input', applyCollectionFilters);
  collectionFilter.addEventListener('change', applyCollectionFilters);
  exhibitionForm.addEventListener('submit', createMultiAgentExhibition);
  recordDialog.addEventListener('click', event => {
    if (event.target === recordDialog) recordDialog.close();
  });

  menuToggle.addEventListener('click', () => {
    const isOpen = menuToggle.getAttribute('aria-expanded') === 'true';
    menuToggle.setAttribute('aria-expanded', String(!isOpen));
    menuToggle.setAttribute('aria-label', isOpen ? 'Ouvrir le menu' : 'Fermer le menu');
    mainNav.classList.toggle('is-open', !isOpen);
    document.body.classList.toggle('menu-open', !isOpen);
  });
  mainNav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      menuToggle.setAttribute('aria-expanded', 'false');
      menuToggle.setAttribute('aria-label', 'Ouvrir le menu');
      mainNav.classList.remove('is-open');
      document.body.classList.remove('menu-open');
    });
  });

  async function restoreExistingExhibition() {
    createExhibitionButton.disabled = true;
    try {
      const result = await window.MuseumPipeline.loadExisting(progress => {
        exhibitionOutput.innerHTML = `
          <div class="pipeline-wait" role="status">
            <span class="loading-mark"></span>
            <div><strong>Une exposition est en cours.</strong><p>Le musée la suit automatiquement et affichera ses résultats dès qu’ils seront prêts.</p></div>
          </div>`;
        setMuseumAgentStatuses([], 'running');
      });
      if (result) {
        renderExhibition(result);
        setMuseumAgentStatuses(result.agents, null);
      }
    } catch (error) {
      exhibitionOutput.innerHTML = `<p class="historian-error" role="alert">${escapeHtml(error.message || 'Impossible de charger les résultats du musée.')}</p>`;
    } finally {
      createExhibitionButton.disabled = false;
    }
  }

  loadExhibitions();
  loadCollection();
  renderMuseumRooms();
  restoreExistingExhibition();
});
