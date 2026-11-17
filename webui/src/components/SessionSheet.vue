<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { formatBytes, formatRate } from "../format";
import { t } from "../i18n";
import type { Session } from "../types";

const props = defineProps<{
  session: Session;
  canWrite: boolean;
}>();
const emit = defineEmits<{ close: []; toggle: [] }>();

const closeButton = ref<HTMLButtonElement | null>(null);
const freeSpace = computed(() =>
  props.session.free_space === null ? "—" : formatBytes(props.session.free_space),
);

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
