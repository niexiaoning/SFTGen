import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  TGTConfig,
  TGTPipelineConfig,
  TGTTaxonomy,
  PipelineTaskStatus
} from '@/api/types'
import api from '@/api'
import { ElMessage } from 'element-plus'

export const useTGTStore = defineStore('tgt', () => {
  // 默认 TGT 配置
  const config = ref<TGTConfig>({
    taxonomy_path: '',
    domain: '',
    sampling_strategy: 'coverage',
    graph_max_hops: 2,
    graph_max_nodes: 20,
    serialization_format: 'natural_language',
    critic_type: 'rule',
    critic_min_score: 0.6,
    generation_target_qa_pairs: 100,
    batch_size: 10
  })

  // 意图树列表
  const taxonomies = ref<TGTTaxonomy[]>([])

  // 当前选中的意图树
  const selectedTaxonomy = ref<TGTTaxonomy | null>(null)

  // 管道运行状态
  const pipelineStatus = ref<PipelineTaskStatus | null>(null)

  // 管道运行中标志
  const pipelineRunning = ref(false)

  // 加载 TGT 配置
  const loadConfig = async () => {
    try {
      const response = await api.tgt.loadConfig()
      if (response.success && response.data) {
        config.value = { ...config.value, ...response.data }
      }
    } catch (error) {
      console.log('使用默认 TGT 配置')
    }
  }

  // 保存 TGT 配置
  const saveConfig = async () => {
    try {
      const response = await api.tgt.saveConfig(config.value)
      if (response.success) {
        ElMessage.success('TGT 配置保存成功')
        return true
      } else {
        ElMessage.error(response.message || 'TGT 配置保存失败')
        return false
      }
    } catch (error: any) {
      ElMessage.error(error.message || 'TGT 配置保存失败')
      return false
    }
  }

  // 更新配置
  const updateConfig = <K extends keyof TGTConfig>(key: K, value: TGTConfig[K]) => {
    config.value[key] = value
  }

  // 加载意图树列表
  const loadTaxonomies = async () => {
    try {
      const response = await api.tgt.listTaxonomies()
      if (response.success && response.taxonomies) {
        taxonomies.value = response.taxonomies
      }
    } catch (error) {
      console.error('加载意图树列表失败', error)
    }
  }

  // 获取单个意图树
  const getTaxonomy = async (taxonomyId: string) => {
    try {
      const response = await api.tgt.getTaxonomy(taxonomyId)
      if (response.success && response.data) {
        selectedTaxonomy.value = response.data.taxonomy
        return {
          taxonomy: response.data.taxonomy,
          nodes: response.data.nodes || [],
          statistics: response.data.statistics || null
        }
      }
    } catch (error) {
      console.error('获取意图树失败', error)
    }
    return null
  }

  // 保存意图树
  const saveTaxonomy = async (data: TGTConfig) => {
    try {
      const response = await api.tgt.saveTaxonomy(data)
      if (response.success && response.data) {
        ElMessage.success('意图树保存成功')
        await loadTaxonomies()
        return response.data
      } else {
        ElMessage.error(response.message || '意图树保存失败')
        return null
      }
    } catch (error: any) {
      ElMessage.error(error.message || '意图树保存失败')
      return null
    }
  }

  // 更新意图树
  const updateTaxonomy = async (taxonomyId: string, data: TGTConfig) => {
    try {
      const response = await api.tgt.updateTaxonomy(taxonomyId, data)
      if (response.success) {
        ElMessage.success('意图树更新成功')
        await loadTaxonomies()
        return true
      } else {
        ElMessage.error(response.message || '意图树更新失败')
        return false
      }
    } catch (error: any) {
      ElMessage.error(error.message || '意图树更新失败')
      return false
    }
  }

  // 删除意图树
  const deleteTaxonomy = async (taxonomyId: string) => {
    try {
      const response = await api.tgt.deleteTaxonomy(taxonomyId)
      if (response.success) {
        ElMessage.success('意图树删除成功')
        await loadTaxonomies()
        if (selectedTaxonomy.value?.id === taxonomyId) {
          selectedTaxonomy.value = null
        }
        return true
      } else {
        ElMessage.error(response.message || '意图树删除失败')
        return false
      }
    } catch (error: any) {
      ElMessage.error(error.message || '意图树删除失败')
      return false
    }
  }

  // 运行 TGT 管道
  const runPipeline = async (pipelineConfig: TGTPipelineConfig) => {
    try {
      pipelineRunning.value = true
      const response = await api.tgt.runPipeline(pipelineConfig)
      if (response.success && response.data) {
        pipelineStatus.value = response.data
        ElMessage.success('TGT 管道已启动')
        return response.data
      } else {
        ElMessage.error(response.message || 'TGT 管道启动失败')
        return null
      }
    } catch (error: any) {
      ElMessage.error(error.message || 'TGT 管道启动失败')
      return null
    } finally {
      pipelineRunning.value = false
    }
  }

  // 获取管道运行状态
  const getPipelineStatus = async (taskId: string) => {
    try {
      const response = await api.tgt.getPipelineStatus(taskId)
      if (response.success && response.data) {
        pipelineStatus.value = response.data
        return response.data
      }
    } catch (error) {
      console.error('获取管道状态失败', error)
    }
    return null
  }

  // 重置配置
  const resetConfig = () => {
    config.value = {
      taxonomy_path: '',
      domain: '',
      sampling_strategy: 'coverage',
      graph_max_hops: 2,
      graph_max_nodes: 20,
      serialization_format: 'natural_language',
      critic_type: 'rule',
      critic_min_score: 0.6,
      generation_target_qa_pairs: 100,
      batch_size: 10
    }
  }

  return {
    config,
    taxonomies,
    selectedTaxonomy,
    pipelineStatus,
    pipelineRunning,
    loadConfig,
    saveConfig,
    updateConfig,
    loadTaxonomies,
    getTaxonomy,
    saveTaxonomy,
    updateTaxonomy,
    deleteTaxonomy,
    runPipeline,
    getPipelineStatus,
    resetConfig
  }
})
