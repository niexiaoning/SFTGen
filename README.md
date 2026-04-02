# ArborGraph

**ArborGraph** 是一个基于知识图谱与层级树结构引导的高质量 SFT（监督微调）合成数据生成平台。

名称由来："Arbor"（拉丁语"树"，代表树状层级结构提取）+ "Graph"（知识图谱），体现了本项目的三大核心特色：
- **源文本处理**：从多种格式的原始文档中提取知识
- **知识图谱构建**：构建细粒度的实体-关系知识图谱
- **层级结构提取**：识别和利用树状层级结构组织知识

## 整体架构

```
┌──────────────────────────────────────────────────────┐
│                    Vue 前端 (frontend/)                │
│          Element Plus + Vue 3 + TypeScript             │
├──────────────────────────────────────────────────────┤
│              FastAPI 后端 (backend/)                    │
│      任务管理 / 文件上传 / 配置 / 审核 / 认证           │
├──────────────────────────────────────────────────────┤
│            ArborGraph 核心库 (arborgraph/)              │
│   文档读取 → 知识图谱构建 → 图分区 → QA 生成            │
│   意图驱动管道：意图采样 → 子图检索 → 批评验证           │
└──────────────────────────────────────────────────────┘
```

## 核心工作流

1. **知识构建**（Knowledge Construction）：从原始文档中提取实体和关系，构建细粒度知识图谱
2. **理解评估**（Comprehension Assessment）：通过 ECE（预期校准误差）识别知识盲点
3. **图组织**（Graph Organization）：基于 BFS/DFS/ECE/Leiden 等策略进行子图采样
4. **QA 生成**（QA Generation）：支持原子/聚合/多跳/CoT/层级等多种生成模式

## 项目结构

```
ArborGraph/
├── arborgraph/              # 核心算法库
│   ├── arborgraph.py        # 主类 ArborGraph
│   ├── intent_pipeline.py   # 意图驱动管道
│   ├── generate.py          # 命令行生成入口
│   ├── evaluate.py          # 评测生成入口
│   ├── bases/               # 基类定义
│   ├── configs/             # 配置文件
│   ├── models/              # 各种模型实现
│   │   ├── generator/       # QA 生成器
│   │   ├── partitioner/     # 图分区器
│   │   ├── kg_builder/      # 知识图谱构建
│   │   ├── llm/             # LLM 客户端
│   │   ├── taxonomy/        # 意图树管理
│   │   └── ...
│   ├── operators/           # 操作算子
│   ├── templates/           # Prompt 模板
│   └── utils/               # 工具函数
├── backend/                 # FastAPI 后端
│   ├── api/                 # API 端点
│   ├── core/                # 任务处理器
│   ├── services/            # 业务服务
│   └── utils/               # 后端工具
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── views/           # 页面组件
│       ├── stores/          # Pinia 状态管理
│       ├── api/             # API 接口
│       └── router/          # 路由配置
├── experiments/             # 实验计划与记录
├── reports/                 # 技术报告
├── docs/                    # 项目文档
├── tests/                   # 测试用例
├── scripts/                 # 工具脚本
├── resources/               # 资源文件
├── arborgraph_cli.py        # 命令行工具
├── arborgraph_eval_cli.py   # 评测 CLI
├── start.sh                 # 服务启动脚本
├── requirements.txt         # Python 依赖
└── environment.yml          # Conda 环境
```

## 快速开始

### 1. 环境配置

```bash
# 创建 Conda 环境
conda env create -f environment.yml
conda activate sftgen

# 或使用 pip
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写 API Key 等配置
```

### 3. 启动服务

```bash
# 启动后端 + 前端
./start.sh start

# 或分别启动
uvicorn backend.app:app --host 0.0.0.0 --port 8000
cd frontend && npm run dev
```

### 4. 命令行使用

```bash
# 单文件处理
python arborgraph_cli.py -i input.txt -k your_api_key

# 批量处理
python arborgraph_cli.py -b file1.txt file2.json -k your_api_key

# 意图驱动模式
python arborgraph_cli.py -i input.txt --intent-config configs/intent_config.yaml
```

## 主要特性

- **多源文档支持**：TXT、JSON、JSONL、CSV、PDF、Markdown、DOCX
- **多种生成模式**：原子 QA、聚合 QA、多跳 QA、CoT 推理、层级 QA
- **知识图谱引导**：基于 ECE 的知识盲点识别，确保知识覆盖
- **意图驱动管道**：通过意图树实现领域自适应的数据生成
- **质量控制**：LLM/规则双重 Critic 验证，确保数据质量
- **批量优化**：Prompt 缓存、批量请求、自适应调度
- **全栈平台**：Vue 3 前端 + FastAPI 后端，支持任务管理与审核
