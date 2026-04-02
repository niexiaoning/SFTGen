"""
Task management runtime module.

This module is the backend-owned home for task persistence and status tracking.
It replaces the previous dependency on the legacy `webui` package.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(Enum):
    """Task lifecycle states."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    """Persisted task metadata."""

    task_id: str
    task_name: str
    task_description: Optional[str]
    task_type: str = "sft"
    filenames: List[str] = None
    filepaths: List[str] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    output_file: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None
    processing_time: Optional[float] = None
    qa_count: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    synthesizer_model: Optional[str] = None
    trainee_model: Optional[str] = None

    @property
    def filename(self) -> str:
        return self.filenames[0] if self.filenames else ""

    @property
    def file_path(self) -> str:
        return self.filepaths[0] if self.filepaths else ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat()
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()

        if self.config and not self.synthesizer_model:
            self.synthesizer_model = self.config.get("synthesizer_model")
        if self.config and not self.trainee_model:
            self.trainee_model = self.config.get("trainee_model")
        return data


class TaskManager:
    """Manage task persistence under `tasks/`."""

    def __init__(self, tasks_dir: str = "tasks"):
        self.tasks_dir = tasks_dir
        self.tasks: Dict[str, TaskInfo] = {}
        self.lock = threading.Lock()

        os.makedirs(self.tasks_dir, exist_ok=True)
        os.makedirs(os.path.join(self.tasks_dir, "outputs"), exist_ok=True)
        self._load_tasks()

    def _load_tasks(self) -> None:
        tasks_file = os.path.join(self.tasks_dir, "tasks.json")
        if not os.path.exists(tasks_file):
            return
        try:
            with open(tasks_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            for task_data in data.get("tasks", []):
                if "filename" in task_data and "filenames" not in task_data:
                    filenames = [task_data["filename"]]
                    filepaths = [task_data["file_path"]]
                else:
                    filenames = task_data.get("filenames", [])
                    filepaths = task_data.get("filepaths", [])

                task = TaskInfo(
                    task_id=task_data["task_id"],
                    task_name=task_data.get(
                        "task_name", task_data.get("filename", "未命名任务")
                    ),
                    task_description=task_data.get("task_description"),
                    task_type=task_data.get("task_type", "sft"),
                    filenames=filenames,
                    filepaths=filepaths,
                    status=TaskStatus(task_data["status"]),
                    created_at=datetime.fromisoformat(task_data["created_at"]),
                    started_at=(
                        datetime.fromisoformat(task_data["started_at"])
                        if task_data.get("started_at")
                        else None
                    ),
                    completed_at=(
                        datetime.fromisoformat(task_data["completed_at"])
                        if task_data.get("completed_at")
                        else None
                    ),
                    error_message=task_data.get("error_message"),
                    output_file=task_data.get("output_file"),
                    token_usage=task_data.get("token_usage"),
                    processing_time=task_data.get("processing_time"),
                    qa_count=task_data.get("qa_count"),
                    config=task_data.get("config"),
                )
                self.tasks[task.task_id] = task
        except Exception as exc:
            print(f"加载任务信息失败: {exc}")

    def _save_tasks(self) -> None:
        tasks_file = os.path.join(self.tasks_dir, "tasks.json")
        try:
            with open(tasks_file, "w", encoding="utf-8") as file:
                json.dump(
                    {"tasks": [task.to_dict() for task in self.tasks.values()]},
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as exc:
            print(f"保存任务信息失败: {exc}")

    def create_task(
        self,
        task_name: str,
        filenames: List[str],
        filepaths: List[str],
        task_description: Optional[str] = None,
        task_type: str = "sft",
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        with self.lock:
            task_id = str(uuid.uuid4())
            task = TaskInfo(
                task_id=task_id,
                task_name=task_name,
                task_description=task_description,
                task_type=task_type,
                filenames=filenames,
                filepaths=filepaths,
                status=TaskStatus.PENDING,
                created_at=datetime.now(),
                config=config,
            )
            self.tasks[task_id] = task
            self._save_tasks()
            return task_id

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        task = self.tasks.get(task_id)
        if (
            task
            and task.status == TaskStatus.COMPLETED
            and task.qa_count is None
            and task.output_file
        ):
            task.qa_count = self._calculate_qa_count(task.output_file)
            if task.qa_count is not None:
                self._save_tasks()
        return task

    def get_all_tasks(self) -> List[TaskInfo]:
        tasks = list(self.tasks.values())
        updated = False
        for task in tasks:
            if (
                task.status == TaskStatus.COMPLETED
                and task.qa_count is None
                and task.output_file
            ):
                task.qa_count = self._calculate_qa_count(task.output_file)
                if task.qa_count is not None:
                    updated = True
        if updated:
            self._save_tasks()
        return tasks

    def _calculate_qa_count(self, output_file: str) -> Optional[int]:
        if not os.path.exists(output_file):
            return None
        try:
            with open(output_file, "r", encoding="utf-8") as file:
                try:
                    data = json.load(file)
                    if isinstance(data, list):
                        return len(data)
                    return None
                except json.JSONDecodeError:
                    file.seek(0)
                    count = 0
                    for line in file:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            json.loads(line)
                            count += 1
                        except json.JSONDecodeError:
                            continue
                    return count if count > 0 else None
        except Exception as exc:
            print(f"计算问答对数量失败: {exc}")
            return None

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error_message: Optional[str] = None,
        output_file: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        qa_count: Optional[int] = None,
    ) -> None:
        with self.lock:
            if task_id not in self.tasks:
                return
            task = self.tasks[task_id]
            task.status = status

            if status == TaskStatus.PROCESSING:
                task.started_at = datetime.now()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.now()
                if task.started_at:
                    task.processing_time = (
                        task.completed_at - task.started_at
                    ).total_seconds()

            if error_message:
                task.error_message = error_message
            if output_file:
                task.output_file = output_file
            if token_usage:
                task.token_usage = token_usage
            if qa_count is not None:
                task.qa_count = qa_count

            self._save_tasks()

    def has_new_files_to_process(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.status == TaskStatus.COMPLETED:
            return len(task.filenames) > 1
        if task.status == TaskStatus.FAILED:
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            if task.status == TaskStatus.FAILED:
                task.status = TaskStatus.PENDING
                task.error_message = None
                self._save_tasks()
                return True
            if task.status == TaskStatus.COMPLETED and len(task.filenames) > 1:
                task.status = TaskStatus.PENDING
                task.error_message = None
                if task.output_file and os.path.exists(task.output_file):
                    try:
                        os.remove(task.output_file)
                    except Exception as exc:
                        print(f"删除旧输出文件失败: {exc}")
                task.output_file = None
                task.qa_count = None
                task.token_usage = None
                task.processing_time = None
                self._save_tasks()
                return True
            return False

    def delete_task(self, task_id: str) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            if task.output_file and os.path.exists(task.output_file):
                try:
                    os.remove(task.output_file)
                except Exception as exc:
                    print(f"删除输出文件失败: {exc}")
            del self.tasks[task_id]
            self._save_tasks()
            return True

    def get_task_output_path(self, task_id: str) -> str:
        return os.path.join(self.tasks_dir, "outputs", f"{task_id}_output.jsonl")

    def add_files_to_task(self, task_id: str, filepaths: list[str]) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            if task.status != TaskStatus.PENDING:
                return False
            task.filepaths.extend(filepaths)
            task.filenames.extend([os.path.basename(path) for path in filepaths])
            self._save_tasks()
            return True

    def remove_file_from_task(self, task_id: str, file_index: int) -> bool:
        with self.lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            if (
                task.status == TaskStatus.PENDING
                and len(task.filenames) > 1
                and 0 <= file_index < len(task.filenames)
            ):
                task.filenames.pop(file_index)
                task.filepaths.pop(file_index)
                self._save_tasks()
                return True
            return False


task_manager = TaskManager()
