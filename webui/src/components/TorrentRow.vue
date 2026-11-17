<script setup lang="ts">
import { computed, onBeforeUnmount } from "vue";

import {
  formatBytes,
  formatEta,
  formatRatio,
  formatRate,
  stateClass,
} from "../format";
import type { Torrent } from "../types";

const props = defineProps<{ torrent: Torrent }>();
const emit = defineEmits<{ longPress: [torrent: Torrent] }>();

let timer: ReturnType<typeof setTimeout> | null = null;
let startX = 0;
let startY = 0;

const progress = computed(() => Math.max(0, Math.min(100, props.torrent.progress)));
const paused = computed(() => props.torrent.state.includes("Paused"));

function clearTimer(): void {
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
}

function onPointerDown(event: PointerEvent): void {
  if (event.button !== 0) return;
  startX = event.clientX;
  startY = event.clientY;
  clearTimer();
  timer = setTimeout(() => {
    timer = null;
    if ("vibrate" in navigator) {
      navigator.vibrate(10);
    }
    emit("longPress", props.torrent);
  }, 500);
}

function onPointerMove(event: PointerEvent): void {
  if (Math.abs(event.clientX - startX) > 10 || Math.abs(event.clientY - startY) > 10) {
    clearTimer();
  }
}

onBeforeUnmount(clearTimer);
</script>

<template>
  <article
    class="torrent-row"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="clearTimer"
    @pointercancel="clearTimer"
    @pointerleave="clearTimer"
    @contextmenu.prevent
  >
    <div class="row-top">
      <div class="row-title" :title="torrent.name">{{ torrent.name }}</div>
      <div class="row-progress">{{ progress.toFixed(1) }}%</div>
    </div>
    <div class="row-meta">
      <span class="state-pill" :class="stateClass(torrent.state)">
        {{ torrent.state }}
      </span>
      <span class="label-pill">{{ torrent.label }}</span>
      <span>{{ formatBytes(torrent.total_size) }}</span>
      <span>ratio {{ formatRatio(torrent.ratio) }}</span>
      <span v-if="!paused">ETA {{ formatEta(torrent.eta) }}</span>
    </div>
    <div class="row-rates">
      <span class="down">↓ {{ formatRate(torrent.download_payload_rate) }}</span>
      <span class="up">↑ {{ formatRate(torrent.upload_payload_rate) }}</span>
    </div>
    <div class="progress-track" aria-hidden="true">
      <div
        class="progress-fill"
        :class="{ complete: progress >= 100 }"
        :style="{ width: `${progress}%` }"
      />
    </div>
  </article>
</template>
