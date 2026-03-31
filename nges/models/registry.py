"""모델 이름 → 어댑터 인스턴스 매핑."""

from __future__ import annotations
from .base import AbstractModel

# 단축명 → (provider, model_id)
MODEL_REGISTRY: dict[str, tuple[str, str]] = {
    "claude":           ("anthropic", "claude-opus-4-6"),
    "claude-sonnet":    ("anthropic", "claude-sonnet-4-6"),
    "claude-haiku":     ("anthropic", "claude-haiku-4-5-20251001"),
    "gpt4o":            ("openai",    "gpt-4o"),
    "gpt4o-mini":       ("openai",    "gpt-4o-mini"),
}


def get_model(name: str) -> AbstractModel:
    """
    name에서 모델 인스턴스를 생성한다.

    지원 형식:
      - 단축명:           "claude", "gpt4o"
      - provider:model_id: "anthropic:claude-opus-4-6"
      - model_id만:       "claude-opus-4-6"  (anthropic 기본 가정)
    """
    if name in MODEL_REGISTRY:
        provider, model_id = MODEL_REGISTRY[name]
    elif ":" in name:
        provider, model_id = name.split(":", 1)
    else:
        # 기본 provider 추론
        if any(name.startswith(p) for p in ("claude", "anthropic")):
            provider, model_id = "anthropic", name
        elif any(name.startswith(p) for p in ("gpt", "o1", "o3")):
            provider, model_id = "openai", name
        else:
            raise ValueError(
                f"알 수 없는 모델: '{name}'\n"
                f"사용 가능: {list(MODEL_REGISTRY.keys())} 또는 'provider:model_id' 형식"
            )

    if provider == "anthropic":
        from .anthropic_model import AnthropicModel
        return AnthropicModel(model_id)
    elif provider == "openai":
        from .openai_model import OpenAIModel
        return OpenAIModel(model_id)
    else:
        raise ValueError(f"지원하지 않는 provider: '{provider}' (anthropic / openai 지원)")
