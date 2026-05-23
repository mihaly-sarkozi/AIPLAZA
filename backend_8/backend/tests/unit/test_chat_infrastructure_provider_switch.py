from __future__ import annotations

from apps.chat.infrastructure import ChatModuleInfrastructure


def test_chat_infrastructure_builds_ollama_openai_compatible_client(monkeypatch):
    from apps.chat import infrastructure as chat_infra_module

    class _Client:
        def __init__(self, **kwargs):
            self.base_url = kwargs.get("base_url")
            self.api_key = kwargs.get("api_key")

    monkeypatch.setattr(ChatModuleInfrastructure, "_openai_client", staticmethod(lambda **kwargs: _Client(**kwargs)))

    monkeypatch.setattr(chat_infra_module.settings, "chat_provider", "ollama", raising=False)
    monkeypatch.setattr(chat_infra_module.settings, "ollama_url", "http://localhost:11434", raising=False)
    monkeypatch.setattr(chat_infra_module.settings, "ollama_api_key", "ollama", raising=False)

    infra = ChatModuleInfrastructure()
    client = infra.build_llm_client()

    assert str(getattr(client, "base_url", "")).rstrip("/") == "http://localhost:11434/v1"


def test_chat_infrastructure_uses_ollama_model_name(monkeypatch):
    from apps.chat import infrastructure as chat_infra_module

    class _Client:
        def __init__(self, **kwargs):
            self.base_url = kwargs.get("base_url")
            self.api_key = kwargs.get("api_key")

    monkeypatch.setattr(ChatModuleInfrastructure, "_openai_client", staticmethod(lambda **kwargs: _Client(**kwargs)))

    monkeypatch.setattr(chat_infra_module.settings, "chat_provider", "ollama", raising=False)
    monkeypatch.setattr(chat_infra_module.settings, "ollama_model", "qwen2.5:7b-instruct", raising=False)
    monkeypatch.setattr(chat_infra_module.settings, "ollama_url", "http://localhost:11434", raising=False)
    monkeypatch.setattr(chat_infra_module.settings, "ollama_api_key", "ollama", raising=False)

    service = ChatModuleInfrastructure().build_chat_service()

    assert service.chat_model_name == "qwen2.5:7b-instruct"
