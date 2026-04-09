"""
SFT 生成结束后在后台线程中运行自动审核（不阻塞任务主流程，便于用户立即查看问答对）。
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional

from backend.schemas import AutoReviewRequest, TaskConfig
from backend.services.auto_review_service import auto_review_service
from backend.services.review_service import review_service
from backend.utils.synthesizer_client_factory import build_synthesizer_openai_client
from backend.utils.task_manager import TaskManager, TaskStatus, task_manager


def schedule_post_sft_auto_review(
    task_id: str,
    log_file: Optional[str],
    config_dict: Dict[str, Any],
    tm: TaskManager | None = None,
) -> None:
    """在守护线程中启动后台自动审核。"""

    def _runner() -> None:
        asyncio.run(_post_sft_auto_review_async(task_id, log_file, config_dict, tm or task_manager))

    t = threading.Thread(
        target=_runner,
        daemon=True,
        name=f"post-sft-auto-review-{task_id[:8]}",
    )
    t.start()


def _format_progress_bar(current: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return f"[{'-' * width}] 0/0 (0.0%)"
    ratio = min(1.0, max(0.0, current / total))
    filled = int(width * ratio)
    bar = "=" * filled + "-" * (width - filled)
    return f"[{bar}] {current}/{total} ({100.0 * ratio:.1f}%)"


async def _post_sft_auto_review_async(
    task_id: str,
    log_file: Optional[str],
    config_dict: Dict[str, Any],
    tm: TaskManager,
) -> None:
    from arborgraph.utils import set_logger, logger as ag_logger

    client = None
    try:
        if log_file:
            set_logger(log_file, if_stream=False, force=True)

        ag_logger.info("")
        ag_logger.info("=" * 60)
        ag_logger.info("[自动审核] 生成阶段已结束，开始在后台自动审核（可随时在「审核」页查看问答对）")
        ag_logger.info("=" * 60)

        cfg = TaskConfig(**config_dict)
        client = build_synthesizer_openai_client(cfg)

        load_result = review_service.load_task_data(task_id)
        if not load_result.get("success"):
            err = load_result.get("error", "加载任务数据失败")
            ag_logger.error("[自动审核] %s", err)
            # 自动审核不应高于 SFT 生成：生成已成功时，自动审核失败仅记录日志，任务最终仍视为已完成
            tm.update_task_status(task_id, TaskStatus.COMPLETED)
            return

        items = load_result.get("data") or []
        item_ids = [row["item_id"] for row in items if row.get("item_id")]
        if not item_ids:
            ag_logger.warning("[自动审核] 无数据项，跳过审核")
            tm.update_task_status(task_id, TaskStatus.COMPLETED)
            return

        request = AutoReviewRequest(
            item_ids=item_ids,
            threshold=0.7,
            auto_approve=True,
            auto_reject=False,
        )

        result = await auto_review_service.auto_review_batch(
            request,
            llm_client=client,
            external_log=ag_logger,
            progress_formatter=_format_progress_bar,
        )

        if result.get("success"):
            data = result.get("data") or {}
            sc = data.get("success_count", 0)
            ec = data.get("error_count", 0)
            ag_logger.info(
                "[自动审核] 全部完成：成功 %s 条，失败 %s 条（详见上文逐条记录）",
                sc,
                ec,
            )
            tm.update_task_status(task_id, TaskStatus.COMPLETED)
        else:
            msg = result.get("error", "自动审核失败")
            ag_logger.error("[自动审核] %s", msg)
            tm.update_task_status(task_id, TaskStatus.COMPLETED)
    except Exception as e:
        try:
            from arborgraph.utils import logger as ag_logger2

            ag_logger2.exception("[自动审核] 后台任务异常: %s", e)
        except Exception:
            pass
        tm.update_task_status(task_id, TaskStatus.COMPLETED)
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
