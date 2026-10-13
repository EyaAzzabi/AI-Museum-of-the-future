from unittest.mock import Mock, patch

import pytest

from agents.culture_art import CultureArtAgent
from agents.culture_scope import resolve_country, matches_country, analysis_status
from rag.vector_store.retriever import RetrievalResult
from rag.vector_store.culture_retrieval import retrieve_culture
from serve_culture_art import create_app


@pytest.mark.parametrize('query', ['contemporary art in Tunisia', 'art contemporain en Tunisie', 'الفن في تونس', 'exhibition in Tunis'])
def test_tunisia_detected_across_languages(query):
    assert resolve_country(query) == 'Tunisia'


def test_country_conflict_rejected():
    with pytest.raises(ValueError, match='conflicts'):
        resolve_country('art in Tunisia', 'Egypt')


def test_comparative_query_is_not_forced_to_one_country():
    assert resolve_country('compare arts in Tunisia and Egypt') is None


def test_publisher_country_is_not_subject_country():
    assert not matches_country({'content':'An exhibition in Cairo.', 'metadata':{'sourcecountry':'TN'}}, 'Tunisia')
    assert matches_country({'content':'Local pottery workshop.', 'metadata':{'country_code':'TN'}}, 'Tunisia')


def test_incidental_tunis_substring_is_not_match():
    assert not matches_country({'content':'A fictional Tunisomething movement.'}, 'Tunisia')


def test_observed_egypt_and_morocco_results_abstain_without_llm():
    # Titles copied from the live output Sarah supplied, not independently fetched.
    chunks = [
        {'chunk_id':'egypt-1', 'content':'القومي للمسرح يناقش تأثير الثقافة المصرية القديمة على الفنون المعاصرة بأحدث إصداراته'},
        {'chunk_id':'egypt-2', 'content':'محافظ القاهرة : شارع الفن منصة للإبداع المصري وإبراز الوجه الحضاري للعاصمة'},
        {'chunk_id':'morocco-1', 'content':'أيام التراث المغربي في باكو لتعزيز الروابط الثقافية والشعبية بين أذربيجان والمغرب'},
    ]
    agent = CultureArtAgent(None)
    agent._call_llm = Mock()
    result = agent.run(chunks, query='contemporary art and cultural identity in Tunisia')
    assert result.selected_artifacts == []
    agent._call_llm.assert_not_called()


def test_query_transmitted_and_non_tunisian_evidence_excluded():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={'perspective':'Short excerpt about Tunisian art.',
        'key_findings':['Observation: an exhibition in Tunis discusses identity [tn-1].'],
        'selected_artifacts':['tn-1','eg-1']})
    result = agent.run([{'chunk_id':'tn-1','content':'An exhibition in Tunis discusses identity.'},
                       {'chunk_id':'eg-1','content':'An exhibition in Cairo discusses Egyptian art.'}],
                       query='cultural identity in Tunisia')
    prompt = agent._call_llm.call_args.args[1]
    assert 'cultural identity in Tunisia' in prompt
    assert 'Cairo' not in prompt
    assert result.selected_artifacts == ['tn-1']


@pytest.mark.parametrize('finding', ['Uncited fact.', 'Fact [unknown].', 'Fact [tn-1] and [unknown].'])
def test_invalid_finding_citations_are_dropped(finding):
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={'perspective':'Art in Tunis', 'key_findings':[finding], 'selected_artifacts':['tn-1']})
    result = agent.run([{'chunk_id':'tn-1','content':'Art in Tunis.'}], query='art in Tunisia')
    assert result.key_findings == []
    assert result.selected_artifacts == []


def test_retrieval_overfetches_then_filters_and_reports_counts(monkeypatch):
    monkeypatch.setenv('CULTURE_EMBEDDING_BACKEND','local')
    sb = Mock()
    sb.rpc.return_value.execute.return_value.data = [
        {'id':'eg-1','content':'Art in Egypt.', 'similarity':.9},
        {'id':'tn-1','content':'Art in Tunis.', 'similarity':.8},
        {'id':'tn-2','content':'Tunisian cinema.', 'similarity':.7},
    ]
    diagnostics = {}
    with patch('rag.vector_store.culture_retrieval.diagnose_supabase', return_value={'sample_dimensions':[384], 'chunks_count':100}), patch('rag.vector_store.culture_retrieval.embed_query',return_value=[.1]*384):
        results = retrieve_culture('art in Tunisia', sb, top_k=2, diagnostics=diagnostics)
    assert [r.chunk_id for r in results] == ['tn-1','tn-2']
    assert sb.rpc.call_args.args[1]['match_count'] == 20
    assert diagnostics['rejected_country_count'] == 1
    assert diagnostics['returned_count'] == 2


def test_status_does_not_claim_factual_support():
    agent = CultureArtAgent(None)
    result = agent._insufficient()
    status = analysis_status(result, [], 'art in Tunisia')
    assert status['status'] == 'insufficient_evidence'
    assert status['scope_country'] == 'Tunisia'
    assert any('full corpus' in item for item in status['limitations'])


def test_api_invalid_country_rejected(monkeypatch):
    monkeypatch.delenv('CULTURE_API_TOKEN', raising=False)
    res = create_app().test_client().post('/api/culture-art',json={'query':'art','country':[]})
    assert res.status_code == 400
