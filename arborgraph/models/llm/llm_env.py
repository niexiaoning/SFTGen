"""
从环境变量或配置字符串解析 OpenAI 兼容 API 的 extra_body（智谱 GLM 的 thinking 等扩展字段）。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from arborgraph.utils.log import logger


def parse_extra_body_json_strings(
    *fragments: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    合并多段 JSON 对象字符串（后者覆盖前者同名字段）。
    用于从 .env 中的 LLM_EXTRA_BODY_JSON、SYNTHESIZER_EXTRA_BODY_JSON 等拼出 extra_body。
    """
    merged: Dict[str, Any] = {}
    for frag in fragments:
        if frag is None:
            continue
        s = str(frag).strip()
        if not s:
            continue
        try:
            data = json.loads(s)
            if not isinstance(data, dict):
                logger.warning("extra_body JSON must be an object, got %s, skipped", type(data))
                continue
            merged.update(data)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON in extra_body fragment: %s", e)
    return merged if merged else None


def load_merged_extra_body(*env_var_names: str) -> Optional[Dict[str, Any]]:
    """从若干环境变量名读取 JSON 字符串并合并为 extra_body。"""
    return parse_extra_body_json_strings(*(os.getenv(n, "") for n in env_var_names))


def zhipu_default_extra_body() -> Dict[str, Any]:
    """智谱 GLM 关闭思考链扩展时的默认 extra_body（可按需在 .env 中覆盖）。"""
    return {"thinking": {"type": "disabled", "clear_thinking": True}}
