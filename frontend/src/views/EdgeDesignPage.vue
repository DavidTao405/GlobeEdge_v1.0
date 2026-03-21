<script setup lang="ts">
/**
 * EdgeDesignPage — W 矩陣影響力邊設計。
 * 選 source/target Agent、設定 weight、顯示 W 矩陣熱圖。
 */
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore, WEIGHT_TYPES } from '../stores/projectStore'
import * as d3 from 'd3'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const projectId = route.params.id as string
const heatmapRef = ref<SVGSVGElement | null>(null)

const form = ref({
  source_id: '',
  target_id: '',
  weight: 0.15,
  weight_type: 'structural',
})

// Local W matrix for visualization
const wMatrix = ref<number[][]>([])

onMounted(async () => {
  await store.loadProject(projectId)
  buildMatrix()
})

function buildMatrix() {
  const n = store.agents.length
  if (!n) return
  const m = Array.from({ length: n }, () => Array(n).fill(0))
  for (const e of store.edges) {
    const si = store.agents.findIndex(a => a.id === e.source_id)
    const ti = store.agents.findIndex(a => a.id === e.target_id)
    if (si >= 0 && ti >= 0) m[si][ti] = e.weight
  }
  wMatrix.value = m
  drawHeatmap()
}

function drawHeatmap() {
  if (!heatmapRef.value || !wMatrix.value.length) return

  const svg = d3.select(heatmapRef.value)
  svg.selectAll('*').remove()

  const n = wMatrix.value.length
  const cellSize = Math.min(28, 300 / n)
  const margin = { left: 60, top: 10 }
  const w = margin.left + n * cellSize
  const h = margin.top + n * cellSize

  svg.attr('width', w).attr('height', h)

  const color = d3.scaleSequential(d3.interpolateBlues).domain([0, 1])

  // Cells
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      svg.append('rect')
        .attr('x', margin.left + j * cellSize)
        .attr('y', margin.top + i * cellSize)
        .attr('width', cellSize - 1)
        .attr('height', cellSize - 1)
        .attr('rx', 2)
        .attr('fill', i === j ? '#1f2937' : color(wMatrix.value[i][j]))
        .append('title')
        .text(`${store.agents[i]?.name} → ${store.agents[j]?.name}: ${wMatrix.value[i][j].toFixed(2)}`)
    }
    // Row labels
    svg.append('text')
      .attr('x', margin.left - 4)
      .attr('y', margin.top + i * cellSize + cellSize / 2)
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'central')
      .attr('fill', '#9ca3af')
      .attr('font-size', 9)
      .text(store.agents[i]?.name?.slice(0, 6) || '')
  }
}

watch(() => store.edges.length, buildMatrix)

async function handleCreate() {
  if (!form.value.source_id || !form.value.target_id) return
  if (form.value.source_id === form.value.target_id) return
  await store.createEdge({
    project_id: projectId,
    ...form.value,
    confidence: 0.5,
  })
  buildMatrix()
  form.value.source_id = ''
  form.value.target_id = ''
  form.value.weight = 0.15
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Influence Edges (W Matrix)</h1>
        <div class="subtitle">{{ store.current?.name }} · {{ store.edges.length }} edges · {{ store.agents.length }} agents</div>
      </div>
      <div class="nav-btns">
        <button class="btn btn-sm" @click="router.push(`/projects/${projectId}/agents`)">← Agents</button>
        <button class="btn btn-primary btn-sm" @click="router.push(`/projects/${projectId}/events`)">Next: Events →</button>
      </div>
    </div>

    <div class="layout">
      <div class="panel-left">
        <!-- Add edge form -->
        <div class="card form-card">
          <div class="form-row-inline">
            <div class="form-row">
              <label>Source (影響者)</label>
              <select v-model="form.source_id" class="input">
                <option value="">Select...</option>
                <option v-for="a in store.agents" :key="a.id" :value="a.id">{{ a.name }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Target (被影響者)</label>
              <select v-model="form.target_id" class="input">
                <option value="">Select...</option>
                <option v-for="a in store.agents" :key="a.id" :value="a.id">{{ a.name }}</option>
              </select>
            </div>
          </div>
          <div class="form-row-inline">
            <div class="form-row">
              <label>Weight <span class="hint">{{ form.weight.toFixed(2) }}</span></label>
              <input type="range" v-model.number="form.weight" min="0" max="1" step="0.05" />
            </div>
            <div class="form-row">
              <label>Type</label>
              <select v-model="form.weight_type" class="input">
                <option v-for="t in WEIGHT_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
          </div>
          <button
            class="btn btn-primary"
            :disabled="!form.source_id || !form.target_id || form.source_id === form.target_id"
            @click="handleCreate"
          >Add Edge</button>
        </div>

        <!-- Edge list -->
        <div v-for="e in store.edges" :key="e.id" class="card edge-card">
          <span class="edge-label">
            {{ store.agents.find(a => a.id === e.source_id)?.name || '?' }}
            <span class="arrow">→</span>
            {{ store.agents.find(a => a.id === e.target_id)?.name || '?' }}
          </span>
          <span class="edge-weight">w={{ e.weight.toFixed(2) }}</span>
          <span class="edge-type">{{ e.weight_type }}</span>
        </div>
      </div>

      <div class="panel-right">
        <div class="card heatmap-panel">
          <div class="heatmap-title">W Matrix Heatmap</div>
          <svg ref="heatmapRef" />
          <div v-if="!store.agents.length" class="muted">Add agents first to see the matrix.</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 22px; }
.subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
.nav-btns { display: flex; gap: 6px; }
.layout { display: flex; gap: 20px; }
.panel-left { flex: 1; }
.panel-right { width: 380px; flex-shrink: 0; }
@media (max-width: 900px) { .layout { flex-direction: column; } .panel-right { width: 100%; } }
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 8px; }
.form-card { border-color: #3b82f6; margin-bottom: 16px; }
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.05em; }
.form-row-inline { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.input { width: 100%; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text-primary); font-size: 13px; }
.hint { font-family: 'IBM Plex Mono', monospace; color: #3b82f6; font-weight: 700; }
input[type="range"] { width: 100%; accent-color: #3b82f6; }
.edge-card { display: flex; align-items: center; gap: 12px; padding: 10px 14px; }
.edge-label { font-size: 13px; flex: 1; }
.arrow { color: #3b82f6; margin: 0 4px; }
.edge-weight { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #3b82f6; }
.edge-type { font-size: 10px; color: var(--text-secondary); background: var(--border); padding: 2px 6px; border-radius: 3px; }
.heatmap-panel { text-align: center; position: sticky; top: 80px; }
.heatmap-title { font-size: 13px; font-weight: 600; margin-bottom: 10px; }
.btn { padding: 6px 14px; border-radius: 6px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--text-primary); background: var(--border); }
.btn:hover { background: #4b5563; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-sm { padding: 5px 12px; font-size: 11px; }
.muted { color: var(--text-secondary); font-size: 12px; padding: 20px 0; }
</style>
