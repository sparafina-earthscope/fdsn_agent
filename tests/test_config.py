"""Tests for fdsn_agent.config."""

import os
from unittest.mock import patch

import pytest

from fdsn_agent.config import LLMConfig, PRESETS


class TestLLMConfig:
    def test_from_preset_anthropic(self):
        cfg = LLMConfig.from_preset("anthropic", api_key="test-key")
        assert cfg.base_url  == "https://api.anthropic.com/v1"
        assert cfg.format    == "anthropic"
        assert cfg.api_key   == "test-key"

    def test_from_preset_ollama(self):
        cfg = LLMConfig.from_preset("ollama")
        assert "11434" in cfg.base_url
        assert cfg.format   == "openai"
        assert cfg.api_key  == ""

    def test_from_preset_model_override(self):
        cfg = LLMConfig.from_preset("anthropic", model="claude-opus-4-6")
        assert cfg.model == "claude-opus-4-6"

    def test_from_preset_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMConfig.from_preset("doesnotexist")

    def test_from_preset_all_providers(self):
        for name in PRESETS:
            cfg = LLMConfig.from_preset(name)
            assert cfg.base_url
            assert cfg.model
            assert cfg.format in ("anthropic", "openai")

    def test_from_env_uses_env_vars(self):
        env = {
            "LLM_BASE_URL": "http://custom:9000/v1",
            "LLM_MODEL":    "custom-model",
            "LLM_API_KEY":  "env-key",
            "LLM_FORMAT":   "openai",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = LLMConfig.from_env()
        assert cfg.base_url == "http://custom:9000/v1"
        assert cfg.model    == "custom-model"
        assert cfg.api_key  == "env-key"

    def test_from_env_falls_back_to_preset(self):
        with patch.dict(os.environ, {}, clear=False):
            # Ensure the vars are absent
            for k in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_FORMAT"):
                os.environ.pop(k, None)
            cfg = LLMConfig.from_env("ollama")
        assert "11434" in cfg.base_url

    def test_defaults(self):
        cfg = LLMConfig(base_url="http://x", model="m")
        assert cfg.max_tokens  == 1024
        assert cfg.temperature == 0.2
        assert cfg.timeout     == 120
        assert cfg.api_key     == ""

    def test_kwargs_override(self):
        cfg = LLMConfig.from_preset("openai", max_tokens=2048, temperature=0.0)
        assert cfg.max_tokens  == 2048
        assert cfg.temperature == 0.0
