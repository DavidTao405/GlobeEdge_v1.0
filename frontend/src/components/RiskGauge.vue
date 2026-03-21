<script setup lang="ts">
/**
 * RiskGauge — D3 弧形儀表板。
 *
 * 顯示 distance_to_tipping 數字 + 顏色
 * green (normal) → yellow (warning) → orange (high) → red (critical)
 */
import { ref, computed, onMounted, watch } from 'vue'
import * as d3 from 'd3'

const props = withDefaults(defineProps<{
  value: number       // lambda_max [0, 1]
  label?: string
}>(), {
  label: 'λ_max',
})

const svgRef = ref<SVGSVGElement | null>(null)

const distance = computed(() => Math.max(0, 1 - props.value))
const riskColor = computed(() => {
  const d = distance.value
  if (d < 0.05) return '#ef4444'   // red
  if (d < 0.15) return '#f97316'   // orange
  if (d < 0.30) return '#eab308'   // yellow
  return '#22c55e'                  // green
})
const riskLabel = computed(() => {
  const d = distance.value
  if (d < 0.05) return 'CRITICAL'
  if (d < 0.15) return 'HIGH'
  if (d < 0.30) return 'WARNING'
  return 'NORMAL'
})

function draw() {
  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const w = 200, h = 130
  const cx = w / 2, cy = h - 10
  const r = 80
  const tau = Math.PI

  // Background arc
  const bgArc = d3.arc<any, d3.DefaultArcObject>()
    .innerRadius(r - 16)
    .outerRadius(r)
    .startAngle(-tau / 2)
    .endAngle(tau / 2)
    .cornerRadius(8)

  // Value arc
  const angle = -tau / 2 + (props.value * tau)
  const valArc = d3.arc<any, d3.DefaultArcObject>()
    .innerRadius(r - 16)
    .outerRadius(r)
    .startAngle(-tau / 2)
    .endAngle(angle)
    .cornerRadius(8)

  const g = svg.append('g').attr('transform', `translate(${cx},${cy})`)

  // Background
  g.append('path')
    .attr('d', bgArc({} as any))
    .attr('fill', 'var(--gauge-bg, #374151)')

  // Value
  g.append('path')
    .attr('d', valArc({} as any))
    .attr('fill', riskColor.value)
    .style('transition', 'fill 0.3s')

  // Center text
  g.append('text')
    .attr('text-anchor', 'middle')
    .attr('y', -20)
    .attr('class', 'gauge-value')
    .text(props.value.toFixed(3))

  g.append('text')
    .attr('text-anchor', 'middle')
    .attr('y', -2)
    .attr('class', 'gauge-label')
    .text(props.label)
}

onMounted(draw)
watch(() => props.value, draw)
</script>

<template>
  <div class="risk-gauge">
    <svg ref="svgRef" viewBox="0 0 200 130" width="200" height="130" />
    <div class="risk-badge" :style="{ background: riskColor }">
      {{ riskLabel }}
    </div>
    <div class="risk-distance">
      Distance to tipping: <strong>{{ distance.toFixed(3) }}</strong>
    </div>
  </div>
</template>

<style scoped>
.risk-gauge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
:deep(.gauge-value) {
  font-size: 22px;
  font-weight: 700;
  fill: var(--text-primary, #f9fafb);
  font-family: 'IBM Plex Mono', monospace;
}
:deep(.gauge-label) {
  font-size: 11px;
  fill: var(--text-secondary, #9ca3af);
  font-family: 'IBM Plex Sans', sans-serif;
}
.risk-badge {
  padding: 2px 12px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  letter-spacing: 0.05em;
}
.risk-distance {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
}
</style>
