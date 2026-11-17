<script setup lang="ts">
import { computed, ref } from "vue";

import type { ActionPayload, LabelInfo, Torrent } from "../types";

const props = defineProps<{
  torrent: Torrent;
  labels: LabelInfo[];
  noLabelCount: number;
}>();
const emit = defineEmits<{
  close: [];
  action: [payload: ActionPayload];
}>();

const selectedLabel = ref(props.torrent.label);
const removeData = ref(false);

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
  if (!confirm(`Eltávolítod: ${props.torrent.name}?`)) return;
  emit("action", { kind: "remove", remove_data: removeData.value });
}
</script>

<template>
  <Teleport to="body">
    <div class="sheet-backdrop" @click.self="emit('close')">
      <section class="sheet" role="dialog" aria-modal="true" aria-label="Torrent műveletek">
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>{{ torrent.name }}</h2>
            <p>{{ torrent.state }} · {{ torrent.label }} · {{ torrent.progress.toFixed(1) }}%</p>
          </div>
          <button class="icon-button" aria-label="Bezárás" @click="emit('close')">✕</button>
        </header>

        <div class="sheet-actions">
          <button
            class="action primary"
            @click="emit('action', { kind: isPaused ? 'resume' : 'pause' })"
          >
            {{ isPaused ? "Folytatás" : "Szüneteltetés" }}
          </button>
          <div class="queue-grid">
            <button class="action" @click="queue('top')">Legfelülre</button>
            <button class="action" @click="queue('up')">Fel</button>
            <button class="action" @click="queue('down')">Le</button>
            <button class="action" @click="queue('bottom')">Legalulra</button>
          </div>
          <label class="field">
            <span>Label</span>
            <div class="inline-field">
              <select v-model="selectedLabel">
                <option v-for="label in labelOptions" :key="label" :value="label">
                  {{ label }}
                </option>
              </select>
              <button class="action" @click="applyLabel">Mentés</button>
            </div>
          </label>
          <label class="checkbox">
            <input v-model="removeData" type="checkbox" />
            <span>Letöltött adatok törlése is</span>
          </label>
          <button class="action danger" @click="remove">Eltávolítás</button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
