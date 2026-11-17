<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ down: number[]; up: number[] }>();

const WIDTH = 100;
const HEIGHT = 30;

function line(values: number[]): string {
  if (!values.length) return "";
  const max = Math.max(1, ...props.down, ...props.up);
  const y = (value: number): string => (HEIGHT - (value / max) * HEIGHT).toFixed(2);
  if (values.length === 1) return `0,${y(values[0])} ${WIDTH},${y(values[0])}`;
  const step = WIDTH / (values.length - 1);
  return values
    .map((value, index) => `${(index * step).toFixed(2)},${y(value)}`)
    .join(" ");
}

const downPoints = computed(() => line(props.down));
const upPoints = computed(() => line(props.up));
</script>

<template>
  <svg
    class="sparkline"
    viewBox="0 0 100 30"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <line
      x1="0"
      y1="29"
      x2="100"
      y2="29"
      class="spark-base"
      vector-effect="non-scaling-stroke"
    />
    <polyline
      v-if="downPoints"
      :points="downPoints"
      class="spark-down"
      vector-effect="non-scaling-stroke"
    />
    <polyline
      v-if="upPoints"
      :points="upPoints"
      class="spark-up"
      vector-effect="non-scaling-stroke"
    />
  </svg>
</template>
