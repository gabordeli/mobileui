<script setup lang="ts">
import { computed, onBeforeUnmount } from "vue";

import {
  formatBytes,
  formatEta,
  formatRatio,
  formatRate,
  stateClass,
} from "../format";
import { stateLabel, t } from "../i18n";
import type { Torrent } from "../types";

const props = defineProps<{
  torrent: Torrent;
  selected: boolean;
  selectionMode: boolean;
}>();
const emit = defineEmits<{
  longPress: [torrent: Torrent];
  select: [torrent: Torrent];
}>();

let timer: ReturnType<typeof setTimeout> | null = null;
let startX = 0;
let startY = 0;
let moved = false;
let longPressed = false;

const progress = computed(() => Math.max(0, Math.min(100, props.torrent.progress)));
const paused = computed(() => props.torrent.state.includes("Paused"));
const isError = computed(
  () =>
    props.torrent.state === "Error" ||
    (!!props.torrent.message && props.torrent.message !== "OK"),
);

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
  moved = false;
  longPressed = false;
  clearTimer();
  timer = setTimeout(() => {
    timer = null;
    longPressed = true;
    if ("vibrate" in navigator) {
      navigator.vibrate(10);
    }
    emit("longPress", props.torrent);
  }, 500);
}

function onPointerMove(event: PointerEvent): void {
  if (Math.abs(event.clientX - startX) > 10 || Math.abs(event.clientY - startY) > 10) {
    moved = true;
    clearTimer();
  }
}

function onClick(): void {
  if (longPressed || moved) {
    longPressed = false;
    moved = false;
    return;
  }
  emit("select", props.torrent);
}

onBeforeUnmount(clearTimer);
</script>

<template>
  <button
    type="button"
    class="torrent-row"
    :class="{ selected, error: isError }"
    :aria-label="torrent.name"
    :aria-pressed="selectionMode ? selected : undefined"
    :aria-haspopup="selectionMode ? undefined : 'dialog'"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="clearTimer"
    @pointercancel="clearTimer"
    @pointerleave="clearTimer"
    @click="onClick"
    @contextmenu.prevent
  >
    <span class="row-top">
      <span
        v-if="selectionMode"
        class="row-check"
        :class="{ on: selected }"
        aria-hidden="true"
      >{{ selected ? "✓" : "" }}</span>
      <span class="row-title" :title="torrent.name">{{ torrent.name }}</span>
      <span class="row-progress">{{ progress.toFixed(1) }}%</span>
    </span>
    <span class="row-meta">
      <span class="state-pill" :class="stateClass(torrent.state)">
        {{ stateLabel(torrent.state) }}
      </span>
      <span v-if="isError" class="row-error" :title="torrent.message">
        {{ t("row.error") }}
      </span>
      <span class="label-pill">{{ torrent.label }}</span>
      <span>{{ formatBytes(torrent.total_size) }}</span>
      <span>{{ t("row.ratio", { value: formatRatio(torrent.ratio) }) }}</span>
      <span v-if="!paused">ETA {{ formatEta(torrent.eta) }}</span>
    </span>
    <span class="row-rates">
      <span class="down">↓ {{ formatRate(torrent.download_payload_rate) }}</span>
      <span class="up">↑ {{ formatRate(torrent.upload_payload_rate) }}</span>
    </span>
    <span class="progress-track" aria-hidden="true">
      <span
        class="progress-fill"
        :class="{ complete: progress >= 100 }"
        :style="{ width: `${progress}%` }"
      />
    </span>
  </button>
</template>
