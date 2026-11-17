<script setup lang="ts">
import { ref } from "vue";

import * as api from "../api";
import type { LabelInfo } from "../types";

const props = defineProps<{
  labels: LabelInfo[];
  noLabelCount: number;
  defaultPath: string;
}>();
const emit = defineEmits<{
  close: [];
  added: [result: { id: string }];
  toast: [message: string];
}>();

const mode = ref<"magnet" | "file">("magnet");
const magnet = ref("");
const file = ref<File | null>(null);
const label = ref("");
const downloadLocation = ref(props.defaultPath);
const addPaused = ref(false);
const loading = ref(false);
const error = ref("");

function pickFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

async function submit(): Promise<void> {
  error.value = "";
  if (mode.value === "magnet" && !magnet.value.trim()) {
    error.value = "Adj meg egy magnet linket.";
    return;
  }
  if (mode.value === "file" && !file.value) {
    error.value = "Válassz egy .torrent fájlt.";
    return;
  }

  loading.value = true;
  const options: api.AddTorrentOptions = {
    label: label.value || undefined,
    download_location: downloadLocation.value.trim() || undefined,
    add_paused: addPaused.value,
  };
  try {
    const result =
      mode.value === "magnet"
        ? await api.addTorrentMagnet(magnet.value.trim(), options)
        : await api.addTorrentFile(file.value as File, options);
    emit("added", result);
    emit("toast", "Torrent hozzáadva");
    emit("close");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Hiba a hozzáadásnál";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="sheet-backdrop" @click.self="emit('close')">
      <section class="sheet add-sheet" role="dialog" aria-modal="true" aria-label="Torrent hozzáadása">
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>Torrent hozzáadása</h2>
            <p>Magnet link vagy .torrent fájl</p>
          </div>
          <button class="icon-button" aria-label="Bezárás" @click="emit('close')">✕</button>
        </header>

        <div class="segmented" role="tablist" aria-label="Hozzáadás módja">
          <button
            class="segment"
            :class="{ active: mode === 'magnet' }"
            role="tab"
            :aria-selected="mode === 'magnet'"
            @click="mode = 'magnet'"
          >
            Magnet
          </button>
          <button
            class="segment"
            :class="{ active: mode === 'file' }"
            role="tab"
            :aria-selected="mode === 'file'"
            @click="mode = 'file'"
          >
            .torrent fájl
          </button>
        </div>

        <div class="add-form">
          <label v-if="mode === 'magnet'" class="field">
            <span>Magnet link</span>
            <textarea
              v-model="magnet"
              rows="3"
              placeholder="magnet:?xt=urn:btih:…"
              spellcheck="false"
            />
          </label>
          <label v-else class="field">
            <span>Torrent fájl</span>
            <input type="file" accept=".torrent,application/x-bittorrent" @change="pickFile" />
            <small v-if="file">{{ file.name }} · {{ Math.ceil(file.size / 1024) }} KiB</small>
          </label>

          <label class="field">
            <span>Label</span>
            <select v-model="label">
              <option value="">Nincs label</option>
              <option v-for="item in labels" :key="item.id" :value="item.id">
                {{ item.id }} ({{ item.count }})
              </option>
              <option v-if="noLabelCount > 0" value="No Label">No Label</option>
            </select>
          </label>

          <label class="field">
            <span>Mentési útvonal</span>
            <input
              v-model="downloadLocation"
              type="text"
              placeholder="/mnt/…"
              autocapitalize="off"
              spellcheck="false"
            />
            <small>Abszolút út; üresen a Deluge alapértéke.</small>
          </label>

          <label class="checkbox">
            <input v-model="addPaused" type="checkbox" />
            <span>Szünetelve induljon</span>
          </label>
        </div>

        <p v-if="error" class="gate-error" role="alert">{{ error }}</p>

        <div class="add-actions">
          <button class="action" :disabled="loading" @click="emit('close')">Mégse</button>
          <button class="action primary" :disabled="loading" @click="submit">
            {{ loading ? "Hozzáadás…" : "Hozzáadás" }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
