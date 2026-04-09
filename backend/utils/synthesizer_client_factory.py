"""
从任务配置构建与 SFT 管线一致的合成器 OpenAIClient（用于生成后自动审核等场景）。
"""

from __future__ import annotations

from arborgraph.models import OpenAIClient, Tokenizer
from arborgraph.models.llm.limitter import RPM, TPM
from arborgraph.models.llm.llm_env import parse_extra_body_json_strings
from backend.schemas import TaskConfig


def build_synthesizer_openai_client(config: TaskConfig) -> OpenAIClient:
    """与 TaskProcessor 中合成器客户端构造逻辑保持一致（extra_body 来自任务配置字符串合并）。"""
    tokenizer_instance = Tokenizer(config.tokenizer)
    extra_body = parse_extra_body_json_strings(
        config.llm_extra_body_json or "",
        config.synthesizer_extra_body_json or "",
    )
    return OpenAIClient(
        model_name=config.synthesizer_model,
        base_url=config.synthesizer_url,
        api_key=config.api_key.strip() if config.api_key else None,
        request_limit=True,
        rpm=RPM(config.rpm),
        tpm=TPM(config.tpm),
        max_tokens=config.llm_max_tokens,
        tokenizer=tokenizer_instance,
        extra_body=extra_body,
    )
