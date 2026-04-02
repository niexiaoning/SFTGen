# SGT-Gen 实验计划（详细执行版）

> 目标：以“可复现 + 可解释 + 可扩展”为标准，完成 SGT-Gen 的可行性验证、主实验、消融实验和补充实验。

---

## 0. 实验原则与成功判据

### 0.1 原则
- 同一轮对比中，固定同一套输入文档、同一模型、同一预算。
- 优先先做小规模可行性，再扩大规模。
- 每个结论都要有对应表格/日志/脚本输出可回溯。

### 0.2 成功判据
- 可行性阶段：SGT-Gen 在“强层级语料”上至少 3 项核心指标优于图-only 基线。
- 主实验阶段：在 A/B/C 三组语料上，呈现“强层级显著提升、弱层级不退化、混合场景有增益”。
- 消融阶段：关键模块移除后性能显著下降，证明组件有效性。

---

## 1. 对比对象与实验分期

### 1.1 方法定义
- `M0`：Doc2QA-Direct（纯文档直接问答生成，弱基线）。
- `M1`：Graph-only（仅知识图谱与常规分区/生成）。
- `M2`：SGT-Gen（树+图+层级分区+critic，全量方法）。
- `M3`：Public-Tree-Data（公开树导向 SFT 数据集，仅作为外部对照数据源）。

### 1.2 分期
- `Phase-A`：可行性分析（小样本、低成本）。
- `Phase-B`：完整主实验（A/B/C 分组全跑）。
- `Phase-C`：消融实验（模块拆解验证）。
- `Phase-D`：补充实验（鲁棒性/效率/迁移性）。

---

## 2. 数据准备（按层级强度分组）

### 2.1 分组标准
- 组 A（强层级）：含明确分类体系、父子概念链。
- 组 B（弱层级）：叙事为主，层级关系稀少。
- 组 C（混合）：部分章节层级明确，部分章节平铺叙事。

### 2.2 目录规范
```
experiments/
├── data/
│   ├── input_docs/
│   │   ├── group_a_hierarchical/
│   │   ├── group_b_flat/
│   │   └── group_c_mixed/
│   ├── outputs/
│   │   ├── m0_direct/
│   │   ├── m1_graph_only/
│   │   ├── m2_sgtgen/
│   │   └── m3_public_tree_data/
│   └── manifests/
│       ├── group_a_manifest.json
│       ├── group_b_manifest.json
│       └── group_c_manifest.json
```

### 2.3 数据规模
- 可行性：每组先 30~50 篇文档，目标 500~1000 QA/方法。
- 主实验：每组目标 5K~10K QA/方法。
- 终版：可扩展到 10K~20K QA/方法。

---

## 3. Phase-A：可行性分析实验

### 3.1 目的
验证“层级感知 + 树图融合”是否在强层级语料上带来可测增益。

### 3.2 输入
- 仅使用 `group_a_hierarchical`。
- 固定同一 LLM 与同一 token 预算。

### 3.3 命令（建议模板）
1) Graph-only（M1）
- `python graphgen_cli.py -i <input_file> -k <API_KEY> --output-file experiments/data/outputs/m1_graph_only/group_a.json`

2) SGT-Gen（M2）
- `python graphgen_cli.py --datog-config graphgen/configs/datog/finance/datog_config.yaml --datog-input <input_file> --datog-output experiments/data/outputs/m2_sgtgen/group_a.json -k <API_KEY>`

3) 评估（自动指标）
- `python scripts/coverage_metrics.py --input experiments/data/outputs/m1_graph_only/group_a.json --output experiments/phase_a/m1_metrics.json`
- `python scripts/coverage_metrics.py --input experiments/data/outputs/m2_sgtgen/group_a.json --output experiments/phase_a/m2_metrics.json`

### 3.4 预期结果类型
- 表格：MTLD、去重率、平均跳数、层级相关指标（兄弟组/链式社区占比）。
- 图：每种方法的认知维度分布柱状图。
- 结论：M2 在强层级语料上显著优于 M1。

---

## 4. Phase-B：完整主实验

### 4.1 目的
验证方法在不同层级结构语料上的稳定性与泛化表现。

### 4.2 运行策略
- 对 A/B/C 三组分别运行 M0/M1/M2。
- M3 作为外部公开数据参考（如只做数据分布和质量层面对照，可不做文档到数据流程）。

### 4.3 关键控制变量
- 统一合成器模型、温度、max tokens、批大小。
- 统一目标生成条数（每组每方法同量级）。
- 同一组内使用同一文档清单（manifest 固定）。

### 4.4 输出文件要求
- `experiments/phase_b/tables/*.csv`：分组结果表。
- `experiments/phase_b/plots/*.png`：分布图、对比图。
- `experiments/phase_b/logs/*.log`：每轮执行日志。

### 4.5 预期结果
- 组 A：M2 > M1（显著）。
- 组 B：M2 ≈ M1（不退化）。
- 组 C：M2 > M1（中等提升）。

---

## 5. Phase-C：消融实验

### 5.1 消融配置
- `Abl-1`: w/o Critic（去掉规则+LLM critic）
- `Abl-2`: w/o Tree（去掉 macro intent）
- `Abl-3`: w/o HierarchicalPartitioner（退化为 BFS/DFS）
- `Abl-4`: w/o ECE（采样策略替换为 random）
- `Abl-5`: w/o Graph（仅树驱动模板）

### 5.2 命令规范
- 每个消融配置单独 yaml。
- 统一调用：
  - `python graphgen_cli.py --datog-config <ablation_config.yaml> --datog-input <input_file> --datog-output <output.json> -k <API_KEY>`

### 5.3 预期结果
- 在组 A 上，去掉层级分区/树引导后下降最明显。
- 去掉 critic 后质量下限（人工评分/拒绝率）显著变差。

---

## 6. Phase-D：补充实验（建议）

### 6.1 鲁棒性实验
- 改变 chunk size、batch size、max_depth，观察性能波动。
- 输出：参数敏感性曲线。

### 6.2 效率实验
- 统计调用次数、总耗时、平均每 1k QA 成本。
- 输出：效率-质量折线图。

### 6.3 迁移实验
- 从金融迁移到网络安全配置包，验证可插拔能力。
- 输出：跨域性能对比表。

---

## 7. 评测指标定义与落地

### 7.1 自动指标
- 多样性：MTLD、去重率。
- 覆盖：分类树覆盖率、认知维度均匀度。
- 深度：平均实体数、平均推理跳数。
- 层级：层级关系识别率、兄弟组社区数、纵向链社区数。
- 质量下限：critic 通过率、拒绝样本占比。

### 7.2 人工/LLM 评测
- 每组每方法随机抽样 50 条。
- 打分维度：事实准确、问题质量、答案完整、自然度、训练价值。
- 结果：均值+方差+评审说明。

---

## 8. 实验执行检查清单

### 8.1 运行前
- `.env` 已配置模型与密钥。
- 输入文档 manifest 已冻结。
- 输出目录清理并备份旧结果。

### 8.2 运行中
- 每个命令记录开始/结束时间。
- 失败样本单独记录到 `failed_cases.jsonl`。

### 8.3 运行后
- 生成统一汇总表 `experiments/final_summary.csv`。
- 保存最终结论与图表到 `experiments/report_assets/`。

---

## 9. 交付物

- 一份完整实验结果表（A/B/C × M0/M1/M2/M3）。
- 一份消融结论表（Abl-1~Abl-5）。
- 一份效率报告（耗时/成本/吞吐）。
- 一份可复现实验脚本集（命令清单 + 配置文件列表）。
