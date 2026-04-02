"""
任务日志读取服务
"""

import os
from typing import Dict, Any

from backend.utils.task_manager import task_manager


class LogService:
    def read_task_log(self, task_id: str, offset: int = 0, limit: int = 400) -> Dict[str, Any]:
        task = task_manager.get_task(task_id)
        if not task:
            return {"success": False, "error": "任务不存在"}

        log_file = getattr(task, "log_file", None)
        if not log_file:
            return {"success": False, "error": "任务尚未产生日志文件"}

        if not os.path.exists(log_file):
            return {"success": False, "error": f"日志文件不存在: {log_file}"}

        offset = max(0, int(offset))
        limit = max(1, min(int(limit), 5000))

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = min(offset, total_lines)
        end = min(start + limit, total_lines)
        chunk = "".join(lines[start:end])

        return {
            "success": True,
            "data": {
                "task_id": task_id,
                "log_file": log_file,
                "offset": start,
                "next_offset": end,
                "total_lines": total_lines,
                "content": chunk,
                "has_more": end < total_lines,
            },
        }


log_service = LogService()

