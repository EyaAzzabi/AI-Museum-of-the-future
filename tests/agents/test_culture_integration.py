from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agents.base_agent import InsightObject
from agents.curator import _is_empty
from agents.culture_art import CultureArtAgent
from rag.vector_store.culture_retrieval import CultureRetrievalError, embed_query, retrieve_culture, vector_dimension
from serve_culture_art import create_app


def test_abstention_is_visible_to_curator():
    assert _is_empty(CultureArtAgent(None).run([]))


def test_vector_dimensions():
    assert vector_dimension('[1,2,3]') == 3
    assert vector_dimension([1, 2]) == 2
    assert vector_dimension('bad') is None


def test_mismatched_dimensions_stop_before_embedding(monkeypatch):
    monkeypatch.setenv('CULTURE_EMBEDDING_BACKEND', 'gemini')
    with patch('rag.vector_store.culture_retrieval.diagnose_supabase', return_value={'sample_dimensions': [384], 'chunks_count': 1}), patch('rag.vector_store.culture_retrieval.embed_query') as embed:
        with pytest.raises(CultureRetrievalError, match='do not match'):
            retrieve_culture('art', Mock())
        embed.assert_not_called()


def test_missing_backend_never_guesses(monkeypatch):
    monkeypatch.delenv('CULTURE_EMBEDDING_BACKEND', raising=False)
    with pytest.raises(CultureRetrievalError, match='confirm'):
        retrieve_culture('art', Mock())


def test_gemini_matches_n8n_model_dimension_and_query_task(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'test-secret')
    response = Mock(status_code=200)
    response.json.return_value = {'embedding': {'values': [0.1] * 1536}}
    with patch('requests.post', return_value=response) as post:
        assert len(embed_query('digital art', 'gemini')) == 1536
        args = post.call_args.kwargs
        assert args['json']['taskType'] == 'RETRIEVAL_QUERY'
        assert args['json']['outputDimensionality'] == 1536
        assert 'gemini-embedding-001' in post.call_args.args[0]
        assert 'test-secret' not in post.call_args.args[0]


def test_rpc_failure_is_not_reported_as_empty_results(monkeypatch):
    monkeypatch.setenv('CULTURE_EMBEDDING_BACKEND', 'gemini')
    sb = Mock()
    sb.rpc.side_effect = RuntimeError('secret-private-url')
    with patch('rag.vector_store.culture_retrieval.diagnose_supabase', return_value={'sample_dimensions': [1536], 'chunks_count': 1}), patch('rag.vector_store.culture_retrieval.embed_query', return_value=[0.1]*1536):
        with pytest.raises(CultureRetrievalError, match='match_chunks failed') as exc:
            retrieve_culture('art', sb)
        assert 'secret-private-url' not in str(exc.value)


@pytest.mark.parametrize('payload', [None, [], {}, {'query':'art','top_k':True}, {'query':'art','top_k':0}, {'query':'art','category':[]}])
def test_api_rejects_bad_inputs(payload, monkeypatch):
    monkeypatch.delenv('CULTURE_API_TOKEN', raising=False)
    client = create_app().test_client()
    assert client.post('/api/culture-art', json=payload).status_code == 400


def test_api_token(monkeypatch):
    monkeypatch.setenv('CULTURE_API_TOKEN', 'private-token')
    client = create_app().test_client()
    assert client.post('/api/culture-art', json={'query':'art'}).status_code == 401


def test_api_empty_retrieval_skips_llm(monkeypatch):
    monkeypatch.delenv('CULTURE_API_TOKEN', raising=False)
    with patch('serve_culture_art.build_supabase_client'), patch('serve_culture_art.retrieve_culture', return_value=[]), patch('serve_culture_art.build_llm_client') as llm:
        res = create_app().test_client().post('/api/culture-art', json={'query':'art'})
        assert res.status_code == 200
        assert res.json['status'] == 'insufficient_evidence'
        llm.assert_not_called()


def test_api_returns_real_pipeline_result_with_mocked_boundaries(monkeypatch):
    monkeypatch.delenv('CULTURE_API_TOKEN', raising=False)
    from rag.vector_store.retriever import RetrievalResult
    chunks = [RetrievalResult('art-1', 'doc-1', 'Museum displays pottery.')]
    with patch('serve_culture_art.build_supabase_client'), patch('serve_culture_art.retrieve_culture', return_value=chunks), patch('serve_culture_art.build_llm_client'), patch.object(CultureArtAgent, '_call_llm', return_value={'perspective':'Pottery','key_findings':['Pottery [art-1].'],'selected_artifacts':['art-1']}):
        res = create_app().test_client().post('/api/culture-art', json={'query':'pottery'})
        assert res.status_code == 200
        assert res.json['insight']['selected_artifacts'] == ['art-1']
        assert res.json['retrieved_evidence'][0]['chunk_id'] == 'art-1'
