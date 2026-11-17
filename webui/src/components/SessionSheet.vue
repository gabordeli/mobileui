<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { formatBytes, formatRate } from "../format";
import { t } from "../i18n";
import type { LimitPayload, Session } from "../types";
import Sparkline from "./Sparkline.vue";

const props = defineProps<{
  session: Session;
  canWrite: boolean;
  downHistory: number[];
  upHistory: number[];
}>();
const emit = defineEmits<{
  close: [];
  toggle: [];
  limits: [payload: LimitPayload];
}>();

const closeButton = ref<HTMLButtonElement | null>(null);
const downLimit = ref(props.session.max_download_speed);
const upLimit = ref(props.session.max_upload_speed);
const freeSpace = computed(() =>
  props.session.free_space === null ? "—" : formatBytes(props.session.free_space),
);

function applyLimits(): void {
  emit("limits", {
    max_download_speed: Number(downLimit.value),
    max_upload_speed: Number(upLimit.value),
  });
}

function nightMode(): void {
  downLimit.value = 512;
  upLimit.value = 128;
  applyLimits();
}

function unlimited(): void {
  downLimit.value = -1;
  upLimit.value = -1;
  applyLimits();
}

onMounted(() => closeButton.value?.focus());
</script>

<template>
  <Teleport to="body">
    <div class="sheet-backdrop" @click.self="emit('close')">
      <section
        class="sheet"
        role="dialog"
        aria-modal="true"
        :aria-label="t('session.title')"
        @keydown.esc="emit('close')"
      >
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>{{ t("session.title") }}</h2>
            <p>{{ session.paused ? t("session.paused") : t("session.running") }}</p>
          </div>
          <button
            ref="closeButton"
            class="icon-button"
            :aria-label="t('sheet.close')"
            @click="emit('close')"
          >
            ✕
          </button>
        </header>

        <div class="stats-grid">
          <div>
            <span>{{ t("session.freeSpace") }}</span>
            <strong>{{ freeSpace }}</strong>
          </div>
          <div>
            <span>{{ t("session.torrents") }}</span>
            <strong>{{ session.num_torrents }}</strong>
          </div>
          <div>
            <span>{{ t("session.download") }}</span>
            <strong class="down">{{ formatRate(session.payload_download_rate) }}</strong>
          </div>
          <div>
            <span>{{ t("session.upload") }}</span>
            <strong class="up">{{ formatRate(session.payload_upload_rate) }}</strong>
          </div>
        </div>

        <div class="sparkline-wrap">
          <Sparkline :down="downHistory" :up="upHistory" />
          <span>{{ t("session.history") }}</span>
        </div>

        <div v-if="canWrite" class="limits">
          <h3>{{ t("limits.title") }}</h3>
          <div class="limits-row">
            <label>
              <span>↓ {{ t("limits.download") }}</span>
              <input v-model.number="downLimit" type="number" min="-1" step="1" />
            </label>
            <label>
              <span>↑ {{ t("limits.upload") }}</span>
              <input v-model.number="upLimit" type="number" min="-1" step="1" />
            </label>
          </div>
          <div class="limits-actions">
            <button class="action primary" @click="applyLimits">
              {{ t("sheet.save") }}
            </button>
            <button class="action" @click="nightMode">{{ t("limits.night") }}</button>
            <button class="action" @click="unlimited">{{ t("limits.unlimited") }}</button>
          </div>
          <p class="limits-hint">{{ t("limits.hint") }}</p>
        </div>

        <div v-if="canWrite" class="sheet-actions">
          <button
            class="action"
            :class="{ primary: session.paused }"
            @click="emit('toggle')"
          >
            {{ session.paused ? t("session.resume") : t("session.pause") }}
          </button>
        </div>
        <p v-else class="readonly-note">{{ t("auth.readonly") }}</p>
      </section>
    </div>
  </Teleport>
</template>
