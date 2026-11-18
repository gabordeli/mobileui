<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

import * as api from "../api";
import { trapFocus } from "../focus";
import { t } from "../i18n";
import type { DirListing } from "../types";

const props = defineProps<{
  initialPath: string;
}>();

const emit = defineEmits<{
  close: [];
  select: [path: string];
}>();

const listing = ref<DirListing | null>(null);
const loading = ref(true);
const error = ref("");
const closeButton = ref<HTMLButtonElement | null>(null);
const dialogEl = ref<HTMLElement | null>(null);
let releaseFocus: (() => void) | null = null;

async function load(path: string): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    listing.value = await api.listDirs(path);
  } catch (err) {
    error.value = err instanceof Error ? err.message : t("fs.error");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  closeButton.value?.focus();
  if (dialogEl.value) releaseFocus = trapFocus(dialogEl.value);
  void load(props.initialPath || "/");
});
onBeforeUnmount(() => releaseFocus?.());

function goUp(): void {
  if (listing.value?.parent) void load(listing.value.parent);
}
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
        class="sheet fs-sheet"
        aria-modal="true"
        :aria-label="t('fs.title')"
        @keydown.esc="emit('close')"
      >
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div class="fs-head">
            <h2>{{ t("fs.title") }}</h2>
            <p class="fs-path" :title="listing?.path">
              {{ listing?.path || "…" }}
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

        <div class="fs-tools">
          <button
            class="action"
            type="button"
            :disabled="!listing?.parent || loading"
            @click="goUp"
          >
            ↑ {{ t("fs.up") }}
          </button>
          <button
            class="action"
            type="button"
            :disabled="loading || !listing"
            @click="listing && load(listing.path)"
          >
            {{ t("fs.refresh") }}
          </button>
        </div>

        <div class="fs-body">
          <p v-if="loading && !listing" class="limits-hint">
            {{ t("fs.loading") }}
          </p>
          <p v-else-if="error" class="gate-error" role="alert">{{ error }}</p>
          <p
            v-else-if="listing && !listing.dirs.length"
            class="limits-hint"
          >
            {{ t("fs.empty") }}
          </p>
          <ul v-else-if="listing" class="fs-list">
            <li v-for="dir in listing.dirs" :key="dir.path">
              <button class="fs-row" type="button" @click="load(dir.path)">
                <span class="fs-icon" aria-hidden="true">📁</span>
                <span class="fs-name">{{ dir.name }}</span>
                <span v-if="!dir.writable" class="fs-lock">
                  {{ t("fs.locked") }}
                </span>
                <span class="fs-chevron" aria-hidden="true">›</span>
              </button>
            </li>
          </ul>
          <p v-if="listing?.truncated" class="limits-hint">
            {{ t("fs.truncated") }}
          </p>
          <p v-if="listing && !listing.writable" class="limits-hint">
            {{ t("fs.notWritable") }}
          </p>
        </div>

        <div class="add-actions">
          <button class="action" type="button" @click="emit('close')">
            {{ t("fs.cancel") }}
          </button>
          <button
            class="action primary"
            type="button"
            :disabled="!listing || !listing.writable || loading"
            @click="listing && emit('select', listing.path)"
          >
            {{ t("fs.select") }}
          </button>
        </div>
      </dialog>
    </div>
  </Teleport>
</template>
