<script setup lang="ts">
/**
 * DimensionPage — 8 個信念維度設定。
 * 維度 0-3, 6-7 是通用維度（唯讀）。
 * 維度 4, 5 可以覆蓋成議題專屬名稱。
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProjectStore, DIMENSION_LABELS } from '../stores/projectStore'

const route = useRoute()
const router = useRouter()
const store = useProjectStore()
const projectId = route.params.id as string

const overrides = ref<Record<number, string>>({})

onMounted(async () => {
  await store.loadProject(projectId)
  overrides.value = { ...store.dimensionOverrides }
})

function save() {
  if (overrides.value[4]) store.setDimensionOverride(4, overrides.value[4])
  if (overrides.value[5]) store.setDimensionOverride(5, overrides.value[5])
  router.push(`/projects/${projectId}/agents`)
}
</script>

<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Dimensions</h1>
        <div class="subtitle">{{ store.current?.name }}</div>
      </div>
      <div class="nav-btns">
        <button class="btn btn-sm" @click="router.push('/projects')">← Projects</button>
        <button class="btn btn-primary btn-sm" @click="save">Next: Agents →</button>
      </div>
    </div>

    <div class="dims-grid">
      <div
        v-for="(label, i) in DIMENSION_LABELS"
        :key="i"
        class="dim-card"
        :class="{ editable: i === 4 || i === 5 }"
      >
        <div class="dim-index">{{ i }}</div>
        <div class="dim-content">
          <div class="dim-default">{{ label }}</div>
          <template v-if="i === 4 || i === 5">
            <input
              v-model="overrides[i]"
              class="input"
              :placeholder="`Override: e.g. ${i === 4 ? '核電接受度' : '再生能源意願'}`"
            />
            <div class="dim-hint">議題專屬維度，可自訂名稱</div>
          </template>
          <template v-else>
            <div class="dim-fixed">通用維度（不可修改）</div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.page-header h1 { margin: 0; font-size: 22px; }
.subtitle { font-size: 13px; color: var(--text-secondary); margin-top: 2px; }
.nav-btns { display: flex; gap: 8px; }
.dims-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
@media (max-width: 768px) { .dims-grid { grid-template-columns: 1fr; } }
.dim-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.dim-card.editable {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}
.dim-index {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  font-family: 'IBM Plex Mono', monospace;
  flex-shrink: 0;
}
.dim-content { flex: 1; }
.dim-default {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 6px;
}
.dim-fixed {
  font-size: 11px;
  color: var(--text-secondary);
}
.dim-hint {
  font-size: 11px;
  color: #3b82f6;
  margin-top: 4px;
}
.input {
  width: 100%;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text-primary);
  font-size: 13px;
}
.btn {
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  color: var(--text-primary);
  background: var(--border);
}
.btn:hover { background: #4b5563; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-sm { padding: 5px 12px; font-size: 11px; }
</style>
