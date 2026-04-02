#!/usr/bin/env python3
"""
TextGraphTree 并行批量处理脚本（增强版）
支持多模型并行处理和 batch size 配置
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from tqdm import tqdm
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_process import BatchProcessor


class ModelConfig:
    """模型配置类"""
    
    def __init__(
        self,
        api_key: str,
        synthesizer_url: str,
        synthesizer_model: str,
        trainee_url: Optional[str] = None,
        trainee_model: Optional[str] = None,
        trainee_api_key: Optional[str] = None,
        model_id: Optional[str] = None
    ):
        """
        初始化模型配置
        
        Args:
            api_key: API Key
            synthesizer_url: Synthesizer API URL
            synthesizer_model: Synthesizer 模型名称
            trainee_url: Trainee API URL
            trainee_model: Trainee 模型名称
            trainee_api_key: Trainee API Key
            model_id: 模型标识符（用于日志）
        """
        self.api_key = api_key
        self.synthesizer_url = synthesizer_url
        self.synthesizer_model = synthesizer_model
        self.trainee_url = trainee_url or synthesizer_url
        self.trainee_model = trainee_model or synthesizer_model
        self.trainee_api_key = trainee_api_key or api_key
        self.model_id = model_id or f"{synthesizer_url}_{synthesizer_model}"
        self.current_tasks = 0  # 当前正在处理的任务数
        self.total_tasks = 0  # 总任务数
        self.completed_tasks = 0  # 已完成任务数


class ParallelBatchProcessor:
    """并行批量处理器类 - 支持多模型并行处理"""
    
    def __init__(
        self,
        model_configs: List[Union[Dict, ModelConfig]],
        use_trainee_model: bool = False,
        output_dir: str = "tasks/outputs",
        log_dir: str = "logs",
        batch_size: int = 1,
        max_workers: Optional[int] = None,
        **kwargs
    ):
        """
        初始化并行批量处理器
        
        Args:
            model_configs: 模型配置列表，每个配置可以是字典或 ModelConfig 对象
                [
                    {
                        "api_key": "key1",
                        "synthesizer_url": "url1",
                        "synthesizer_model": "model1",
                        ...
                    },
                    {
                        "api_key": "key2",
                        "synthesizer_url": "url2",
                        "synthesizer_model": "model2",
                        ...
                    }
                ]
            use_trainee_model: 是否使用 Trainee 模型
            output_dir: 输出目录
            log_dir: 日志目录
            batch_size: 每个模型同时处理的任务数（batch size）
            max_workers: 最大工作线程数（默认：模型数量 * batch_size）
            **kwargs: 其他配置参数（传递给 BatchProcessor）
        """
        # 转换模型配置
        self.model_configs = []
        for config in model_configs:
            if isinstance(config, dict):
                self.model_configs.append(ModelConfig(**config))
            else:
                self.model_configs.append(config)
        
        if not self.model_configs:
            raise ValueError("至少需要提供一个模型配置")
        
        self.use_trainee_model = use_trainee_model
        self.output_dir = Path(output_dir)
        self.log_dir = Path(log_dir)
        self.batch_size = batch_size
        self.max_workers = max_workers or (len(self.model_configs) * batch_size)
        
        # 创建输出和日志目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存其他配置参数
        self.processor_kwargs = kwargs
        
        # 统计信息
        self.stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_tokens": 0,
            "total_time": 0,
            "file_results": [],
            "model_stats": {config.model_id: {
                "processed": 0,
                "failed": 0,
                "tokens": 0
            } for config in self.model_configs}
        }
        
        # 任务队列和锁
        self.task_queue = Queue()
        self.stats_lock = threading.Lock()
        
        # 设置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志"""
        log_file = self.log_dir / f"parallel_batch_process_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"并行批量处理日志文件: {log_file}")
        self.logger.info(f"配置了 {len(self.model_configs)} 个模型")
        self.logger.info(f"Batch size: {self.batch_size}, Max workers: {self.max_workers}")
    
    def _get_next_model(self) -> ModelConfig:
        """获取下一个可用的模型（负载均衡）"""
        # 选择当前任务数最少的模型
        return min(self.model_configs, key=lambda m: m.current_tasks)
    
    def _process_file_with_model(
        self,
        file_path: Union[str, Path],
        model_config: ModelConfig,
        output_file: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        使用指定模型处理单个文件
        
        Args:
            file_path: 输入文件路径
            model_config: 模型配置
            output_file: 输出文件路径
            
        Returns:
            处理结果字典
        """
        model_config.current_tasks += 1
        model_config.total_tasks += 1
        
        try:
            # 确定输出文件路径
            if output_file is None:
                base_name = Path(file_path).stem
                model_suffix = model_config.model_id.replace("/", "_").replace(":", "_")
                output_file = self.output_dir / f"{base_name}_{model_suffix}_output.jsonl"
            else:
                output_file = Path(output_file)
            
            # 创建 BatchProcessor 实例
            processor = BatchProcessor(
                api_key=model_config.api_key,
                synthesizer_url=model_config.synthesizer_url,
                synthesizer_model=model_config.synthesizer_model,
                trainee_url=model_config.trainee_url,
                trainee_model=model_config.trainee_model,
                trainee_api_key=model_config.trainee_api_key,
                use_trainee_model=self.use_trainee_model,
                output_dir=str(self.output_dir),
                log_dir=str(self.log_dir),
                **self.processor_kwargs
            )
            
            # 处理文件
            self.logger.info(f"[{model_config.model_id}] 开始处理: {file_path}")
            result = processor.process_file(file_path, output_file)
            
            # 更新统计信息
            with self.stats_lock:
                if result["success"]:
                    self.stats["processed_files"] += 1
                    self.stats["total_tokens"] += result.get("tokens_used", 0)
                    self.stats["model_stats"][model_config.model_id]["processed"] += 1
                    self.stats["model_stats"][model_config.model_id]["tokens"] += result.get("tokens_used", 0)
                    model_config.completed_tasks += 1
                else:
                    self.stats["failed_files"] += 1
                    self.stats["model_stats"][model_config.model_id]["failed"] += 1
                    model_config.completed_tasks += 1
                
                self.stats["file_results"].append({
                    **result,
                    "model_id": model_config.model_id
                })
            
            if result["success"]:
                self.logger.info(
                    f"[{model_config.model_id}] ✅ 处理成功: {file_path} "
                    f"(tokens: {result.get('tokens_used', 0)})"
                )
            else:
                self.logger.error(
                    f"[{model_config.model_id}] ❌ 处理失败: {file_path} - "
                    f"{result.get('error_msg', '未知错误')}"
                )
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"[{model_config.model_id}] 处理异常: {file_path} - {error_msg}")
            
            with self.stats_lock:
                self.stats["failed_files"] += 1
                self.stats["model_stats"][model_config.model_id]["failed"] += 1
                model_config.completed_tasks += 1
                self.stats["file_results"].append({
                    "file_path": str(file_path),
                    "success": False,
                    "error_msg": error_msg,
                    "model_id": model_config.model_id
                })
            
            return {
                "file_path": str(file_path),
                "success": False,
                "error_msg": error_msg,
                "model_id": model_config.model_id
            }
        finally:
            model_config.current_tasks -= 1
    
    def _worker_thread(
        self,
        worker_id: int,
        progress_bar: Optional[tqdm] = None
    ):
        """
        工作线程函数
        
        Args:
            worker_id: 工作线程 ID
            progress_bar: 进度条对象
        """
        while True:
            try:
                # 从队列获取任务（超时1秒，避免无限阻塞）
                task = self.task_queue.get(timeout=1)
                if task is None:  # 结束信号
                    break
                
                file_path, output_file = task
                
                # 选择模型（负载均衡）
                model_config = self._get_next_model()
                
                # 处理文件
                result = self._process_file_with_model(file_path, model_config, output_file)
                
                # 更新进度条
                if progress_bar:
                    progress_bar.update(1)
                    if result["success"]:
                        progress_bar.set_postfix({
                            "成功": self.stats["processed_files"],
                            "失败": self.stats["failed_files"]
                        })
                
                self.task_queue.task_done()
                
            except Empty:
                # 队列为空，继续等待（这是正常的超时情况）
                continue
            except Exception as e:
                # 其他异常，记录错误并继续
                self.logger.error(f"工作线程 {worker_id} 错误: {e}", exc_info=True)
                # 如果已经获取了任务，需要标记为完成
                try:
                    self.task_queue.task_done()
                except ValueError:
                    # 如果 task_done() 被调用次数超过 put() 次数，忽略错误
                    pass
    
    def process_batch(
        self,
        file_paths: List[Union[str, Path]],
        output_dir: Optional[Union[str, Path]] = None,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        并行批量处理多个文件
        
        Args:
            file_paths: 文件路径列表
            output_dir: 输出目录（可选）
            continue_on_error: 遇到错误时是否继续处理其他文件
            
        Returns:
            批量处理结果字典
        """
        if output_dir:
            self.output_dir = Path(output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        batch_start_time = time.time()
        self.stats = {
            "total_files": len(file_paths),
            "processed_files": 0,
            "failed_files": 0,
            "total_tokens": 0,
            "total_time": 0,
            "file_results": [],
            "model_stats": {config.model_id: {
                "processed": 0,
                "failed": 0,
                "tokens": 0
            } for config in self.model_configs}
        }
        
        self.logger.info("=" * 80)
        self.logger.info("开始并行批量处理")
        self.logger.info(f"文件数量: {len(file_paths)}")
        self.logger.info(f"模型数量: {len(self.model_configs)}")
        self.logger.info(f"Batch size: {self.batch_size}")
        self.logger.info(f"最大工作线程数: {self.max_workers}")
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info("=" * 80)
        
        # 验证文件
        valid_files = []
        for file_path in file_paths:
            file_path = Path(file_path)
            if not file_path.exists():
                self.logger.warning(f"跳过不存在的文件: {file_path}")
                continue
            
            valid_extensions = ['.txt', '.json', '.jsonl', '.csv']
            if not any(file_path.suffix.lower() == ext for ext in valid_extensions):
                self.logger.warning(f"跳过不支持的文件类型: {file_path}")
                continue
            
            valid_files.append(file_path)
        
        if not valid_files:
            self.logger.error("没有找到有效的文件进行处理")
            return {
                "success": False,
                "error": "没有有效的文件",
                "stats": self.stats
            }
        
        self.stats["total_files"] = len(valid_files)
        
        # 将所有任务放入队列
        for file_path in valid_files:
            self.task_queue.put((file_path, None))
        
        # 创建进度条
        pbar = tqdm(total=len(valid_files), desc="并行批量处理", unit="文件")
        
        # 创建工作线程
        threads = []
        for i in range(self.max_workers):
            thread = threading.Thread(
                target=self._worker_thread,
                args=(i, pbar),
                daemon=True,
                name=f"Worker-{i}"
            )
            thread.start()
            threads.append(thread)
        
        # 等待所有任务完成
        self.task_queue.join()
        
        # 发送结束信号
        for _ in range(self.max_workers):
            self.task_queue.put(None)
        
        # 等待所有线程结束
        for thread in threads:
            thread.join(timeout=5)
        
        pbar.close()
        
        # 计算总时间
        self.stats["total_time"] = time.time() - batch_start_time
        
        # 打印总结
        self.logger.info("=" * 80)
        self.logger.info("并行批量处理完成")
        self.logger.info(f"总文件数: {self.stats['total_files']}")
        self.logger.info(f"成功处理: {self.stats['processed_files']}")
        self.logger.info(f"处理失败: {self.stats['failed_files']}")
        self.logger.info(f"总 token 使用量: {self.stats['total_tokens']}")
        self.logger.info(f"总处理时间: {self.stats['total_time']:.2f}秒")
        
        # 各模型统计
        self.logger.info("\n各模型处理统计:")
        for model_id, model_stat in self.stats["model_stats"].items():
            self.logger.info(
                f"  {model_id}: "
                f"成功 {model_stat['processed']}, "
                f"失败 {model_stat['failed']}, "
                f"Tokens {model_stat['tokens']}"
            )
        
        if self.stats["processed_files"] > 0:
            avg_time = self.stats["total_time"] / self.stats["processed_files"]
            self.logger.info(f"平均处理时间: {avg_time:.2f}秒/文件")
        
        self.logger.info("=" * 80)
        
        return {
            "success": self.stats["failed_files"] == 0,
            "stats": self.stats
        }
    
    def save_results(self, output_file: Optional[Union[str, Path]] = None):
        """
        保存处理结果到 JSON 文件
        
        Args:
            output_file: 输出文件路径（可选，默认自动生成）
        """
        if output_file is None:
            output_file = self.output_dir / f"parallel_batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            output_file = Path(output_file)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"处理结果已保存到: {output_file}")
        return output_file


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="TextGraphTree 并行批量处理脚本 - 支持多模型并行处理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:

  # 使用多个模型并行处理
  python batch_process_parallel.py -i file1.txt file2.txt -c config.json

  # 使用配置文件（包含多个模型配置）
  python batch_process_parallel.py -c config.json -b 2

  # 从文件列表批量处理
  python batch_process_parallel.py -l file_list.txt -c config.json --batch-size 3
        """
    )
    
    # 输入参数组
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input-files", nargs='+', help="输入文件路径列表")
    input_group.add_argument("-l", "--file-list", help="包含文件路径列表的文本文件")
    input_group.add_argument("-c", "--config", help="配置文件路径 (JSON 格式)")
    
    # 模型配置
    parser.add_argument("-m", "--models-config", help="模型配置文件路径 (JSON 格式，包含模型列表)")
    
    # 并行配置
    parser.add_argument("-b", "--batch-size", type=int, default=1,
                      help="每个模型同时处理的任务数 (默认: 1)")
    parser.add_argument("-w", "--max-workers", type=int, default=None,
                      help="最大工作线程数 (默认: 模型数量 * batch_size)")
    
    # 输出配置
    parser.add_argument("-o", "--output-dir", default="tasks/outputs",
                      help="输出目录 (默认: tasks/outputs)")
    
    args = parser.parse_args()
    
    # 加载环境变量
    load_dotenv()
    
    # 加载模型配置
    if args.models_config:
        with open(args.models_config, 'r', encoding='utf-8') as f:
            models_data = json.load(f)
            if isinstance(models_data, list):
                model_configs = models_data
            elif isinstance(models_data, dict) and "models" in models_data:
                model_configs = models_data["models"]
            else:
                print("❌ 错误: 模型配置文件格式不正确")
                sys.exit(1)
    else:
        # 默认使用单个模型（从环境变量）
        model_configs = [{
            "api_key": os.getenv("SYNTHESIZER_API_KEY", ""),
            "synthesizer_url": os.getenv("SYNTHESIZER_BASE_URL", "https://api.huiyan-ai.cn/v1"),
            "synthesizer_model": os.getenv("SYNTHESIZER_MODEL", "gpt-4.1-mini-2025-04-14"),
        }]
    
    if not model_configs:
        print("❌ 错误: 未提供模型配置")
        sys.exit(1)
    
    # 确定输入文件
    if args.input_files:
        file_paths = args.input_files
    elif args.file_list:
        with open(args.file_list, 'r', encoding='utf-8') as f:
            file_paths = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    elif args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
            file_paths = config.get("file_paths", [])
            # 如果配置文件中有模型配置，使用它
            if "models" in config:
                model_configs = config["models"]
    else:
        print("❌ 错误: 未指定输入文件")
        sys.exit(1)
    
    # 创建并行处理器
    processor = ParallelBatchProcessor(
        model_configs=model_configs,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        output_data_type=os.getenv("OUTPUT_DATA_TYPE", "aggregated"),  # pragma: allowlist secret
        output_data_format=os.getenv("OUTPUT_DATA_FORMAT", "Alpaca"),
    )
    
    # 处理文件
    result = processor.process_batch(file_paths)
    
    # 保存结果
    processor.save_results()
    
    # 打印总结
    print("\n" + "=" * 60)
    print("📊 并行批量处理总结:")
    print(f"   总文件数: {result['stats']['total_files']}")
    print(f"   成功处理: {result['stats']['processed_files']}")
    print(f"   处理失败: {result['stats']['failed_files']}")
    print(f"   总 token 使用量: {result['stats']['total_tokens']}")
    print(f"   总处理时间: {result['stats']['total_time']:.2f}秒")
    print("=" * 60)
    
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()

