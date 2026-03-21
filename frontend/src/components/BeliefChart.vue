<script setup lang="ts">
/**
 * BeliefChart — Observable Plot。
 *
 * 每個維度的 belief mean，areaY 畫 95% CI 區間帶。
 */
import { ref, onMounted, watch } from 'vue'
import * as Plot from '@observablehq/plot'

const props = defineProps<{
  mean: number[][][]       // (horizon+1, n_agents, n_dims)
  ciLower?: number[][][]
  ciUpper?: number[][][]
  nAgents: number
  nDims: number
}>()

const containerRef = ref<HTMLDivElement | null>(null)

const DIM_LABELS = [
  'Media Trust',
  'Social Safety',
  'Identity',
  'Econ Anxiety',
  'Policy Support',
  'Info Environment',
  'Group Cohesion',
  'External Threat',
]

function draw() {
  if (!containerRef.value || !props.mean?.length) return
  containerRef.value.innerHTML = ''

  // Aggregate across agents: mean over agents for each (t, dim)
  const horizon = props.mean.length
  const nDims = props.nDims || 8

  const data: { t: number; dim: string; value: number; lower: number; upper: number }[] = []

  for (let t = 0; t < horizon; t++) {
    for (let d = 0; d < nDims; d++) {
      let sum = 0, sumL = 0, sumU = 0
      for (let a = 0; a < props.nAgents; a++) {
        sum += props.mean[t]?.[a]?.[d] ?? 0
        sumL += props.ciLower?.[t]?.[a]?.[d] ?? sum / props.nAgents
        sumU += props.ciUpper?.[t]?.[a]?.[d] ?? sum / props.nAgents
      }
      data.push({
        t,
        dim: DIM_LABELS[d] || `Dim ${d}`,
        value: sum / props.nAgents,
        lower: sumL / props.nAgents,
        upper: sumU / props.nAgents,
      })
    }
  }

  const plot = Plot.plot({
    width: 560,
    height: 320,
    style: {
      background: 'transparent',
      color: 'var(--text-primary, #f9fafb)',
      fontSize: '11px',
      fontFamily: '"IBM Plex Sans", sans-serif',
    },
    color: { legend: true },
    x: { label: 'Time step', grid: true },
    y: { label: 'Belief (mean over agents)', domain: [-1, 1], grid: true },
    marks: [
      Plot.ruleY([0], { stroke: '#4b5563', strokeDasharray: '4,4' }),
      // CI band per dimension
      Plot.areaY(data, {
        x: 't',
        y1: 'lower',
        y2: 'upper',
        fill: 'dim',
        fillOpacity: 0.1,
        curve: 'catmull-rom',
      }),
      // Mean line per dimension
      Plot.lineY(data, {
        x: 't',
        y: 'value',
        stroke: 'dim',
        strokeWidth: 1.5,
        curve: 'catmull-rom',
      }),
    ],
  })

  containerRef.value.appendChild(plot)
}

onMounted(draw)
watch(() => props.mean, draw, { deep: true })
</script>

<template>
  <div class="chart-card">
    <h3 class="chart-title">Belief Trajectories (95% CI)</h3>
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
}
.chart-container {
  overflow-x: auto;
}
</style>
