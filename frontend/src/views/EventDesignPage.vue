<script setup lang="ts">
/**
 * EventDesignPage — ExternalEvent 設計 + Run Simulation。
 * 手動建立事件、用滑桿設定 impact_vector、最後提交仿真。
 */
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore } from '../stores/projectStore'
import { useSimulationStore } from '../stores/simulationStore'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const simStore = useSimulationStore()
const projectId = route.params.id as string

const form = ref({
  title: '',
  domain: 'domestic',
  description: '',
  impact_vector: [0, 0, 0, 0, 0, 0, 0, 0],
})

const domains = ['domestic', 'geopolitical', 'financial', 'natural']

onMounted(async () => {
  await store.loadProject(projectId)
})

function handleAdd() {
  if (!form.value.title.trim()) return
  store.addEvent({
    title: form.value.title,
    domain: form.value.domain,
    description: form.value.description,
    impact_vector: [...form.value.impact_vector],
  })
  form.value = { title: '', domain: 'domestic', description: '', impact_vector: [0, 0, 0, 0, 0, 0, 0, 0] }
}

async function runSimulation() {
  await simStore.submit(projectId)
  if (simStore.simulationId) {
    router.push(`/dashboard/${simStore.simulationId}`)
  }
}

function impactColor(v: number): string {
  if (v > 0.3) return '#34d399'
  if (v < -0.3) return '#fca5a5'
  return '#9ca3af'
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Events & Simulation</h1>
        <div class="subtitle">{{ store.current?.name }} · {{ store.events.length }} events</div>
      </div>
      <div class="nav-btns">
        <button class="btn btn-sm" @click="router.push(`/projects/${projectId}/edges`)">← Edges</button>
        <button
          class="btn btn-run"
          :disabled="simStore.status === 'running' || simStore.status === 'queued'"
          @click="runSimulation"
        >
          🚀 Run Simulation
        </button>
      </div>
    </div>

    <!-- Summary bar -->
    <div class="summary-bar">
      <div class="summary-item">
        <div class="summary-val">{{ store.agents.length }}</div>
        <div class="summary-label">Agents</div>
      </div>
      <div class="summary-item">
        <div class="summary-val">{{ store.edges.length }}</div>
        <div class="summary-label">Edges</div>
      </div>
      <div class="summary-item">
        <div class="summary-val">{{ store.events.length }}</div>
        <div class="summary-label">Events</div>
      </div>
      <div class="summary-item">
        <div class="summary-val">{{ store.current?.alpha }}</div>
        <div class="summary-label">Alpha</div>
      </div>
      <div class="summary-item">
        <div class="summary-val">{{ store.current?.mc_runs?.toLocaleString() }}</div>
        <div class="summary-label">MC Runs</div>
      </div>
    </div>

    <!-- Add event form -->
    <div class="card form-card">
      <div class="form-row-inline">
        <div class="form-row">
          <label>Event Title</label>
          <input v-model="form.title" class="input" placeholder="e.g. 台電宣布電費調漲" />
        </div>
        <div class="form-row">
          <label>Domain</label>
          <select v-model="form.domain" class="input">
            <option v-for="d in domains" :key="d" :value="d">{{ d }}</option>
          </select>
        </div>
      </div>

      <div class="sliders">
        <div class="slider-header">Impact Vector</div>
        <div v-for="(label, i) in store.dimensionLabels" :key="i" class="slider-row">
          <label>
            <span class="dim-idx">{{ i }}</span>
            {{ label }}
            <span class="slider-val" :style="{ color: impactColor(form.impact_vector[i]) }">
              {{ form.impact_vector[i] >= 0 ? '+' : '' }}{{ form.impact_vector[i].toFixed(2) }}
            </span>
          </label>
          <input
            type="range"
            v-model.number="form.impact_vector[i]"
            min="-1" max="1" step="0.05"
          />
        </div>
      </div>

      <button class="btn btn-primary" :disabled="!form.title.trim()" @click="handleAdd">
        Add Event
      </button>
    </div>

    <!-- Event list -->
    <div v-for="(ev, i) in store.events" :key="i" class="card event-card">
      <div class="event-header">
        <div>
          <div class="event-title">{{ ev.title }}</div>
          <div class="event-domain">{{ ev.domain }}</div>
        </div>
        <button class="btn btn-xs" @click="store.removeEvent(i)">✕</button>
      </div>
      <div class="impact-chips">
        <span
          v-for="(v, j) in ev.impact_vector"
          :key="j"
          class="impact-chip"
          :style="{ color: impactColor(v), borderColor: impactColor(v) }"
        >
          {{ store.dimensionLabels[j]?.slice(0, 3) }}{{ v >= 0 ? '+' : '' }}{{ v.toFixed(1) }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 22px; }
.subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
.nav-btns { display: flex; gap: 8px; align-items: center; }
.summary-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  padding: 12px 20px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.summary-item { text-align: center; min-width: 60px; }
.summary-val { font-size: 18px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; }
.summary-label { font-size: 10px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; }
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 10px; }
.form-card { border-color: #3b82f6; margin-bottom: 20px; }
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.05em; }
.form-row-inline { display: grid; grid-template-columns: 2fr 1fr; gap: 10px; }
.input { width: 100%; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text-primary); font-size: 13px; }
.sliders { margin: 12px 0; }
.slider-header { font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.slider-row { margin-bottom: 5px; }
.slider-row label { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-secondary); margin-bottom: 2px; }
.dim-idx { font-family: 'IBM Plex Mono', monospace; font-size: 10px; background: var(--border); width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
.slider-val { margin-left: auto; font-family: 'IBM Plex Mono', monospace; font-weight: 600; font-size: 12px; }
input[type="range"] { width: 100%; accent-color: #3b82f6; }
.event-card { }
.event-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
.event-title { font-size: 14px; font-weight: 600; }
.event-domain { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.impact-chips { display: flex; gap: 4px; flex-wrap: wrap; }
.impact-chip {
  font-size: 10px;
  font-family: 'IBM Plex Mono', monospace;
  padding: 2px 6px;
  border-radius: 3px;
  border: 1px solid;
  background: transparent;
}
.btn { padding: 6px 14px; border-radius: 6px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--text-primary); background: var(--border); }
.btn:hover { background: #4b5563; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-sm { padding: 5px 12px; font-size: 11px; }
.btn-xs { padding: 3px 8px; font-size: 10px; }
.btn-run {
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  color: #fff;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 700;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.btn-run:hover:not(:disabled) { filter: brightness(1.1); }
</style>
