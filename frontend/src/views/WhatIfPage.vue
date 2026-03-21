<script setup lang="ts">
/**
 * WhatIfPage — 反事實分析。
 *
 * 左側：介入設定（移除 Agent / 修改 belief / 修改 edge）
 * 右側：基準 vs What If 結果對比
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../lib/api'

const route = useRoute()
const simId = route.params.simId as string

// State
const agents = ref<any[]>([])
const projectId = ref('')
const interventions = ref<any[]>([])
const loading = ref(false)
const result = ref<any>(null)

// Form
const ivType = ref<'remove_agent' | 'modify_belief' | 'modify_edge'>('remove_agent')
const ivTarget = ref('')
const ivDim = ref(0)
const ivValue = ref(0)
const ivEdgeTarget = ref('')
const ivEdgeWeight = ref(0.15)

const dimLabels = [
  '政府信任度', '制度公信力', '社會公平感', '經濟焦慮度',
  '[議題專屬A]', '[議題專屬B]', '群體凝聚度', '外部威脅感知',
]

onMounted(async () => {
  // Load simulation to get project_id, then load agents
  try {
    const sim = await api.get(`/simulations/${simId}/status`)
    // Try to get project agents
    const projects = await api.get<any[]>('/projects')
    if (projects.length) {
      projectId.value = projects[0].id
      agents.value = await api.get<any[]>(`/agents?project_id=${projects[0].id}`)
    }
  } catch { /* ignore */ }
})

function addIntervention() {
  const iv: any = { type: ivType.value, target: ivTarget.value }

  if (ivType.value === 'remove_agent') {
    const agent = agents.value.find(a => a.id === ivTarget.value)
    iv.description = `移除 ${agent?.name || ivTarget.value}`
  } else if (ivType.value === 'modify_belief') {
    const agent = agents.value.find(a => a.id === ivTarget.value)
    iv.params = { dim: ivDim.value, value: ivValue.value }
    iv.description = `${agent?.name || '?'} dim${ivDim.value} → ${ivValue.value.toFixed(2)}`
  } else if (ivType.value === 'modify_edge') {
    const src = agents.value.find(a => a.id === ivTarget.value)
    const tgt = agents.value.find(a => a.id === ivEdgeTarget.value)
    iv.params = { target: ivEdgeTarget.value, weight: ivEdgeWeight.value }
    iv.description = `${src?.name || '?'} → ${tgt?.name || '?'} w=${ivEdgeWeight.value.toFixed(2)}`
  }

  interventions.value.push(iv)
}

function removeIntervention(i: number) {
  interventions.value.splice(i, 1)
}

async function runWhatIf() {
  if (!interventions.value.length) return
  loading.value = true
  result.value = null
  try {
    result.value = await api.post(`/simulations/${simId}/whatif`, {
      interventions: interventions.value,
    })
  } catch (e: any) {
    result.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

// Diff helpers
const lambdaDelta = computed(() => result.value?.diff?.lambda_max_delta ?? 0)
const lambdaDirection = computed(() => lambdaDelta.value > 0 ? '↑' : lambdaDelta.value < 0 ? '↓' : '—')
const lambdaColor = computed(() => lambdaDelta.value > 0 ? '#ef4444' : lambdaDelta.value < 0 ? '#10b981' : '#9ca3af')
</script>

<template>
  <div class="whatif">
    <div class="page-header">
      <div>
        <h1>What If Analysis</h1>
        <div class="subtitle">Baseline: {{ simId.slice(0, 8) }}...</div>
      </div>
    </div>

    <div class="layout">
      <!-- Left: Interventions -->
      <div class="panel-left">
        <div class="card form-card">
          <div class="section-title">Add Intervention</div>

          <div class="form-row">
            <label>Type</label>
            <select v-model="ivType" class="input">
              <option value="remove_agent">Remove Agent</option>
              <option value="modify_belief">Modify Belief</option>
              <option value="modify_edge">Modify Edge Weight</option>
            </select>
          </div>

          <div class="form-row">
            <label>{{ ivType === 'modify_edge' ? 'Source Agent' : 'Agent' }}</label>
            <select v-model="ivTarget" class="input">
              <option value="">Select...</option>
              <option v-for="a in agents" :key="a.id" :value="a.id">
                {{ a.name }} ({{ a.type }})
              </option>
            </select>
          </div>

          <template v-if="ivType === 'modify_belief'">
            <div class="form-row">
              <label>Dimension</label>
              <select v-model.number="ivDim" class="input">
                <option v-for="(l, i) in dimLabels" :key="i" :value="i">{{ i }}: {{ l }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Value <span class="hint">{{ ivValue.toFixed(2) }}</span></label>
              <input type="range" v-model.number="ivValue" min="-1" max="1" step="0.05" />
            </div>
          </template>

          <template v-if="ivType === 'modify_edge'">
            <div class="form-row">
              <label>Target Agent</label>
              <select v-model="ivEdgeTarget" class="input">
                <option value="">Select...</option>
                <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Weight <span class="hint">{{ ivEdgeWeight.toFixed(2) }}</span></label>
              <input type="range" v-model.number="ivEdgeWeight" min="0" max="1" step="0.05" />
            </div>
          </template>

          <button class="btn btn-primary" :disabled="!ivTarget" @click="addIntervention">
            + Add
          </button>
        </div>

        <!-- Intervention list -->
        <div v-for="(iv, i) in interventions" :key="i" class="card iv-card">
          <div class="iv-row">
            <span class="iv-type">{{ iv.type }}</span>
            <span class="iv-desc">{{ iv.description }}</span>
            <button class="btn btn-xs" @click="removeIntervention(i)">✕</button>
          </div>
        </div>

        <button
          class="btn btn-run"
          :disabled="loading || !interventions.length"
          @click="runWhatIf"
        >
          {{ loading ? '⏳ Running...' : '🔬 Run What If' }}
        </button>
      </div>

      <!-- Right: Results -->
      <div class="panel-right">
        <template v-if="result && !result.error">
          <!-- Lambda comparison -->
          <div class="card lambda-card">
            <div class="lambda-row">
              <div class="lambda-box">
                <div class="lambda-label">Baseline λ_max</div>
                <div class="lambda-val">{{ result.baseline.lambda_max.toFixed(4) }}</div>
              </div>
              <div class="lambda-arrow" :style="{ color: lambdaColor }">
                {{ lambdaDirection }} {{ Math.abs(lambdaDelta).toFixed(4) }}
              </div>
              <div class="lambda-box">
                <div class="lambda-label">What If λ_max</div>
                <div class="lambda-val">{{ result.whatif.lambda_max.toFixed(4) }}</div>
              </div>
            </div>
          </div>

          <!-- Interventions applied -->
          <div class="card">
            <div class="section-title">Interventions Applied</div>
            <div v-for="(desc, i) in result.interventions_applied" :key="i" class="applied-item">
              ✅ {{ desc }}
            </div>
            <div class="stat-line">Elapsed: {{ result.elapsed_sec }}s</div>
          </div>

          <!-- Dimension deltas -->
          <div class="card">
            <div class="section-title">Dimension Impact</div>
            <div v-for="d in result.diff.dimension_deltas" :key="d.dim" class="delta-row">
              <span class="delta-label">{{ d.label }}</span>
              <div class="delta-bar-container">
                <div
                  class="delta-bar"
                  :class="{ pos: d.mean_delta > 0, neg: d.mean_delta < 0 }"
                  :style="{ width: Math.min(Math.abs(d.mean_delta) * 200, 100) + '%' }"
                />
              </div>
              <span class="delta-val" :class="{ pos: d.mean_delta > 0, neg: d.mean_delta < 0 }">
                {{ d.mean_delta >= 0 ? '+' : '' }}{{ d.mean_delta.toFixed(4) }}
              </span>
            </div>
            <div class="stat-line">
              Total belief shift: {{ result.diff.total_belief_shift.toFixed(4) }}
            </div>
          </div>

          <!-- EWS comparison -->
          <div class="card">
            <div class="section-title">EWS Alerts Comparison</div>
            <div class="ews-compare">
              <div>
                <div class="ews-label">Baseline: {{ result.baseline.alerts.length }} alerts</div>
                <div v-for="a in result.baseline.alerts" :key="'b'+a.t" class="ews-chip">
                  t={{ a.t }} {{ a.severity }}
                </div>
              </div>
              <div>
                <div class="ews-label">What If: {{ result.whatif.alerts.length }} alerts</div>
                <div v-for="a in result.whatif.alerts" :key="'w'+a.t" class="ews-chip whatif">
                  t={{ a.t }} {{ a.severity }}
                </div>
              </div>
            </div>
          </div>

          <!-- Variance comparison chart (text-based) -->
          <div class="card">
            <div class="section-title">Variance Timeline</div>
            <div class="variance-chart">
              <div
                v-for="(_, t) in result.baseline.variance_over_time"
                :key="t"
                class="var-row"
                v-show="t % 5 === 0 || t === result.baseline.variance_over_time.length - 1"
              >
                <span class="var-t">t={{ t }}</span>
                <div class="var-bars">
                  <div class="var-bar baseline" :style="{ width: Math.min(result.baseline.variance_over_time[t] * 300, 100) + '%' }" />
                  <div class="var-bar whatif" :style="{ width: Math.min(result.whatif.variance_over_time[t] * 300, 100) + '%' }" />
                </div>
              </div>
            </div>
            <div class="var-legend">
              <span class="legend-dot baseline" /> Baseline
              <span class="legend-dot whatif" /> What If
            </div>
          </div>
        </template>

        <div v-else-if="result?.error" class="card error-box">
          ⚠️ {{ result.error }}
        </div>

        <div v-else-if="!loading" class="muted">
          Add interventions and click "Run What If" to see results.
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.whatif { max-width: 1200px; }
.page-header { margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 22px; }
.subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 2px; font-family: 'IBM Plex Mono', monospace; }
.layout { display: flex; gap: 20px; }
.panel-left { width: 360px; flex-shrink: 0; }
.panel-right { flex: 1; min-width: 0; }
@media (max-width: 900px) { .layout { flex-direction: column; } .panel-left { width: 100%; } }
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 10px; }
.form-card { border-color: #8b5cf6; }
.section-title { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.05em; }
.input { width: 100%; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text-primary); font-size: 13px; }
.hint { font-family: 'IBM Plex Mono', monospace; color: #8b5cf6; font-weight: 700; }
input[type="range"] { width: 100%; accent-color: #8b5cf6; }
.iv-card { padding: 10px 14px; }
.iv-row { display: flex; align-items: center; gap: 8px; }
.iv-type { font-size: 10px; font-family: 'IBM Plex Mono', monospace; background: rgba(139, 92, 246, 0.15); color: #a78bfa; padding: 2px 6px; border-radius: 3px; }
.iv-desc { font-size: 13px; flex: 1; }
.btn { padding: 6px 14px; border-radius: 6px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--text-primary); background: var(--border); }
.btn:hover { background: #4b5563; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #8b5cf6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #7c3aed; }
.btn-xs { padding: 3px 8px; font-size: 10px; }
.btn-run { width: 100%; margin-top: 12px; background: linear-gradient(135deg, #8b5cf6, #6d28d9); color: #fff; padding: 10px; font-size: 14px; font-weight: 700; border: none; border-radius: 8px; cursor: pointer; }
.btn-run:hover:not(:disabled) { filter: brightness(1.1); }
.lambda-card { }
.lambda-row { display: flex; align-items: center; justify-content: center; gap: 20px; }
.lambda-box { text-align: center; }
.lambda-label { font-size: 11px; color: var(--text-secondary); }
.lambda-val { font-size: 24px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.lambda-arrow { font-size: 18px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.applied-item { font-size: 13px; margin-bottom: 4px; }
.stat-line { font-size: 11px; color: var(--text-secondary); margin-top: 8px; font-family: 'IBM Plex Mono', monospace; }
.delta-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.delta-label { font-size: 11px; width: 90px; color: var(--text-secondary); flex-shrink: 0; }
.delta-bar-container { flex: 1; height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; }
.delta-bar { height: 100%; border-radius: 4px; transition: width 0.3s; }
.delta-bar.pos { background: #10b981; }
.delta-bar.neg { background: #ef4444; }
.delta-val { font-size: 11px; font-family: 'IBM Plex Mono', monospace; width: 60px; text-align: right; }
.delta-val.pos { color: #34d399; }
.delta-val.neg { color: #fca5a5; }
.ews-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.ews-label { font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
.ews-chip { font-size: 10px; font-family: 'IBM Plex Mono', monospace; background: rgba(239, 68, 68, 0.1); color: #fca5a5; padding: 2px 6px; border-radius: 3px; margin-bottom: 2px; display: inline-block; margin-right: 4px; }
.ews-chip.whatif { background: rgba(139, 92, 246, 0.1); color: #a78bfa; }
.variance-chart { margin: 8px 0; }
.var-row { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.var-t { font-size: 10px; font-family: 'IBM Plex Mono', monospace; width: 30px; color: var(--text-secondary); }
.var-bars { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.var-bar { height: 4px; border-radius: 2px; }
.var-bar.baseline { background: #6b7280; }
.var-bar.whatif { background: #8b5cf6; }
.var-legend { display: flex; gap: 16px; font-size: 10px; color: var(--text-secondary); margin-top: 6px; align-items: center; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.legend-dot.baseline { background: #6b7280; }
.legend-dot.whatif { background: #8b5cf6; }
.error-box { background: rgba(239, 68, 68, 0.1); border-color: #ef4444; color: #fca5a5; font-size: 13px; }
.muted { color: var(--text-secondary); font-size: 13px; padding: 40px 0; text-align: center; }
</style>
