<script setup lang="ts">
/**
 * ProjectListPage — 專案管理。
 * 建立專案、設定 alpha/mc_runs/sim_horizon、進入專案詳情。
 */
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useProjectStore } from '../stores/projectStore'

const store = useProjectStore()
const router = useRouter()

const showForm = ref(false)
const form = ref({
  name: '',
  description: '',
  alpha: 0.3,
  mc_runs: 10000,
  sim_horizon: 30,
  noise_level: 0.05,
  use_forgetting: false,
  use_elm: false,
  use_motivated_reasoning: false,
})

onMounted(() => store.fetchProjects())

async function handleCreate() {
  if (!form.value.name.trim()) return
  const p = await store.createProject(form.value)
  showForm.value = false
  form.value = { name: '', description: '', alpha: 0.3, mc_runs: 10000, sim_horizon: 30, noise_level: 0.05 }
  router.push(`/projects/${p.id}/dimensions`)
}

function goTo(projectId: string, tab: string) {
  router.push(`/projects/${projectId}/${tab}`)
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Projects</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? 'Cancel' : '+ New Project' }}
      </button>
    </div>

    <!-- Create Form -->
    <div v-if="showForm" class="card form-card">
      <div class="form-row">
        <label>Name</label>
        <input v-model="form.name" class="input" placeholder="e.g. 台灣能源政策" />
      </div>
      <div class="form-row">
        <label>Description</label>
        <input v-model="form.description" class="input" placeholder="Optional description" />
      </div>
      <div class="form-grid">
        <div class="form-row">
          <label>Alpha <span class="hint">{{ form.alpha }}</span></label>
          <input type="range" v-model.number="form.alpha" min="0.1" max="0.9" step="0.05" />
        </div>
        <div class="form-row">
          <label>MC Runs</label>
          <input type="number" v-model.number="form.mc_runs" class="input input-sm" />
        </div>
        <div class="form-row">
          <label>Horizon</label>
          <input type="number" v-model.number="form.sim_horizon" class="input input-sm" />
        </div>
        <div class="form-row">
          <label>Noise <span class="hint">{{ form.noise_level }}</span></label>
          <input type="range" v-model.number="form.noise_level" min="0.01" max="0.2" step="0.01" />
        </div>
      </div>
      <!-- Psychology Mechanisms -->
      <div class="psych-section">
        <div class="psych-title">🧠 Psychology Mechanisms</div>
        <label class="checkbox-row">
          <input type="checkbox" v-model="form.use_forgetting" />
          Ebbinghaus Forgetting — agents forget at type-specific rates
        </label>
        <label class="checkbox-row">
          <input type="checkbox" v-model="form.use_elm" />
          ELM Dual Pathway — high-involvement agents process deeper
        </label>
        <label class="checkbox-row">
          <input type="checkbox" v-model="form.use_motivated_reasoning" />
          Motivated Reasoning — Backfire Effect on distant beliefs
        </label>
      </div>

      <button class="btn btn-primary" :disabled="!form.name.trim()" @click="handleCreate">
        Create Project
      </button>
    </div>

    <!-- Project List -->
    <div v-if="store.loading" class="muted">Loading...</div>
    <div v-else-if="!store.projects.length" class="muted">No projects yet. Create one to begin.</div>

    <div v-for="p in store.projects" :key="p.id" class="card project-card">
      <div class="project-header">
        <div>
          <div class="project-name">{{ p.name }}</div>
          <div class="project-meta">
            α={{ p.alpha }} · MC={{ p.mc_runs?.toLocaleString() }} · H={{ p.sim_horizon }}
            <span v-if="p.status !== 'active'" class="badge">{{ p.status }}</span>
          </div>
        </div>
        <div class="project-actions">
          <button class="btn btn-sm" @click="goTo(p.id, 'dimensions')">Dimensions</button>
          <button class="btn btn-sm" @click="goTo(p.id, 'agents')">Agents</button>
          <button class="btn btn-sm" @click="goTo(p.id, 'edges')">Edges</button>
          <button class="btn btn-sm" @click="goTo(p.id, 'events')">Events</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.page-header h1 { margin: 0; font-size: 24px; }
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 12px;
}
.form-card { margin-bottom: 24px; }
.form-row {
  margin-bottom: 12px;
}
.form-row label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.hint {
  font-family: 'IBM Plex Mono', monospace;
  color: #3b82f6;
  font-weight: 700;
}
.input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text-primary);
  font-size: 13px;
}
.input-sm { width: 120px; }
.project-card { cursor: default; }
.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.project-name {
  font-size: 16px;
  font-weight: 600;
}
.project-meta {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'IBM Plex Mono', monospace;
  margin-top: 4px;
}
.project-actions {
  display: flex;
  gap: 6px;
}
.badge {
  background: #374151;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  margin-left: 8px;
}
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--text-primary);
  background: var(--border);
  transition: background 0.15s;
}
.btn:hover { background: #4b5563; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover:not(:disabled) { background: #2563eb; }
.btn-sm { padding: 5px 12px; font-size: 11px; }
.muted { color: var(--text-secondary); font-size: 14px; }
input[type="range"] { width: 100%; accent-color: #3b82f6; }
.psych-section { margin: 16px 0; padding: 14px; background: rgba(139, 92, 246, 0.05); border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 8px; }
.psych-title { font-size: 13px; font-weight: 600; margin-bottom: 10px; color: #a78bfa; }
.checkbox-row { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; cursor: pointer; }
.checkbox-row input[type="checkbox"] { accent-color: #8b5cf6; }
</style>
