"""Deterministic contracts and retrieval regressions; no real LLM quality claims."""
from unittest.mock import Mock, patch

import pytest

from rag.vector_store.culture_reranker import CultureReranker
from rag.vector_store.culture_retrieval import CultureRetrievalError, retrieve_culture
from rag.vector_store.retriever import RetrievalResult


def candidate(cid='artist', content='An artist from Tunisia performs rock music.', score=.2):
    return RetrievalResult(cid, 'doc-'+cid, content, {}, score)


def decision(cid='artist', score=2, quote='An artist from Tunisia performs rock music.'):
    return dict(chunk_id=cid, relevance=score, evidence_quote=quote, reason='A limited artistic example.')


def test_empty_pool_never_initializes_provider():
    factory=Mock()
    info={}
    assert CultureReranker(factory)([], 'art', 'Tunisia', info)==[]
    factory.assert_not_called()


def test_broad_query_recovers_artist_beyond_top_five(monkeypatch):
    monkeypatch.setenv('CULTURE_EMBEDDING_BACKEND','local')
    pool=[candidate(str(i), 'Tunisia political news.', .9) for i in range(78)] + [candidate()]
    def judge(system,user):
        import json
        rows=json.loads(user)['candidates']
        return {'decisions':[decision(r['chunk_id'], 2 if r['chunk_id']=='artist' else 0,
                                     r['content'] if r['chunk_id']=='artist' else '') for r in rows]}
    sb=Mock()
    sb.rpc.return_value.execute.return_value.data=[]
    info={}
    with patch('rag.vector_store.culture_retrieval.diagnose_supabase',return_value={'sample_dimensions':[384],'chunks_count':79}), patch('rag.vector_store.culture_retrieval.embed_query',return_value=[1,0]), patch('rag.vector_store.culture_retrieval._country_first_candidates',return_value=(pool,{})), patch('agents.culture_art.CultureArtAgent._call_llm',side_effect=judge):
        results=retrieve_culture('contemporary art and cultural identity in Tunisia',sb,
                                 diagnostics=info,reranker=CultureReranker(Mock()))
    assert [r.chunk_id for r in results]==['artist']
    assert info['rerank_candidate_count']==79
    assert info['rerank_calls']==10
    assert info['rerank_unreviewed_count']==0
    assert info['returned_count']==1


@pytest.mark.parametrize('bad',[
    {}, {'decisions':[]}, {'decisions':[decision('invented')]},
    {'decisions':[decision(score=True)]}, {'decisions':[decision(score=4)]},
    {'decisions':[decision(quote='invented quote')]}, {'decisions':[decision(quote='')]},
    {'decisions':[dict(decision(), reason=None)]}, {'decisions':[None]},
])
def test_invalid_provider_output_fails_explicitly(bad):
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value=bad):
        with pytest.raises(CultureRetrievalError,match='screening failed'):
            CultureReranker(Mock())([candidate()], 'art', 'Tunisia', {})


def test_duplicate_decision_cannot_hide_missing_candidate():
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value={'decisions':[decision(),decision()]}):
        with pytest.raises(CultureRetrievalError):
            CultureReranker(Mock())([candidate(),candidate('other')], 'art','Tunisia',{})


def test_budget_and_excerpts_are_visible_and_bounded():
    source=candidate(content='x'*1700)
    info={}
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value={'decisions':[decision(score=1,quote='')]}) as call:
        results=CultureReranker(Mock(),max_candidates=1)([source,candidate('other')],'art','Tunisia',info)
    assert results==[]
    assert info['rerank_unreviewed_count']==1
    assert info['rerank_decisions'][0]['excerpt_truncated'] is True
    import json
    assert len(json.loads(call.call_args.args[1])['candidates'][0]['content'])==1600


def test_failure_does_not_leak_provider_secrets_or_return_partial_success():
    with patch('agents.culture_art.CultureArtAgent._call_llm',side_effect=[{'decisions':[decision()]}, RuntimeError('private-key')]):
        with pytest.raises(CultureRetrievalError) as error:
            CultureReranker(Mock(),batch_size=1)([candidate(),candidate('other')],'art','Tunisia',{})
    assert 'private-key' not in str(error.value)


def test_scores_sort_without_mutating_input():
    rows=[candidate('a'),candidate('b')]
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value={'decisions':[decision('a',2),decision('b',3)]}):
        ranked=CultureReranker(Mock())(rows,'art','Tunisia',{})
    assert [r.chunk_id for r in ranked]==['b','a']
    assert 'relevance_grade' not in rows[0].metadata


@pytest.mark.parametrize('status',[400,401,403,404,413,429,503])
def test_wrapped_http_failures_are_identified_without_provider_text(status):
    provider_error=RuntimeError('SECRET_PROVIDER_PAYLOAD')
    provider_error.status_code=status
    wrapped=ValueError('SECRET_WRAPPED_PAYLOAD')
    wrapped.__cause__=provider_error
    with patch('agents.culture_art.CultureArtAgent._call_llm',side_effect=wrapped):
        with pytest.raises(CultureRetrievalError) as error:
            CultureReranker(Mock())([candidate()],'art','Tunisia',{})
    assert f'LLM_HTTP_{status}' in str(error.value)
    assert 'batch 1/1' in str(error.value)
    assert 'SECRET' not in str(error.value)


def test_format_error_identifies_failed_contract():
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value={'decisions':[decision(quote='invented')]}):
        with pytest.raises(CultureRetrievalError,match='MODEL_FORMAT: Unsupported evidence quote'):
            CultureReranker(Mock())([candidate()],'art','Tunisia',{})


def test_timeout_is_distinct_from_invalid_json():
    from rag.vector_store.culture_reranker import _safe_failure
    import json
    assert _safe_failure(TimeoutError('secret')).startswith('LLM_TIMEOUT:')
    assert _safe_failure(json.JSONDecodeError('secret','secret',0)).startswith('MODEL_JSON:')


def test_whitespace_tolerance_returns_actual_source_span():
    from rag.vector_store.culture_reranker import _match_quote
    assert _match_quote('art in Tunisia','art\n in\u00a0Tunisia')=='art\n in\u00a0Tunisia'
    assert _match_quote('art in Tunisia','art in Egypt') is None
    assert _match_quote('art ... Tunisia','art created in Tunisia') is None
    assert _match_quote('Tunisian music','music from Tunisia') is None
    assert _match_quote('  ','anything') is None


def test_bad_quote_is_excluded_and_later_batch_still_examined():
    info={}
    with patch('agents.culture_art.CultureArtAgent._call_llm',side_effect=[
        {'decisions':[decision('bad',quote='invented quote')]},
        {'decisions':[decision('artist')]},
    ]):
        result=CultureReranker(Mock(),batch_size=1)([candidate('bad'),candidate()],'art','Tunisia',info)
    assert [r.chunk_id for r in result]==['artist']
    assert info['rerank_calls']==2
    assert info['rerank_quote_rejections']==['bad']
    assert info['rerank_warnings']


def test_rejected_quotes_surface_in_final_warnings():
    from agents.culture_scope import analysis_status
    from agents.base_agent import InsightObject
    output=analysis_status(InsightObject('culture_art','',''.split(),[]), [], 'art',
                           retrieval={'rerank_warnings':['Quote validation excluded a candidate.']})
    assert 'Quote validation excluded a candidate.' in output['warnings']


def test_resume_after_rate_limit_reuses_completed_batches(tmp_path):
    error=RuntimeError('private quota detail')
    error.status_code=429
    rows=[candidate('first'),candidate('second')]
    first_payload={'decisions':[decision('first')]}
    second_payload={'decisions':[decision('second')]}
    with patch('agents.culture_art.CultureArtAgent._call_llm',side_effect=[first_payload,error]):
        with pytest.raises(CultureRetrievalError,match='Saved batches: 1'):
            CultureReranker(Mock(),batch_size=1,cache_dir=tmp_path)(rows,'art','Tunisia',{})
    info={}
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value=second_payload) as call:
        result=CultureReranker(Mock(),batch_size=1,cache_dir=tmp_path)(rows,'art','Tunisia',info)
    assert call.call_count==1
    assert [r.chunk_id for r in result]==['first','second']
    assert info['rerank_cached_batches']==1
    assert info['rerank_saved_batches']==1


def test_changed_query_or_source_invalidates_checkpoint(tmp_path):
    payload={'decisions':[decision()]}
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value=payload) as call:
        ranker=CultureReranker(Mock(),cache_dir=tmp_path)
        ranker([candidate()],'art','Tunisia',{})
        ranker([candidate()],'art','Tunisia',{})
        assert call.call_count==1
        ranker([candidate()],'music','Tunisia',{})
        assert call.call_count==2
        ranker([candidate(content=candidate().content+' Extra context.')],'art','Tunisia',{})
        assert call.call_count==3


def test_corrupt_or_expired_cache_is_ignored(tmp_path):
    from rag.vector_store.culture_reranker import _read_checkpoint
    import json,time
    p=tmp_path/'entry.json'
    p.write_text('invalid',encoding='utf-8')
    assert _read_checkpoint(p) is None
    p.write_text(json.dumps({'saved_at':time.time()-90000,'payload':{'decisions':[]}}),encoding='utf-8')
    assert _read_checkpoint(p) is None


def test_invalid_response_is_never_checkpointed(tmp_path):
    with patch('agents.culture_art.CultureArtAgent._call_llm',return_value={'decisions':[]}):
        with pytest.raises(CultureRetrievalError):
            CultureReranker(Mock(),cache_dir=tmp_path)([candidate()],'art','Tunisia',{})
    assert not list(tmp_path.glob('*.json'))
