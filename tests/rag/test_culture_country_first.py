from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from rag.vector_store.culture_retrieval import (
    CultureRetrievalError, _country_first_candidates, _parse_vector, _cosine,
    _lexical_coverage, retrieve_culture,
)


class Query:
    def __init__(self, pages):
        self.pages = pages
        self.start = 0
        self.filters = ''
    def select(self, fields):
        assert 'embedding' in fields and 'documents(' in fields
        return self
    def or_(self, filters):
        self.filters = filters
        return self
    def order(self, column):
        assert column == 'id'
        return self
    def eq(self, *args):
        return self
    def range(self, start, end):
        self.start = start
        return self
    def execute(self):
        return SimpleNamespace(data=self.pages.get(self.start, []))


def client_with(rows):
    client = Mock()
    statement = Query({0:rows})
    client.table.return_value = statement
    return client, statement


def row(id, content, embedding, title=''):
    return {'id':id,'document_id':'doc-'+id,'content':content,'embedding':embedding,
            'metadata':{'source':'synthetic','category':'history'},
            'documents':{'title':title,'url':'https://example.com/source','published_at':'2020-12-10'}}


def test_cosine_is_real_vector_comparison():
    assert _cosine([1,0],[1,0]) == 1
    assert _cosine([1,0],[0,1]) == 0
    assert _cosine([1,0],[1]) is None
    assert _cosine([1,0],[0,0]) is None


@pytest.mark.parametrize('value',[None,'bad','[1, NaN]',[float('inf')],[True],[]])
def test_invalid_vectors_are_skipped(value):
    assert _parse_vector(value) is None


def test_country_search_enriches_sources_and_ranks_stored_vectors():
    rows = [row('art','Artist from Tunisia performs rock music.', '[1,0]', 'Joe Luciano interview'),
            row('other','A Tunisian electrical crisis.', [0,1], 'Electricity')]
    client, statement = client_with(rows)
    results, diagnostics = _country_first_candidates(client,'Tunisia','Joe Luciano rock music',[1,0])
    assert len(results) == 2
    assert 'content.ilike."%Tunisia%"' in statement.filters
    assert 'sourcecountry' not in statement.filters
    assert results[0].similarity == 1
    assert results[0].metadata['title'] == 'Joe Luciano interview'
    assert results[0].metadata['url'] == 'https://example.com/source'
    assert results[0].metadata['published_at'] == '2020-12-10'
    assert diagnostics['country_candidates_count'] == 2
    assert diagnostics['country_vectors_skipped'] == 0


def test_dimensions_and_missing_vectors_reported():
    client,_ = client_with([row('missing','Art in Tunisia.',None),row('dim','Art in Tunis.',[1,0,0])])
    results, diagnostics = _country_first_candidates(client,'Tunisia','art',[1,0])
    assert results == []
    assert diagnostics['country_vectors_skipped'] == 2


def test_incidental_country_substring_removed_after_lexical_fetch():
    client,_ = client_with([row('bad','A Tunisomething artifact.',[1,0])])
    assert _country_first_candidates(client,'Tunisia','art',[1,0])[0] == []


def test_read_failure_is_explicit():
    client = Mock()
    client.table.side_effect = RuntimeError('private-url')
    with pytest.raises(CultureRetrievalError,match='Country-first read failed') as exc:
        _country_first_candidates(client,'Tunisia','art',[1,0])
    assert 'private-url' not in str(exc.value)


def test_general_lexical_scoring_not_person_specific():
    assert _lexical_coverage('Alice Example rock in Tunisia','Alice Example rock singer','Tunisia') == 1
    assert _lexical_coverage('Alice Example rock in Tunisia','Electricity in Tunisia','Tunisia') == 0


def test_source_missing_from_rpc_is_recovered_and_deduplicated(monkeypatch):
    monkeypatch.setenv('CULTURE_EMBEDDING_BACKEND','local')
    artist=row('artist','An artist from Tunisia performs rock and promotes freedom of expression.',[1,0],'Joe Luciano interview')
    client,_=client_with([artist])
    client.rpc.return_value.execute.return_value.data = [
        {'id':'news','content':'Electrical crisis in Tunisia.','similarity':.5,'metadata':{}}]
    info={}
    with patch('rag.vector_store.culture_retrieval.diagnose_supabase',return_value={'sample_dimensions':[384],'chunks_count':7296}),patch('rag.vector_store.culture_retrieval.embed_query',return_value=[1,0]):
        results=retrieve_culture('Joe Luciano Tunisian rock music and freedom of expression',client,top_k=1,diagnostics=info)
    assert results[0].chunk_id=='artist'
    assert info['retrieval_method']=='country_first_hybrid'
    assert info['country_candidates_count']==1
    assert results[0].metadata['title']=='Joe Luciano interview'
