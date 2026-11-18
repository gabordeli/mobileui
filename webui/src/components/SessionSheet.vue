<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { trapFocus } from "../focus";
import { formatBytes, formatRate } from "../format";
import { t } from "../i18n";
import type { LimitPayload, QueueSettings, Session } from "../types";
import PushToggle from "./PushToggle.vue";
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
  queue: [payload: Partial<QueueSettings>];
}>();

const closeButton = ref<HTMLButtonElement | null>(null);
const dialogEl = ref<HTMLElement | null>(null);
let releaseFocus: (() => void) | null = null;
const downLimit = ref(props.session.max_download_speed);
const upLimit = ref(props.session.max_upload_speed);
const queueDown = ref(props.session.queue.max_active_downloading);
const queueSeed = ref(props.session.queue.max_active_seeding);
const queueTotal = ref(props.session.queue.max_active_limit);
const queueTop = ref(props.session.queue.queue_new_to_top);
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

function applyQueue(): void {
  emit("queue", {
    max_active_downloading: Number(queueDown.value),
    max_active_seeding: Number(queueSeed.value),
    max_active_limit: Number(queueTotal.value),
    queue_new_to_top: queueTop.value,
  });
}

onMounted(() => {
  closeButton.value?.focus();
  if (dialogEl.value) releaseFocus = trapFocus(dialogEl.value);
});
onBeforeUnmount(() => releaseFocus?.());
</script>

<template>
  <Teleport to="body">
    <div
      class="sheet-backdrop"
      tabindex="-1"
      @click.self="emit('close')"
      @keydown.esc="emit('close')"
    >
      <dialog
        ref="dialogEl"
        open
        class="sheet"
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

        <div v-if="canWrite" class="limits">
          <h3>{{ t("queue.title") }}</h3>
          <div class="limits-row queue-row">
            <label>
              <span>{{ t("queue.downloading") }}</span>
              <input v-model.number="queueDown" type="number" min="-1" max="9999" step="1" />
            </label>
            <label>
              <span>{{ t("queue.seeding") }}</span>
              <input v-model.number="queueSeed" type="number" min="-1" max="9999" step="1" />
            </label>
            <label>
              <span>{{ t("queue.total") }}</span>
              <input v-model.number="queueTotal" type="number" min="-1" max="9999" step="1" />
            </label>
          </div>
          <label class="queue-top">
            <input v-model="queueTop" type="checkbox" />
            <span>{{ t("queue.newToTop") }}</span>
          </label>
          <div class="limits-actions">
            <button class="action primary" @click="applyQueue">
              {{ t("sheet.save") }}
            </button>
          </div>
          <p class="limits-hint">{{ t("queue.hint") }}</p>
        </div>

        <PushToggle />

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
      </dialog>
    </div>
  </Teleport>
</template>
