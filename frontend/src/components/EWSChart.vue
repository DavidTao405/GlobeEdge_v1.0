<script setup lang="ts">
/**
 * EWSChart — Observable Plot 折線圖。
 *
 * lambda_max + variance 時序，標示閾值警戒線。
 */
import { ref, onMounted, watch } from 'vue'
import * as Plot from '@observablehq/plot'

const props = defineProps<{
  varianceOverTime: number[]
  lambdaMax: number
}>()

const containerRef = ref<HTMLDivElement | null>(null)

const THRESHOLDS = {
  variance_warn: 0.03,
  variance_critical: 0.08,
  lambda_warn: 0.85,
  lambda_critical: 0.95,
}

function draw() {
  if (!containerRef.value || !props.varianceOverTime?.length) return
  containerRef.value.innerHTML = ''

  const data = props.varianceOverTime.map((v, t) => ({ t, variance: v }))

  const plot = Plot.plot({
    width: 560,
    height: 280,
    style: {
      background: 'transparent',
      color: 'var(--text-primary, #f9fafb)',
      fontSize: '11px',
      fontFamily: '"IBM Plex Sans", sans-serif',
    },
    x: { label: 'Time step', grid: true },
    y: { label: 'Variance', grid: true, domain: [0, Math.max(0.1, ...props.varianceOverTime) * 1.2] },
    marks: [
      // Threshold zones
      Plot.ruleY([THRESHOLDS.variance_warn], {
        stroke: '#eab308',
        strokeDasharray: '6,3',
        strokeWidth: 1,
      }),
      Plot.ruleY([THRESHOLDS.variance_critical], {
        stroke: '#ef4444',
        strokeDasharray: '6,3',
        strokeWidth: 1,
      }),
      // Variance line
      Plot.lineY(data, {
        x: 't',
        y: 'variance',
        stroke: '#60a5fa',
        strokeWidth: 2,
        curve: 'catmull-rom',
      }),
      Plot.dot(data, {
        x: 't',
        y: 'variance',
        fill: '#60a5fa',
        r: 2.5,
      }),
      // Annotations
      Plot.text([{ t: data.length - 1, y: THRESHOLDS.variance_warn }], {
        x: 't', y: 'y',
        text: () => 'WARN',
        fill: '#eab308',
        dx: 30, dy: -6,
        fontSize: 9,
      }),
      Plot.text([{ t: data.length - 1, y: THRESHOLDS.variance_critical }], {
        x: 't', y: 'y',
        text: () => 'CRIT',
        fill: '#ef4444',
        dx: 30, dy: -6,
        fontSize: 9,
      }),
    ],
  })

  containerRef.value.appendChild(plot)
}

onMounted(draw)
watch(() => props.varianceOverTime, draw, { deep: true })
</script>

<template>
  <div class="chart-card">
    <h3 class="chart-title">
      EWS Indicators
      <span class="chip">λ_max = {{ lambdaMax.toFixed(4) }}</span>
    </h3>
    <div ref="containerRef" class="chart-container" />
  </div>
</template>

<style scoped>
.chart-card {
  background: var(--card-bg, #1f2937);
  border-radius: 12px;
  padding: 20px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: var(--text-primary, #f9fafb);
  display: flex;
  align-items: center;
  gap: 10px;
}
.chip {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  font-family: 'IBM Plex Mono', monospace;
}
.chart-container {
  overflow-x: auto;
}
</style>
