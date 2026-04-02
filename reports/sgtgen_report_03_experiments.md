# SGT-Gen 技术报告（三）：实验方案与执行细节

## 1. 实验目标与问题定义

本实验围绕四个核心问题展开：

1. SGT-Gen 相比“仅图谱流程”是否在数据质量上更优？
2. SGT-Gen 的层级感知模块是否确实带来结构收益？
3. SGT-Gen 的 Critic 机制是否有效过滤低质量样本？
4. 使用 SGT-Gen 生成数据进行 SFT 后，下游任务表现是否提升？

## 2. 实验分期

### Phase A：可行性验证（低成本）

- 数据：组 A（强层级）一个领域（建议金融）
- 规模：30-50 文档，目标 500-1000 QA/方法
- 输出：是否存在清晰正向信号

### Phase B：完整对比实验

- 数据：组 A/B/C 各一个领域
- 规模：5k-10k QA/方法
- 输出：质量、覆盖、结构指标全量表格

### Phase C：消融实验

- 对 SGT-Gen 的关键模块逐项去除
- 输出：模块贡献度

### Phase D：下游微调实验

- 固定底座模型、统一训练参数
- 输出：多基准任务增益

## 3. 数据准备与目录约定

建议目录：

- `experiments/data/input_docs/group_a_hierarchical`
- `experiments/data/input_docs/group_b_flat`
- `experiments/data/input_docs/group_c_mixed`
- `experiments/data/sgtgen_baseline_output`
- `experiments/data/sgtgen_full_output`
- `experiments/eval_results`

文档准入规则：

- 单文档建议 >200 tokens
- 优先包含定义、分类、层级描述
- 去重并剔除明显噪声文档

## 4. 基线与对比方法

- M0：Self-Instruct（可选）
- M1：仅图谱流程（关闭 taxonomy/critic/hierarchical）
- M2：SGT-Gen（完整流程）
- M3：外部公开指令数据集子集（仅用于补充对比）

## 5. 实验命令（可直接执行）

### 5.1 生成（M1/M2）

M1（仅图谱）：

- `python3 graphgen_cli.py -i <input_file> -k <API_KEY> --output_data_type all --output_data_format chatml --qa-pair-limit 1000`

M2（完整 SGT-Gen）：

- `python3 graphgen_cli.py --datog-config graphgen/configs/datog/finance/datog_config.yaml --datog-input <input_file> --api-key <API_KEY> --datog-output experiments/data/sgtgen_full_output/finance_qa.json`

### 5.2 自动评测

- `python3 scripts/coverage_metrics.py --input experiments/data/sgtgen_full_output/finance_qa.json --output experiments/eval_results/coverage_finance.json`
- `python3 -m graphgen.evaluate --folder experiments/data/sgtgen_full_output --output experiments/eval_results --tokenizer <tokenizer_name>`

### 5.3 汇总表生成（建议新增脚本）

- `python3 experiments/scripts/aggregate_metrics.py --inputs experiments/eval_results --output experiments/eval_results/summary_table.csv`

## 6. 指标体系

### 6.1 文本质量

- MTLD
- 平均问答长度
- 去重率（问题级）
- LLM-as-Judge（事实、可读性、训练价值）

### 6.2 覆盖与结构

- taxonomy 覆盖率
- 维度分布均衡度
- 层级关系识别率
- 兄弟社区数 / 链式社区数

### 6.3 质量控制与效率

- Critic 通过率
- 每 1k 样本耗时
- token 成本

## 7. 消融实验清单

- w/o Critic
- w/o Taxonomy（随机或均匀采样）
- w/o HierarchicalPartitioner
- w/o ECE（改 random）
- w/o Prompt Merging（评估速度影响）

每组消融固定：

- 相同输入文档
- 相同模型与 API
- 相同目标样本数

## 8. 期望结果类型

应至少得到以下“可发表级”结果：

1. 一张主对比表（M1 vs M2，在 A/B/C 三组上的关键指标）
2. 一张消融表（模块贡献）
3. 一张成本-质量权衡图（token 成本 vs 质量得分）
4. 一组案例分析（成功样例/失败样例）

## 9. 风险与应对

- 生成卡住：降低 batch、启用并发限制
- 成本超预算：先跑 Phase A 再扩展
- 指标噪声：固定随机种子，多次重复取均值
- 可复现性差：保留配置快照与日志文件

