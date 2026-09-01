import pytest
from src.embeddings.base import BaseEmbeddingProvider
from src.embeddings.factory import EmbeddingFactory, FallbackEmbeddingProvider
from src.embeddings.fastembed_provider import FastEmbedProvider


def test_fastembed_provider():
    provider = FastEmbedProvider()
    assert provider.name == "fastembed"
    assert provider.dimension > 0
    vec = provider.get_embedding("ejercicios de hombro")
    assert isinstance(vec, list)
    assert len(vec) == provider.dimension
    assert isinstance(vec[0], float)


def test_embedding_factory():
    provider = EmbeddingFactory.get_provider("fastembed")
    assert isinstance(provider, BaseEmbeddingProvider)
    vec = provider.get_embedding("prueba de texto")
    assert len(vec) > 0


def test_fallback_chain_handles_unconfigured_safely(monkeypatch):
    # Ensure even without API keys, FastEmbed local is available
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    
    fallback = FallbackEmbeddingProvider(primary="jina")
    vec = fallback.get_embedding("sentadillas y peso muerto")
    assert len(vec) > 0
