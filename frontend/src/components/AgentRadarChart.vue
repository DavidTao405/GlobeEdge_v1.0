<script setup lang="ts">
/**
 * AgentRadarChart — D3 雷達圖顯示 Agent 的 8 維信念向量。
 */
import { ref, watch, onMounted } from 'vue'
import * as d3 from 'd3'

const props = defineProps<{
  values: number[]
  labels: string[]
  size?: number
}>()

const svgRef = ref<SVGSVGElement | null>(null)

function draw() {
  if (!svgRef.value || !props.values.length) return

  const svg = d3.select(svgRef.value)
  svg.selectAll('*').remove()

  const size = props.size || 200
  const cx = size / 2
  const cy = size / 2
  const r = size / 2 - 30
  const n = props.values.length
  const angle = (2 * Math.PI) / n

  // Grid circles
  const levels = [0.25, 0.5, 0.75, 1.0]
  levels.forEach(lev => {
    svg.append('circle')
      .attr('cx', cx).attr('cy', cy)
      .attr('r', r * lev)
      .attr('fill', 'none')
      .attr('stroke', '#374151')
      .attr('stroke-width', 0.5)
  })

  // Zero circle (maps to value 0, since range is -1 to 1, 0 is at 0.5*r)
  svg.append('circle')
    .attr('cx', cx).attr('cy', cy)
    .attr('r', r * 0.5)
    .attr('fill', 'none')
    .attr('stroke', '#4b5563')
    .attr('stroke-width', 1)
    .attr('stroke-dasharray', '4,3')

  // Axes
  for (let i = 0; i < n; i++) {
    const a = angle * i - Math.PI / 2
    const x = cx + r * Math.cos(a)
    const y = cy + r * Math.sin(a)
    svg.append('line')
      .attr('x1', cx).attr('y1', cy)
      .attr('x2', x).attr('y2', y)
      .attr('stroke', '#374151')
      .attr('stroke-width', 0.5)

    // Label
    const lx = cx + (r + 18) * Math.cos(a)
    const ly = cy + (r + 18) * Math.sin(a)
    svg.append('text')
      .attr('x', lx).attr('y', ly)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('fill', '#9ca3af')
      .attr('font-size', 9)
      .text(props.labels[i]?.slice(0, 4) || `d${i}`)
  }

  // Data polygon (map -1..1 to 0..1 for radius)
  const points = props.values.map((v, i) => {
    const norm = (v + 1) / 2 // -1→0, 0→0.5, 1→1
    const a = angle * i - Math.PI / 2
    return [
      cx + r * norm * Math.cos(a),
      cy + r * norm * Math.sin(a),
    ]
  })

  // Fill
  svg.append('polygon')
    .attr('points', points.map(p => p.join(',')).join(' '))
    .attr('fill', 'rgba(59, 130, 246, 0.15)')
    .attr('stroke', '#3b82f6')
    .attr('stroke-width', 1.5)

  // Dots
  points.forEach(([x, y]) => {
    svg.append('circle')
      .attr('cx', x).attr('cy', y)
      .attr('r', 3)
      .attr('fill', '#3b82f6')
  })
}

onMounted(draw)
watch(() => [props.values, props.labels], draw, { deep: true })
</script>

<template>
  <svg ref="svgRef" :width="size || 200" :height="size || 200" />
</template>
