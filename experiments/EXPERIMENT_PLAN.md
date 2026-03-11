# KGE-Gen (DA-ToG) 可行性验证实验规划

> **目标**：初步验证 DA-ToG（树 + 图 + Critic）相比 GraphGen（仅图）和 Condor（仅树）的提升，判断新论文的可行性。
>
> **原则**：快速、低成本、能给出明确信号。不追求完美，先跑通再迭代。

---

## 一、实验总览

### 1.1 对比方法

| 编号 | 方法 | 数据来源 | 说明 |
|------|------|----------|------|
| **M1** | GraphGen | 自己生成 | 仅用 KG + 分区 + QA 生成，代码库已有 |
| **M2** | DA-ToG (Ours) | 自己生成 | 分类树 + KG + Critic，代码库已有 |
| **M3** | Condor | 公开数据 | 从 HuggingFace 下载 Condor-SFT-20K |
| **M0** | Self-Instruct (可选) | 自己生成 | 直接让 LLM 从文档生成 QA，作为最弱 baseline |

### 1.2 两个实验阶段

| 阶段 | 内容 | 不需要微调 | 周期 |
|------|------|-----------|------|
| **Phase 1** | QA 数据质量直接对比 | ✅ | 3-5 天 |
| **Phase 2** | 微调同一模型后的下游效果对比 | ❌ 需要 GPU | 5-7 天 |

---

## 二、Phase 1：QA 数据质量对比（核心验证）

### 2.1 数据准备

#### 输入文档
- 使用项目自带的示例文档：`resources/input_examples/txt_demo.txt`
- 额外准备 1-2 个领域的文档（建议 50-100 篇，总量 ~50K tokens）
- **GraphGen 和 DA-ToG 必须用同一批文档**

#### 各方法生成数据

```bash
# M1: GraphGen —— 文档 → KG → 分区 → QA
source /workspace/.venv/bin/activate
python graphgen_cli.py -i <input_file> -k <API_KEY> \
    --output experiments/data/graphgen_output/

# M2: DA-ToG —— 文档 → KG + 分类树 + Critic → QA
python scripts/run_domain.py \
    --domain graphgen/configs/datog/finance \
    --output experiments/data/datog_output/

# M3: Condor —— 直接下载
# huggingface-cli download internlm/Condor-SFT-20K \
#     --local-dir experiments/data/condor_data/
```

#### 数据量对齐
- 每种方法生成/抽取 **1000-5000 条** QA 对（先用小规模验证流程）
- 正式实验时扩大到 10K-20K

### 2.2 自动化评测指标

| 维度 | 指标 | 计算方法 | 预期结果 |
|------|------|----------|----------|
| **多样性** | MTLD 词汇多样性 | `graphgen/models/evaluator/mtld_evaluator.py` | DA-ToG ≥ GraphGen |
| **多样性** | 问题去重率 | 问题文本 hash 后统计唯一率 | DA-ToG 更高 |
| **覆盖广度** | 分类树节点覆盖率 | `DAToGMetrics.calculate_coverage()` | DA-ToG >> GraphGen |
| **覆盖广度** | 认知维度分布均匀度 | `DAToGMetrics.calculate_distribution()` | DA-ToG 更均匀 |
| **事实深度** | 平均涉及实体数 | 统计 QA metadata 中的 graph 信息 | DA-ToG ≈ GraphGen |
| **事实深度** | 平均推理跳数 | 子图最短路径统计 | DA-ToG ≈ GraphGen |
| **质量下限** | Critic 通过率 | DA-ToG 的 RuleCritic 通过/拒绝比例 | DA-ToG 有数据，GraphGen 无 |
| **长度分布** | 平均问题/答案长度 | tokenizer 统计 | 三者对比 |

### 2.3 人工/LLM-as-Judge 评测

从每组数据中随机抽 **50 条**，用 GPT-4 或人工打分（1-5 分）：

| 评分维度 | 说明 |
|----------|------|
| 事实准确性 | 答案是否包含事实错误或幻觉 |
| 问题质量 | 问题是否清晰、有意义、有难度梯度 |
| 答案完整性 | 答案是否充分回答了问题 |
| 话题多样性 | 50 条样本是否覆盖了不同子话题 |
| 自然度 | 语言是否自然流畅，而非"图转文"式僵硬 |
| 训练价值 | 该 QA 对用来 SFT 微调是否有实际价值 |

### 2.4 GraphGen vs DA-ToG 核心对比表（模板）

| 指标 | GraphGen (M1) | DA-ToG (M2) | 提升 |
|------|---------------|-------------|------|
| MTLD ↑ | | | |
| 问题唯一率 ↑ | | | |
| 分类树覆盖率 ↑ | N/A | | |
| 认知维度均匀度 ↑ | N/A | | |
| 平均实体数 | | | |
| 平均跳数 | | | |
| Critic 通过率 | N/A | | |
| 人工评分均值 ↑ | | | |

### 2.5 和 Condor 的对比策略

Condor 未开源代码，对比方式：

1. **数据层面**：下载 Condor-SFT-20K，用同样的自动化指标（MTLD、长度分布、去重率）直接和 DA-ToG 生成的数据对比
2. **效果层面**：留到 Phase 2，用微调后的模型在 Benchmark 上对比
3. **论文写法**：如有指标无法直接对比，引用 Condor 论文中的报告数字，注明"Results cited from original paper"

---

## 三、Phase 2：下游微调效果对比（需 GPU）

### 3.1 实验设置

| 配置项 | 统一设置 |
|--------|----------|
| **Base 模型** | Qwen-2.5-7B（或 Llama-3-8B） |
| **微调工具** | LLaMA Factory |
| **SFT 数据量** | 每组统一 10K-20K 条 |
| **微调超参** | lr=2e-5, epochs=3, batch_size=4, max_len=2048（统一） |
| **微调方式** | LoRA (rank=64) 或 Full Fine-tuning |

### 3.2 微调数据来源

| 组别 | 数据 |
|------|------|
| M0 (可选) | Self-Instruct 生成的 QA |
| M1 | GraphGen 生成的 QA |
| M2 | DA-ToG 生成的 QA |
| M3 | Condor-SFT-20K（抽取等量子集） |

### 3.3 评测 Benchmark

| 类型 | Benchmark | 评测什么 |
|------|-----------|----------|
| 通用知识 | MMLU / C-Eval | SFT 后通用能力是否保持或提升 |
| 对话质量 | AlpacaEval / MT-Bench | 人类偏好评分 |
| 领域知识 | FinEval / 自建 100 题 | 垂直领域知识是否增强 |
| 推理能力 | GSM8K / ARC (可选) | 推理能力是否受益 |

### 3.4 下游效果对比表（模板）

| Benchmark | Base (M0) | GraphGen (M1) | DA-ToG (M2) | Condor (M3) |
|-----------|-----------|----------------|-------------|-------------|
| C-Eval | | | | |
| MMLU | | | | |
| AlpacaEval | | | | |
| FinEval | | | | |
| 自建测试集 | | | | |

---

## 四、消融实验（Phase 1 确认可行后再做）

| 消融组 | 设置 | 验证什么 |
|--------|------|----------|
| DA-ToG w/o Critic | 去掉 Logic-Critic 层 | Critic 的价值 |
| DA-ToG w/o Tree | 去掉 Macro-Intent 层 | 分类树的价值 |
| DA-ToG w/o Graph | 去掉 Micro-Fact 层 | 图谱的价值 |
| DA-ToG w/o ECE | 随机采样替换 ECE | 知识盲点识别的价值 |

---

## 五、关键决策记录

### 5.1 关于 Condor 的对比

- **不需要**用和 Condor 完全相同的数据集和模型
- **需要**在自己的实验中统一 Base 模型和微调超参
- Condor-SFT-20K 可直接用于微调对比
- 如需更严格对比，可用 Condor README 中的 Prompt 模板实现简化版

### 5.2 关于合成器模型

- GraphGen 和 DA-ToG **必须用同一个 LLM**（如 Qwen-2.5-72B 或 GPT-4）
- 在 `.env` 中配置 `SYNTHESIZER_MODEL`、`SYNTHESIZER_BASE_URL`、`SYNTHESIZER_API_KEY`

### 5.3 变量控制清单

| 变量 | 是否需要统一 | 说明 |
|------|-------------|------|
| 输入文档 | ✅ GraphGen 和 DA-ToG 之间 | Condor 不依赖外部文档，无需统一 |
| 合成器 LLM | ✅ 所有自己跑的方法 | Condor 用的是他们自己的模型 |
| 生成数据量 | ✅ 所有方法 | 对齐到同一量级 |
| 被微调的 Base 模型 | ✅ 所有方法 | 必须完全一致 |
| 微调超参 | ✅ 所有方法 | lr, epochs, batch_size 等 |
| 评测 Benchmark | ✅ 所有方法 | 同一套测试题 |

---

## 六、目录结构

```
experiments/
├── EXPERIMENT_PLAN.md          ← 本文件（实验规划）
├── data/
│   ├── graphgen_output/        ← GraphGen 生成的 QA 数据
│   ├── datog_output/           ← DA-ToG 生成的 QA 数据
│   └── condor_data/            ← Condor-SFT-20K 下载数据
├── phase1_data_quality/        ← Phase 1 数据质量对比结果
├── phase2_downstream/          ← Phase 2 微调效果对比结果
├── eval_results/               ← 评测结果汇总
└── scripts/                    ← 实验脚本
```

---

## 七、执行优先级

```
Week 1 (最高优先级):
  ├── [1] 准备输入文档
  ├── [2] 用 GraphGen 生成 QA 数据
  ├── [3] 用 DA-ToG 生成 QA 数据
  └── [4] Phase 1 自动化指标对比 → 得到第一张对比表

Week 2 (确认可行后):
  ├── [5] 下载 Condor-SFT-20K
  ├── [6] Phase 1 人工/LLM-Judge 评测
  └── [7] 三方数据质量对比表

Week 3-4 (需 GPU):
  ├── [8] LLaMA Factory 微调 × 3-4 组
  ├── [9] Benchmark 评测
  └── [10] Phase 2 下游效果对比表

Week 5+ (可行性确认后):
  ├── [11] 消融实验
  ├── [12] 扩大数据规模重跑
  └── [13] 论文撰写
```
