from __future__ import annotations

from agents.base_agent import InsightObject
from agents.shared_context import SharedContext, compute_cross_references
from multimodal.analyze_image import VisualDescription, analyze_image
from rag.vector_store.retriever import RetrievalResult, Retriever


class DummyEmbeddings:
    def __init__(self, embedding=None):
        self.embedding = embedding or [0.1] * 1536

    def create(self, **kwargs):
        class Response:
            class Data:
                embedding = [0.1] * 1536

            data = [Data()]

        return Response()


class DummyChat:
    def __init__(self, content: str = '{"agent":"historian","perspective":"test","key_findings":["a"],"selected_artifacts":["x"]}'):
        self.content = content

    def create(self, **kwargs):
        class Message:
            content = self.content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


class DummySupabase:
    def rpc(self, name, params):
        class Response:
            data = [
                {"chunk_id": "x", "document_id": "doc-1", "content": "Some text", "metadata": {"category": "culture"}, "similarity": 0.82},
                {"chunk_id": "y", "document_id": "doc-2", "content": "More text", "metadata": {"category": "science"}, "similarity": 0.62},
            ]

        return Response()


def test_cross_references_are_detected():
    insights = {
        "historian": InsightObject("historian", "History", ["A"], ["artifact-1", "artifact-2"]),
        "sociologist": InsightObject("sociologist", "Society", ["B"], ["artifact-2", "artifact-3"]),
    }
    assert compute_cross_references(insights) == ["artifact-2"]


def test_retriever_returns_sorted_results():
    retriever = Retriever(DummySupabase(), type("Client", (), {"embeddings": DummyEmbeddings(), "chat": type("Chat", (), {"completions": DummyChat()})})())
    results = retriever.retrieve("museum history")
    assert len(results) >= 1
    assert results[0].similarity >= results[-1].similarity
    assert isinstance(results[0], RetrievalResult)


def test_analyze_image_returns_description_for_mocked_content(monkeypatch):
    class MockClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    class Message:
                        content = "scene: city\nobjects: building, people\ntags: urban, culture"

                    class Choice:
                        message = Message()

                    class Response:
                        choices = [Choice()]

                    return Response()

        class embeddings:
            @staticmethod
            def create(**kwargs):
                class Data:
                    embedding = [0.1, 0.2, 0.3]

                class Response:
                    data = [Data()]

                return Response()

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: type("Resp", (), {"status_code": 200, "content": b"abc"})())
    result = analyze_image("https://example.com/image.jpg", openai_client=MockClient())
    assert isinstance(result, VisualDescription)
    assert result.description
    assert result.scene or result.tags or result.objects
