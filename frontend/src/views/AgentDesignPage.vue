<script setup lang="ts">
/**
 * AgentDesignPage — Agent 設計。
 * 新增 Agent、設定類型、用滑桿設定 belief_init、雷達圖即時更新。
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore, AGENT_TYPES, AGENT_DOMAINS } from '../stores/projectStore'
import { api } from '../lib/api'
import AgentRadarChart from '../components/AgentRadarChart.vue'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const projectId = route.params.id as string

const showForm = ref(false)
const form = ref({
  name: '',
  type: 'media',
  domain: 'news',
  belief_init: [0, 0, 0, 0, 0, 0, 0, 0],
})

// AI 估計
const aiTopic = ref('')
const aiTexts = ref('')
const aiEstimating = ref(false)
const aiSuggested = ref<number[] | null>(null)
const aiReasoning = ref('')
const aiConfidence = ref(0)

const selectedAgent = ref<number | null>(null)
const selectedBeliefs = computed(() => {
  if (selectedAgent.value !== null && store.agents[selectedAgent.value]) {
    return store.agents[selectedAgent.value].belief_init
  }
  return form.value.belief_init
})

onMounted(async () => {
  await store.loadProject(projectId)
})

async function handleCreate() {
  if (!form.value.name.trim()) return
  await store.createAgent({
    project_id: projectId,
    ...form.value,
  })
  form.value = { name: '', type: 'media', domain: 'news', belief_init: [0, 0, 0, 0, 0, 0, 0, 0] }
  aiSuggested.value = null
  aiReasoning.value = ''
  showForm.value = false
}

async function handleAIEstimate() {
  if (!form.value.name.trim() || !aiTopic.value.trim()) return
  const texts = aiTexts.value.split('\n').filter(t => t.trim())
  if (!texts.length) return

  aiEstimating.value = true
  aiSuggested.value = null
  try {
    const res = await api.post<{
      vector: number[]
      confidence: number
      reasoning: string
    }>('/agents/estimate-belief', {
      agent_name: form.value.name,
      agent_type: form.value.type,
      topic: aiTopic.value,
      texts,
      dimension_labels: store.dimensionLabels,
    })
    aiSuggested.value = res.vector
    aiConfidence.value = res.confidence
    aiReasoning.value = res.reasoning
  } catch (e: any) {
    aiReasoning.value = `Error: ${e.message}`
  } finally {
    aiEstimating.value = false
  }
}

function acceptAISuggestion() {
  if (aiSuggested.value) {
    form.value.belief_init = [...aiSuggested.value]
  }
}

function selectAgent(i: number) {
  selectedAgent.value = selectedAgent.value === i ? null : i
}

const typeColors: Record<string, string> = {
  media: '#3b82f6',
  kol: '#f59e0b',
  demographic: '#10b981',
  forum: '#8b5cf6',
  institution: '#ef4444',
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Agents</h1>
        <div class="subtitle">{{ store.current?.name }} · {{ store.agents.length }} agents</div>
      </div>
      <div class="nav-btns">
        <button class="btn btn-sm" @click="router.push(`/projects/${projectId}/dimensions`)">← Dimensions</button>
        <button class="btn btn-sm" @click="showForm = !showForm">{{ showForm ? 'Cancel' : '+ Agent' }}</button>
        <button class="btn btn-primary btn-sm" @click="router.push(`/projects/${projectId}/edges`)">Next: Edges →</button>
      </div>
    </div>

    <div class="layout">
      <!-- Left: Agent list + form -->
      <div class="panel-left">
        <!-- Create form -->
        <div v-if="showForm" class="card form-card">
          <div class="form-row">
            <label>Name</label>
            <input v-model="form.name" class="input" placeholder="e.g. 台電官方" />
          </div>
          <div class="form-row-inline">
            <div class="form-row">
              <label>Type</label>
              <select v-model="form.type" class="input">
                <option v-for="t in AGENT_TYPES" :key="t" :value="t">{{ t }}</option>
              </select>
            </div>
            <div class="form-row">
              <label>Domain</label>
              <select v-model="form.domain" class="input">
                <option v-for="d in AGENT_DOMAINS" :key="d" :value="d">{{ d }}</option>
              </select>
            </div>
          </div>
          <div class="sliders">
            <div v-for="(label, i) in store.dimensionLabels" :key="i" class="slider-row">
              <label>
                <span class="dim-idx">{{ i }}</span>
                {{ label }}
                <span class="slider-val">{{ form.belief_init[i].toFixed(2) }}</span>
                <span
                  v-if="aiSuggested && aiSuggested[i] !== undefined"
                  class="ai-dot"
                  :style="{ left: ((aiSuggested[i] + 1) / 2 * 100) + '%' }"
                  :title="'AI suggests: ' + aiSuggested[i].toFixed(2)"
                >
                  ●
                </span>
              </label>
              <div class="slider-container">
                <input
                  type="range"
                  v-model.number="form.belief_init[i]"
                  min="-1" max="1" step="0.05"
                />
              </div>
            </div>
          </div>

          <!-- AI 估計區 -->
          <div class="ai-section">
            <div class="ai-header">🤖 AI Belief Estimation</div>
            <div class="form-row">
              <label>Topic</label>
              <input v-model="aiTopic" class="input" placeholder="e.g. 台灣能源政策" />
            </div>
            <div class="form-row">
              <label>Reference Texts (one per line)</label>
              <textarea
                v-model="aiTexts"
                class="input textarea"
                rows="3"
                placeholder="貼入相關新聞標題或摘要..."
              />
            </div>
            <div class="ai-actions">
              <button
                class="btn btn-ai"
                :disabled="aiEstimating || !form.name.trim() || !aiTopic.trim()"
                @click="handleAIEstimate"
              >
                {{ aiEstimating ? '⏳ Estimating...' : '🤖 AI Estimate' }}
              </button>
              <button
                v-if="aiSuggested"
                class="btn btn-accept"
                @click="acceptAISuggestion"
              >
                ✅ Accept Suggestion
              </button>
            </div>
            <div v-if="aiReasoning" class="ai-result">
              <div v-if="aiConfidence" class="ai-confidence">
                Confidence: {{ (aiConfidence * 100).toFixed(0) }}%
              </div>
              <div class="ai-reasoning">{{ aiReasoning }}</div>
            </div>
          </div>

          <button class="btn btn-primary" :disabled="!form.name.trim()" @click="handleCreate">
            Add Agent
          </button>
        </div>

        <!-- Agent list -->
        <div
          v-for="(agent, i) in store.agents"
          :key="agent.id"
          class="card agent-card"
          :class="{ selected: selectedAgent === i }"
          @click="selectAgent(i)"
        >
          <div class="agent-header">
            <span class="agent-dot" :style="{ background: typeColors[agent.type] || '#6b7280' }" />
            <span class="agent-name">{{ agent.name }}</span>
            <span class="agent-type">{{ agent.type }}</span>
          </div>
          <div class="agent-beliefs">
            <span
              v-for="(v, j) in agent.belief_init"
              :key="j"
              class="belief-chip"
              :class="{ pos: v > 0.2, neg: v < -0.2 }"
            >{{ v >= 0 ? '+' : '' }}{{ v.toFixed(1) }}</span>
          </div>
        </div>

        <div v-if="!store.agents.length && !showForm" class="muted">
          No agents yet. Click "+ Agent" to create one.
        </div>
      </div>

      <!-- Right: Radar chart -->
      <div class="panel-right">
        <div class="radar-panel card">
          <div class="radar-title">Belief Vector</div>
          <AgentRadarChart
            :values="selectedBeliefs"
            :labels="store.dimensionLabels"
            :size="280"
          />
          <div class="radar-hint">
            {{ selectedAgent !== null ? store.agents[selectedAgent]?.name : 'New Agent Preview' }}
          </div>
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
.panel-left { flex: 1; min-width: 0; }
.panel-right { width: 320px; flex-shrink: 0; }
@media (max-width: 900px) { .layout { flex-direction: column; } .panel-right { width: 100%; } }
.card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 8px; }
.form-card { margin-bottom: 16px; border-color: #3b82f6; }
.form-row { margin-bottom: 10px; }
.form-row label { display: block; font-size: 11px; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; text-transform: uppercase; letter-spacing: 0.05em; }
.form-row-inline { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.input { width: 100%; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--text-primary); font-size: 13px; }
select.input { cursor: pointer; }
.sliders { margin: 14px 0; }
.slider-row { margin-bottom: 6px; }
.slider-row label { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--text-secondary); margin-bottom: 2px; }
.dim-idx { font-family: 'IBM Plex Mono', monospace; font-size: 10px; background: var(--border); width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; }
.slider-val { margin-left: auto; font-family: 'IBM Plex Mono', monospace; color: #3b82f6; font-weight: 600; font-size: 12px; }
input[type="range"] { width: 100%; accent-color: #3b82f6; }
.agent-card { cursor: pointer; transition: border-color 0.15s; }
.agent-card:hover { border-color: #4b5563; }
.agent-card.selected { border-color: #3b82f6; background: rgba(59, 130, 246, 0.05); }
.agent-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.agent-dot { width: 8px; height: 8px; border-radius: 50%; }
.agent-name { font-size: 14px; font-weight: 600; }
.agent-type { font-size: 11px; color: var(--text-secondary); margin-left: auto; font-family: 'IBM Plex Mono', monospace; }
.agent-beliefs { display: flex; gap: 4px; flex-wrap: wrap; }
.belief-chip { font-size: 10px; font-family: 'IBM Plex Mono', monospace; padding: 1px 5px; border-radius: 3px; background: var(--border); color: var(--text-secondary); }
.belief-chip.pos { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.belief-chip.neg { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }
.radar-panel { text-align: center; position: sticky; top: 80px; }
.radar-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.radar-hint { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }
.btn { padding: 6px 14px; border-radius: 6px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--text-primary); background: var(--border); }
.btn:hover { background: #4b5563; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-sm { padding: 5px 12px; font-size: 11px; }
.muted { color: var(--text-secondary); font-size: 13px; padding: 20px 0; }
.slider-container { position: relative; }
.ai-dot { position: absolute; color: #f59e0b; font-size: 8px; top: -2px; transform: translateX(-50%); pointer-events: none; z-index: 1; }
.ai-section { margin: 16px 0; padding: 14px; background: rgba(245, 158, 11, 0.05); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 8px; }
.ai-header { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: #f59e0b; }
.textarea { resize: vertical; font-size: 12px; min-height: 60px; font-family: inherit; }
.ai-actions { display: flex; gap: 8px; margin-top: 8px; }
.btn-ai { background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; padding: 6px 16px; border: none; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-ai:hover:not(:disabled) { filter: brightness(1.1); }
.btn-ai:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-accept { background: #10b981; color: #fff; padding: 6px 16px; border: none; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-accept:hover { background: #059669; }
.ai-result { margin-top: 10px; padding: 8px 12px; background: var(--card-bg); border-radius: 6px; font-size: 12px; }
.ai-confidence { color: #f59e0b; font-weight: 600; font-family: 'IBM Plex Mono', monospace; margin-bottom: 4px; }
.ai-reasoning { color: var(--text-secondary); }
</style>
