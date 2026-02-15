<template>
  <div class="datog-config-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>DA-ToG 配置</span>
          <div class="header-actions">
            <el-button @click="handleReset">重置为默认</el-button>
            <el-button type="primary" @click="handleSave" :loading="saving">保存配置</el-button>
          </div>
        </div>
      </template>

      <el-form :model="config" label-width="180px" label-position="left">
        <el-collapse v-model="activeNames">
          <!-- 意图树配置 -->
          <el-collapse-item title="意图树配置" name="taxonomy">
            <el-alert
              title="DA-ToG (Domain-Agnostic Tree-of-Graphs)"
              type="info"
              :closable="false"
              style="margin-bottom: 20px"
            >
              <template #default>
                <div style="font-size: 12px; line-height: 1.6">
                  <p>DA-ToG 是一个领域无关的树状图生成框架，通过三层次结构实现高质量SFT数据生成：</p>
                  <ul style="margin: 8px 0; padding-left: 20px">
                    <li><strong>Macro-Intent Layer</strong>：意图树 (TaxonomyTree)，定义认知维度和目标意图</li>
                    <li><strong>Micro-Fact Layer</strong>：知识图谱适配器，从KG中提取事实知识</li>
                    <li><strong>Logic-Critic Layer</strong>：评审器，对生成结果进行质量控制</li>
                  </ul>
                </div>
              </template>
            </el-alert>

            <el-form-item label="意图树路径">
              <el-input v-model="config.taxonomy_path" placeholder="请输入意图树文件路径" />
              <span class="form-item-tip">意图树的JSON文件路径，用于定义生成目标</span>
            </el-form-item>

            <el-form-item label="领域名称">
              <el-input v-model="config.domain" placeholder="如：finance, medical, education" />
              <span class="form-item-tip">标识当前配置所属的领域</span>
            </el-form-item>
          </el-collapse-item>

          <!-- 采样策略配置 -->
          <el-collapse-item title="采样策略配置" name="sampling">
            <el-form-item label="采样策略">
              <el-select v-model="config.sampling_strategy">
                <el-option label="Coverage (覆盖率优先)" value="coverage" />
                <el-option label="Uniform Branch (均分支)" value="uniform_branch" />
                <el-option label="Depth Weighted (深度加权)" value="depth_weighted" />
              </el-select>
              <span class="form-item-tip">选择意图节点的采样策略</span>
            </el-form-item>

            <template v-if="config.sampling_strategy === 'coverage'">
              <el-alert
                title="Coverage 策略"
                type="success"
                :closable="false"
                style="margin-bottom: 16px"
              >
                优先覆盖所有意图节点，确保每个认知维度都有代表数据
              </el-alert>
            </template>

            <template v-if="config.sampling_strategy === 'uniform_branch'">
              <el-alert
                title="Uniform Branch 策略"
                type="success"
                :closable="false"
                style="margin-bottom: 16px"
              >
                在每个分支上均匀采样，确保树结构的平衡覆盖
              </el-alert>
            </template>

            <template v-if="config.sampling_strategy === 'depth_weighted'">
              <el-alert
                title="Depth Weighted 策略"
                type="success"
                :closable="false"
                style="margin-bottom: 16px"
              >
                根据深度加权采样，深层节点获得更多采样机会
              </el-alert>
            </template>
          </el-collapse-item>

          <!-- 知识图谱配置 -->
          <el-collapse-item title="知识图谱配置" name="graph">
            <el-form-item label="最大跳数">
              <el-slider
                v-model="config.graph_max_hops"
                :min="1"
                :max="5"
                :step="1"
                show-input
              />
              <span class="form-item-tip">子图中允许的最大跳数，控制事实检索范围</span>
            </el-form-item>

            <el-form-item label="最大节点数">
              <el-slider
                v-model="config.graph_max_nodes"
                :min="5"
                :max="100"
                :step="5"
                show-input
              />
              <span class="form-item-tip">单个子图的最大节点数，控制生成上下文规模</span>
            </el-form-item>

            <el-form-item label="序列化格式">
              <el-radio-group v-model="config.serialization_format">
                <el-radio label="natural_language">自然语言</el-radio>
                <el-radio label="markdown">Markdown</el-radio>
                <el-radio label="json">JSON</el-radio>
              </el-radio-group>
              <span class="form-item-tip">知识图谱子图序列化为输入时的格式</span>
            </el-form-item>
          </el-collapse-item>

          <!-- 评审器配置 -->
          <el-collapse-item title="评审器配置" name="critic">
            <el-form-item label="评审器类型">
              <el-radio-group v-model="config.critic_type">
                <el-radio label="llm">LLM评审器</el-radio>
                <el-radio label="rule">规则评审器</el-radio>
                <el-radio label="none">不使用评审</el-radio>
              </el-radio-group>
              <span class="form-item-tip">选择用于质量控制的方法</span>
            </el-form-item>

            <template v-if="config.critic_type !== 'none'">
              <el-form-item label="最低评分">
                <el-slider
                  v-model="config.critic_min_score"
                  :min="0"
                  :max="1"
                  :step="0.1"
                  show-input
                />
                <span class="form-item-tip">低于此分数的问答对将被过滤</span>
              </el-form-item>

              <template v-if="config.critic_type === 'llm'">
                <el-alert
                  title="LLM评审器"
                  type="info"
                  :closable="false"
                >
                  使用大语言模型对生成的问答对进行质量评估，准确性高但消耗API
                </el-alert>
              </template>

              <template v-if="config.critic_type === 'rule'">
                <el-alert
                  title="规则评审器"
                  type="info"
                  :closable="false"
                >
                  基于预设规则进行快速评估，速度快但相对简单
                </el-alert>
              </template>
            </template>
          </el-collapse-item>

          <!-- 生成配置 -->
          <el-collapse-item title="生成配置" name="generation">
            <el-form-item label="目标问答对数量">
              <el-input-number
                v-model="config.generation_target_qa_pairs"
                :min="10"
                :max="10000"
                :step="10"
                controls-position="right"
              />
              <span class="form-item-tip">计划生成的问答对总数</span>
            </el-form-item>

            <el-form-item label="批处理大小">
              <el-input-number
                v-model="config.batch_size"
                :min="1"
                :max="50"
                :step="1"
              />
              <span class="form-item-tip">单次批处理的意图节点数量，影响生成速度和内存使用</span>
            </el-form-item>
          </el-collapse-item>
        </el-collapse>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDAToGStore } from '@/stores/datog'
import { ElMessage, ElMessageBox } from 'element-plus'

const datogStore = useDAToGStore()
const config = ref({ ...datogStore.config })
const activeNames = ref(['taxonomy', 'sampling', 'graph', 'critic', 'generation'])
const saving = ref(false)

// 保存配置
const handleSave = async () => {
  saving.value = true
  try {
    datogStore.config = { ...config.value }
    const success = await datogStore.saveConfig()
    if (success) {
      config.value = { ...datogStore.config }
    }
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
    datogStore.resetConfig()
    config.value = { ...datogStore.config }
    ElMessage.success('配置已重置')
  } catch {
    // 用户取消操作
  }
}

onMounted(async () => {
  await datogStore.loadConfig()
  config.value = { ...datogStore.config }
})
</script>

<style scoped>
.datog-config-container {
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
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
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
  border-left: 3px solid #10b981;
  border-radius: 4px;
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
  color: #10b981;
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
  box-shadow: 0 0 0 1px #10b981 inset;
}

:deep(.el-slider__runway) {
  border-radius: 6px;
}

:deep(.el-slider__bar) {
  background: linear-gradient(90deg, #10b981 0%, #059669 100%);
}

:deep(.el-slider__button) {
  border: 2px solid #10b981;
}

:deep(.el-radio) {
  display: block;
  margin: 12px 0;
  padding: 10px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

:deep(.el-radio:hover) {
  background: #ecfdf5;
}

:deep(.el-radio__label) {
  font-weight: 500;
}

:deep(.el-select) {
  width: 100%;
}

:deep(.el-select .el-input__wrapper) {
  border-radius: 6px;
}

:deep(.el-alert) {
  border-radius: 8px;
  border: none;
  padding: 16px;
}

:deep(.el-alert--info) {
  background: linear-gradient(135deg, #e0f2fe 0%, #f0f9ff 100%);
}

:deep(.el-alert--success) {
  background: linear-gradient(135deg, #d1fae5 0%, #ecfdf5 100%);
}
</style>
