# KGE-Gen 代码架构与核心逻辑说明

> 本文档面向新手开发者，详细说明 KGE-Gen 项目的主要框架、逻辑和核心模块。

## 📋 目录

- [项目概述](#项目概述)
- [整体架构](#整体架构)
- [核心工作流程](#核心工作流程)
- [主要模块说明](#主要模块说明)
- [代码结构](#代码结构)
- [关键概念](#关键概念)
- [数据流](#数据流)
- [快速上手](#快速上手)

---

## 项目概述

KGE-Gen 是一个**知识图谱引导的合成数据生成平台**，主要功能是：

1. **从文档构建知识图谱**：从原始文档（文本、PDF、CSV等）中提取实体和关系，构建结构化知识图谱
2. **生成训练数据**：基于知识图谱生成高质量的问答对（QA pairs），用于训练大语言模型
3. **提供 Web 界面**：通过 Web UI 和 API 接口，方便用户上传文档、管理任务、审核数据

### 核心价值

- **解决数据稀缺问题**：自动生成大量高质量训练数据
- **知识图谱引导**：通过结构化知识确保生成数据的准确性和相关性
- **多种生成模式**：支持原子问答、聚合问答、多跳问答、链式思考等多种模式

---

## 整体架构

KGE-Gen 采用**前后端分离**的架构设计：

```
┌─────────────────────────────────────────────────────────┐
│                     前端层 (Frontend)                    │
│  ┌──────────────────────────────┐  ┌──────────────┐  │
│  │  Vue 3 前端（推荐）          │  │  CLI 工具    │  │
│  └──────────────┬───────────────┘  └──────┬───────┘  │
└─────────────────┼──────────────────────────┼──────────┘
                  └────────────┬─────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │      FastAPI 后端服务 (Backend)     │
          │  ┌──────────────────────────────┐  │
          │  │   API 路由 / 任务管理        │  │
          │  │   用户认证 / 数据审核        │  │
          │  └──────────────┬───────────────┘  │
          └─────────────────┼─────────────────┘
                            │
          ┌─────────────────▼─────────────────┐
          │    KGE-Gen 核心库 (Core Library)  │
          │  ┌──────────────────────────────┐  │
          │  │  知识构建 / 图组织 / QA生成   │  │
          │  │  LLM 调用 / 存储管理          │  │
          │  └──────────────────────────────┘  │
          └────────────────────────────────────┘
```

### 三层架构说明

#### 1. **前端层** (`frontend/`，`webui/` 仅保留任务/工具模块)
- **Vue 3 前端**：提供现代化的 Web 界面，用于任务管理、数据审核（`start.sh` 仅启动后端 + Vue）
- **`webui/` 目录**：遗留的 Gradio 应用已不再由启动脚本拉起；其中的 `task_manager`、`utils` 等仍被后端与 CLI 使用
- **CLI 工具**：命令行接口，适合批量处理

#### 2. **后端服务层** (`backend/`)
- **FastAPI 应用**：提供 RESTful API 接口
- **任务管理**：处理任务创建、执行、状态追踪
- **用户认证**：JWT Token 认证，支持管理员和审核员角色
- **数据审核**：支持人工审核和自动审核

#### 3. **核心库层** (`graphgen/`)
- **KGE-Gen 核心逻辑**：知识图谱构建和 QA 生成的核心算法
- **存储系统**：文档存储、知识图谱存储、QA 存储
- **LLM 客户端**：封装 OpenAI、Ollama 等 LLM 接口

---

## 核心工作流程

KGE-Gen 的核心工作流程分为**四个主要步骤**：

```
原始文档
    │
    ▼
┌─────────────────────────────────────────┐
│  步骤1: 知识构建 (Knowledge Construction)│
│  - 文档读取和分割                        │
│  - 实体和关系提取                        │
│  - 知识图谱构建                          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  步骤2: 理解评估 (Comprehension Assess) │
│  - 语义变体生成 (可选)                   │
│  - 置信度评估 (可选)                     │
│  - 知识盲点识别                          │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  步骤3: 图组织 (Graph Organization)      │
│  - 知识图谱分区                          │
│  - 子图提取 (k-hop)                      │
│  - 批次准备                              │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  步骤4: QA 生成 (QA Generation)          │
│  - 问题生成                              │
│  - 答案生成                              │
│  - 格式化输出                            │
└──────────────┬──────────────────────────┘
               │
               ▼
          问答对数据
```

### 详细流程说明

#### 步骤1: 知识构建 (`insert()`)

**代码位置**：`graphgen/graphgen.py::GraphGen.insert()`

**主要流程**：

1. **文档读取** (`graphgen/operators/read/read_files.py`)
   - 支持多种格式：文本、PDF、CSV、JSON、JSONL
   - 使用不同的 Reader 类处理不同格式

2. **文档分割** (`graphgen/operators/split/split_chunks.py`)
   - 将长文档分割成较小的 chunk（片段）
   - 支持多种分割策略：递归字符分割、Markdown 分割等
   - 配置参数：`chunk_size`（分块大小）、`chunk_overlap`（重叠大小）

3. **实体和关系提取** (`graphgen/operators/build_kg/build_text_kg.py`)
   - 使用 LLM（合成器模型）从每个 chunk 中提取实体和关系
   - 提取器：`graphgen/models/kg_builder/light_rag_kg_builder.py`
   - 提示模板：`graphgen/templates/kg/kg_extraction.py`

4. **知识聚合**
   - 将多个 chunk 中提取的实体和关系合并
   - 相同实体/关系会被合并，描述会被聚合
   - 存储到 `NetworkXStorage`（基于 NetworkX 的图存储）

**关键代码**：

```python
# graphgen/graphgen.py:92-163
async def insert(self, read_config: Dict, split_config: Dict):
    # 1. 读取文件
    data = read_files(read_config["input_file"], self.working_dir)
    
    # 2. 分割文档
    inserting_chunks = await chunk_documents(
        text_docs,
        split_config["chunk_size"],
        split_config["chunk_overlap"],
        self.tokenizer_instance,
    )
    
    # 3. 提取实体和关系
    _add_entities_and_relations = await build_text_kg(
        llm_client=self.synthesizer_llm_client,
        kg_instance=self.graph_storage,
        chunks=inserting_chunks,
    )
```

#### 步骤2: 理解评估 (`quiz_and_judge()`)

**代码位置**：`graphgen/graphgen.py::KGE-Gen.quiz_and_judge()`

**主要流程**：

1. **语义变体生成** (`graphgen/operators/quiz.py`)
   - 对知识图谱中的每条边（关系）生成多个语义变体
   - 生成肯定形式和否定形式
   - 用于后续的置信度评估

2. **置信度评估** (`graphgen/operators/judge.py`)
   - 使用训练模型（Trainee Model）对语义变体进行判断
   - 计算模型对每个知识点的置信度
   - 识别知识盲点（置信度低的知识点）

3. **理解损失计算** (`graphgen/utils/calculate_confidence.py`)
   - 基于置信度计算理解损失（Comprehension Loss）
   - 用于后续的图分区策略（ECE 方法）

**注意**：此步骤是可选的，只有在配置了 `if_trainee_model=True` 时才会执行。

#### 步骤3: 图组织 (`generate()` 中的分区)

**代码位置**：`graphgen/operators/partition/partition_kg.py`

**主要流程**：

1. **知识图谱分区**
   - 将整个知识图谱分割成多个子图（社区/批次）
   - 支持多种分区方法：
     - **BFS**：广度优先搜索分区
     - **DFS**：深度优先搜索分区
     - **ECE**：基于预期校准误差的分区（优先选择知识盲点）
     - **Leiden**：基于社区检测的分区
     - **Anchor BFS**：基于锚点的 BFS 分区

2. **子图提取**
   - 对每个社区提取 k-hop 子图（k 跳邻域）
   - 包含节点、边和相关的上下文信息

3. **批次准备**
   - 将子图组织成批次（batch）
   - 每个批次包含节点列表和边列表

**关键代码**：

```python
# graphgen/graphgen.py:303-310
async def generate(self, partition_config: Dict, generate_config: Dict):
    # Step 1: 图分区
    batches = await partition_kg(
        self.graph_storage,
        self.chunks_storage,
        self.tokenizer_instance,
        partition_config,
    )
```

#### 步骤4: QA 生成 (`generate()` 中的生成)

**代码位置**：`graphgen/operators/generate/generate_qas.py`

**主要流程**：

1. **选择生成器**
   - 根据配置的 `mode` 选择对应的生成器：
     - **atomic**：原子问答生成器 (`AtomicGenerator`)
     - **aggregated**：聚合问答生成器 (`AggregatedGenerator`)
     - **multi_hop**：多跳问答生成器 (`MultiHopGenerator`)
     - **cot**：链式思考生成器 (`CoTGenerator`)
     - **all**：生成所有模式

2. **问题生成**
   - 对每个批次（子图），使用 LLM 生成问题
   - 不同模式使用不同的提示模板
   - 模板位置：`graphgen/templates/generation/`

3. **答案生成**
   - 对于 atomic 模式，可能采用两阶段生成：
     - 先生成问题，再去重
     - 再为每个问题生成答案
   - 其他模式通常一次性生成问答对

4. **格式化输出**
   - 将生成的问答对格式化为指定格式：
     - **Alpaca**：`{"instruction": "...", "input": "...", "output": "..."}`
     - **ShareGPT**：`{"conversations": [...]}`
     - **ChatML**：`{"messages": [...]}`
   - 添加元数据：context、graph、source_chunks 等

5. **去重和限制**
   - 基于问题内容的 hash 进行去重
   - 如果配置了 `target_qa_pairs`，限制生成数量
   - 如果配置了 `mode_ratios`，按比例分配各模式的数量

**关键代码**：

```python
# graphgen/operators/generate/generate_qas.py:89-321
async def generate_qas(
    llm_client: BaseLLMClient,
    batches: list,
    generation_config: dict,
    ...
):
    mode = generation_config["mode"]
    
    # 选择生成器
    if mode == "atomic":
        generator = AtomicGenerator(actual_llm_client, ...)
    elif mode == "aggregated":
        generator = AggregatedGenerator(actual_llm_client, ...)
    # ...
    
    # 生成 QA 对
    results = await run_concurrent(
        generate_with_storage,
        batches,
        desc="[4/4]Generating QAs",
    )
    
    # 格式化输出
    formatted_results = generator.format_generation_results(
        results,
        output_data_format=data_format
    )
```

---

## 主要模块说明

### 1. 核心类：`KGE-Gen`

**位置**：`graphgen/graphgen.py`

**职责**：KGE-Gen 的核心类，封装了整个工作流程。

**主要属性**：
- `synthesizer_llm_client`：合成器 LLM 客户端（用于提取和生成）
- `trainee_llm_client`：训练模型 LLM 客户端（用于评估，可选）
- `tokenizer_instance`：分词器实例
- `graph_storage`：知识图谱存储（NetworkX）
- `chunks_storage`：文档片段存储（JSON）
- `qa_storage`：问答对存储（JSON List）

**主要方法**：
- `insert()`：知识构建
- `search()`：外部搜索（可选）
- `quiz_and_judge()`：理解评估（可选）
- `generate()`：QA 生成
- `clear()`：清理所有存储

### 2. 存储系统

#### `NetworkXStorage` (`graphgen/models/storage/networkx_storage.py`)
- **用途**：存储知识图谱（节点和边）
- **底层**：基于 NetworkX 图库
- **方法**：`add_node()`, `add_edge()`, `get_all_nodes()`, `get_all_edges()`

#### `JsonKVStorage` (`graphgen/models/storage/json_storage.py`)
- **用途**：键值对存储（文档、片段、搜索结果等）
- **格式**：JSON 文件
- **方法**：`upsert()`, `get_by_id()`, `filter_keys()`

#### `JsonListStorage` (`graphgen/models/storage/json_storage.py`)
- **用途**：列表存储（问答对）
- **格式**：JSON 数组文件
- **方法**：`upsert()`, `all_items()`

### 3. LLM 客户端

#### `OpenAIClient` (`graphgen/models/llm/openai_client.py`)
- **用途**：封装 OpenAI 兼容的 API 调用
- **功能**：
  - 异步调用 LLM API
  - Token 使用量统计
  - 请求限流（RPM/TPM）
  - 批量请求优化

#### `BatchLLMWrapper` (`graphgen/models/llm/batch_llm_wrapper.py`)
- **用途**：批量请求包装器，优化 LLM 调用
- **功能**：
  - 批量请求合并
  - 请求缓存
  - 自适应批处理大小

### 4. 生成器（Generators）

#### `AtomicGenerator` (`graphgen/models/generator/atomic_generator.py`)
- **用途**：生成原子问答对（单个事实）
- **特点**：问题简单直接，答案简短

#### `AggregatedGenerator` (`graphgen/models/generator/aggregated_generator.py`)
- **用途**：生成聚合问答对（多个相关事实）
- **特点**：问题涉及多个实体/关系

#### `MultiHopGenerator` (`graphgen/models/generator/multi_hop_generator.py`)
- **用途**：生成多跳问答对（需要推理路径）
- **特点**：问题需要多步推理才能回答

#### `CoTGenerator` (`graphgen/models/generator/cot_generator.py`)
- **用途**：生成链式思考问答对
- **特点**：答案包含推理过程

### 5. 分区器（Partitioners）

#### `ECEPartitioner` (`graphgen/models/partitioner/ece_partitioner.py`)
- **用途**：基于预期校准误差的分区
- **特点**：优先选择知识盲点（理解损失高的区域）

#### `BFSPartitioner` (`graphgen/models/partitioner/bfs_partitioner.py`)
- **用途**：广度优先搜索分区
- **特点**：从根节点开始，逐层扩展

#### `DFSPartitioner` (`graphgen/models/partitioner/dfs_partitioner.py`)
- **用途**：深度优先搜索分区
- **特点**：深度优先遍历图

#### `LeidenPartitioner` (`graphgen/models/partitioner/leiden_partitioner.py`)
- **用途**：基于 Leiden 算法的社区检测分区
- **特点**：识别图中的社区结构

### 6. 后端服务模块

#### `TaskProcessor` (`backend/core/task_processor.py`)
- **职责**：处理 KGE-Gen 任务的执行
- **流程**：
  1. 初始化 KGE-Gen 实例
  2. 执行知识构建
  3. 执行理解评估（可选）
  4. 执行 QA 生成
  5. 保存结果并更新任务状态

#### `TaskService` (`backend/services/task_service.py`)
- **职责**：任务管理服务
- **功能**：创建任务、查询任务、更新任务状态

#### `ReviewService` (`backend/services/review_service.py`)
- **职责**：数据审核服务
- **功能**：人工审核、批量审核、审核统计

#### `AuthService` (`backend/services/auth_service.py`)
- **职责**：用户认证服务
- **功能**：用户登录、Token 生成、权限验证

---

## 代码结构

### 项目目录结构

```
KGE-Gen/
├── backend/              # FastAPI 后端服务
│   ├── api/              # API 路由定义
│   ├── core/             # 核心业务逻辑
│   ├── services/         # 业务服务层
│   ├── schemas.py        # 数据模型定义
│   ├── config.py         # 配置管理
│   └── app.py            # FastAPI 应用入口
│
├── frontend/             # Vue 3 前端应用
│   ├── src/
│   │   ├── api/          # API 调用封装
│   │   ├── views/        # 页面组件
│   │   ├── stores/       # 状态管理
│   │   └── router/       # 路由配置
│   └── package.json
│
├── graphgen/             # KGE-Gen 核心库
│   ├── bases/            # 基础类和接口
│   ├── models/           # 模型实现
│   │   ├── generator/    # 生成器
│   │   ├── partitioner/ # 分区器
│   │   ├── kg_builder/   # 知识图谱构建器
│   │   ├── llm/          # LLM 客户端
│   │   └── storage/      # 存储系统
│   ├── operators/        # 操作符（核心逻辑）
│   │   ├── build_kg/     # 知识构建
│   │   ├── generate/     # QA 生成
│   │   ├── partition/    # 图分区
│   │   └── split/        # 文档分割
│   ├── templates/        # 提示模板
│   ├── utils/            # 工具函数
│   ├── graphgen.py       # KGE-Gen 核心类
│   └── generate.py       # CLI 入口
│
├── webui/                # 任务管理/工具（Gradio app.py 已不作为默认入口）
│   ├── app.py            # 遗留 Gradio（默认不启动）
│   └── task_processor.py # 任务处理（仍被引用）
│
├── batch_process/        # 批量处理脚本
├── docs/                 # 文档
├── scripts/              # 工具脚本
└── resources/            # 资源文件
```

### 关键文件说明

| 文件路径 | 说明 |
|---------|------|
| `graphgen/graphgen.py` | KGE-Gen 核心类，包含主要工作流程 |
| `graphgen/generate.py` | CLI 入口，命令行工具的主函数 |
| `backend/app.py` | FastAPI 应用入口 |
| `backend/core/task_processor.py` | 任务处理器，执行 KGE-Gen 任务 |
| `graphgen/operators/generate/generate_qas.py` | QA 生成的核心逻辑 |
| `graphgen/operators/build_kg/build_text_kg.py` | 文本知识图谱构建 |
| `graphgen/operators/partition/partition_kg.py` | 图分区逻辑 |
| `graphgen/models/generator/` | 各种生成器实现 |
| `graphgen/models/partitioner/` | 各种分区器实现 |

---

## 关键概念

### 1. Chunk（文档片段）

**定义**：将长文档分割后得到的小片段。

**数据结构**：
```python
@dataclass
class Chunk:
    id: str              # 片段唯一标识
    content: str         # 片段内容
    type: str            # 片段类型（text/image等）
    metadata: dict       # 元数据
```

**用途**：
- 作为实体/关系提取的输入单位
- 存储原始文档的片段信息
- 在生成 QA 时提供上下文

### 2. 知识图谱（Knowledge Graph）

**定义**：由节点（实体）和边（关系）组成的图结构。

**节点（Node）**：
- 表示实体（如：人物、地点、概念等）
- 包含属性：`name`（名称）、`description`（描述）、`entity_type`（类型）等

**边（Edge）**：
- 表示实体之间的关系
- 包含属性：`source`（源节点）、`target`（目标节点）、`description`（关系描述）等

**存储**：使用 `NetworkXStorage`，底层基于 NetworkX 图库。

### 3. Batch（批次）

**定义**：图分区后得到的子图，用于 QA 生成。

**结构**：
```python
batch = (
    nodes,    # [(node_id, node_data), ...]
    edges     # [(source, target, edge_data), ...]
)
```

**用途**：
- 作为 QA 生成的输入单位
- 每个批次对应一个或多个 QA 对

### 4. 生成模式（Generation Mode）

**atomic（原子模式）**：
- 生成简单的单事实问答对
- 问题直接，答案简短
- 示例：Q: "北京是哪个国家的首都？" A: "中国"

**aggregated（聚合模式）**：
- 生成涉及多个相关事实的问答对
- 问题可能涉及多个实体/关系
- 示例：Q: "介绍北京的历史和地理位置" A: "..."

**multi_hop（多跳模式）**：
- 生成需要多步推理的问答对
- 问题需要沿着知识图谱的多条边进行推理
- 示例：Q: "A 和 C 有什么关系？"（需要先找到 A→B，再找到 B→C）

**cot（链式思考模式）**：
- 生成包含推理过程的问答对
- 答案会展示推理步骤
- 示例：Q: "..." A: "首先...，然后...，因此..."

### 5. 输出格式（Output Format）

**Alpaca 格式**：
```json
{
  "instruction": "问题",
  "input": "",
  "output": "答案"
}
```

**ShareGPT 格式**：
```json
{
  "conversations": [
    {"from": "human", "value": "问题"},
    {"from": "gpt", "value": "答案"}
  ]
}
```

**ChatML 格式**：
```json
{
  "messages": [
    {"role": "user", "content": "问题"},
    {"role": "assistant", "content": "答案"}
  ]
}
```

---

## 数据流

### 完整数据流示例

```
1. 用户上传文档
   └─> backend/services/file_service.py
       └─> 保存到 cache/uploads/

2. 创建任务
   └─> backend/api/endpoints.py::create_task()
       └─> backend/services/task_service.py
           └─> 任务信息保存到 tasks/tasks.json

3. 执行任务
   └─> backend/core/task_processor.py::process_task()
       └─> 初始化 KGE-Gen 实例
           └─> graphgen/graphgen.py::KGE-Gen()

4. 知识构建
   └─> KGE-Gen.insert()
       ├─> 读取文档 (operators/read/read_files.py)
       ├─> 分割文档 (operators/split/split_chunks.py)
       │   └─> 保存到 chunks_storage (JsonKVStorage)
       └─> 提取实体/关系 (operators/build_kg/build_text_kg.py)
           └─> 保存到 graph_storage (NetworkXStorage)

5. 理解评估（可选）
   └─> KGE-Gen.quiz_and_judge()
       ├─> 生成语义变体 (operators/quiz.py)
       └─> 评估置信度 (operators/judge.py)

6. QA 生成
   └─> KGE-Gen.generate()
       ├─> 图分区 (operators/partition/partition_kg.py)
       │   └─> 生成批次列表
       └─> 生成 QA 对 (operators/generate/generate_qas.py)
           ├─> 选择生成器 (models/generator/)
           ├─> 调用 LLM 生成
           └─> 格式化输出
               └─> 保存到 qa_storage (JsonListStorage)

7. 保存结果
   └─> backend/core/task_processor.py
       └─> 保存到 tasks/outputs/{task_id}.json

8. 数据审核（可选）
   └─> backend/services/review_service.py
       └─> 审核结果保存到 tasks/reviews/
```

### 存储数据流

```
原始文档
    │
    ▼
full_docs_storage (JsonKVStorage)
    │
    ▼
chunks_storage (JsonKVStorage)
    │
    ▼
graph_storage (NetworkXStorage)
    │
    ▼
分区后的批次 (batches)
    │
    ▼
qa_storage (JsonListStorage)
    │
    ▼
最终输出文件 (tasks/outputs/{task_id}.json)
```

---

## 快速上手

### 1. 理解核心流程

建议按以下顺序阅读代码：

1. **入口点**：
   - CLI：`graphgen/generate.py::main()`
   - Web API：`backend/main.py` → `backend/app.py` → `backend/core/task_processor.py`

2. **核心类**：
   - `graphgen/graphgen.py::KGE-Gen`：理解主要方法和流程

3. **关键操作**：
   - `graphgen/operators/build_kg/build_text_kg.py`：知识构建
   - `graphgen/operators/partition/partition_kg.py`：图分区
   - `graphgen/operators/generate/generate_qas.py`：QA 生成

4. **生成器**：
   - `graphgen/models/generator/atomic_generator.py`：理解生成逻辑

### 2. 调试技巧

- **查看日志**：任务执行日志保存在 `cache/{task_id}/logs/`
- **检查存储**：知识图谱和 QA 数据保存在 `cache/{task_id}/` 目录
- **API 文档**：访问 `http://localhost:8000/docs` 查看 API 文档

### 3. 常见修改场景

**修改生成模式**：
- 编辑 `graphgen/models/generator/` 下的生成器类
- 修改提示模板：`graphgen/templates/generation/`

**添加新的分区方法**：
- 在 `graphgen/models/partitioner/` 下创建新的分区器类
- 实现 `BasePartitioner` 接口
- 在 `graphgen/operators/partition/partition_kg.py` 中注册

**修改输出格式**：
- 编辑生成器的 `format_generation_results()` 方法
- 参考：`graphgen/models/generator/atomic_generator.py::format_generation_results()`

**优化 LLM 调用**：
- 查看 `graphgen/models/llm/batch_llm_wrapper.py`：批量请求优化
- 查看 `graphgen/utils/batch_request_manager.py`：批量请求管理

---

## 总结

KGE-Gen 的核心思想是：

1. **从文档到知识图谱**：通过 LLM 提取实体和关系，构建结构化知识图谱
2. **从知识图谱到 QA 对**：基于知识图谱的子图，生成高质量的问答对
3. **多种生成模式**：支持不同复杂度的问答对，满足不同训练需求

**关键设计原则**：
- **模块化**：各模块职责清晰，易于扩展
- **异步处理**：使用异步 I/O 提高性能
- **可配置**：通过配置文件灵活控制行为
- **可扩展**：易于添加新的生成器、分区器等

希望这份文档能帮助你快速理解 KGE-Gen 的代码架构和核心逻辑！如有疑问，建议查看具体的代码实现和注释。

