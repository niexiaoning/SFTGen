# ArborGraph (ArborGraph-Intent) 可行性验证实验规划

> **目标**：初步验证 ArborGraph-Intent（树 + 图 + Critic）相比 GraphGen（仅图）和 Condor（仅树）的提升，判断新论文的可行性。
>
> **原则**：快速、低成本、能给出明确信号。不追求完美，先跑通再迭代。

---

## 一、实验总览

### 1.1 对比方法

| 编号 | 方法 | 数据来源 | 说明 |
|------|------|----------|------|
| **M1** | GraphGen | 自己生成 | 仅用 KG + 分区 + QA 生成，代码库已有 |
| **M2** | ArborGraph-Intent (Ours) | 自己生成 | 分类树 + KG + Critic，代码库已有 |
| **M3** | Condor | 公开数据 | 从 HuggingFace 下载 Condor-SFT-20K |
| **M0** | Self-Instruct (可选) | 自己生成 | 直接让 LLM 从文档生成 QA，作为最弱 baseline |

### 1.2 两个实验阶段

| 阶段 | 内容 | 不需要微调 | 周期 |
|------|------|-----------|------|
| **Phase 1** | QA 数据质量直接对比 | ✅ | 3-5 天 |
| **Phase 2** | 微调同一模型后的下游效果对比 | ❌ 需要 GPU | 5-7 天 |

---

## 二、数据集设计（核心策略）

### 2.0 新项目的核心差异化能力

在设计数据集之前，需要明确新项目相比 GraphGen 的两层改进：

1. **图分区层**：新增 `HierarchicalPartitioner`，能识别层级关系（`is_a`, `subclass_of`, `part_of` 等），进行横向兄弟分组和纵向链式采样，生成对比类和分类类 QA
2. **ArborGraph-Intent 框架层**：引入 Condor 式分类树（Macro-Intent）+ 认知维度模板 + Logic-Critic 验证

因此，**层级结构越明显的文档，新项目的优势越大**。但为论文可信度，需同时包含有利和不利场景。

### 2.1 数据集分组策略

将实验数据集分为三组，覆盖不同层级强度的文档：

| 分组 | 层级特征 | 文档类型 | 预期结果 | 论文中的作用 |
|------|----------|----------|----------|-------------|
| **组 A：强层级** | 文本包含显式分类体系、总-分结构 | 教科书、分类标准、技术规范 | ArborGraph-Intent >> GraphGen | 证明核心优势 |
| **组 B：弱层级** | 文本为平铺叙事，无明显层级 | 新闻报道、研究论文、事实描述 | ArborGraph-Intent ≈ GraphGen | 证明不会更差 |
| **组 C：混合型** | 部分内容有层级，部分为平铺 | 领域综述、维基百科词条 | ArborGraph-Intent > GraphGen | 证明真实场景有效 |

论文叙事目标：
> "在层级知识丰富的场景中，ArborGraph-Intent 显著优于 GraphGen（+X%）；在层级知识较少的场景中，ArborGraph-Intent 与 GraphGen 持平，不引入额外开销。"

### 2.2 各组推荐数据源

#### 组 A：强层级文档（首批实验优先用这组）

| 领域 | 推荐数据源 | 层级特征 | 规模建议 |
|------|-----------|----------|----------|
| **计算机科学** | ACM CCS 分类下的 Wikipedia 词条 | 算法→排序算法→快速排序 | 30-50 篇 |
| **医学** | MeSH 分类下的疾病描述文档 | 心血管疾病→冠心病→心肌梗死 | 30-50 篇 |
| **金融** | 银行业监管文件（巴塞尔协议章节） | 风险→市场风险→利率风险（与已有 `finance/taxonomy.json` 对齐） | 30-50 篇 |
| **生物学** | 物种分类科普文档 | 界→门→纲→目→科→属→种 | 30-50 篇 |

适合的文档特征：
- 文本本身包含"XX 分为 A、B、C 三类"等分类描述
- 有清晰的"总-分"结构（先概述再展开）
- 概念之间有明确的 is_a / part_of / subclass_of 关系
- 章节嵌套明显（标准规范类）

#### 组 B：弱层级文档

| 领域 | 推荐数据源 | 特征 | 规模建议 |
|------|-----------|------|----------|
| **科技新闻** | 科技媒体文章 | 平铺叙事、事件报道 | 30-50 篇 |
| **学术论文** | arXiv 摘要/引言 | 论证型、横向关联为主 | 30-50 篇 |
| **历史** | 历史事件描述 | 时间线叙事、因果链 | 30-50 篇 |

#### 组 C：混合型文档

| 领域 | 推荐数据源 | 特征 | 规模建议 |
|------|-----------|------|----------|
| **综合** | 维基百科长文章 | 有目录结构但内容混合 | 30-50 篇 |
| **教育** | 在线课程讲义 | 部分章节有分类，部分为讲解 | 30-50 篇 |

### 2.3 可行性验证阶段的最小数据集

首批实验只需组 A 的 **1 个领域**即可：

- 选择 **金融** 或 **计算机科学**（与已有 taxonomy.json 对齐最方便）
- 准备 30-50 篇文档，总量 30K-50K tokens
- 用同一批文档分别跑 GraphGen 和 ArborGraph-Intent
- 如果组 A 上没有优势 → 方法有问题，需要回去改
- 如果组 A 上有明显优势 → 再补组 B、C 做完整论文实验

### 2.4 不适合的文档类型（避免使用）

| 类型 | 原因 |
|------|------|
| 纯叙事/新闻 | 没有层级关系，两种方法差异不大 |
| 纯事实罗列 | 实体之间主要是横向关联，GraphGen 本来就擅长 |
| 对话/评论 | 非知识型文本，提取不出有意义的 KG |
| 过短文本（<200 tokens） | 构建不出有意义的知识图谱 |

---

## 三、Phase 1：QA 数据质量对比（核心验证）

### 3.1 数据准备

#### 输入文档
- **首批实验**：组 A 的 1 个领域（建议金融），30-50 篇，30K-50K tokens
- **完整实验**：组 A + B + C 各 1 个领域，每组 30-50 篇
- **GraphGen 和 ArborGraph-Intent 必须用同一批文档**

#### 各方法生成数据

```bash
# M1: GraphGen —— 文档 → KG → 分区(BFS/ECE) → QA
source /workspace/.venv/bin/activate
python arborgraph_cli.py -i <input_file> -k <API_KEY> \
    --output experiments/data/arborgraph_output/

# M2: ArborGraph-Intent —— 文档 → KG + 分类树 + HierarchicalPartitioner + Critic → QA
python scripts/run_domain.py \
    --domain graphgen/configs/intent/finance \
    --output experiments/data/intent_output/

# M3: Condor —— 直接下载
# huggingface-cli download internlm/Condor-SFT-20K \
#     --local-dir experiments/data/condor_data/
```

#### 数据量对齐
- 可行性验证：每种方法 **500-1000 条**
- 正式实验：每种方法 **5K-10K 条**（每个数据集分组分别生成）
- 论文最终版：扩大到 10K-20K

### 3.2 自动化评测指标

| 维度 | 指标 | 计算方法 | 预期结果 |
|------|------|----------|----------|
| **多样性** | MTLD 词汇多样性 | `graphgen/models/evaluator/mtld_evaluator.py` | ArborGraph-Intent ≥ GraphGen |
| **多样性** | 问题去重率 | 问题文本 hash 后统计唯一率 | ArborGraph-Intent 更高 |
| **覆盖广度** | 分类树节点覆盖率 | `IntentMetrics.calculate_coverage()` | ArborGraph-Intent >> GraphGen |
| **覆盖广度** | 认知维度分布均匀度 | `IntentMetrics.calculate_distribution()` | ArborGraph-Intent 更均匀 |
| **事实深度** | 平均涉及实体数 | 统计 QA metadata 中的 graph 信息 | ArborGraph-Intent ≈ GraphGen |
| **事实深度** | 平均推理跳数 | 子图最短路径统计 | ArborGraph-Intent ≈ GraphGen |
| **质量下限** | Critic 通过率 | ArborGraph-Intent 的 RuleCritic 通过/拒绝比例 | ArborGraph-Intent 有数据，GraphGen 无 |
| **长度分布** | 平均问题/答案长度 | tokenizer 统计 | 三者对比 |

### 3.3 人工/LLM-as-Judge 评测

从每组数据中随机抽 **50 条**，用 GPT-4 或人工打分（1-5 分）：

| 评分维度 | 说明 |
|----------|------|
| 事实准确性 | 答案是否包含事实错误或幻觉 |
| 问题质量 | 问题是否清晰、有意义、有难度梯度 |
| 答案完整性 | 答案是否充分回答了问题 |
| 话题多样性 | 50 条样本是否覆盖了不同子话题 |
| 自然度 | 语言是否自然流畅，而非"图转文"式僵硬 |
| 训练价值 | 该 QA 对用来 SFT 微调是否有实际价值 |

### 3.4 层级感知专项指标（新增）

针对新项目的核心差异化能力，增加以下层级相关指标：

| 指标 | 计算方法 | 说明 |
|------|----------|------|
| **层级关系识别率** | 统计 KG 中被标记为 is_a/subclass_of/part_of 的边占总边数的比例 | 越高说明文档层级越丰富 |
| **兄弟分组社区数** | `HierarchicalPartitioner` 输出中 `type=sibling_group` 的社区数量 | ArborGraph-Intent 独有，GraphGen 为 0 |
| **纵向链式社区数** | `HierarchicalPartitioner` 输出中 `type=vertical_chain` 的社区数量 | ArborGraph-Intent 独有，GraphGen 为 0 |
| **对比类 QA 占比** | 人工/LLM 标注生成的 QA 中包含"对比""区别""不同"等对比性问题的比例 | ArborGraph-Intent 应更高 |
| **分类类 QA 占比** | 人工/LLM 标注生成的 QA 中包含"属于""分为""类型"等分类性问题的比例 | ArborGraph-Intent 应更高 |

这组指标按数据集分组（A/B/C）分别统计，预期：
- **组 A（强层级）**：ArborGraph-Intent 层级指标远高于 GraphGen
- **组 B（弱层级）**：两者层级指标都低，差异不大
- **组 C（混合）**：ArborGraph-Intent 层级指标中等偏高

### 3.5 GraphGen vs ArborGraph-Intent 核心对比表（模板）

按数据集分组分别填写，以下为单组模板：

| 指标 | GraphGen (M1) | ArborGraph-Intent (M2) | 提升 |
|------|---------------|-------------|------|
| MTLD ↑ | | | |
| 问题唯一率 ↑ | | | |
| 分类树覆盖率 ↑ | N/A | | |
| 认知维度均匀度 ↑ | N/A | | |
| 平均实体数 | | | |
| 平均跳数 | | | |
| Critic 通过率 | N/A | | |
| 兄弟分组社区数 | 0 | | |
| 纵向链式社区数 | 0 | | |
| 对比类 QA 占比 ↑ | | | |
| 分类类 QA 占比 ↑ | | | |
| 人工评分均值 ↑ | | | |

论文中应展示三组（A/B/C）各一张表，或合并为一张大表。

### 3.6 和 Condor 的对比策略

Condor 未开源代码，对比方式：

1. **数据层面**：下载 Condor-SFT-20K，用同样的自动化指标（MTLD、长度分布、去重率）直接和 ArborGraph-Intent 生成的数据对比
2. **效果层面**：留到 Phase 2，用微调后的模型在 Benchmark 上对比
3. **论文写法**：如有指标无法直接对比，引用 Condor 论文中的报告数字，注明"Results cited from original paper"

---

## 四、Phase 2：下游微调效果对比（需 GPU）

### 4.1 实验设置

| 配置项 | 统一设置 |
|--------|----------|
| **Base 模型** | Qwen-2.5-7B（或 Llama-3-8B） |
| **微调工具** | LLaMA Factory |
| **SFT 数据量** | 每组统一 10K-20K 条 |
| **微调超参** | lr=2e-5, epochs=3, batch_size=4, max_len=2048（统一） |
| **微调方式** | LoRA (rank=64) 或 Full Fine-tuning |

### 4.2 微调数据来源

| 组别 | 数据 |
|------|------|
| M0 (可选) | Self-Instruct 生成的 QA |
| M1 | GraphGen 生成的 QA |
| M2 | ArborGraph-Intent 生成的 QA |
| M3 | Condor-SFT-20K（抽取等量子集） |

### 4.3 评测 Benchmark

| 类型 | Benchmark | 评测什么 |
|------|-----------|----------|
| 通用知识 | MMLU / C-Eval | SFT 后通用能力是否保持或提升 |
| 对话质量 | AlpacaEval / MT-Bench | 人类偏好评分 |
| 领域知识 | FinEval / 自建 100 题 | 垂直领域知识是否增强 |
| 推理能力 | GSM8K / ARC (可选) | 推理能力是否受益 |

### 4.4 下游效果对比表（模板）

| Benchmark | Base (M0) | GraphGen (M1) | ArborGraph-Intent (M2) | Condor (M3) |
|-----------|-----------|----------------|-------------|-------------|
| C-Eval | | | | |
| MMLU | | | | |
| AlpacaEval | | | | |
| FinEval | | | | |
| 自建测试集 | | | | |

---

## 五、消融实验（Phase 1 确认可行后再做）

| 消融组 | 设置 | 验证什么 |
|--------|------|----------|
| ArborGraph-Intent w/o Critic | 去掉 Logic-Critic 层 | Critic 的价值 |
| ArborGraph-Intent w/o Tree | 去掉 Macro-Intent 层 | 分类树的价值 |
| ArborGraph-Intent w/o Graph | 去掉 Micro-Fact 层 | 图谱的价值 |
| ArborGraph-Intent w/o ECE | 随机采样替换 ECE | 知识盲点识别的价值 |
| ArborGraph-Intent w/o HierPartitioner | 用 BFS 替换 HierarchicalPartitioner | 层级分区的价值（在组 A 上做） |

消融实验建议**在组 A（强层级）文档上做**，因为层级相关模块在这类数据上效果最明显，消融后的下降也最显著。

---

## 六、关键决策记录

### 6.1 关于 Condor 的对比

- **不需要**用和 Condor 完全相同的数据集和模型
- **需要**在自己的实验中统一 Base 模型和微调超参
- Condor-SFT-20K 可直接用于微调对比
- 如需更严格对比，可用 Condor README 中的 Prompt 模板实现简化版

### 6.2 关于合成器模型

- GraphGen 和 ArborGraph-Intent **必须用同一个 LLM**（如 Qwen-2.5-72B 或 GPT-4）
- 在 `.env` 中配置 `SYNTHESIZER_MODEL`、`SYNTHESIZER_BASE_URL`、`SYNTHESIZER_API_KEY`

### 6.3 关于数据集选择的原则

- **不能只选有利数据集**：如果只展示组 A（强层级），审稿人会质疑"是否挑数据了"
- **分组对比是最佳策略**：同时展示强层级/弱层级/混合三组，证明方法的鲁棒性
- **可行性验证阶段先只用组 A**：用最有利的场景快速验证方法是否有效
- **正式实验再补齐组 B、C**：确认可行后再投入资源做完整对比
- **论文中应报告文档的层级特征**：如层级关系占比、平均层级深度，让读者理解各组差异

### 6.4 关于代码库中评测工具的现状

| 工具 | 状态 | 说明 |
|------|------|------|
| `graphgen/evaluate.py` 评测主脚本 | ✅ 已实现 | 一键跑 MTLD + UniEval + 奖励模型，需要 GPU |
| `MTLDEvaluator` | ✅ 已实现 | 纯 CPU |
| `UniEvaluator` | ✅ 已实现 | 需要 GPU + 模型 `MingZhong/unieval-sum` |
| `RewardEvaluator` | ✅ 已实现 | 需要 GPU + 模型 `OpenAssistant/reward-model-deberta-v3-large-v2` |
| `LengthEvaluator` | ✅ 已实现 | 纯 CPU |
| `scripts/coverage_metrics.py` | ✅ 已实现 | 长尾覆盖率、复杂关系覆盖率、平均跳数，纯 CPU |
| `IntentMetrics` | ✅ 已实现 | 分类树覆盖率、认知维度分布 |
| 三个 Baseline（直接生成/模板填充/检索增强） | ❌ 未实现 | 论文注明"需单独实现" |
| `EXPERIMENT_SCRIPTS.md` | ❌ 不存在 | 论文引用但从未创建 |
| 论文中的 300 篇文档数据集 | ❌ 不存在 | 需自行准备 |

### 6.5 变量控制清单

| 变量 | 是否需要统一 | 说明 |
|------|-------------|------|
| 输入文档 | ✅ GraphGen 和 ArborGraph-Intent 之间 | Condor 不依赖外部文档，无需统一 |
| 合成器 LLM | ✅ 所有自己跑的方法 | Condor 用的是他们自己的模型 |
| 生成数据量 | ✅ 所有方法 | 对齐到同一量级 |
| 被微调的 Base 模型 | ✅ 所有方法 | 必须完全一致 |
| 微调超参 | ✅ 所有方法 | lr, epochs, batch_size 等 |
| 评测 Benchmark | ✅ 所有方法 | 同一套测试题 |

---

## 七、目录结构

```
experiments/
├── EXPERIMENT_PLAN.md              ← 本文件（实验规划）
├── data/
│   ├── input_docs/                 ← 输入文档
│   │   ├── group_a_hierarchical/   ← 组 A：强层级文档
│   │   ├── group_b_flat/           ← 组 B：弱层级文档
│   │   └── group_c_mixed/          ← 组 C：混合型文档
│   ├── arborgraph_output/            ← GraphGen 生成的 QA 数据
│   │   ├── group_a/
│   │   ├── group_b/
│   │   └── group_c/
│   ├── intent_output/               ← ArborGraph-Intent 生成的 QA 数据
│   │   ├── group_a/
│   │   ├── group_b/
│   │   └── group_c/
│   └── condor_data/                ← Condor-SFT-20K 下载数据
├── phase1_data_quality/            ← Phase 1 数据质量对比结果
├── phase2_downstream/              ← Phase 2 微调效果对比结果
├── eval_results/                   ← 评测结果汇总
└── scripts/                        ← 实验脚本
```

---

## 八、执行优先级

```
Week 1 (最高优先级 — 可行性验证):
  ├── [1] 准备组 A（强层级）文档（1 个领域，30-50 篇）
  ├── [2] 用 GraphGen 在组 A 上生成 500-1000 条 QA
  ├── [3] 用 ArborGraph-Intent 在组 A 上生成 500-1000 条 QA
  ├── [4] Phase 1 自动化指标对比（MTLD + 覆盖度 + 层级指标）
  └── [5] 得到第一张对比表 → 判断可行性信号

Week 2 (可行性确认后 — 补齐数据集):
  ├── [6] 准备组 B（弱层级）和组 C（混合型）文档
  ├── [7] 三组数据集分别跑 GraphGen 和 ArborGraph-Intent
  ├── [8] 下载 Condor-SFT-20K
  ├── [9] Phase 1 人工/LLM-Judge 评测（每组各抽 50 条）
  └── [10] 完整的三方 × 三组对比表

Week 3-4 (需 GPU):
  ├── [11] LLaMA Factory 微调 × 3-4 组
  ├── [12] Benchmark 评测
  └── [13] Phase 2 下游效果对比表

Week 5+ (正式论文实验):
  ├── [14] 消融实验（在组 A 上做）
  ├── [15] 扩大数据规模重跑（每组 5K-10K）
  └── [16] 论文撰写
```
