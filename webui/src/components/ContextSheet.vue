<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { stateLabel, t } from "../i18n";
import type { ActionPayload, LabelInfo, Torrent } from "../types";

const props = defineProps<{
  torrent: Torrent;
  labels: LabelInfo[];
  noLabelCount: number;
  canWrite: boolean;
}>();
const emit = defineEmits<{
  close: [];
  action: [payload: ActionPayload];
}>();

const selectedLabel = ref(props.torrent.label);
const removeData = ref(false);
const closeButton = ref<HTMLButtonElement | null>(null);

const isPaused = computed(() => props.torrent.state.includes("Paused"));
const labelOptions = computed(() => {
  const options = props.labels.map((label) => label.id);
  if (props.noLabelCount > 0 || props.torrent.label === "No Label") {
    options.push("No Label");
  }
  return options;
});

function queue(action: string): void {
  emit("action", { kind: "queue", action });
}

function applyLabel(): void {
  emit("action", { kind: "label", label: selectedLabel.value });
}

function remove(): void {
  if (!confirm(t("sheet.confirmRemove", { name: props.torrent.name }))) return;
  emit("action", { kind: "remove", remove_data: removeData.value });
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
        :aria-label="t('sheet.title')"
        @keydown.esc="emit('close')"
      >
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>{{ torrent.name }}</h2>
            <p>
              {{ stateLabel(torrent.state) }} · {{ torrent.label }} ·
              {{ torrent.progress.toFixed(1) }}%
            </p>
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

        <div v-if="canWrite" class="sheet-actions">
          <button
            class="action primary"
            @click="emit('action', { kind: isPaused ? 'resume' : 'pause' })"
          >
            {{ isPaused ? t("sheet.resume") : t("sheet.pause") }}
          </button>
          <div class="queue-grid">
            <button class="action" @click="queue('top')">{{ t("sheet.top") }}</button>
            <button class="action" @click="queue('up')">{{ t("sheet.up") }}</button>
            <button class="action" @click="queue('down')">{{ t("sheet.down") }}</button>
            <button class="action" @click="queue('bottom')">{{ t("sheet.bottom") }}</button>
          </div>
          <label class="field">
            <span>{{ t("sheet.label") }}</span>
            <div class="inline-field">
              <select v-model="selectedLabel">
                <option v-for="label in labelOptions" :key="label" :value="label">
                  {{ label }}
                </option>
              </select>
              <button class="action" @click="applyLabel">{{ t("sheet.save") }}</button>
            </div>
          </label>
          <label class="checkbox">
            <input v-model="removeData" type="checkbox" />
            <span>{{ t("sheet.removeData") }}</span>
          </label>
          <button class="action danger" @click="remove">{{ t("sheet.remove") }}</button>
        </div>
        <p v-else class="readonly-note">{{ t("auth.readonly") }}</p>
      </section>
    </div>
  </Teleport>
</template>
