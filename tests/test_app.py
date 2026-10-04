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
