(() => {
  const specialistNames = ['historian', 'sociologist', 'technology', 'culture_art', 'visual'];
  const wait = milliseconds => new Promise(resolve => window.setTimeout(resolve, milliseconds));

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      throw new Error('Le serveur a renvoyé une réponse illisible.');
    }
  }

  function agentStatus(status) {
    return ({ ok: 'complete', abstained: 'no_evidence', error: 'error' })[status] || 'unavailable';
  }

  function hasSavedAgentEvidence(body) {
    return (body.artifacts || []).length > 0
      || Object.values(body.insights || {}).some(insight => (insight.selected_artifacts || []).length > 0);
  }

  function toFrontendResult(body) {
    const insights = body.insights || {};
    const agents = specialistNames.map(name => {
      const insight = insights[name] || {};
      return {
        name,
        status: agentStatus(insight.status),
        perspective: insight.perspective || '',
        findings: insight.key_findings || [],
        selected_artifacts: insight.selected_artifacts || [],
      };
    });
    const review = body.review || {};
    const hasReview = ['agreements', 'tensions', 'weak_findings']
      .some(key => Array.isArray(review[key]) && review[key].length > 0);
    agents.push({ name: 'reviewer', status: hasReview ? 'complete' : 'unavailable' });

    const exhibition = body.exhibition;
    agents.push({
      name: 'curator',
      status: exhibition ? 'complete' : 'unavailable',
      perspective: exhibition?.concept || '',
      findings: [],
    });
    const factChecks = (exhibition?.sections || [])
      .map(section => section.fact_check)
      .filter(Boolean);
    agents.push({ name: 'fact_checker', status: factChecks.length ? 'complete' : 'unavailable' });

    return {
      run_id: body.run_id,
      query: body.config?.query || exhibition?.title || '',
      duration_s: Number(body.timings?.total) || 0,
      artifacts: body.artifacts || [],
      error: body.error || '',
      partial: body.status === 'failed' || !exhibition,
      agents,
      exhibition: exhibition ? {
        ...exhibition,
        review,
        fact_check: factChecks,
      } : null,
    };
  }

  async function followRun(runId, statusPath, onProgress) {
    const statusUrl = new URL(statusPath || `/api/exhibition/${encodeURIComponent(runId)}`, window.location.origin);
    if (statusUrl.origin !== window.location.origin) {
      throw new Error('Le serveur a renvoyé une adresse de suivi invalide.');
    }
    const deadline = Date.now() + 16 * 60 * 1000;
    while (Date.now() < deadline) {
      await wait(1500);
      const statusResponse = await fetch(statusUrl.pathname);
      const body = await readJson(statusResponse);
      if (!statusResponse.ok) {
        throw new Error(body.error || `Impossible de suivre l’analyse (HTTP ${statusResponse.status}).`);
      }
      if (body.status === 'running') {
        onProgress(body);
        continue;
      }
      if (body.status !== 'done' || !body.exhibition) {
        if (body.status === 'failed' && hasSavedAgentEvidence(body)) return toFrontendResult(body);
        throw new Error(body.error || 'Le pipeline n’a pas pu terminer cette exposition.');
      }
      return toFrontendResult(body);
    }
    throw new Error('L’analyse dépasse le délai d’attente du navigateur. Consultez le tableau de bord pour vérifier son état.');
  }

  async function run(payload, onProgress = () => {}) {
    const startResponse = await fetch('/api/exhibition', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await readJson(startResponse);
    if (startResponse.status === 409 && body.run_id && body.status_url) {
      onProgress({ status: 'running', conflict: true });
      return followRun(body.run_id, body.status_url, onProgress);
    }
    if (!startResponse.ok && startResponse.status !== 202) {
      const error = new Error(body.error || `L’analyse a échoué (HTTP ${startResponse.status}).`);
      error.status = startResponse.status;
      throw error;
    }
    if (body.status === 'running') {
      return followRun(body.run_id, body.status_url, onProgress);
    }
    if (body.status === 'failed' || !body.exhibition) {
      throw new Error(body.error || 'Le serveur n’a pas renvoyé de résultat pour cette exposition.');
    }
    return toFrontendResult(body);
  }

  async function loadRun(runId, onProgress = () => {}) {
    if (!runId) return null;
    const statusResponse = await fetch(`/api/exhibition/${encodeURIComponent(runId)}`);
    const body = await readJson(statusResponse);
    if (!statusResponse.ok) {
      throw new Error(body.error || `Impossible de charger le run ${runId} (HTTP ${statusResponse.status}).`);
    }
    if (body.status === 'running') {
      onProgress(body);
      return followRun(runId, `/api/exhibition/${encodeURIComponent(runId)}`, onProgress);
    }
    if (body.status === 'failed' && hasSavedAgentEvidence(body)) return toFrontendResult(body);
    if (body.status !== 'done' || !body.exhibition) {
      throw new Error(body.error || 'Ce run n’a pas encore d’exposition complète.');
    }
    return toFrontendResult(body);
  }

  async function loadExisting(onProgress = () => {}) {
    const params = new URLSearchParams(window.location.search);
    const requestedRun = params.get('run');
    if (requestedRun) {
      return loadRun(requestedRun, onProgress);
    }

    const listResponse = await fetch('/api/exhibitions');
    const listing = await readJson(listResponse);
    if (!listResponse.ok) {
      throw new Error(listing.error || `Impossible de charger les expositions (HTTP ${listResponse.status}).`);
    }
    if (listing.running) {
      onProgress({ status: 'running', resumed: true });
      return followRun(
        listing.running,
        `/api/exhibition/${encodeURIComponent(listing.running)}`,
        onProgress,
      );
    }

    const latestResponse = await fetch('/api/exhibition/latest');
    if (latestResponse.ok) {
      const latest = await readJson(latestResponse);
      if (latest.status === 'done' && latest.exhibition) return toFrontendResult(latest);
    } else if (latestResponse.status !== 404) {
      const latest = await readJson(latestResponse);
      throw new Error(latest.error || `Impossible de charger la dernière exposition (HTTP ${latestResponse.status}).`);
    }

    for (const run of (listing.runs || []).filter(item => !item.complete).slice(0, 5)) {
      const partialResponse = await fetch(`/api/exhibition/${encodeURIComponent(run.run_id)}`);
      if (!partialResponse.ok) continue;
      const partial = await readJson(partialResponse);
      if (partial.status === 'failed' && hasSavedAgentEvidence(partial)) return toFrontendResult(partial);
    }
    return null;
  }

  window.MuseumPipeline = { run, loadExisting, loadRun };
})();
