/**
 * Project Store — 專案 + Agent + Edge + Event CRUD。
 */
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../lib/api'

/* ── Types ──────────────────────────────────── */

export interface Project {
  id: string
  name: string
  description?: string
  alpha: number
  mc_runs: number
  noise_level: number
  sim_horizon: number
  status: string
}

export interface Agent {
  id: string
  project_id: string
  name: string
  type: string
  domain: string
  belief_init: number[]
}

export interface Edge {
  id: string
  project_id: string
  source_id: string
  target_id: string
  weight: number
  weight_type: string
  confidence: number
}

export interface ExternalEvent {
  id?: string
  title: string
  description?: string
  domain: string
  impact_vector: number[]
}

export const DIMENSION_LABELS = [
  '政府信任度',
  '制度公信力',
  '社會公平感',
  '經濟焦慮度',
  '[議題專屬 A]',
  '[議題專屬 B]',
  '群體凝聚度',
  '外部威脅感知',
]

export const AGENT_TYPES = ['media', 'kol', 'demographic', 'forum', 'institution']
export const AGENT_DOMAINS = ['news', 'social', 'financial', 'government']
export const WEIGHT_TYPES = ['structural', 'behavioral', 'semantic']

/* ── Store ──────────────────────────────────── */

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const current = ref<Project | null>(null)
  const agents = ref<Agent[]>([])
  const edges = ref<Edge[]>([])
  const events = ref<ExternalEvent[]>([])
  const dimensionOverrides = ref<Record<number, string>>({})
  const loading = ref(false)

  const dimensionLabels = computed(() =>
    DIMENSION_LABELS.map((label, i) => dimensionOverrides.value[i] || label)
  )

  /* ── Projects ─────────────────────────────── */

  async function fetchProjects() {
    loading.value = true
    try {
      projects.value = await api.get<Project[]>('/projects')
    } finally {
      loading.value = false
    }
  }

  async function createProject(data: Partial<Project>) {
    const p = await api.post<Project>('/projects', data)
    projects.value.push(p)
    return p
  }

  async function loadProject(id: string) {
    loading.value = true
    try {
      current.value = await api.get<Project>(`/projects/${id}`)
      await Promise.all([fetchAgents(id), fetchEdges(id)])
    } finally {
      loading.value = false
    }
  }

  async function updateProject(id: string, data: Partial<Project>) {
    current.value = await api.patch<Project>(`/projects/${id}`, data)
    const idx = projects.value.findIndex(p => p.id === id)
    if (idx >= 0) projects.value[idx] = current.value
  }

  /* ── Agents ───────────────────────────────── */

  async function fetchAgents(projectId: string) {
    // API returns agents nested or separately
    try {
      const res = await api.get<Agent[]>(`/agents?project_id=${projectId}`)
      agents.value = res
    } catch {
      agents.value = []
    }
  }

  async function createAgent(data: Partial<Agent>) {
    const a = await api.post<Agent>('/agents', data)
    agents.value.push(a)
    return a
  }

  /* ── Edges ────────────────────────────────── */

  async function fetchEdges(projectId: string) {
    try {
      const res = await api.get<{ matrix?: number[][] }>(`/agents/edges/matrix?project_id=${projectId}`)
      // The matrix endpoint returns the full W matrix; we also need individual edges
    } catch {
      // ignore if not available yet
    }
  }

  async function createEdge(data: Partial<Edge>) {
    const e = await api.post<Edge>('/agents/edges', data)
    edges.value.push(e)
    return e
  }

  /* ── Events (local state, not yet persisted via API) ─── */

  function addEvent(ev: ExternalEvent) {
    events.value.push(ev)
  }

  function removeEvent(index: number) {
    events.value.splice(index, 1)
  }

  function setDimensionOverride(index: number, label: string) {
    dimensionOverrides.value[index] = label
  }

  function reset() {
    current.value = null
    agents.value = []
    edges.value = []
    events.value = []
    dimensionOverrides.value = {}
  }

  return {
    projects,
    current,
    agents,
    edges,
    events,
    loading,
    dimensionLabels,
    dimensionOverrides,
    fetchProjects,
    createProject,
    loadProject,
    updateProject,
    fetchAgents,
    createAgent,
    fetchEdges,
    createEdge,
    addEvent,
    removeEvent,
    setDimensionOverride,
    reset,
  }
})
