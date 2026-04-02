# SGT-Gen 参考项目清单与可迁移优化点

> 目的：为后续版本给出“可直接落地”的借鉴路线，每个项目都包含来源、方法论与在 SGT-Gen 中的接入方式。

## 1) GraphRAG（Microsoft）
- 来源：`https://github.com/microsoft/graphrag`
- 方法论：
  - 从文本抽取实体/关系/claims，构建层级社区图与摘要；
  - 支持 local/global 两类查询，强调跨文档推理。
- 可借鉴点：
  - 将当前 `partition + generate` 前加入“社区摘要层”，减少生成阶段上下文噪声；
  - 为 SGT-Gen 增加 global query 路径，用于覆盖“跨文档、跨主题”的问答生成。
- 对应优化：
  - 增加 `community_summary` 存储 namespace；
  - 在 `DAToGGenerator` prompt 中引入 `community_summary` 字段。

## 2) LightRAG（HKU DS）
- 来源：`https://github.com/HKUDS/LightRAG`
- 方法论：
  - 双层检索（低层实体 + 高层结构），以速度和简单性为目标；
  - 强调高效索引和快速推理路径。
- 可借鉴点：
  - 为 SGT-Gen 的 intent->subgraph 检索增加“快路径”（高频节点缓存 + top-k 邻域索引）；
  - 在大规模批量生成时降低检索延迟。
- 对应优化：
  - 增加 graph 索引缓存；
  - 新增 `fast_retrieve=True` 配置与基准测试脚本。

## 3) KAG（OpenSPG）
- 来源：`https://github.com/OpenSPG/KAG`
- 方法论：
  - 逻辑形式驱动的混合推理（符号 + 神经）；
  - schema 约束知识构建，强化复杂问答的可解释性。
- 可借鉴点：
  - 把现有 RuleCritic 扩展为“逻辑约束判定器”（例如路径一致性、前提可达性）；
  - 在复杂问答中输出推理轨迹元数据（便于复核）。
- 对应优化：
  - 新增 `logic_consistency_score`；
  - 为 multi-hop 输出增加 `reasoning_path` 结构化字段。

## 4) Self-Instruct（Stanford）
- 来源：`https://github.com/yizhongw/self-instruct`
- 方法论：
  - 自举生成 + 过滤迭代，构建大规模指令数据。
- 可借鉴点：
  - 作为 SGT-Gen baseline 和 fallback 生成器；
  - 当图谱覆盖不足时提供“文本直生”补充集。
- 对应优化：
  - 在实验中加入 `self_instruct_baseline.py`；
  - 对比 SGT-Gen 的事实性/去重率/覆盖率。

## 5) WizardLM / Evol-Instruct
- 来源：WizardLM 论文与开源实现（基于 Evol-Instruct）
- 方法论：
  - 通过指令进化提升问题复杂度与多样性。
- 可借鉴点：
  - 在 SGT-Gen 生成后追加“复杂化重写”阶段（仅重写问题，不改事实锚点）；
  - 提升高阶推理样本占比。
- 对应优化：
  - 新增 `instruction_evolution` 后处理模块；
  - 以 RuleCritic 验证事实不漂移。

## 6) OpenAI Evals / DeepEval / RAGAS
- 来源：
  - `https://github.com/openai/evals`
  - `https://deepeval.com/`
- 方法论：
  - 标准化评测任务、可 CI 化质量回归；
  - RAG 相关维度（faithfulness、context precision/recall）可复用。
- 可借鉴点：
  - 将 SGT-Gen 的离线实验固化为评测流水线；
  - 建立质量门禁（低于阈值禁止发布数据集）。
- 对应优化：
  - 增加 `experiments/scripts/run_eval_suite.sh`；
  - 将关键指标接入 CI 报告。

## 7) LlamaIndex DatasetGenerator
- 来源：LlamaIndex 官方文档
- 方法论：
  - 从文档自动生成 labeled RAG 数据集。
- 可借鉴点：
  - 复用其 dataset schema 设计（query / context / answer / metadata）；
  - 使 SGT-Gen 输出可直接接入更多训练与评测工具链。
- 对应优化：
  - 增加统一导出器：`llamaindex_rag_dataset`。

---

## 结合优先级建议
1. **先做工程收益高的**：GraphRAG 社区摘要 + DeepEval 评测流水线。
2. **再做质量提升**：KAG 风格逻辑一致性校验 + Evol-Instruct 问题复杂化。
3. **最后做生态互通**：LlamaIndex 数据集导出与统一 schema。
