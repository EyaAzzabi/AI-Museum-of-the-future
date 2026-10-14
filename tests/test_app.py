from app import create_app


def test_dashboard_serves_assets_and_favicon():
    client = create_app().test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b'/web/styles.css' in response.data
    assert b'/web/app.js' in response.data
    assert client.get('/web/styles.css').status_code == 200
    assert client.get('/web/app.js').status_code == 200
    assert client.get('/favicon.ico').status_code == 204


def test_validation_api_returns_steps():
    client = create_app().test_client()
    response = client.get('/api/validate')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'status' in payload
    assert 'steps' in payload
    assert isinstance(payload['steps'], list)
    assert len(payload['steps']) >= 6
    agents_step = next(step for step in payload['steps'] if step['name'] == 'Agents implemented and communicating')
    assert agents_step['ok'] is True


def test_historian_presets_api():
    client = create_app().test_client()
    response = client.get('/api/historian/presets')
    assert response.status_code == 200
    payload = response.get_json()
    assert 'presets' in payload
    assert len(payload['presets']) >= 3
    assert payload['presets'][0]['chunks'][0]['chunk_id']


def test_historian_analyze_endpoint_without_key_reports_error(monkeypatch):
    # No canned "simulation": without a key the endpoint says so instead of inventing findings
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = create_app().test_client()

    response = client.post('/api/historian/analyze', json={"chunks": [{"chunk_id": "test-c1", "content": "x"}]})
    assert response.status_code == 503
    assert response.get_json()['ok'] is False

    bad_response = client.post('/api/historian/analyze', json={"chunks": []})
    assert bad_response.status_code == 400


def test_historian_analyze_endpoint_live_path(monkeypatch):
    import json
    from types import SimpleNamespace

    import app as app_module

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    content = json.dumps({
        "perspective": "Vue depuis 2126.",
        "key_findings": ["Événement Clé : test"],
        "selected_artifacts": ["test-c1", "invented-id"],
    })
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    )))
    monkeypatch.setattr(app_module, "build_llm_client", lambda: fake_client)
    client = app_module.create_app().test_client()

    response = client.post('/api/historian/analyze', json={"chunks": [{"chunk_id": "test-c1", "content": "x"}]})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True and payload['mode'] == 'live'
    assert payload['insight']['selected_artifacts'] == ["test-c1"]


def test_historian_presets_are_about_tunisia():
    presets = create_app().test_client().get('/api/historian/presets').get_json()['presets']
    for preset in presets:
        for chunk in preset['chunks']:
            assert chunk['metadata']['country'] == 'Tunisia'


def test_embed_endpoint_returns_gemini_shaped_384_dim_vector(monkeypatch):
    from types import SimpleNamespace

    import rag.vector_store.local_embeddings as local_embeddings

    fake = SimpleNamespace(embeddings=SimpleNamespace(
        create=lambda input, **_: SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 384)])
    ))
    monkeypatch.setattr(local_embeddings, "build_embedding_client", lambda: fake)
    client = create_app().test_client()

    response = client.post('/api/embed', json={"text": "Tunisie 2022"})
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload['embedding']['values']) == 384
    assert payload['dim'] == 384

    assert client.post('/api/embed', json={"text": "  "}).status_code == 400
