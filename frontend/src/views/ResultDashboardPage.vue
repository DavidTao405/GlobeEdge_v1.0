<script setup lang="ts">
/**
 * ResultDashboardPage — 仿真結果儀表板。
 *
 * 流程：
 *   1. 輸入 Project ID → submit
 *   2. 顯示 running 進度條
 *   3. 完成後渲染 RiskGauge + EWSChart + BeliefChart
 */
import { ref } from 'vue'
import { useSimulationStore } from '../stores/simulationStore'
import RiskGauge from '../components/RiskGauge.vue'
import EWSChart from '../components/EWSChart.vue'
import BeliefChart from '../components/BeliefChart.vue'
import ProgressBar from '../components/ProgressBar.vue'

const store = useSimulationStore()
const projectId = ref('')
const simIdInput = ref('')

async function handleSubmit() {
  if (!projectId.value.trim()) return
  await store.submit(projectId.value.trim())
}

async function handleLoad() {
  if (!simIdInput.value.trim()) return
  await store.loadResult(simIdInput.value.trim())
}
</script>

<template>
  <div class="dashboard">
    <header class="header">
      <h1>GlobeEdge</h1>
      <span class="subtitle">Social Belief Dynamics Model</span>
    </header>

    <!-- Controls -->
    <section class="controls">
      <div class="input-group">
        <input
          v-model="projectId"
          placeholder="Project ID"
          class="input"
          :disabled="store.status === 'running' || store.status === 'queued'"
        />
        <button
          class="btn btn-primary"
          :disabled="!projectId || store.status === 'running' || store.status === 'queued'"
          @click="handleSubmit"
        >
          Run Simulation
        </button>
      </div>
      <div class="input-group">
        <input
          v-model="simIdInput"
          placeholder="Load Simulation ID"
          class="input"
        />
        <button class="btn btn-secondary" :disabled="!simIdInput" @click="handleLoad">
          Load
        </button>
      </div>
    </section>

    <!-- Progress -->
    <section v-if="store.status === 'queued' || store.status === 'running'" class="section">
      <ProgressBar :progress="store.progress" :status="store.status" />
    </section>

    <!-- Error -->
    <section v-if="store.status === 'failed'" class="section error-box">
      ⚠️ {{ store.error }}
    </section>

    <!-- Results -->
    <section v-if="store.status === 'completed' && store.result?.summary" class="section">
      <!-- Top stats row -->
      <div class="stats-row">
        <RiskGauge :value="store.lambdaMax" label="λ_max" />

        <div class="stat-cards">
          <div class="stat-card">
            <div class="stat-value">{{ store.result.summary.mc_runs?.toLocaleString() }}</div>
            <div class="stat-label">MC Runs</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ store.result.summary.n_agents }}</div>
            <div class="stat-label">Agents</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ store.result.summary.horizon }}</div>
            <div class="stat-label">Horizon</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ store.result.summary.device?.toUpperCase() }}</div>
            <div class="stat-label">Device</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ store.result.elapsed_sec?.toFixed(1) }}s</div>
            <div class="stat-label">Elapsed</div>
          </div>
        </div>
      </div>

      <!-- Charts -->
      <div class="charts-grid">
        <EWSChart
          :variance-over-time="store.result.summary.variance_over_time ?? []"
          :lambda-max="store.lambdaMax"
        />
        <BeliefChart
          v-if="store.result.summary.final_mean"
          :mean="(store.result as any).summary?.mean ?? []"
          :ci-lower="(store.result as any).summary?.ci_lower"
          :ci-upper="(store.result as any).summary?.ci_upper"
          :n-agents="store.result.summary.n_agents"
          :n-dims="store.result.summary.n_dims"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}
.header {
  margin-bottom: 32px;
}
.header h1 {
  font-size: 28px;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary, #f9fafb);
  font-family: 'IBM Plex Sans', sans-serif;
}
.subtitle {
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
}
.controls {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.input-group {
  display: flex;
  gap: 8px;
}
.input {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid var(--border, #374151);
  background: var(--card-bg, #1f2937);
  color: var(--text-primary, #f9fafb);
  font-size: 13px;
  font-family: 'IBM Plex Mono', monospace;
  width: 300px;
}
.input::placeholder { color: #6b7280; }
.btn {
  padding: 8px 20px;
  border-radius: 8px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-primary {
  background: #3b82f6;
  color: #fff;
}
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-secondary {
  background: #374151;
  color: #d1d5db;
}
.btn-secondary:hover:not(:disabled) { background: #4b5563; }
.section {
  margin-bottom: 24px;
}
.error-box {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid #ef4444;
  border-radius: 8px;
  padding: 12px 16px;
  color: #fca5a5;
  font-size: 13px;
}
.stats-row {
  display: flex;
  gap: 32px;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.stat-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.stat-card {
  background: var(--card-bg, #1f2937);
  border-radius: 10px;
  padding: 14px 20px;
  text-align: center;
  min-width: 80px;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary, #f9fafb);
  font-family: 'IBM Plex Mono', monospace;
}
.stat-label {
  font-size: 11px;
  color: var(--text-secondary, #9ca3af);
  margin-top: 4px;
}
.charts-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 20px;
}
@media (min-width: 1024px) {
  .charts-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
