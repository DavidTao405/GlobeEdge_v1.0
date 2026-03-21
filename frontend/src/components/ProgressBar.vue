<script setup lang="ts">
defineProps<{
  progress: number   // 0 ~ 1
  status: string
}>()
</script>

<template>
  <div class="progress-wrapper">
    <div class="progress-bar">
      <div
        class="progress-fill"
        :style="{ width: `${Math.min(progress * 100, 100)}%` }"
        :class="{ indeterminate: status === 'queued' }"
      />
    </div>
    <span class="progress-label">
      {{ status === 'queued' ? 'Queued...' : `${(progress * 100).toFixed(0)}%` }}
    </span>
  </div>
</template>

<style scoped>
.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}
.progress-bar {
  flex: 1;
  height: 8px;
  background: var(--gauge-bg, #374151);
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: #60a5fa;
  border-radius: 4px;
  transition: width 0.5s ease;
}
.progress-fill.indeterminate {
  width: 40% !important;
  animation: indeterminate 1.5s ease-in-out infinite;
}
@keyframes indeterminate {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}
.progress-label {
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
  font-family: 'IBM Plex Mono', monospace;
  min-width: 50px;
}
</style>
