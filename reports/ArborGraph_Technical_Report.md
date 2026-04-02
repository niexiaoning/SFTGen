# ArborGraph：基于知识图谱与层级树结构引导的高质量 SFT 合成数据生成框架

## 1. 摘要

大语言模型（LLM）的监督微调（Supervised Fine-Tuning, SFT）对高质量训练数据的需求日益增长，然而人工标注成本高昂且难以规模化。合成数据生成为解决这一瓶颈提供了可行路径，但现有方法普遍面临知识覆盖不全、数据多样性不足以及质量控制薄弱等挑战。本文提出 ArborGraph——一个融合知识图谱（Knowledge Graph）、层级树结构（Hierarchical Tree Structure）与意图驱动生成（Intent-Driven Generation）的全栈 SFT 合成数据生成框架。ArborGraph 名称源自拉丁语"Arbor"（树）与"Graph"（图），体现了其"树-图"双核心的架构设计理念。

ArborGraph 在两项前序工作基础上演进而来：GraphGen（知识图谱引导的问答生成）与 Condor（意图树驱动的数据合成）。框架的核心创新包括：（1）基于预期校准误差（Expected Calibration Error, ECE）的知识盲点识别机制，确保生成数据的知识覆盖完整性；（2）支持原子、聚合、多跳、思维链（Chain-of-Thought, CoT）及层级等五种 QA 生成模式；（3）意图驱动管道通过分类树（Taxonomy Tree）与多样性采样实现领域自适应的数据合成；（4）LLM 批评家（Critic）与规则批评家的双重质量验证机制。工程层面，ArborGraph 通过 Prompt 缓存、批量请求调度、Prompt 合并及自适应批量管理等优化策略显著降低 LLM 调用成本，并提供基于 Vue 3 + FastAPI 的全栈可视化平台，支持任务管理、数据审核与用户认证。

## 2. 引言与研究背景

### 2.1 问题背景

监督微调是提升大语言模型任务表现的关键技术，但高质量 SFT 数据的人工标注成本高昂且难以规模化。基于 LLM 的合成数据生成为此提供了可行路径，但面临三大系统性问题：知识幻觉导致事实准确性无法保障、缺乏结构化引导导致知识分布偏差、缺少质量反馈环路导致低质量样本难以过滤。

### 2.2 前序工作

ArborGraph 建立在两项前序工作的基础之上：

**GraphGen** 提出了知识图谱引导的 QA 生成范式：从源文本构建实体-关系知识图谱，基于图分区策略划分子图社区，以子图上下文引导 LLM 生成问答对。GraphGen 引入 ECE 机制，通过让待训练模型判断知识图谱命题，识别知识盲点并实现针对性数据生成。

**Condor** 提出了意图驱动的数据合成框架。通过构建领域特定的意图分类树，将 SFT 数据需求分解为层次化意图节点，通过多样性采样确保意图覆盖均衡，并使用批评家机制验证质量。

### 2.3 ArborGraph 的贡献

ArborGraph 将上述两项工作有机整合，形成统一的"树-图"合成数据生成框架。主要贡献包括：

1. **统一架构**：将知识图谱构建、ECE 盲点识别、多模式 QA 生成与意图驱动管道整合为可配置、可扩展的端到端系统。
2. **层级结构感知**：引入层级关系识别与序列化机制，使生成器能够利用知识图谱中的 is-a、part-of 等层级结构信息生成更具深度的 QA 对。
3. **多层次质量控制**：融合 LLM 批评家与可插拔规则批评家，结合抽取结果修复、响应解析容错等机制，构建全链路质量保障体系。
4. **工程优化**：通过 Prompt 缓存、批量请求调度、Prompt 合并和自适应批量管理等策略，在保证数据质量的前提下显著降低 LLM 调用成本。

## 3. 系统架构概述

ArborGraph 采用三层架构设计：

```
┌─────────────────────────────────────────────────────────┐
│                  Vue 前端 (frontend/)                     │
│           Element Plus + Vue 3 + TypeScript               │
│    视图层：任务管理 / 意图配置 / 数据审核 / 用户认证         │
├─────────────────────────────────────────────────────────┤
│               FastAPI 后端 (backend/)                     │
│   API 层：任务端点 / 意图端点 / 认证服务 / 审核服务          │
│   服务层：任务处理 / 文件管理 / 配置管理 / 自动审核          │
├─────────────────────────────────────────────────────────┤
│            ArborGraph 核心库 (arborgraph/)                 │
│   ArborGraph 主类：insert → search → quiz_and_judge → generate │
│   IntentPipeline：intent sampling → subgraph retrieval →     │
│                   QA generation → critic validation          │
└─────────────────────────────────────────────────────────┘
```

### 3.1 核心库架构

核心库 `arborgraph/` 采用模块化设计，主要由以下子系统构成：

- **基类层**（`bases/`）：定义 `BaseLLMClient`、`BaseGenerator`、`BasePartitioner`、`BaseGraphStorage`、`BaseCritic` 等抽象基类，确保各模块间的接口一致性。
- **模型层**（`models/`）：实现各功能组件，包括文档读取器（`reader/`）、文本切分器（`splitter/`）、知识图谱构建器（`kg_builder/`）、图分区器（`partitioner/`）、QA 生成器（`generator/`）、意图分类树（`taxonomy/`）、LLM 客户端（`llm/`）、质量评估器（`evaluator/`）、批评家（`critic/`）等。
- **操作层**（`operators/`）：封装高层操作流程，包括文件读取、文本切分、知识图谱构建、图分区、QA 生成、搜索增强、质量评估等。
- **模板层**（`templates/`）：管理所有 Prompt 模板，支持中英文双语。

### 3.2 双管道设计

ArborGraph 提供两条互补的数据生成管道：

**主管道**（`ArborGraph` 类）遵循 `insert → search → quiz_and_judge → generate` 的四阶段流程。`insert` 阶段负责文档读取、文本切分与知识图谱构建；`search` 阶段可选地通过外部搜索（Wikipedia、Google、Bing）增强知识图谱；`quiz_and_judge` 阶段利用 ECE 机制识别知识盲点；`generate` 阶段基于图分区和指定生成模式产出 QA 对。

**意图管道**（`IntentPipeline` 类）遵循"意图采样 → 子图检索 → QA 生成 → 批评验证"的流程。该管道基于预定义的分类树进行意图采样，通过图适配器检索与意图相关的子图，使用意图感知的生成器产出 QA 对，最后经批评家验证后输出。

## 4. 核心算法设计

### 4.1 知识图谱构建

知识图谱构建是 ArborGraph 的基础环节，负责从原始文本中抽取结构化的实体-关系三元组。框架采用 `LightRAGKGBuilder` 作为核心构建器，其工作流程如下：

**文本预处理**：支持 TXT、JSON、JSONL、CSV、PDF、Markdown、DOCX 七种格式。文本切分支持递归字符切分和 Markdown 感知切分等策略，通过 `chunk_overlap` 配置重叠窗口保持上下文连贯。

**实体与关系抽取**：利用 LLM 从文本块中抽取实体（名称、类型、描述、来源）和关系（源实体、目标实体、描述、强度）。使用中英文双语 Prompt 模板，输出基于定界符解析。

**Prompt 合并优化**：将多个文本块的抽取任务合并为单一 Prompt（通过 `[文本1]`、`[文本2]` 标记区分），合并大小 5 可减少约 80% LLM 调用。合并响应经分段解析分配给各文本块，LLM 未遵循格式时回退到全文解析。

**多模态与合并**：支持从图像等多模态文档构建知识图谱。抽取后通过名称规范化和描述聚合合并同名实体和关系，以 NetworkX 图结构存储。

### 4.2 ECE 知识盲点识别

ECE（Expected Calibration Error，预期校准误差）机制是 ArborGraph 实现"知识盲点识别"的核心算法。其基本原理是：通过让待训练模型（Trainee Model）对知识图谱中的关系命题进行概率判断，衡量模型对各知识点的掌握程度。

**问答与评判流程**（`quiz_and_judge`）：`quiz` 阶段利用合成器 LLM 将图谱边描述转述为自然语言陈述；`judge` 阶段提交给待训练模型判断真伪并记录损失值，loss 值高的关系对应知识盲点。

**ECE 分区策略**（`ECEPartitioner`）：继承自 `BFSPartitioner`，支持 `random`（随机）、`min_loss`（优先已掌握知识）、`highest_loss`（聚焦薄弱环节）三种采样策略。以种子单元为起点 BFS 扩展社区，直至达到最大单元数或 token 长度限制。

### 4.3 多模式 QA 生成

ArborGraph 支持五种互补的 QA 生成模式，适用于不同类型的 SFT 训练需求：

**原子 QA 生成**（`AtomicGenerator`）：基于子图中少量实体-关系生成事实性问答对。支持多模板变体采样增强多样性，引入层级结构上下文（通过 `HierarchySerializer`）丰富结构感知能力，支持两阶段和一阶段生成。

**聚合式 QA 生成**：先将子图中多个实体和关系重述为连贯段落作为答案，再反向生成问题。支持合并模式一次性生成，减少 50% API 调用。对应实现类为聚合生成器（Aggreg. Generator）。

**多跳 QA 生成**（`MultiHopGenerator`）：利用多实体关系链生成多步推理问答对，输出包含问题、答案和推理路径。

**CoT 推理生成**（`CoTGenerator`）：分模板设计和推理生成两阶段。输出结构化为 `thinking_process`、`final_answer` 和兼容性字段 `answer`。支持合并模式减少调用。

**层级 QA 生成**（`TreeStructureGenerator`）：专注于 is-a、part-of 等层级关系的问答生成。将层级关系序列化为 Markdown 树或 JSON 格式，基于同级比较、继承推理、抽象泛化和多层级分析四种推理模式生成问题。

### 4.4 意图驱动管道

意图驱动管道（`IntentPipeline`）是 ArborGraph 实现领域自适应数据合成的核心组件。该管道由三层构成：

**宏观意图层**（Macro-Intent Layer）：基于 `TaxonomyTree`（分类树）和 `DiversitySampler`（多样性采样器）。分类树是一种可插拔的层级任务意图树，每个节点携带唯一标识、名称、描述、认知维度（支持概念解释、关系推理、规则遵循、异常诊断、对比分析、程序性知识六种维度）等属性。分类树支持 JSON 和 YAML 两种格式加载，兼容平坦格式（parent\_id 引用）和嵌套格式（children 数组）。

`DiversitySampler` 提供三种采样策略：均匀分支采样（`uniform_branch`，按分支等比例分配）、深度加权采样（`depth_weighted`，偏好深层节点）、覆盖追踪采样（`coverage`，优先采样未覆盖节点）。

**微观事实层**（Micro-Fact Layer）：通过 `NetworkXGraphAdapter` 和 `IntentGraphLinker` 在知识图谱中检索与意图相关的子图，支持配置最大跳数和最大节点数，将子图序列化为自然语言作为生成依据。

**逻辑批评层**（Logic-Critic Layer）：对生成的 QA 对进行质量验证，通过后标注元数据输出。管道采用迭代策略，循环执行"采样→检索→生成→验证"，最大迭代次数为目标数量的 3 倍。完成后输出覆盖率统计。

### 4.5 层级结构提取

ArborGraph 提供多种图分区策略将知识图谱组织为适合 QA 生成的子图社区：

**BFS 分区**（`BFSPartitioner`）：以随机种子节点为起点，通过广度优先搜索扩展社区，直至达到最大节点数限制。适用于一般性的图分区需求。

**DFS 分区**（`DFSPartitioner`）：采用深度优先搜索策略扩展社区，倾向于生成沿路径延伸的线性社区，适用于链式推理数据的生成。

**Leiden 分区**（`LeidenPartitioner`）：利用 Leiden 社区检测算法，基于模块度（Modularity）将知识图谱划分为内聚性强的社区。实现上使用 igraph 库构建图结构，通过 `ModularityVertexPartition` 进行社区检测。支持仅使用最大连通分量（LCC）和全图两种模式，并提供社区规模上限切分功能。

**ECE 分区**（`ECEPartitioner`）：如 4.2 节所述，基于模型知识盲点进行分区。

**锚点 BFS 分区**（`AnchorBFSPartitioner`）：以特定类型或特定 ID 的节点为锚点进行 BFS 扩展，适用于围绕核心概念生成数据的场景。

**层级分区**（`HierarchicalPartitioner`）：专门识别知识图谱中的层级关系（如 is-a、part-of），以具有层级父子关系的节点集合构建社区，支持配置最大深度和每层最大兄弟节点数。

## 5. 工程实现

### 5.1 模块化设计

ArborGraph 的核心库遵循严格的分层抽象设计。`bases/` 目录定义了所有功能组件的抽象基类：

- `BaseLLMClient`：统一的 LLM 客户端接口，定义 `generate_answer`、`generate_topk_per_token`、`generate_inputs_prob` 等核心方法，以及温度、top-p、top-k 等生成参数。
- `BaseGenerator`：QA 生成器基类，定义 `build_prompt`、`parse_response`、`generate` 等方法，并提供上下文和来源信息附加的通用逻辑。
- `BasePartitioner`：图分区器基类，定义 `partition` 和 `community2batch` 方法，将社区（Community）转换为生成器所需的批次格式。
- `BaseGraphStorage`：图存储抽象，定义节点和边的 CRUD 操作。
- `BaseCritic`：质量批评家基类，定义 `validate` 方法，返回 `CriticResult`（包含通过与否、分数、原因和建议）。

这种设计使得各组件可以独立替换和扩展。例如，可以在不修改管道代码的情况下，将 `OpenAIClient` 替换为其他 LLM 后端，或自定义新的分区算法。

### 5.2 LLM 客户端与优化

`OpenAIClient` 是框架的主要 LLM 客户端实现，基于 OpenAI 异步 SDK 构建。其关键设计包括：

- **双客户端架构**：ArborGraph 主类同时维护合成器客户端（`synthesizer_llm_client`）和待训练客户端（`trainee_llm_client`），分别用于数据生成和知识盲点评估，支持使用不同的模型和配置。
- **自动重试**：使用 `tenacity` 库实现指数退避重试策略，针对限流、连接和超时异常最多重试 5 次。
- **速率限制**：通过 RPM/TPM 限制器控制请求频率。
- **Token 统计与兼容性**：自动记录 token 使用量，支持思维标签过滤和 Extra Body 参数注入以兼容不同 API 提供商。

### 5.3 批量处理与缓存

为降低 LLM 调用成本并提升处理效率，ArborGraph 实现了多层次的优化机制：

**Prompt 缓存**（`PromptCache`）：基于 Prompt 文本、历史对话和生成参数的组合哈希进行缓存查找。支持最大条目数限制（默认 10000 条）和 TTL 过期策略，采用 FIFO 淘汰策略。

**批量请求管理器**（`BatchRequestManager`）：将多个独立 LLM 请求聚合为批次。管理器维护异步请求队列，当请求数达到阈值或等待超时时触发批量处理，每个请求通过 `asyncio.Future` 获取结果。

**自适应批量管理器**（`AdaptiveBatchRequestManager`）：在基础管理器上增加动态调整。通过滑动窗口监控 API 响应时间和错误率：响应过慢或错误率过高时减半批量大小，响应快速且稳定时增加 50%，调整间隔不低于 10 秒。

**批量 LLM 包装器**（`BatchLLMWrapper`）：透明封装缓存和批量管理器，在 `generate_answer` 中依次检查缓存、使用批量管理器、写入缓存，上层代码无需感知优化细节。

**Prompt 合并**：KG 构建阶段将多个文本块抽取任务合并为单一 Prompt（合并大小 5 可减少约 80% 调用），并实现空响应重试机制。

**合并生成模式**：聚合式、CoT 等生成器支持合并模式，将两阶段生成压缩为单次调用，减少 50% API 调用。解析失败时自动回退到两阶段模式。

### 5.4 全栈平台架构

ArborGraph 提供完整的 Web 平台，支持可视化操作与协作：

**前端**（Vue 3 + Element Plus + TypeScript）：包含任务管理（`Tasks.vue`、`TaskDetail.vue`、`CreateTask.vue`）、数据审核（`Review.vue`、`ReviewDetail.vue`）、意图管道配置（`IntentPipeline.vue`、`IntentConfig.vue`、`IntentTaxonomies.vue`）、全局配置与用户认证等核心视图。使用 Pinia 状态管理和 Vue Router 路由控制。

**后端**（FastAPI）：提供 RESTful API 端点，包括核心任务管理（`endpoints.py`）、意图管道（`endpoints_intent.py`）、异步任务处理（`task_processor.py`）、认证服务（`auth_service.py`）、审核服务（`review_service.py`、`auto_review_service.py`）、配置管理（`config_service.py`）和文件管理（`file_service.py`）。

## 6. 质量控制机制

ArborGraph 构建了多层次的质量控制体系，贯穿数据生成的全过程：

### 6.1 LLM 批评家

`LLMCritic` 使用 LLM 自身作为质量审查员，对生成的 QA 对进行四维评估：

- **事实准确性**（Factual Accuracy）：答案是否与上下文中的事实一致。
- **逻辑连贯性**（Logical Coherence）：答案是否逻辑严谨、结构合理。
- **完整性**（Completeness）：答案是否充分回应了问题。
- **相关性**（Relevance）：问题是否与源上下文相关。

批评家使用结构化的 Prompt 引导 LLM 以 JSON 格式输出评分结果，包含各维度得分（0-1）、综合得分、通过与否判断、原因说明和改进建议。系统提供可配置的最低通过分数（默认 0.6），并支持最多 2 次重试以应对 LLM 响应解析失败的情况。

### 6.2 规则批评家

`RuleCritic` 提供可插拔的规则验证框架，适用于具有明确形式规则的领域。内置规则包括：

- `min_answer_length`：答案最小长度验证。
- `min_question_length`：问题最小长度验证。
- `answer_not_identical_to_question`：答案不得与问题完全相同。
- `answer_contains_keywords`：答案应包含上下文中的关键词。

每条规则携带权重，综合得分为加权通过率。用户可自定义规则函数并注册到批评家中，满足领域特定的质量要求（如数学证明的格式验证、法规引用的合规性检查等）。

### 6.3 响应解析容错

框架在 LLM 响应解析阶段实现了多层容错机制：

- **响应修复**（`repair_llm_response`）：预处理 LLM 输出，修复常见格式问题。
- **多标记与多语言支持**：兼容 "Question:/Answer:"、"问题：/答案："、"Q:/A:" 等多种标记格式。
- **元描述过滤与降级策略**：自动移除 LLM 前导描述，标准解析失败时回退到宽松正则匹配。

### 6.4 去重机制

生成的 QA 对通过内容哈希（`compute_content_hash`）进行去重。每个问题文本经哈希计算生成唯一标识，在存储前检查是否已存在相同哈希的 QA 对，避免重复数据进入训练集。

## 7. 实验设计

ArborGraph 配备了系统性的实验验证计划，分为六个阶段：

**Phase 0（可行性验证）**：验证各核心模块（原子、多跳、聚合、CoT 四种生成模式）可正常运行并端到端产出有效 SFT 数据，每种模式应输出至少 5 条 Alpaca 格式的 QA 对。

**Phase 1（数据质量对比）**：与基线方法对比生成数据的质量，评估指标包括事实准确性、知识覆盖度、问题多样性等。

**Phase 2（下游微调效果）**：验证生成数据在下游 SFT 任务中的实际效果，通过微调后模型在标准评测基准上的表现评估数据价值。

**Phase 3（消融实验）**：分析各模块（ECE 盲点识别、意图驱动管道、多模式生成、质量控制等）对最终数据质量的贡献度。

**Phase 4（效率实验）**：评估各项工程优化（Prompt 缓存、批量处理、Prompt 合并、自适应批量）对 LLM 调用成本和端到端处理时间的改善程度。

**Phase 5（领域迁移实验）**：验证框架在不同领域（如通用、医学、法律、金融等）上的迁移能力和适应性。

## 8. 总结与展望

### 8.1 工作总结

ArborGraph 框架从知识图谱构建、层级结构提取、意图驱动采样到多模式 QA 生成，形成了一条完整的 SFT 合成数据生成链路。相较于现有方法，ArborGraph 的核心优势在于：

1. **知识覆盖的系统性**：ECE 机制确保生成数据聚焦于模型的知识薄弱环节，而非重复已掌握的知识。
2. **数据类型的多样性**：五种生成模式覆盖了从简单事实回忆到复杂多步推理的完整认知谱系。
3. **领域适应的灵活性**：可插拔的分类树和规则批评家使得框架可快速适配新领域。
4. **工程效率的优化**：多层次的缓存、批量和合并策略显著降低 LLM 调用成本。
5. **全栈平台的可用性**：Web 可视化平台降低了使用门槛，支持团队协作和数据审核。

### 8.2 未来展望

ArborGraph 未来的发展方向包括以下几个维度：

**算法层面**：引入更精细的多模态知识图谱构建能力；探索基于强化学习的自适应生成策略；研究跨文档、跨语言的知识图谱融合。

**工程层面**：实现分布式知识图谱构建和 QA 生成；引入向量数据库支持语义检索；完善评测框架实现自动化闭环评估。

**应用层面**：开发垂直领域预置模板；支持人机协作的交互式数据生成；拓展至评测数据集构建、数据增强、知识蒸馏等场景。
