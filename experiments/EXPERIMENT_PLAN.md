# ArborGraph 实验计划

## 总览

本实验旨在系统性验证 ArborGraph 框架在 SFT 数据生成任务中的有效性。实验分为四个阶段：

1. **可行性验证实验**（Phase 0）：验证核心管线可正常运行并产出有效数据
2. **数据质量对比实验**（Phase 1）：与基线方法对比生成数据的质量
3. **下游微调效果实验**（Phase 2）：验证生成数据在下游任务中的实际效果
4. **消融实验**（Phase 3）：分析各模块的贡献度

附加：**效率实验**（Phase 4）与**领域迁移实验**（Phase 5）。

---

## Phase 0：可行性验证实验

### 目标
确认 ArborGraph 各核心模块可正常运行、端到端产出有效 SFT 数据。

### 0.1 基础管线测试

**数据准备**
- 使用 `resources/input_examples/txt_demo.txt` 作为输入（约 2KB 纯文本）
- 确保环境变量配置正确（`.env` 文件）

**执行命令**
```bash
# 测试 API 连接
python arborgraph_cli.py -i resources/input_examples/txt_demo.txt \
  -k $SYNTHESIZER_API_KEY --test-connection

# 运行完整管线（原子模式）
python arborgraph_cli.py -i resources/input_examples/txt_demo.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type atomic \
  --output-data-format Alpaca \
  --chunk-size 512 \
  --chunk-overlap 50 \
  -o experiments/outputs/phase0_atomic.json

# 运行多跳模式
python arborgraph_cli.py -i resources/input_examples/txt_demo.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type multi_hop \
  --output-data-format Alpaca \
  -o experiments/outputs/phase0_multihop.json

# 运行聚合模式
python arborgraph_cli.py -i resources/input_examples/txt_demo.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type aggregated \
  --output-data-format Alpaca \
  -o experiments/outputs/phase0_aggregated.json

# 运行 CoT 模式
python arborgraph_cli.py -i resources/input_examples/txt_demo.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type cot \
  --output-data-format Alpaca \
  -o experiments/outputs/phase0_cot.json
```

**期望结果**
- 每种模式输出一个 JSON/JSONL 文件，包含至少 5 条 QA 对
- QA 对格式符合 Alpaca 格式：`{"instruction": "...", "input": "...", "output": "..."}`
- 日志中无报错，所有步骤（读取 → 切分 → 知识图谱 → 分区 → 生成）完整执行

**验证脚本**
```bash
python -c "
import json, sys
for mode in ['atomic', 'multihop', 'aggregated', 'cot']:
    path = f'experiments/outputs/phase0_{mode}.json'
    try:
        with open(path) as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else len(data.get('items', []))
        print(f'{mode}: {count} QA pairs generated ✓')
        if count == 0:
            print(f'  WARNING: {mode} generated 0 pairs')
            sys.exit(1)
    except FileNotFoundError:
        print(f'{mode}: file not found ✗')
        sys.exit(1)
print('Phase 0.1 PASSED')
"
```

### 0.2 多格式输入测试

**数据准备**
- `resources/input_examples/json_demo.json`
- `resources/input_examples/jsonl_demo.jsonl`
- `resources/input_examples/csv_demo.csv`

**执行命令**
```bash
for fmt in json jsonl csv; do
  python arborgraph_cli.py -i "resources/input_examples/${fmt}_demo.${fmt}" \
    -k $SYNTHESIZER_API_KEY \
    --output-data-type atomic \
    -o "experiments/outputs/phase0_format_${fmt}.json"
done
```

**期望结果**
- 每种格式均能正常读取并生成 QA 对
- 输出文件非空且格式合法

### 0.3 意图驱动管线测试

**数据准备**
- 使用 `arborgraph/configs/intent/finance/intent_config.yaml` 作为配置
- 输入文本：准备一份约 5000 字的金融领域文本

**执行命令**
```bash
python arborgraph_cli.py -i experiments/data/finance_sample.txt \
  -k $SYNTHESIZER_API_KEY \
  --intent-config arborgraph/configs/intent/finance/intent_config.yaml \
  -o experiments/outputs/phase0_intent.json
```

**期望结果**
- 输出包含意图标注的 QA 对
- 指标报告包含意图覆盖率信息

### 0.4 批量处理测试

**执行命令**
```bash
python arborgraph_cli.py -b \
  resources/input_examples/txt_demo.txt \
  resources/input_examples/json_demo.json \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type atomic
```

**期望结果**
- 两个文件均成功处理
- 批量日志文件生成，包含处理统计

---

## Phase 1：数据质量对比实验

### 目标
对比 ArborGraph 与基线方法生成数据的质量。

### 1.0 数据集准备

准备 3 组不同特征的数据集：

| 数据集 | 特征 | 大小 | 来源 |
|--------|------|------|------|
| D1-强层级 | 有明确层级结构（如教材、技术文档） | 10-20KB | Wikipedia 技术文章 |
| D2-弱层级 | 无明显层级结构（如新闻、对话） | 10-20KB | 新闻语料 |
| D3-混合 | 混合多种文体 | 10-20KB | 综合语料 |

**数据准备命令**
```bash
mkdir -p experiments/data/{d1_strong_hierarchy,d2_weak_hierarchy,d3_mixed}

# D1：从 Wikipedia 获取技术文章（手动准备）
# 将内容保存至 experiments/data/d1_strong_hierarchy/input.txt

# D2：准备新闻语料
# 将内容保存至 experiments/data/d2_weak_hierarchy/input.txt

# D3：混合语料
# 将内容保存至 experiments/data/d3_mixed/input.txt
```

### 1.1 基线方法实现

**方法 A：Self-Instruct（基线）**
```bash
# 使用纯 LLM 直接生成 QA 对（不经过知识图谱）
python experiments/baselines/self_instruct.py \
  --input experiments/data/d1_strong_hierarchy/input.txt \
  --model $SYNTHESIZER_MODEL \
  --api-key $SYNTHESIZER_API_KEY \
  --num-samples 100 \
  --output experiments/outputs/phase1/self_instruct_d1.json
```

**方法 B：ArborGraph（本项目）**
```bash
for dataset in d1_strong_hierarchy d2_weak_hierarchy d3_mixed; do
  for mode in atomic aggregated multi_hop cot; do
    python arborgraph_cli.py \
      -i "experiments/data/${dataset}/input.txt" \
      -k $SYNTHESIZER_API_KEY \
      --output-data-type $mode \
      --output-data-format Alpaca \
      --chunk-size 1024 \
      --chunk-overlap 100 \
      -o "experiments/outputs/phase1/arborgraph_${dataset}_${mode}.json"
  done
done
```

**方法 C：ArborGraph + 意图驱动**
```bash
for dataset in d1_strong_hierarchy d2_weak_hierarchy d3_mixed; do
  python arborgraph_cli.py \
    -i "experiments/data/${dataset}/input.txt" \
    -k $SYNTHESIZER_API_KEY \
    --intent-config arborgraph/configs/intent_config.yaml \
    -o "experiments/outputs/phase1/arborgraph_intent_${dataset}.json"
done
```

### 1.2 自动化评测指标

对所有生成的数据集计算以下指标：

| 指标 | 说明 | 工具/命令 |
|------|------|-----------|
| MTLD | 词汇多样性（越高越好） | `scripts/coverage_metrics.py` |
| UniEval | 语义质量（越高越好） | `arborgraph/models/evaluator/uni_evaluator.py` |
| BLEU-Self | 自相似度（越低越好） | 自定义脚本 |
| 知识覆盖率 | 知识图谱节点覆盖比例 | `scripts/coverage_metrics.py` |
| 长度分布 | 回答长度的统计分布 | `arborgraph/models/evaluator/length_evaluator.py` |

**执行命令**
```bash
python experiments/eval/run_metrics.py \
  --input-dir experiments/outputs/phase1/ \
  --output experiments/results/phase1_metrics.json \
  --metrics mtld,length,coverage,self_bleu
```

**期望结果格式**
```json
{
  "method": "arborgraph_atomic",
  "dataset": "d1_strong_hierarchy",
  "metrics": {
    "mtld": 85.3,
    "avg_answer_length": 128.5,
    "coverage_ratio": 0.82,
    "self_bleu": 0.15,
    "unique_entities_covered": 45
  }
}
```

### 1.3 LLM-as-Judge 评测

使用 GPT-4 级别模型作为评判者，评估生成质量。

**评测维度**
- 事实准确性（1-5 分）
- 问题质量（1-5 分）
- 回答完整性（1-5 分）
- 知识深度（1-5 分）

**执行命令**
```bash
python experiments/eval/llm_judge.py \
  --input-dir experiments/outputs/phase1/ \
  --judge-model gpt-4o \
  --judge-api-key $JUDGE_API_KEY \
  --sample-size 50 \
  --output experiments/results/phase1_judge.json
```

**期望结果**
- 每种方法每个数据集的各维度平均分数
- ArborGraph 在事实准确性和知识深度上应显著优于 Self-Instruct

### 1.4 层级感知指标

针对强层级数据集 D1，额外评测：
- 层级覆盖深度
- 父子关系保持率
- 跨层级推理能力

```bash
python experiments/eval/hierarchy_metrics.py \
  --input experiments/outputs/phase1/arborgraph_d1_strong_hierarchy_atomic.json \
  --source experiments/data/d1_strong_hierarchy/input.txt \
  --output experiments/results/phase1_hierarchy.json
```

---

## Phase 2：下游微调效果实验

### 目标
验证 ArborGraph 生成的 SFT 数据在下游微调任务中的实际效果。

### 2.1 微调数据准备

将 Phase 1 中各方法生成的数据转换为微调格式。

**执行命令**
```bash
# 合并各模式生成的数据
python experiments/scripts/merge_datasets.py \
  --input-dir experiments/outputs/phase1/ \
  --method arborgraph \
  --output experiments/finetune_data/arborgraph_train.json

python experiments/scripts/merge_datasets.py \
  --input-dir experiments/outputs/phase1/ \
  --method self_instruct \
  --output experiments/finetune_data/self_instruct_train.json
```

### 2.2 模型微调

使用 Qwen2.5-7B-Instruct 作为基础模型，分别用不同数据集微调。

**微调配置**
- 基础模型：Qwen/Qwen2.5-7B-Instruct
- 微调方法：LoRA (rank=16, alpha=32)
- 学习率：2e-5
- Epoch：3
- 批量大小：4
- 最大长度：2048

**执行命令**（使用 LLaMA-Factory 或类似工具）
```bash
# 使用 ArborGraph 数据微调
python -m llama_factory.train \
  --model_name_or_path Qwen/Qwen2.5-7B-Instruct \
  --dataset experiments/finetune_data/arborgraph_train.json \
  --output_dir experiments/models/arborgraph_ft \
  --lora_rank 16 \
  --learning_rate 2e-5 \
  --num_train_epochs 3 \
  --per_device_train_batch_size 4

# 使用 Self-Instruct 数据微调
python -m llama_factory.train \
  --model_name_or_path Qwen/Qwen2.5-7B-Instruct \
  --dataset experiments/finetune_data/self_instruct_train.json \
  --output_dir experiments/models/self_instruct_ft \
  --lora_rank 16 \
  --learning_rate 2e-5 \
  --num_train_epochs 3 \
  --per_device_train_batch_size 4
```

### 2.3 下游评测

在多个 Benchmark 上评测微调后的模型：

| Benchmark | 评测内容 | 评测命令 |
|-----------|----------|----------|
| MMLU | 多学科知识 | `lm_eval --model hf --model_args pretrained=experiments/models/arborgraph_ft --tasks mmlu --batch_size 8` |
| C-Eval | 中文知识 | `lm_eval --model hf --model_args pretrained=experiments/models/arborgraph_ft --tasks ceval --batch_size 8` |
| AlpacaEval | 指令跟随 | `alpaca_eval --model_outputs experiments/eval_outputs/arborgraph_alpaca.json` |
| MT-Bench | 多轮对话 | `python fastchat/llm_judge/gen_model_answer.py --model-path experiments/models/arborgraph_ft` |

**期望结果**
- ArborGraph 微调的模型在领域相关 Benchmark 上应优于 Self-Instruct 微调的模型
- 特别是在需要事实性知识的任务上，差距应更明显

### 2.4 结果汇总

```bash
python experiments/eval/summarize_results.py \
  --phase1 experiments/results/phase1_metrics.json \
  --phase2-dir experiments/results/phase2/ \
  --output experiments/results/final_summary.json
```

**期望输出格式**
| 方法 | MMLU | C-Eval | AlpacaEval | MT-Bench |
|------|------|--------|------------|----------|
| Base Model | - | - | - | - |
| + Self-Instruct | - | - | - | - |
| + ArborGraph (atomic) | - | - | - | - |
| + ArborGraph (all modes) | - | - | - | - |
| + ArborGraph + Intent | - | - | - | - |

---

## Phase 3：消融实验

### 目标
分析 ArborGraph 各核心模块的贡献度。

### 3.1 模块消融矩阵

| 实验编号 | 知识图谱 | ECE 评估 | 多模式生成 | 意图驱动 | 层级提取 |
|----------|----------|----------|------------|----------|----------|
| A0 (完整) | ✓ | ✓ | ✓ | ✓ | ✓ |
| A1 | ✗ | - | ✓ | ✗ | ✗ |
| A2 | ✓ | ✗ | ✓ | ✗ | ✗ |
| A3 | ✓ | ✓ | 仅atomic | ✗ | ✗ |
| A4 | ✓ | ✓ | ✓ | ✗ | ✗ |
| A5 | ✓ | ✓ | ✓ | ✓ | ✗ |

**执行命令**

```bash
# A1: 无知识图谱（直接文本生成）
python experiments/ablation/run_without_kg.py \
  -i experiments/data/d1_strong_hierarchy/input.txt \
  -o experiments/outputs/ablation/a1_no_kg.json

# A2: 无 ECE（随机采样替代）
python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
  -k $SYNTHESIZER_API_KEY \
  --edge-sampling random \
  --output-data-type all \
  -o experiments/outputs/ablation/a2_no_ece.json

# A3: 仅 atomic 模式
python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type atomic \
  -o experiments/outputs/ablation/a3_atomic_only.json

# A4: 无意图驱动（标准管线）
python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type all \
  -o experiments/outputs/ablation/a4_no_intent.json

# A5: 无层级提取
python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type atomic,aggregated,multi_hop,cot \
  -o experiments/outputs/ablation/a5_no_hierarchy.json
```

### 3.2 消融评测

对每个消融实验计算相同的质量指标，并与完整版本 A0 对比。

```bash
python experiments/eval/run_metrics.py \
  --input-dir experiments/outputs/ablation/ \
  --output experiments/results/ablation_metrics.json \
  --metrics mtld,length,coverage,self_bleu
```

**期望结果**
- A0 (完整版) 应在综合指标上最优
- 知识图谱模块 (A1 vs A4) 贡献最大
- ECE 评估 (A2 vs A4) 对知识覆盖率提升显著
- 多模式生成 (A3 vs A4) 提升数据多样性

---

## Phase 4：效率实验

### 目标
评估 ArborGraph 的批量优化策略对效率的影响。

### 4.1 Token 使用效率

```bash
# 无优化
python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
  -k $SYNTHESIZER_API_KEY \
  --output-data-type all \
  --chunk-size 1024 \
  -o experiments/outputs/efficiency/no_opt.json 2>&1 | tee experiments/logs/no_opt.log

# 启用 Prompt 缓存
# (默认已启用，通过日志对比 token 使用量)
```

**评测指标**
- 总 Token 消耗量
- 生成每条 QA 的平均 Token 消耗
- 端到端时间
- API 调用次数

### 4.2 不同 chunk_size 的影响

```bash
for chunk_size in 256 512 1024 2048; do
  python arborgraph_cli.py -i experiments/data/d1_strong_hierarchy/input.txt \
    -k $SYNTHESIZER_API_KEY \
    --chunk-size $chunk_size \
    --output-data-type atomic \
    -o "experiments/outputs/efficiency/chunk_${chunk_size}.json"
done
```

**期望结果**
- chunk_size 影响知识图谱粒度和 QA 质量
- 存在一个最优 chunk_size 平衡点

---

## Phase 5：领域迁移实验

### 目标
验证 ArborGraph 在不同领域的适用性。

### 5.1 领域数据集

| 领域 | 数据来源 | 大小 |
|------|----------|------|
| 金融 | 金融法规/报告 | 10KB |
| 医疗 | 医学教材摘要 | 10KB |
| 法律 | 法律条文 | 10KB |
| 技术 | 技术文档 | 10KB |

### 5.2 跨领域生成

```bash
for domain in finance medical legal tech; do
  python arborgraph_cli.py \
    -i "experiments/data/domains/${domain}/input.txt" \
    -k $SYNTHESIZER_API_KEY \
    --output-data-type all \
    -o "experiments/outputs/domains/${domain}_output.json"
done
```

### 5.3 领域适应性评测

使用 LLM-as-Judge 评估各领域生成数据的专业性和准确性。

```bash
python experiments/eval/domain_judge.py \
  --input-dir experiments/outputs/domains/ \
  --judge-model gpt-4o \
  --output experiments/results/domain_metrics.json
```

---

## 实验目录结构

```
experiments/
├── EXPERIMENT_PLAN.md           # 本文件
├── RELATED_WORK_AND_MOTIVATION.md
├── baselines/                   # 基线方法实现
│   └── self_instruct.py
├── data/                        # 实验数据
│   ├── d1_strong_hierarchy/
│   ├── d2_weak_hierarchy/
│   ├── d3_mixed/
│   └── domains/
├── eval/                        # 评测脚本
│   ├── run_metrics.py
│   ├── llm_judge.py
│   ├── hierarchy_metrics.py
│   ├── domain_judge.py
│   └── summarize_results.py
├── scripts/                     # 辅助脚本
│   └── merge_datasets.py
├── ablation/                    # 消融实验脚本
│   └── run_without_kg.py
├── outputs/                     # 实验输出
│   ├── phase0/
│   ├── phase1/
│   ├── ablation/
│   ├── efficiency/
│   └── domains/
├── results/                     # 结果汇总
│   ├── phase1_metrics.json
│   ├── phase1_judge.json
│   ├── ablation_metrics.json
│   └── final_summary.json
└── logs/                        # 实验日志
```

## 执行优先级

1. **最高优先级**：Phase 0（可行性验证） → 确保系统可运行
2. **高优先级**：Phase 1.1-1.2（数据质量自动评测） → 量化质量差异
3. **中优先级**：Phase 3（消融实验） → 理解各模块贡献
4. **低优先级**：Phase 1.3（LLM-as-Judge）, Phase 2（下游微调）, Phase 4-5 → 深度验证

## 注意事项

1. 所有实验使用相同的 API Key 和模型配置，确保公平对比
2. 每次实验记录 Token 消耗，用于成本分析
3. 对于随机性实验，设置固定 seed 并报告 3 次运行的均值和标准差
4. 所有中间结果和日志保留，便于问题排查和结果复现
