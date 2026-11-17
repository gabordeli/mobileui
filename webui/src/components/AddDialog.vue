<script setup lang="ts">
import { onMounted, ref } from "vue";

import * as api from "../api";
import { t } from "../i18n";
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
const closeButton = ref<HTMLButtonElement | null>(null);

onMounted(() => closeButton.value?.focus());

function pickFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  file.value = input.files?.[0] ?? null;
}

async function submit(): Promise<void> {
  error.value = "";
  if (mode.value === "magnet" && !magnet.value.trim()) {
    error.value = t("add.needMagnet");
    return;
  }
  if (mode.value === "file" && !file.value) {
    error.value = t("add.needFile");
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
    emit("toast", t("toast.added"));
    emit("close");
  } catch (err) {
    error.value = err instanceof Error ? err.message : t("add.error");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="sheet-backdrop" @click.self="emit('close')">
      <section
        class="sheet add-sheet"
        role="dialog"
        aria-modal="true"
        :aria-label="t('add.title')"
        @keydown.esc="emit('close')"
      >
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>{{ t("add.title") }}</h2>
            <p>{{ t("add.subtitle") }}</p>
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

        <div class="segmented" role="tablist" :aria-label="t('add.title')">
          <button
            class="segment"
            :class="{ active: mode === 'magnet' }"
            role="tab"
            :aria-selected="mode === 'magnet'"
            @click="mode = 'magnet'"
          >
            {{ t("add.magnetTab") }}
          </button>
          <button
            class="segment"
            :class="{ active: mode === 'file' }"
            role="tab"
            :aria-selected="mode === 'file'"
            @click="mode = 'file'"
          >
            {{ t("add.fileTab") }}
          </button>
        </div>

        <div class="add-form">
          <label v-if="mode === 'magnet'" class="field">
            <span>{{ t("add.magnet") }}</span>
            <textarea
              v-model="magnet"
              rows="3"
              :placeholder="t('add.magnetPlaceholder')"
              spellcheck="false"
            />
          </label>
          <label v-else class="field">
            <span>{{ t("add.file") }}</span>
            <input type="file" accept=".torrent,application/x-bittorrent" @change="pickFile" />
            <small v-if="file">
              {{ t("add.fileHint", { name: file.name, size: Math.ceil(file.size / 1024) }) }}
            </small>
          </label>

          <label class="field">
            <span>{{ t("add.label") }}</span>
            <select v-model="label">
              <option value="">{{ t("add.noLabel") }}</option>
              <option v-for="item in labels" :key="item.id" :value="item.id">
                {{ item.id }} ({{ item.count }})
              </option>
              <option v-if="noLabelCount > 0" value="No Label">
                {{ t("add.noLabel") }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>{{ t("add.path") }}</span>
            <input
              v-model="downloadLocation"
              type="text"
              placeholder="/mnt/…"
              autocapitalize="off"
              spellcheck="false"
            />
            <small>{{ t("add.pathHint") }}</small>
          </label>

          <label class="checkbox">
            <input v-model="addPaused" type="checkbox" />
            <span>{{ t("add.paused") }}</span>
          </label>
        </div>

        <p v-if="error" class="gate-error" role="alert">{{ error }}</p>

        <div class="add-actions">
          <button class="action" :disabled="loading" @click="emit('close')">
            {{ t("add.cancel") }}
          </button>
          <button class="action primary" :disabled="loading" @click="submit">
            {{ loading ? t("add.submitting") : t("add.submit") }}
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>
