#!/usr/bin/env python3
"""
TextGraphTree 命令行工具
将 TextGraphTree Demo web app 转换为命令行脚本版本
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from importlib.resources import files

import pandas as pd
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

from textgraphtree.engine import TextGraphTree
from textgraphtree.models import OpenAIClient, Tokenizer
from textgraphtree.models.llm.limitter import RPM, TPM
from textgraphtree.models.llm.llm_env import load_merged_extra_body
from textgraphtree.utils import set_logger
from backend.runtime import cleanup_workspace, setup_workspace

# TGT imports
from textgraphtree.tgt_pipeline import TGTPipeline
from textgraphtree.models.taxonomy.taxonomy_tree import TaxonomyTree
from textgraphtree.models.storage.networkx_storage import NetworkXStorage
from textgraphtree.utils.tgt_metrics import TGMetrics


class TextGraphTreeCLI:
    """TextGraphTree 命令行接口类"""
    
    def __init__(self):
        self.root_dir = str(files("textgraphtree").parent)
        sys.path.append(self.root_dir)
        load_dotenv()
        self.batch_logger = None
        self.batch_stats = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "total_tokens": 0,
            "total_time": 0,
            "file_stats": []
        }
        
    def test_api_connection(self, api_base: str, api_key: str, model_name: str) -> bool:
        """测试 API 连接"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=api_base)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1  # pragma: allowlist secret
            )
            if not response.choices or not response.choices[0].message:
                print(f"❌ {model_name}: API 响应无效")
                return False
            print(f"✅ {model_name}: API 连接成功")
            return True
        except Exception as e:
            print(f"❌ {model_name}: API 连接失败: {str(e)}")
            return False
    
    def init_graph_gen(self, config: dict, env: dict) -> TextGraphTree:
        """初始化 TextGraphTree 实例"""
        # 设置工作目录
        log_file, working_dir = setup_workspace(os.path.join(self.root_dir, "cache"))
        set_logger(log_file, if_stream=True)
        os.environ.update({k: str(v) for k, v in env.items()})

        # 创建 tokenizer 和 LLM 客户端
        tokenizer_instance = Tokenizer(config.get("tokenizer", "cl100k_base"))  # pragma: allowlist secret
        synthesizer_llm_client = OpenAIClient(
            model_name=env.get("SYNTHESIZER_MODEL", ""),
            base_url=env.get("SYNTHESIZER_BASE_URL", ""),
            api_key=env.get("SYNTHESIZER_API_KEY", ""),
            request_limit=True,
            rpm=RPM(env.get("RPM", 1000)),
            tpm=TPM(env.get("TPM", 50000)),
            tokenizer=tokenizer_instance,
            extra_body=load_merged_extra_body(
                "LLM_EXTRA_BODY_JSON", "SYNTHESIZER_EXTRA_BODY_JSON"
            ),
        )

        trainee_llm_client = OpenAIClient(
            model_name=env.get("TRAINEE_MODEL", ""),
            base_url=env.get("TRAINEE_BASE_URL", ""),
            api_key=env.get("TRAINEE_API_KEY", ""),
            request_limit=True,
            rpm=RPM(env.get("RPM", 1000)),
            tpm=TPM(env.get("TPM", 50000)),
            tokenizer=tokenizer_instance,
            extra_body=load_merged_extra_body(
                "LLM_EXTRA_BODY_JSON", "TRAINEE_EXTRA_BODY_JSON"
            ),
        )

        # 创建 TextGraphTree 实例（传递 synthesizer_llm_client 和 trainee_llm_client）
        graph_gen = TextGraphTree(
            working_dir=working_dir,
            tokenizer_instance=tokenizer_instance,
            synthesizer_llm_client=synthesizer_llm_client,
            trainee_llm_client=trainee_llm_client,
        )

        return graph_gen
    
    def count_tokens(self, file_path: str, tokenizer_name: str) -> tuple:
        """计算文件中的 token 数量"""
        if not file_path or not os.path.exists(file_path):
            return 0, 0

        if file_path.endswith(".jsonl"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f]
        elif file_path.endswith(".json"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                data = [item for sublist in data for item in sublist]
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
                chunks = [data[i : i + 512] for i in range(0, len(data), 512)]
                data = [{"content": chunk} for chunk in chunks]
        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            if "content" in df.columns:
                data = df["content"].tolist()
            else:
                data = df.iloc[:, 0].tolist()
        else:
            raise ValueError(f"不支持的文件类型: {file_path}")

        tokenizer = Tokenizer(tokenizer_name)

        # 计算 token 数量
        token_count = 0
        for item in data:
            if isinstance(item, dict):
                content = item.get("content", "")
            else:
                content = item
            token_count += len(tokenizer.encode_string(content))

        estimated_usage = token_count * 50  # 估算使用量
        return token_count, estimated_usage
    
    def setup_batch_logging(self, log_file: str):
        """设置批量处理日志"""
        self.batch_logger = logging.getLogger('batch_processing')
        self.batch_logger.setLevel(logging.INFO)
        
        # 清除现有的处理器
        for handler in self.batch_logger.handlers[:]:
            self.batch_logger.removeHandler(handler)
        
        # 创建文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        
        self.batch_logger.addHandler(file_handler)
        
        # 记录开始信息
        self.batch_logger.info("=" * 80)
        self.batch_logger.info("TextGraphTree 批量处理开始")
        self.batch_logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.batch_logger.info("=" * 80)
    
    def log_batch_config(self, args):
        """记录批量处理配置"""
        if not self.batch_logger:
            return
            
        config_info = {
            "模型配置": {
                "使用Trainee模型": args.use_trainee_model,
                "Synthesizer URL": args.synthesizer_url,
                "Synthesizer 模型": args.synthesizer_model,
                "Trainee URL": args.trainee_url,
                "Trainee 模型": args.trainee_model,
            },
            "生成配置": {
                "文本块大小": args.chunk_size,
                "文本块重叠": args.chunk_overlap,
                "Tokenizer": args.tokenizer,
                "输出数据类型": args.output_data_type,
                "输出数据格式": args.output_data_format,
                "测验样本数": args.quiz_samples,
            },
            "遍历策略": {
                "双向遍历": args.bidirectional,
                "扩展方法": args.expand_method,
                "最大额外边数": args.max_extra_edges,
                "最大token数": args.max_tokens,  # pragma: allowlist secret
                "最大深度": args.max_depth,
                "边采样策略": args.edge_sampling,
                "孤立节点策略": args.isolated_node_strategy,
                "损失策略": args.loss_strategy,
            },
            "限制配置": {
                "每分钟请求数": args.rpm,
                "每分钟token数": args.tpm,
            }
        }
        
        self.batch_logger.info("批量处理配置:")
        for category, settings in config_info.items():
            self.batch_logger.info(f"  {category}:")
            for key, value in settings.items():
                self.batch_logger.info(f"    {key}: {value}")
    
    def log_file_result(self, file_path: str, success: bool, tokens_used: int, 
                       synthesizer_tokens: int, trainee_tokens: int, 
                       processing_time: float, output_file: str = None, error_msg: str = None):
        """记录单个文件的处理结果"""
        if not self.batch_logger:
            return
            
        self.batch_logger.info("-" * 60)
        self.batch_logger.info(f"文件: {file_path}")
        self.batch_logger.info(f"处理状态: {'成功' if success else '失败'}")
        
        if success:
            self.batch_logger.info(f"输出文件: {output_file}")
            self.batch_logger.info(f"总token使用量: {tokens_used}")
            self.batch_logger.info(f"Synthesizer tokens: {synthesizer_tokens}")
            self.batch_logger.info(f"Trainee tokens: {trainee_tokens}")
            self.batch_logger.info(f"处理时间: {processing_time:.2f}秒")
        else:
            self.batch_logger.info(f"错误信息: {error_msg}")
        
        # 更新统计信息
        self.batch_stats["file_stats"].append({
            "file_path": file_path,
            "success": success,
            "tokens_used": tokens_used,
            "synthesizer_tokens": synthesizer_tokens,
            "trainee_tokens": trainee_tokens,
            "processing_time": processing_time,
            "output_file": output_file,
            "error_msg": error_msg
        })
        
        if success:
            self.batch_stats["processed_files"] += 1
            self.batch_stats["total_tokens"] += tokens_used
        else:
            self.batch_stats["failed_files"] += 1
    
    def log_batch_summary(self):
        """记录批量处理总结"""
        if not self.batch_logger:
            return
            
        self.batch_logger.info("=" * 80)
        self.batch_logger.info("批量处理总结")
        self.batch_logger.info(f"总文件数: {self.batch_stats['total_files']}")
        self.batch_logger.info(f"成功处理: {self.batch_stats['processed_files']}")
        self.batch_logger.info(f"处理失败: {self.batch_stats['failed_files']}")
        self.batch_logger.info(f"总token使用量: {self.batch_stats['total_tokens']}")
        self.batch_logger.info(f"总处理时间: {self.batch_stats['total_time']:.2f}秒")
        
        if self.batch_stats["processed_files"] > 0:
            avg_time = self.batch_stats["total_time"] / self.batch_stats["processed_files"]
            self.batch_logger.info(f"平均处理时间: {avg_time:.2f}秒/文件")
        
        self.batch_logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.batch_logger.info("=" * 80)
    
    def process_single_file(self, file_path: str, args, progress_bar=None) -> dict:
        """处理单个文件"""
        start_time = time.time()
        result = {
            "file_path": file_path,
            "success": False,
            "tokens_used": 0,
            "synthesizer_tokens": 0,
            "trainee_tokens": 0,
            "processing_time": 0,
            "output_file": None,
            "error_msg": None
        }
        
        try:
            # 更新进度条描述
            if progress_bar:
                progress_bar.set_description(f"处理 {os.path.basename(file_path)}")
            
            # 构建配置
            config = {
                "if_trainee_model": args.use_trainee_model,
                "read": {
                    "input_file": file_path,
                },
                "split": {
                    "chunk_size": args.chunk_size,
                    "chunk_overlap": args.chunk_overlap,
                    # 批量请求优化
                    "enable_batch_requests": True,
                    "batch_size": 30,
                    "max_wait_time": 1.0,
                    "use_adaptive_batching": True,
                    "min_batch_size": 10,
                    "max_batch_size": 50,
                    "enable_extraction_cache": True,
                    # Prompt合并优化
                    "enable_prompt_merging": True,
                    "prompt_merge_size": 5,
                },
                "output_data_type": args.output_data_type,
                "output_data_format": args.output_data_format,
                "tokenizer": args.tokenizer,
                "search": {"enabled": False},
                "quiz_and_judge": {
                    "enabled": args.use_trainee_model,
                    "quiz_samples": args.quiz_samples,
                    "re_judge": False,
                    # 批量请求优化
                    "enable_batch_requests": True,
                    "batch_size": 30,
                    "max_wait_time": 1.0,
                },
                "traverse_strategy": {
                    "bidirectional": args.bidirectional,
                    "expand_method": args.expand_method,
                    "max_extra_edges": args.max_extra_edges,
                    "max_tokens": args.max_tokens,  # pragma: allowlist secret
                    "max_depth": args.max_depth,
                    "edge_sampling": args.edge_sampling,
                    "isolated_node_strategy": args.isolated_node_strategy,
                    "loss_strategy": args.loss_strategy,
                },
            }

            env = {
                "SYNTHESIZER_BASE_URL": args.synthesizer_url,
                "SYNTHESIZER_MODEL": args.synthesizer_model,
                "TRAINEE_BASE_URL": args.trainee_url,
                "TRAINEE_MODEL": args.trainee_model,
                "SYNTHESIZER_API_KEY": args.api_key,
                "TRAINEE_API_KEY": args.trainee_api_key,
                "RPM": args.rpm,
                "TPM": args.tpm,
            }

            # 初始化 TextGraphTree
            graph_gen = self.init_graph_gen(config, env)
            graph_gen.clear()

            # 处理数据
            graph_gen.insert(
                read_config=config["read"],
                split_config=config["split"]
            )

            # 构建 quiz_and_judge 配置
            quiz_and_judge_config = {
                "enabled": config["if_trainee_model"],
                "quiz_samples": config["quiz_and_judge"]["quiz_samples"],
                "re_judge": False,
                # 批量请求优化
                "enable_batch_requests": config["quiz_and_judge"].get("enable_batch_requests", True),
                "batch_size": config["quiz_and_judge"].get("batch_size", 30),
                "max_wait_time": config["quiz_and_judge"].get("max_wait_time", 1.0),
            }
            
            if quiz_and_judge_config["enabled"]:
                graph_gen.quiz_and_judge(quiz_and_judge_config=quiz_and_judge_config)

            # 构建 partition 配置（使用 ECE 方法）
            traverse_strategy = config.get("traverse_strategy", {})
            edge_sampling = traverse_strategy.get("edge_sampling", "max_loss")  # pragma: allowlist secret
            
            # 如果 unit_sampling 不是 "random" 但没有使用 trainee 模型，则使用 "random"
            # 因为 min_loss 和 max_loss 需要 quiz_and_judge 来获取 loss 值  # pragma: allowlist secret
            if edge_sampling in ["min_loss", "max_loss"] and not config["if_trainee_model"]:  # pragma: allowlist secret
                edge_sampling = "random"
            
            partition_config = {
                "method": "ece",
                "method_params": {
                    "max_units_per_community": traverse_strategy.get("max_extra_edges", 5) + 10,
                    "min_units_per_community": 3,
                    "max_tokens_per_community": traverse_strategy.get("max_tokens", 256) * 40,  # pragma: allowlist secret
                    "unit_sampling": edge_sampling,
                }
            }

            # 构建 generate 配置
            generate_config = {
                "mode": config["output_data_type"],  # 支持 "atomic", "multi_hop", "aggregated", "cot", "all"  # pragma: allowlist secret
                "data_format": config["output_data_format"],
                # 优化配置
                "use_multi_template": True,
                "template_seed": None,
                "chinese_only": getattr(args, "chinese_only", False),
                # 批量请求配置
                "enable_batch_requests": True,
                "batch_size": 30,
                "max_wait_time": 1.0,
                "use_adaptive_batching": True,
                "min_batch_size": 10,
                "max_batch_size": 50,
                # 缓存优化
                "enable_prompt_cache": True,
                "cache_max_size": 50000,
                "cache_ttl": None,
                # 合并模式优化
                "use_combined_mode": True,
                # 去重优化
                "enable_deduplication": True,
                "persistent_deduplication": True,
                # 生成数量与比例
                "target_qa_pairs": getattr(args, "qa_pair_limit", None),
                "mode_ratios": {
                    "atomic": 25.0,
                    "aggregated": 25.0,  # pragma: allowlist secret
                    "multi_hop": 25.0,
                    "cot": 25.0,
                },
            }

            # 生成问答对
            graph_gen.generate(
                partition_config=partition_config,
                generate_config=generate_config
            )

            # 保存输出
            output_data = graph_gen.qa_storage.data
            
            # 确定输出文件名
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_file = f"{base_name}_textgraphtree_output.jsonl"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            # 计算实际使用的 token
            synthesizer_tokens = sum(u["total_tokens"] for u in graph_gen.synthesizer_llm_client.token_usage)
            trainee_tokens = sum(u["total_tokens"] for u in graph_gen.trainee_llm_client.token_usage) if config["if_trainee_model"] else 0
            total_tokens = synthesizer_tokens + trainee_tokens

            processing_time = time.time() - start_time
            
            result.update({
                "success": True,
                "tokens_used": total_tokens,
                "synthesizer_tokens": synthesizer_tokens,
                "trainee_tokens": trainee_tokens,
                "processing_time": processing_time,
                "output_file": output_file
            })

            # 清理工作空间
            cleanup_workspace(graph_gen.working_dir)

        except Exception as e:
            processing_time = time.time() - start_time
            result.update({
                "processing_time": processing_time,
                "error_msg": str(e)
            })
            
            if progress_bar:
                progress_bar.set_description(f"失败: {os.path.basename(file_path)}")

        return result
    
    def run_batch_processing(self, args):
        """运行批量处理"""
        batch_start_time = time.time()
        
        # 设置批量处理日志
        log_file = f"textgraphtree_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self.setup_batch_logging(log_file)
        
        # 记录配置
        self.log_batch_config(args)
        
        # 验证所有文件
        valid_files = []
        for file_path in args.input_files:
            if not os.path.exists(file_path):
                print(f"⚠️  跳过不存在的文件: {file_path}")
                continue
            
            valid_extensions = ['.txt', '.json', '.jsonl', '.csv']
            if not any(file_path.endswith(ext) for ext in valid_extensions):
                print(f"⚠️  跳过不支持的文件类型: {file_path}")
                continue
                
            valid_files.append(file_path)
        
        if not valid_files:
            print("❌ 没有找到有效的文件进行处理")
            return False
        
        self.batch_stats["total_files"] = len(valid_files)
        
        print(f"🚀 开始批量处理 {len(valid_files)} 个文件...")
        print(f"📝 日志文件: {log_file}")
        
        # 测试 API 连接
        print("🔗 测试 API 连接...")
        if not self.test_api_connection(args.synthesizer_url, args.api_key, args.synthesizer_model):
            return False
            
        if args.use_trainee_model:
            if not self.test_api_connection(args.trainee_url, args.trainee_api_key, args.trainee_model):
                return False
        
        # 使用进度条处理文件
        with tqdm(total=len(valid_files), desc="批量处理", unit="文件") as pbar:
            for file_path in valid_files:
                result = self.process_single_file(file_path, args, pbar)
                
                # 记录结果
                self.log_file_result(
                    result["file_path"], 
                    result["success"],
                    result["tokens_used"],
                    result["synthesizer_tokens"],
                    result["trainee_tokens"],
                    result["processing_time"],
                    result["output_file"],
                    result["error_msg"]
                )
                
                pbar.update(1)
        
        # 记录总结
        self.batch_stats["total_time"] = time.time() - batch_start_time
        self.log_batch_summary()
        
        # 打印总结
        print("\n" + "=" * 60)
        print("📊 批量处理总结:")
        print(f"   总文件数: {self.batch_stats['total_files']}")
        print(f"   成功处理: {self.batch_stats['processed_files']}")
        print(f"   处理失败: {self.batch_stats['failed_files']}")
        print(f"   总token使用量: {self.batch_stats['total_tokens']}")
        print(f"   总处理时间: {self.batch_stats['total_time']:.2f}秒")
        print(f"   日志文件: {log_file}")
        print("=" * 60)
        
        return self.batch_stats["failed_files"] == 0
    
    def run_graphgen(self, args):
        """运行 TextGraphTree 主流程"""
        print("🚀 开始运行 TextGraphTree...")
        
        # 构建配置
        config = {
            "if_trainee_model": args.use_trainee_model,
            "read": {
                "input_file": args.input_file,
            },
            "split": {
                "chunk_size": args.chunk_size,
                "chunk_overlap": args.chunk_overlap,
                # 批量请求优化
                "enable_batch_requests": True,
                "batch_size": 30,
                "max_wait_time": 1.0,
                "use_adaptive_batching": True,
                "min_batch_size": 10,
                "max_batch_size": 50,
                "enable_extraction_cache": True,
                # Prompt合并优化
                "enable_prompt_merging": True,
                "prompt_merge_size": 5,
            },
            "output_data_type": args.output_data_type,
            "output_data_format": args.output_data_format,
            "tokenizer": args.tokenizer,
            "search": {"enabled": False},
            "quiz_and_judge": {
                "enabled": args.use_trainee_model,
                "quiz_samples": args.quiz_samples,
                "re_judge": False,
                # 批量请求优化
                "enable_batch_requests": True,
                "batch_size": 30,
                "max_wait_time": 1.0,
            },
            "traverse_strategy": {
                "bidirectional": args.bidirectional,
                "expand_method": args.expand_method,
                "max_extra_edges": args.max_extra_edges,
                "max_tokens": args.max_tokens,  # // pragma: allowlist secret
                "max_depth": args.max_depth,
                "edge_sampling": args.edge_sampling,
                "isolated_node_strategy": args.isolated_node_strategy,
                "loss_strategy": args.loss_strategy,
            },
        }

        env = {
            "SYNTHESIZER_BASE_URL": args.synthesizer_url,
            "SYNTHESIZER_MODEL": args.synthesizer_model,
            "TRAINEE_BASE_URL": args.trainee_url,
            "TRAINEE_MODEL": args.trainee_model,
            "SYNTHESIZER_API_KEY": args.api_key,
            "TRAINEE_API_KEY": args.trainee_api_key,
            "RPM": args.rpm,
            "TPM": args.tpm,
        }
        graph_gen = self.init_graph_gen(config, env)

        # 测试 API 连接
        print("🔗 测试 API 连接...")
        if not self.test_api_connection(env["SYNTHESIZER_BASE_URL"], env["SYNTHESIZER_API_KEY"], env["SYNTHESIZER_MODEL"]):
            return False
            
        if config["if_trainee_model"]:
            if not self.test_api_connection(env["TRAINEE_BASE_URL"], env["TRAINEE_API_KEY"], env["TRAINEE_MODEL"]):
                return False

        # 计算 token 使用量
        print("📊 计算 token 使用量...")
        token_count, estimated_usage = self.count_tokens(args.input_file, args.tokenizer)
        print(f"📝 源文本 token 数量: {token_count}")
        print(f"📈 预计 token 使用量: {estimated_usage}")

        # 初始化 TextGraphTree
        print("🔧 初始化 TextGraphTree...")
       
        graph_gen.clear()

        try:
            # 处理数据
            print("📖 处理输入数据...")
            graph_gen.insert(
                read_config=config["read"],
                split_config=config["split"]
            )

            # 构建 quiz_and_judge 配置
            quiz_and_judge_config = {
                "enabled": config["if_trainee_model"],
                "quiz_samples": config["quiz_and_judge"]["quiz_samples"],
                "re_judge": False,
                # 批量请求优化
                "enable_batch_requests": config["quiz_and_judge"].get("enable_batch_requests", True),
                "batch_size": config["quiz_and_judge"].get("batch_size", 30),
                "max_wait_time": config["quiz_and_judge"].get("max_wait_time", 1.0),
            }
            
            if quiz_and_judge_config["enabled"]:
                # 生成测验和判断
                print("❓ 生成测验和判断...")
                graph_gen.quiz_and_judge(quiz_and_judge_config=quiz_and_judge_config)

            # 构建 partition 配置（使用 ECE 方法）
            traverse_strategy = config.get("traverse_strategy", {})
            edge_sampling = traverse_strategy.get("edge_sampling", "max_loss")  # pragma: allowlist secret
            
            # 如果 unit_sampling 不是 "random" 但没有使用 trainee 模型，则使用 "random"
            # 因为 min_loss 和 max_loss 需要 quiz_and_judge 来获取 loss 值  # // pragma: allowlist secret
            if edge_sampling in ["min_loss", "max_loss"] and not config["if_trainee_model"]:
                edge_sampling = "random"
            
            partition_config = {
                "method": "ece",
                "method_params": {
                    "max_units_per_community": traverse_strategy.get("max_extra_edges", 5) + 10,
                    "min_units_per_community": 3,
                    "max_tokens_per_community": traverse_strategy.get("max_tokens", 256) * 40,
                    "unit_sampling": edge_sampling,
                }
            }

            # 构建 generate 配置
            generate_config = {
                "mode": config["output_data_type"],  # 支持 "atomic", "multi_hop", "aggregated", "cot", "all"  # pragma: allowlist secret
                "data_format": config["output_data_format"],
                # 优化配置
                "use_multi_template": True,
                "template_seed": None,
                "chinese_only": getattr(args, "chinese_only", False),
                # 批量请求配置
                "enable_batch_requests": True,
                "batch_size": 30,
                "max_wait_time": 1.0,
                "use_adaptive_batching": True,
                "min_batch_size": 10,
                "max_batch_size": 50,
                # 缓存优化
                "enable_prompt_cache": True,
                "cache_max_size": 50000,
                "cache_ttl": None,
                # 合并模式优化
                "use_combined_mode": True,
                # 去重优化
                "enable_deduplication": True,
                "persistent_deduplication": True,
                # 生成数量与比例
                "target_qa_pairs": getattr(args, "qa_pair_limit", None),
                "mode_ratios": {
                    "atomic": 25.0,
                    "aggregated": 25.0,  # pragma: allowlist secret
                    "multi_hop": 25.0,
                    "cot": 25.0,
                },
            }

            # 生成问答对
            print("🔄 生成问答对...")
            graph_gen.generate(
                partition_config=partition_config,
                generate_config=generate_config
            )

            # 保存输出
            print("💾 保存输出...")
            output_data = graph_gen.qa_storage.data
            
            # 确定输出文件名
            if args.output_file:
                output_file = args.output_file
            else:
                base_name = os.path.splitext(os.path.basename(args.input_file))[0]
                output_file = f"{base_name}_textgraphtree_output.jsonl"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            # 计算实际使用的 token
            synthesizer_tokens = sum(u["total_tokens"] for u in graph_gen.synthesizer_llm_client.token_usage)
            trainee_tokens = sum(u["total_tokens"] for u in graph_gen.trainee_llm_client.token_usage) if config["if_trainee_model"] else 0
            total_tokens = synthesizer_tokens + trainee_tokens

            print("✅ TextGraphTree 运行完成!")
            print(f"📁 输出文件: {output_file}")
            print(f"🔢 实际使用 token: {total_tokens}")
            print(f"📊 Synthesizer tokens: {synthesizer_tokens}")
            if config["if_trainee_model"]:
                print(f"📊 Trainee tokens: {trainee_tokens}")

            return True

        except Exception as e:
            print(f"❌ 运行出错: {str(e)}")
            return False

        finally:
            # 清理工作空间
            cleanup_workspace(graph_gen.working_dir)

    def run_tgt(self, args):
        """运行 TGT 管道"""
        print("🚀 开始运行 TGT 管道...")

        # Load config
        with open(args.tgt_config, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        tgt_config = config_data.get("tgt", config_data)

        # Setup working directory
        log_file, working_dir = setup_workspace(os.path.join(self.root_dir, "cache"))
        set_logger(log_file, if_stream=True)

        # Get environment variables for LLM client
        env = {
            "SYNTHESIZER_BASE_URL": os.environ.get("SYNTHESIZER_BASE_URL", ""),
            "SYNTHESIZER_MODEL": os.environ.get("SYNTHESIZER_MODEL", ""),
            "SYNTHESIZER_API_KEY": os.environ.get("SYNTHESIZER_API_KEY", ""),
            "RPM": os.environ.get("RPM", "1000"),
            "TPM": os.environ.get("TPM", "50000"),
        }

        # Setup LLM client
        tokenizer_instance = Tokenizer(config_data.get("tokenizer", "cl100k_base"))  # pragma: allowlist secret
        llm_client = OpenAIClient(
            model_name=env.get("SYNTHESIZER_MODEL", ""),
            base_url=env.get("SYNTHESIZER_BASE_URL", ""),
            api_key=env.get("SYNTHESIZER_API_KEY", ""),
            request_limit=True,
            rpm=RPM(env.get("RPM", 1000)),
            tpm=TPM(env.get("TPM", 50000)),
            tokenizer=tokenizer_instance,
            extra_body=load_merged_extra_body(
                "LLM_EXTRA_BODY_JSON", "SYNTHESIZER_EXTRA_BODY_JSON"
            ),
        )

        # Build or load KG
        graph_storage = None
        if args.input_file:
            print(f"📖 从输入文件构建知识图谱: {args.input_file}")
            graph_gen = TextGraphTree(
                working_dir=working_dir,
                tokenizer_instance=tokenizer_instance,
                synthesizer_llm_client=llm_client,
            )
            graph_gen.clear()
            read_config = {"input_file": args.input_file}
            split_config = {
                "chunk_size": 1024,
                "chunk_overlap": 50,
            }
            graph_gen.insert(read_config=read_config, split_config=split_config)
            graph_storage = graph_gen.graph_storage
            print("✅ 知识图谱构建完成")
        elif args.kg_path:
            print(f"📖 从文件加载知识图谱: {args.kg_path}")
            graph_storage = NetworkXStorage()
            try:
                graph_storage.load(args.kg_path)
            except:
                pass
        else:
            print("❌ 错误: 需要提供 --input-file 或 --kg-path")
            return False

        # Load taxonomy
        taxonomy_config = tgt_config.get("taxonomy", {})
        taxonomy_path = taxonomy_config.get("path")
        if not taxonomy_path or not os.path.exists(taxonomy_path):
            print(f"❌ 错误: 意图树文件不存在: {taxonomy_path}")
            return False

        print(f"📖 加载意图树: {taxonomy_path}")
        tree = TaxonomyTree.load(taxonomy_path)
        print(f"✅ 意图树加载完成: {tree.name} ({tree.size} 节点)")

        # Create and run pipeline
        print("🔧 初始化 TGT 管道...")
        pipeline = TGTPipeline.from_config(args.tgt_config, llm_client, graph_storage)

        # Run pipeline
        target_count = tgt_config.get("generation", {}).get("target_qa_pairs", 100)
        batch_size = tgt_config.get("generation", {}).get("batch_size", 10)

        print(f"🎯 目标: 生成 {target_count} 个 QA 对 (批次大小: {batch_size})")

        try:
            results = asyncio.run(pipeline.run(target_count=target_count, batch_size=batch_size))

            # Determine output file
            if args.output_file:
                output_file = args.output_file
            else:
                base_name = os.path.splitext(os.path.basename(args.tgt_config))[0]
                output_file = f"{base_name}_tgt_output.json"

            # Save results
            print(f"💾 保存结果到: {output_file}")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # Generate metrics report
            metrics = TGMetrics(tree)
            report = metrics.generate_report(output_file)
            metrics_file = output_file.replace(".json", "_metrics.json")
            print(f"📊 保存指标报告到: {metrics_file}")
            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            print("✅ TGT 管道运行完成!")
            print(f"📊 意图覆盖率: {report['coverage']['overall_ratio']:.1%}")
            print(f"📊 生成 QA 对数: {len(results)}")
            return True

        except Exception as e:
            print(f"❌ TGT 管道运行出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            cleanup_workspace(working_dir)


def create_parser():
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="TextGraphTree 命令行工具 - 从文本生成知识图谱训练数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 单个文件处理
  python textgraphtree_cli.py -i input.txt -k your_api_key

  # 批量处理多个文件
  python textgraphtree_cli.py -b file1.txt file2.json file3.csv -k your_api_key

  # 从文件列表批量处理
  python textgraphtree_cli.py -l file_list.txt -k your_api_key

  # 使用 Trainee 模型
  python textgraphtree_cli.py -i input.txt -k your_api_key --use-trainee-model --trainee-api-key your_trainee_key

  # 自定义参数
  python textgraphtree_cli.py -i input.txt -k your_api_key --chunk-size 2048 --max-depth 3
        """
    )

    # 输入参数组 - 互斥选择
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("-i", "--input-file", help="单个输入文件路径 (.txt, .json, .jsonl, .csv)")
    input_group.add_argument("-b", "--batch-files", nargs='+', help="批量处理多个文件路径")
    input_group.add_argument("-l", "--file-list", help="包含文件路径列表的文本文件")
    
    # 其他必需参数
    parser.add_argument("-k", "--api-key", 
                      default=os.getenv("SYNTHESIZER_API_KEY", "sk-wFHN2ySjUYxCx3LrWAkJEMB11FMxYDvF6DHdye9yVDwIH2no"), 
                      help="SiliconFlow API Key (默认从环境变量 SYNTHESIZER_API_KEY 读取)")
    parser.add_argument("-o", "--output-file", help="单个文件的输出路径 (批量处理时忽略)")

    # 模型配置
    model_group = parser.add_argument_group("模型配置")
    model_group.add_argument("--use-trainee-model", action="store_true", help="使用 Trainee 模型")
    model_group.add_argument("--synthesizer-url", 
                           default=os.getenv("SYNTHESIZER_BASE_URL", "https://api.huiyan-ai.cn/v1"), 
                           help="Synthesizer API URL (默认从环境变量 SYNTHESIZER_BASE_URL 读取)")
    model_group.add_argument("--synthesizer-model", 
                           default=os.getenv("SYNTHESIZER_MODEL", "gpt-4.1-mini-2025-04-14"), 
                           help="Synthesizer 模型名称 (默认从环境变量 SYNTHESIZER_MODEL 读取)")
    model_group.add_argument("--trainee-url", 
                           default=os.getenv("TRAINEE_BASE_URL", "https://api.siliconflow.cn/v1"), 
                           help="Trainee API URL (默认从环境变量 TRAINEE_BASE_URL 读取)")
    model_group.add_argument("--trainee-model", 
                           default=os.getenv("TRAINEE_MODEL", "Qwen/Qwen2.5-7B-Instruct"), 
                           help="Trainee 模型名称 (默认从环境变量 TRAINEE_MODEL 读取)")
    model_group.add_argument("--trainee-api-key", 
                           default=os.getenv("TRAINEE_API_KEY", ""), 
                           help="Trainee 模型的 API Key (默认从环境变量 TRAINEE_API_KEY 读取)")

    # 生成配置
    gen_group = parser.add_argument_group("生成配置")
    gen_group.add_argument("--chunk-size", type=int, 
                          default=int(os.getenv("CHUNK_SIZE", "1024")), 
                          help="文本块大小 (默认从环境变量 CHUNK_SIZE 读取)")
    gen_group.add_argument("--chunk-overlap", type=int, 
                          default=int(os.getenv("CHUNK_OVERLAP", "100")), 
                          help="文本块重叠大小 (默认从环境变量 CHUNK_OVERLAP 读取)")
    gen_group.add_argument("--tokenizer", 
                          default=os.getenv("TOKENIZER", "cl100k_base"),   # pragma: allowlist secret
                          help="Tokenizer 名称 (默认从环境变量 TOKENIZER 读取)")
    gen_group.add_argument("--output-data-type", choices=["atomic", "multi_hop", "aggregated", "cot", "all"],   # // pragma: allowlist secret
                          default=os.getenv("OUTPUT_DATA_TYPE", "aggregated"),   # pragma: allowlist secret
                          help="输出数据类型 (默认从环境变量 OUTPUT_ + DATA_TYPE 读取)")  # pragma: allowlist secret
    gen_group.add_argument("--output-data-format", choices=["Alpaca", "Sharegpt", "ChatML"], 
                          default=os.getenv("OUTPUT_DATA_FORMAT", "Alpaca"), 
                          help="输出数据格式 (默认从环境变量 OUTPUT_DATA_FORMAT 读取)")
    gen_group.add_argument("--quiz-samples", type=int, 
                          default=int(os.getenv("QUIZ_SAMPLES", "2")), 
                          help="测验样本数量 (默认从环境变量 QUIZ_SAMPLES 读取)")
    gen_group.add_argument("--chinese-only", action="store_true",
                          default=os.getenv("CHINESE_ONLY", "false").lower() == "true",
                          help="只生成中文问答对 (默认从环境变量 CHINESE_ONLY 读取)")
    gen_group.add_argument("--qa-pair-limit", type=int,
                          default=int(os.getenv("QA_PAIR_LIMIT", "0")) or None,
                          help="目标QA对数量限制，0表示不限制 (默认从环境变量 QA_PAIR_LIMIT 读取)")

    # 遍历策略
    traverse_group = parser.add_argument_group("遍历策略")
    traverse_group.add_argument("--bidirectional", action="store_true", 
                               default=os.getenv("BIDIRECTIONAL", "True").lower() == "true", 
                               help="双向遍历 (默认从环境变量 BIDIRECTIONAL 读取)")
    traverse_group.add_argument("--expand-method", choices=["max_width", "max_tokens"], 
                               default=os.getenv("GRAPH_EXPANSION_MODE", "max_tokens"),   # pragma: allowlist secret
                               help="扩展方法 (默认从环境变量 EXPAND_ + METHOD 读取)")  # pragma: allowlist secret
    traverse_group.add_argument("--max-extra-edges", type=int, 
                               default=int(os.getenv("MAX_EXTRA_EDGES", "5")), 
                               help="最大额外边数 (默认从环境变量 MAX_EXTRA_EDGES 读取)")
    traverse_group.add_argument("--max-tokens", type=int, 
                               default=int(os.getenv("MAX_TOKENS", "256")), 
                               help="最大 token 数 (默认从环境变量 MAX_TOKENS 读取)")
    traverse_group.add_argument("--max-depth", type=int, 
                               default=int(os.getenv("MAX_DEPTH", "2")), 
                               help="最大深度 (默认从环境变量 MAX_DEPTH 读取)")
    traverse_group.add_argument("--edge-sampling", choices=["max_loss", "min_loss", "random"], 
                               default=os.getenv("EDGE_POLICY_MODE", "max_loss"),   # pragma: allowlist secret
                               help="边采样策略 (默认从环境变量 EDGE_ + SAMPLING 读取)")  # pragma: allowlist secret
    traverse_group.add_argument("--isolated-node-strategy", choices=["add", "ignore"], 
                               default=os.getenv("ISOLATED_NODE_STRATEGY", "ignore"), 
                               help="孤立节点策略 (默认从环境变量 ISOLATED_NODE_STRATEGY 读取)")
    traverse_group.add_argument("--loss-strategy", choices=["only_edge", "both"],   # pragma: allowlist secret
                               default=os.getenv("LOSS_ROUTING_MODE", "only_edge"),   # pragma: allowlist secret
                               help="损失策略 (默认从环境变量 LOSS_ + STRATEGY 读取)")  # pragma: allowlist secret

    # 限制配置
    limit_group = parser.add_argument_group("限制配置")
    limit_group.add_argument("--rpm", type=int, 
                           default=int(os.getenv("RPM", "1000")), 
                           help="每分钟请求数 (默认从环境变量 RPM 读取)")
    limit_group.add_argument("--tpm", type=int, 
                           default=int(os.getenv("TPM", "50000")), 
                           help="每分钟 token 数 (默认从环境变量 TPM 读取)")

    # TGT 模式参数组
    tgt_group = parser.add_argument_group("TGT 模式")
    tgt_group.add_argument("--tgt-config", help="TGT 配置文件路径")
    tgt_group.add_argument("--tgt-input", help="构建知识图谱的输入文件 (与 --tgt-config 配合使用)")
    tgt_group.add_argument("--tgt-kg", help="现有知识图谱路径")
    tgt_group.add_argument("--tgt-output", help="TGT 输出文件路径")

    # 测试连接
    parser.add_argument("--test-connection", action="store_true", help="仅测试 API 连接")

    return parser


def load_file_list(file_list_path: str) -> list:
    """从文件中加载文件路径列表"""
    try:
        with open(file_list_path, 'r', encoding='utf-8') as f:
            files = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return files
    except Exception as e:
        print(f"❌ 无法读取文件列表 {file_list_path}: {str(e)}")
        sys.exit(1)

def main():
    """主函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 验证 API Key
    if not args.api_key:
        print("❌ 错误: 未提供 API Key")
        print("请通过以下方式之一提供 API Key:")
        print("1. 命令行参数: -k your_api_key")
        print("2. 环境变量: SYNTHESIZER_API_KEY=your_api_key")
        print("3. .env 文件: SYNTHESIZER_API_KEY=your_api_key")
        sys.exit(1)

    # 确定输入文件列表
    input_files = []
    
    if args.input_file:
        # 单个文件处理
        input_files = [args.input_file]
    elif args.batch_files:
        # 批量处理多个文件
        input_files = args.batch_files
    elif args.file_list:
        # 从文件列表加载
        input_files = load_file_list(args.file_list)
    
    # 验证输入文件
    valid_extensions = ['.txt', '.json', '.jsonl', '.csv']
    invalid_files = []
    
    for file_path in input_files:
        if not os.path.exists(file_path):
            print(f"❌ 输入文件不存在: {file_path}")
            invalid_files.append(file_path)
        elif not any(file_path.endswith(ext) for ext in valid_extensions):
            print(f"❌ 不支持的文件类型: {file_path}")
            invalid_files.append(file_path)
    
    if invalid_files:
        print(f"❌ 发现 {len(invalid_files)} 个无效文件，程序退出")
        sys.exit(1)

    # 如果使用 trainee 模型但没有提供 trainee api key，使用主 api key
    if args.use_trainee_model and not args.trainee_api_key:
        args.trainee_api_key = args.api_key

    # TGT 模式检查
    if hasattr(args, 'tgt_config') and args.tgt_config:
        cli = TextGraphTreeCLI()
        # 设置 tgt 参数
        args.tgt_input = getattr(args, 'tgt_input', None) or args.input_file
        args.tgt_kg = getattr(args, 'tgt_kg', None)
        args.tgt_output = getattr(args, 'tgt_output', None) or args.output_file
        success = cli.run_tgt(args)
        sys.exit(0 if success else 1)

    cli = TextGraphTreeCLI()

    # 如果只是测试连接
    if args.test_connection:
        print("🔗 测试 API 连接...")
        success = cli.test_api_connection(args.synthesizer_url, args.api_key, args.synthesizer_model)
        if args.use_trainee_model:
            success &= cli.test_api_connection(args.trainee_url, args.trainee_api_key, args.trainee_model)
        
        if success:
            print("✅ 所有 API 连接测试通过")
            sys.exit(0)
        else:
            print("❌ API 连接测试失败")
            sys.exit(1)

    # 判断是单个文件还是批量处理
    if len(input_files) == 1:
        # 单个文件处理
        args.input_file = input_files[0]
        success = cli.run_graphgen(args)
    else:
        # 批量处理
        args.input_files = input_files
        success = cli.run_batch_processing(args)
    
    if success:
        print("🎉 任务完成!")
        sys.exit(0)
    else:
        print("💥 任务失败!")
        sys.exit(1)


if __name__ == "__main__":
    main()
