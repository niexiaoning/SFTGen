<template>
  <div class="config-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>配置设置</span>
          <div class="header-actions">
            <el-button @click="handleReset">重置为默认</el-button>
            <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          </div>
        </div>
      </template>

      <el-form :model="config" label-width="200px" label-position="left">
        <el-collapse v-model="activeNames">
          <!-- 模型配置 -->
          <el-collapse-item title="模型配置" name="model">
            <el-form-item label="Tokenizer">
              <el-input v-model="config.tokenizer" placeholder="cl100k_base" />
            </el-form-item>

            <el-form-item label="Synthesizer Base URL">
              <el-input v-model="config.synthesizer_url" placeholder="https://api.siliconflow.cn/v1" />
            </el-form-item>

            <el-form-item label="Synthesizer Model">
              <el-input v-model="config.synthesizer_model" placeholder="Qwen/Qwen2.5-7B-Instruct" />
            </el-form-item>

            <el-form-item label="Synthesizer API Key">
              <el-input
                v-model="config.api_key"
                type="password"
                show-password
                placeholder="请输入API Key"
              />
            </el-form-item>

            <el-form-item label="测试连接">
              <el-button @click="handleTestConnection" :loading="testing">测试 Synthesizer 连接</el-button>
            </el-form-item>

            <el-form-item label="LLM 扩展请求体 (JSON)">
              <el-input
                v-model="config.llm_extra_body_json"
                type="textarea"
                :rows="3"
                placeholder='可选。智谱示例：{"thinking":{"type":"disabled","clear_thinking":true}}'
              />
              <span class="form-item-tip">智谱等 OpenAI 兼容接口的额外字段，会写入任务环境变量</span>
            </el-form-item>

            <el-form-item label="LLM 输出上限 (max_tokens)">
              <el-input-number
                v-model="config.llm_max_tokens"
                :min="256"
                :max="32768"
                :step="256"
                controls-position="right"
              />
              <span class="form-item-tip">
                限制“模型输出 token 数”，不是上下文窗口。过小会导致 finish_reason=length，抽取关系更容易缺失。
              </span>
            </el-form-item>

            <el-divider />

            <el-form-item label="使用 Trainee 模型">
              <el-switch v-model="config.if_trainee_model" />
            </el-form-item>

            <template v-if="config.if_trainee_model">
              <el-form-item label="Trainee Base URL">
                <el-input v-model="config.trainee_url" placeholder="https://api.siliconflow.cn/v1" />
              </el-form-item>

              <el-form-item label="Trainee Model">
                <el-input v-model="config.trainee_model" placeholder="Qwen/Qwen2.5-7B-Instruct" />
              </el-form-item>

              <el-form-item label="Trainee API Key">
                <el-input
                  v-model="config.trainee_api_key"
                  type="password"
                  show-password
                  placeholder="请输入API Key"
                />
              </el-form-item>

              <el-form-item label="Quiz Samples">
                <el-input-number v-model="config.quiz_samples" :min="1" :max="10" />
                <span class="form-item-tip">每个社区生成的问答样本数量</span>
              </el-form-item>
            </template>
          </el-collapse-item>

          <!-- 文本切分配置 -->
          <el-collapse-item title="文本切分配置" name="split">
            <el-form-item label="Chunk Size">
              <el-slider
                v-model="config.chunk_size"
                :min="256"
                :max="4096"
                :step="256"
                show-input
              />
              <span class="form-item-tip">文本块的大小（token数）</span>
            </el-form-item>

            <el-form-item label="Chunk Overlap">
              <el-slider
                v-model="config.chunk_overlap"
                :min="0"
                :max="500"
                :step="50"
                show-input
              />
              <span class="form-item-tip">文本块之间的重叠大小（token数）</span>
            </el-form-item>

            <el-divider content-position="left">合并抽取（Prompt Merging）</el-divider>

            <el-form-item label="启用合并抽取">
              <el-switch v-model="config.enable_prompt_merging" />
              <span class="form-item-tip">
                将多个 chunk 合并为一个 prompt 进行实体关系抽取，显著减少 LLM 调用次数（与“批量请求”不同）
              </span>
            </el-form-item>

            <el-form-item
              label="合并数量（chunk/次）"
              v-if="config.enable_prompt_merging"
            >
              <el-input-number
                v-model="config.prompt_merge_size"
                :min="1"
                :max="20"
              />
              <span class="form-item-tip">每次合并的 chunk 数量。1 表示不合并；建议 3-8</span>
            </el-form-item>
          </el-collapse-item>

          <!-- 分区配置 -->
          <el-collapse-item title="图分区配置" name="partition">
            <el-form-item label="分区方法">
              <el-select v-model="config.partition_method">
                <el-option label="ECE (推荐)" value="ece" />
                <el-option label="DFS" value="dfs" />
                <el-option label="BFS" value="bfs" />
                <el-option label="Leiden" value="leiden" />
                <el-option label="Hierarchical" value="hierarchical" />
              </el-select>
            </el-form-item>

            <!-- ECE 参数 -->
            <template v-if="config.partition_method === 'ece'">
              <el-divider content-position="left">ECE 参数</el-divider>
              <el-form-item label="Max Units Per Community">
                <el-input-number v-model="config.ece_max_units" :min="1" :max="100" />
                <span class="form-item-tip">每个社区的最大单元数</span>
              </el-form-item>
              <el-form-item label="Min Units Per Community">
                <el-input-number v-model="config.ece_min_units" :min="1" :max="100" />
                <span class="form-item-tip">每个社区的最小单元数</span>
              </el-form-item>
              <el-form-item label="Max Tokens Per Community">
                <el-slider
                  v-model="config.ece_max_tokens"
                  :min="512"
                  :max="20480"
                  :step="512"
                  show-input
                />
                <span class="form-item-tip">每个社区的最大token数</span>
              </el-form-item>
            </template>

            <!-- DFS 参数 -->
            <template v-if="config.partition_method === 'dfs'">
              <el-divider content-position="left">DFS 参数</el-divider>
              <el-form-item label="Max Units Per Community">
                <el-input-number v-model="config.dfs_max_units" :min="1" :max="100" />
              </el-form-item>
            </template>

            <!-- BFS 参数 -->
            <template v-if="config.partition_method === 'bfs'">
              <el-divider content-position="left">BFS 参数</el-divider>
              <el-form-item label="Max Units Per Community">
                <el-input-number v-model="config.bfs_max_units" :min="1" :max="100" />
              </el-form-item>
            </template>

            <!-- Leiden 参数 -->
            <template v-if="config.partition_method === 'leiden'">
              <el-divider content-position="left">Leiden 参数</el-divider>
              <el-form-item label="Max Community Size">
                <el-input-number v-model="config.leiden_max_size" :min="1" :max="100" />
              </el-form-item>
              <el-form-item label="Use Largest Connected Component">
                <el-switch v-model="config.leiden_use_lcc" />
              </el-form-item>
              <el-form-item label="Random Seed">
                <el-input-number v-model="config.leiden_random_seed" :min="0" />
              </el-form-item>
            </template>

            <!-- Hierarchical 参数 -->
            <template v-if="config.partition_method === 'hierarchical'">
              <el-divider content-position="left">Hierarchical 参数</el-divider>
              <el-alert
                title="层次化分区说明"
                type="info"
                :closable="false"
                style="margin-bottom: 16px"
              >
                <template #default>
                  <div style="font-size: 12px; line-height: 1.6">
                    <p>层次化分区适用于具有层次结构的知识图谱（如分类体系、本体结构）：</p>
                    <ul style="margin: 8px 0; padding-left: 20px">
                      <li><strong>兄弟分组</strong>：将父节点和所有子节点归为一组，适合比较类问题</li>
                      <li><strong>链式采样</strong>：沿层次结构采样祖先→后代路径，适合继承类问题</li>
                    </ul>
                  </div>
                </template>
              </el-alert>

              <el-form-item label="层次关系类型">
                <el-select
                  v-model="config.hierarchical_relations"
                  multiple
                  filterable
                  allow-create
                  default-first-option
                  placeholder="选择或输入关系类型"
                >
                  <el-option label="is_a" value="is_a" />
                  <el-option label="subclass_of" value="subclass_of" />
                  <el-option label="part_of" value="part_of" />
                  <el-option label="includes" value="includes" />
                  <el-option label="type_of" value="type_of" />
                </el-select>
                <span class="form-item-tip">选择知识图谱中的层次关系类型，可多选或自定义输入</span>
              </el-form-item>

              <el-form-item label="最大层次深度">
                <el-slider
                  v-model="config.max_hierarchical_depth"
                  :min="1"
                  :max="10"
                  :step="1"
                  show-input
                />
                <span class="form-item-tip">链式采样的最大深度（层级数），建议 2-5</span>
              </el-form-item>

              <el-form-item label="最大兄弟节点数">
                <el-slider
                  v-model="config.max_siblings_per_community"
                  :min="2"
                  :max="20"
                  :step="1"
                  show-input
                />
                <span class="form-item-tip">每个兄弟分组的最大节点数，建议 5-15</span>
              </el-form-item>
            </template>
          </el-collapse-item>

          <!-- 生成配置 -->
          <el-collapse-item title="数据生成配置" name="generate">
            <el-form-item label="只生成中文">
              <el-switch v-model="config.chinese_only" />
              <span class="form-item-tip">强制生成纯中文问答对，问题和答案都不包含英文（推荐用于中文训练数据）</span>
            </el-form-item>

            <el-form-item label="先问后答（双阶段生成）">
              <el-switch v-model="config.question_first" />
              <span class="form-item-tip">先仅生成问题并去重，再统一生成答案，显著减少重复问答（Atomic 默认开启）</span>
            </el-form-item>

            <el-form-item label="生成模式">
              <el-checkbox-group v-model="config.mode">
                <el-checkbox label="atomic">Atomic - 原子级问答</el-checkbox>
                <el-checkbox label="multi_hop">Multi-hop - 多跳问答</el-checkbox>
                <el-checkbox label="aggregated">Aggregated - 聚合问答</el-checkbox>
                <el-checkbox label="cot">CoT - 思维链问答</el-checkbox>
                <el-checkbox label="hierarchical">Hierarchical - 层次化问答</el-checkbox>
              </el-checkbox-group>
              <div class="form-item-tip">可选择多个生成模式，将同时生成所有选中模式的数据</div>
            </el-form-item>

            <el-form-item label="输出数据格式">
              <el-radio-group v-model="config.data_format">
                <el-radio label="Alpaca">Alpaca</el-radio>
                <el-radio label="Sharegpt">Sharegpt</el-radio>
                <el-radio label="ChatML">ChatML</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-divider content-position="left">数量与类型控制</el-divider>

            <el-form-item label="目标问答数量">
              <el-input-number
                v-model="config.qa_pair_limit"
                :min="0"
                :max="20000"
                :step="50"
                controls-position="right"
              />
              <span class="form-item-tip">0 或留空表示不限制数量，建议根据训练需求设定目标值</span>
            </el-form-item>

            <el-form-item label="类型占比（%）">
              <div class="qa-ratio-grid">
                <div class="qa-ratio-item">
                  <span class="qa-ratio-label">Atomic</span>
                  <el-input-number
                    v-model="config.qa_ratio_atomic"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </div>
                <div class="qa-ratio-item">
                  <span class="qa-ratio-label">Aggregated</span>
                  <el-input-number
                    v-model="config.qa_ratio_aggregated"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </div>
                <div class="qa-ratio-item">
                  <span class="qa-ratio-label">Multi-hop</span>
                  <el-input-number
                    v-model="config.qa_ratio_multi_hop"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </div>
                <div class="qa-ratio-item">
                  <span class="qa-ratio-label">CoT</span>
                  <el-input-number
                    v-model="config.qa_ratio_cot"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </div>
                <div class="qa-ratio-item">
                  <span class="qa-ratio-label">Hierarchical</span>
                  <el-input-number
                    v-model="config.qa_ratio_hierarchical"
                    :min="0"
                    :max="100"
                    :step="1"
                  />
                </div>
              </div>
              <span class="form-item-tip">当前占比合计：{{ ratioTotal }}%，建议接近 100%</span>
            </el-form-item>

            <el-divider content-position="left">Hierarchical 生成配置</el-divider>

            <el-form-item label="树结构格式" v-if="config.mode.includes('hierarchical')">
              <el-radio-group v-model="config.structure_format">
                <el-radio label="markdown">Markdown (推荐)</el-radio>
                <el-radio label="json">JSON</el-radio>
                <el-radio label="outline">Outline</el-radio>
              </el-radio-group>
              <div class="form-item-tip">
                <p><strong>Markdown</strong>：易读性强，适合LLM理解层次结构</p>
                <p><strong>JSON</strong>：结构化强，便于程序处理</p>
                <p><strong>Outline</strong>：紧凑格式，适合深层结构</p>
              </div>
            </el-form-item>

          </el-collapse-item>

          <!-- 限流配置 -->
          <el-collapse-item title="API 限流配置" name="rate_limit">
            <el-form-item label="RPM (每分钟请求数)">
              <el-slider
                v-model="config.rpm"
                :min="10"
                :max="10000"
                :step="10"
                show-input
              />
            </el-form-item>

            <el-form-item label="TPM (每分钟Token数)">
              <el-slider
                v-model="config.tpm"
                :min="1000"
                :max="5000000"
                :step="1000"
                show-input
              />
            </el-form-item>
          </el-collapse-item>

          <!-- 高级设置（默认折叠） -->
          <el-collapse-item title="高级设置" name="advanced">
            <el-alert
              title="高级设置说明"
              type="info"
              :closable="false"
              style="margin-bottom: 16px"
            >
              <template #default>
                <div style="font-size: 12px; line-height: 1.6">
                  <p>
                    这里集中放一些“高级/性能相关”的参数，默认不建议频繁改动。
                  </p>
                </div>
              </template>
            </el-alert>

            <el-divider content-position="left">性能优化</el-divider>

            <el-form-item label="动态 Chunk Size 调整">
              <el-switch v-model="config.dynamic_chunk_size" />
              <span class="form-item-tip">根据文本长度和复杂度自动调整 chunk 大小，提升分块质量（影响抽取与生成的上游分块）</span>
            </el-form-item>

            <el-form-item label="启用提取缓存">
              <el-switch v-model="config.enable_extraction_cache" />
              <span class="form-item-tip">缓存“实体关系抽取”结果，避免重复抽取相同 chunk（节省 LLM 调用）</span>
            </el-form-item>

            <el-form-item label="多模板采样">
              <el-switch v-model="config.use_multi_template" />
              <span class="form-item-tip">为问答生成使用多个模板变体，提升数据多样性（通常建议开启）</span>
            </el-form-item>

            <el-form-item label="模板随机种子">
              <el-input-number
                v-model="config.template_seed"
                :min="0"
                :max="999999"
                :disabled="!config.use_multi_template"
              />
              <span class="form-item-tip">用于复现同一套模板采样结果；留空则每次随机</span>
            </el-form-item>

            <el-divider content-position="left">全局去重</el-divider>

            <el-form-item label="全局记忆去重（跨任务）">
              <el-switch v-model="config.persistent_deduplication" />
              <span class="form-item-tip">
                将历史任务生成过的问题作为“全局记忆库”参与去重，避免跨任务重复生成与重复调用 LLM（通常建议开启）
              </span>
            </el-form-item>

            <el-divider content-position="left">任务队列</el-divider>

            <el-alert
              title="任务队列（请求队列/批处理）"
              type="info"
              :closable="false"
              style="margin-bottom: 16px"
            >
              <template #default>
                <div style="font-size: 12px; line-height: 1.6">
                  <p>
                    这是<strong>吞吐优化</strong>：不减少 LLM 调用次数，只是让请求更平滑、更高吞吐。
                    当前后端会在<strong>知识抽取阶段</strong>与<strong>问答生成阶段</strong>复用同一组参数（<code>enable_batch_requests/batch_size/max_wait_time</code>）。
                  </p>
                </div>
              </template>
            </el-alert>

            <el-form-item label="启用任务队列">
              <el-switch v-model="config.enable_batch_requests" />
              <span class="form-item-tip">
                开启后会对“抽取/生成”等阶段的批处理队列生效（具体取决于该阶段是否启用了队列实现）
              </span>
            </el-form-item>

            <template v-if="config.enable_batch_requests">
              <el-form-item label="队列批量大小">
                <el-input-number v-model="config.batch_size" :min="1" :max="50" />
                <span class="form-item-tip">队列攒到多少个请求再发送/处理，建议 5-20</span>
              </el-form-item>

              <el-form-item label="队列最大等待时间（秒）">
                <el-slider
                  v-model="config.max_wait_time"
                  :min="0.1"
                  :max="2.0"
                  :step="0.1"
                  show-input
                />
                <span class="form-item-tip">超过该时间即使未达到批量大小也会发送请求（降低尾延迟）</span>
              </el-form-item>
            </template>
          </el-collapse-item>
        </el-collapse>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useConfigStore } from '@/stores/config'
import api from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const configStore = useConfigStore()
// 确保 mode 是数组格式
const initialConfig = { ...configStore.config }
if (typeof initialConfig.mode === 'string') {
  initialConfig.mode = [initialConfig.mode]
} else if (!Array.isArray(initialConfig.mode)) {
  initialConfig.mode = ['aggregated']
}
const config = ref(initialConfig)
const activeNames = ref(['model', 'split', 'partition', 'generate', 'rate_limit'])
const saving = ref(false)
const testing = ref(false)

const ratioTotal = computed(() => {
  const ratios = [
    Number(config.value.qa_ratio_atomic ?? 0),
    Number(config.value.qa_ratio_aggregated ?? 0),
    Number(config.value.qa_ratio_multi_hop ?? 0),
    Number(config.value.qa_ratio_cot ?? 0),
    Number(config.value.qa_ratio_hierarchical ?? 0)
  ]
  const total = ratios.reduce((sum, value) => {
    const normalized = Number.isFinite(value) ? value : 0
    return sum + normalized
  }, 0)
  return Math.round(total * 10) / 10
})

// 保存配置
const handleSave = async () => {
  saving.value = true
  try {
    // 更新 store
    configStore.config = { ...config.value }
    await configStore.saveConfig()
  } finally {
    saving.value = false
  }
}

// 重置配置
const handleReset = async () => {
  try {
    await ElMessageBox.confirm('确定要重置为默认配置吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    configStore.resetConfig()
    // 确保 mode 是数组格式
    const resetConfig = { ...configStore.config }
    if (typeof resetConfig.mode === 'string') {
      resetConfig.mode = [resetConfig.mode]
    } else if (!Array.isArray(resetConfig.mode)) {
      resetConfig.mode = ['aggregated']
    }
    config.value = resetConfig
    ElMessage.success('配置已重置')
  } catch {
    // 用户取消操作
  }
}

// 测试连接
const handleTestConnection = async () => {
  if (!config.value.api_key) {
    ElMessage.error('请先填写 API Key')
    return
  }

  if (!config.value.synthesizer_url) {
    ElMessage.error('请先填写 Synthesizer Base URL')
    return
  }

  if (!config.value.synthesizer_model) {
    ElMessage.error('请先填写 Synthesizer Model')
    return
  }

  testing.value = true
  try {
    const response = await api.testConnection({
      base_url: config.value.synthesizer_url || '',
      api_key: config.value.api_key,
      model_name: config.value.synthesizer_model || ''
    })
    if (response.success) {
      ElMessage.success(response.message || '连接测试成功')
    } else {
      ElMessage.error(response.error || '连接测试失败')
    }
  } catch (error: any) {
    // 提取错误信息
    const errorMessage = error?.response?.data?.detail || 
                        error?.response?.data?.error || 
                        error?.message || 
                        '连接测试失败，请检查配置和网络连接'
    ElMessage.error(errorMessage)
    console.error('连接测试失败:', error)
  } finally {
    testing.value = false
  }
}

onMounted(async () => {
  await configStore.loadConfig()
  // 确保 mode 是数组格式
  const loadedConfig = { ...configStore.config }
  if (typeof loadedConfig.mode === 'string') {
    loadedConfig.mode = [loadedConfig.mode]
  } else if (!Array.isArray(loadedConfig.mode)) {
    loadedConfig.mode = ['aggregated']
  }
  config.value = loadedConfig
})
</script>

<style scoped>
.config-container {
  max-width: 1200px;
  margin: 0 auto;
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

:deep(.el-card) {
  border-radius: 12px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
}

:deep(.el-card:hover) {
  box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.12);
}

:deep(.el-card__header) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom: none;
  padding: 20px 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
  color: white;
}

.header-actions {
  display: flex;
  gap: 12px;
}

:deep(.el-card__header .el-button) {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
  font-weight: 500;
  border-radius: 8px;
}

:deep(.el-card__header .el-button:hover) {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.5);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(255, 255, 255, 0.3);
}

:deep(.el-card__body) {
  padding: 32px;
}

.form-item-tip {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  padding: 8px 12px;
  background: #f8fafc;
  border-left: 3px solid #409eff;
  border-radius: 4px;
}

.qa-ratio-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.qa-ratio-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  background: white;
  border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.2s;
}

.qa-ratio-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.qa-ratio-label {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  min-width: 90px;
}

:deep(.el-collapse) {
  border: none;
}

:deep(.el-collapse-item) {
  margin-bottom: 16px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  background: white;
}

:deep(.el-collapse-item__header) {
  font-size: 16px;
  font-weight: 600;
  background: #fafbfc;
  padding: 16px 20px;
  border-bottom: 1px solid #e4e7ed;
  color: #303133;
  transition: all 0.3s;
}

:deep(.el-collapse-item__header:hover) {
  background: #f0f2f5;
  color: #409eff;
}

:deep(.el-collapse-item__wrap) {
  border: none;
  background: white;
}

:deep(.el-collapse-item__content) {
  padding: 24px 20px;
}

:deep(.el-form-item) {
  margin-bottom: 28px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #475569;
}

:deep(.el-input__wrapper) {
  border-radius: 6px;
  box-shadow: 0 0 0 1px #dcdfe6 inset;
  transition: all 0.3s;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c0c4cc inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #409eff inset;
}

:deep(.el-slider__runway) {
  border-radius: 6px;
}

:deep(.el-slider__bar) {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
}

:deep(.el-slider__button) {
  border: 2px solid #667eea;
}

:deep(.el-radio),
:deep(.el-checkbox) {
  display: block;
  margin: 12px 0;
  padding: 10px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

:deep(.el-radio:hover),
:deep(.el-checkbox:hover) {
  background: #f0f9ff;
}

:deep(.el-radio__label),
:deep(.el-checkbox__label) {
  font-weight: 500;
}

:deep(.el-divider) {
  margin: 32px 0;
}

:deep(.el-divider__text) {
  font-size: 14px;
  font-weight: 600;
  color: #64748b;
  background: white;
  padding: 0 16px;
}

:deep(.el-input-number) {
  border-radius: 6px;
}

:deep(.el-select) {
  width: 100%;
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 6px;
}

:deep(.el-switch.is-checked .el-switch__core) {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-color: #667eea;
}

:deep(.el-alert) {
  border-radius: 8px;
  border: none;
  padding: 16px;
}

:deep(.el-alert--info) {
  background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 100%);
}
</style>

