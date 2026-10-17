from unittest.mock import Mock

from agents.culture_art import CultureArtAgent


CHUNKS = [{"chunk_id": "art-1", "document_id": "doc-1",
           "content": "An exhibition in Tunis explores identity through digital art.",
           "metadata": {"category": "culture", "source": "museum"}}]


def test_evidence_ids_and_metadata_reach_llm():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={"perspective": "Digital art in Tunis",
        "key_findings": ["Identity through digital art [art-1]."],
        "selected_artifacts": ["art-1", "invented-id", "art-1"]})
    result = agent.run(CHUNKS)
    assert result.selected_artifacts == ["art-1"]
    prompt = agent._call_llm.call_args.args[1]
    assert '"chunk_id": "art-1"' in prompt
    assert '"source": "museum"' in prompt


def test_empty_evidence_does_not_call_llm():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock()
    assert agent.run([]).key_findings == []
    agent._call_llm.assert_not_called()


def test_entirely_invented_references_abstain():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={"perspective": "Invented",
        "key_findings": ["Invented work"], "selected_artifacts": ["unknown"]})
    result = agent.run(CHUNKS)
    assert result.selected_artifacts == []
    assert result.key_findings == []


def test_wrong_field_types_abstain_without_character_lists():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={"perspective": "Art",
        "key_findings": "a finding", "selected_artifacts": "art-1"})
    assert agent.run(CHUNKS).key_findings == []


def test_missing_fields_do_not_invent_findings():
    agent = CultureArtAgent(None)
    agent._call_llm = Mock(return_value={})
    assert agent.run(CHUNKS).selected_artifacts == []


def test_missing_prompt_does_not_send_contextless_llm_request(tmp_path):
    import pytest
    agent = CultureArtAgent(None, tmp_path / 'missing.md')
    agent._call_llm = Mock()
    with pytest.raises(ValueError, match='placeholder'):
        agent.run(CHUNKS)
    agent._call_llm.assert_not_called()


def test_version_header_is_not_sent_to_llm():
    agent = CultureArtAgent(None)
    assert not agent._load_prompt_template().startswith('## v')
