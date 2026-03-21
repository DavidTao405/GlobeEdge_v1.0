/**
 * Simulation Store — 仿真佇列管理。
 *
 * submit() → POST /api/simulations → _poll() 輪詢
 * outputMode: dashboard | report | api
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../lib/api'

export interface SimulationSummary {
  id: string
  status: string
  elapsed_sec: number | null
  summary: {
    horizon: number
    n_agents: number
    n_dims: number
    mc_runs: number
    device: string
    lambda_max: number
    final_mean: number[][]
    variance_over_time: number[]
  } | null
}

export interface SimulationStatus {
  id: string
  status: string
  progress?: number
  error?: string
  source?: string
}

export const useSimulationStore = defineStore('simulation', () => {
  const result = ref<SimulationSummary | null>(null)
  const status = ref<'idle' | 'queued' | 'running' | 'completed' | 'failed'>('idle')
  const progress = ref(0)
  const error = ref<string | null>(null)
  const outputMode = ref<'dashboard' | 'report' | 'api'>('dashboard')
  const simulationId = ref<string | null>(null)

  // 衍生計算
  const lambdaMax = computed(() => result.value?.summary?.lambda_max ?? 0)
  const distanceToTipping = computed(() => Math.max(0, 1 - lambdaMax.value))
  const riskLevel = computed(() => {
    const d = distanceToTipping.value
    if (d < 0.05) return 'critical'
    if (d < 0.15) return 'high'
    if (d < 0.30) return 'warning'
    return 'normal'
  })

  async function submit(projectId: string, mcRuns?: number) {
    status.value = 'queued'
    progress.value = 0
    error.value = null
    result.value = null

    try {
      const res = await api.post('/simulations', {
        project_id: projectId,
        mc_runs: mcRuns,
      })
      simulationId.value = res.id
      await _poll(res.id)
    } catch (e: any) {
      status.value = 'failed'
      error.value = e.message
    }
  }

  async function _poll(simId: string) {
    status.value = 'running'
    const MAX_ATTEMPTS = 600 // 30 分鐘
    let attempts = 0

    while (attempts < MAX_ATTEMPTS) {
      const s = await api.get<SimulationStatus>(`/simulations/${simId}/status`)
      progress.value = s.progress ?? progress.value

      if (s.status === 'completed' || s.status === 'done') {
        result.value = await api.get<SimulationSummary>(
          `/simulations/${simId}/result/summary`
        )
        status.value = 'completed'
        return
      }

      if (s.status === 'failed') {
        status.value = 'failed'
        error.value = s.error || 'Simulation failed'
        return
      }

      await new Promise(r => setTimeout(r, 3000))
      attempts++
    }

    status.value = 'failed'
    error.value = 'Polling timeout'
  }

  /** 載入已完成的仿真結果 */
  async function loadResult(simId: string) {
    simulationId.value = simId
    result.value = await api.get<SimulationSummary>(
      `/simulations/${simId}/result/summary`
    )
    status.value = result.value.status === 'done' ? 'completed' : 'idle'
  }

  function reset() {
    result.value = null
    status.value = 'idle'
    progress.value = 0
    error.value = null
    simulationId.value = null
  }

  return {
    result,
    status,
    progress,
    error,
    outputMode,
    simulationId,
    lambdaMax,
    distanceToTipping,
    riskLevel,
    submit,
    loadResult,
    reset,
  }
})
