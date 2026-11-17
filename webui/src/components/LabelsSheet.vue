<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

import { trapFocus } from "../focus";
import { t } from "../i18n";
import type { LabelInfo } from "../types";

defineProps<{ labels: LabelInfo[]; canWrite: boolean }>();
const emit = defineEmits<{
  close: [];
  add: [id: string];
  remove: [id: string];
}>();

const newLabel = ref("");
const dialogEl = ref<HTMLElement | null>(null);
let releaseFocus: (() => void) | null = null;

onMounted(() => {
  if (dialogEl.value) releaseFocus = trapFocus(dialogEl.value);
});
onBeforeUnmount(() => releaseFocus?.());

function add(): void {
  const id = newLabel.value.trim();
  if (!id) return;
  emit("add", id);
  newLabel.value = "";
}

function remove(id: string): void {
  if (confirm(t("labels.confirmRemove", { name: id }))) {
    emit("remove", id);
  }
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
        class="sheet"
        aria-modal="true"
        :aria-label="t('labels.title')"
        @keydown.esc="emit('close')"
      >
        <div class="sheet-handle" aria-hidden="true" />
        <header class="sheet-head">
          <div>
            <h2>{{ t("labels.title") }}</h2>
            <p>{{ t("labels.subtitle") }}</p>
          </div>
          <button
            class="icon-button"
            :aria-label="t('sheet.close')"
            @click="emit('close')"
          >
            ✕
          </button>
        </header>

        <ul v-if="labels.length" class="label-list">
          <li v-for="item in labels" :key="item.id">
            <span class="label-name">{{ item.id }}</span>
            <span class="label-count">{{ item.count }}</span>
            <button
              v-if="canWrite"
              class="action danger compact"
              @click="remove(item.id)"
            >
              {{ t("labels.remove") }}
            </button>
          </li>
        </ul>
        <p v-else class="files-empty">{{ t("labels.empty") }}</p>

        <div v-if="canWrite" class="label-add">
          <input
            v-model="newLabel"
            type="text"
            :placeholder="t('labels.newPlaceholder')"
            :aria-label="t('labels.newPlaceholder')"
            autocapitalize="off"
            spellcheck="false"
            @keydown.enter.prevent="add"
          />
          <button class="action primary" :disabled="!newLabel.trim()" @click="add">
            {{ t("labels.add") }}
          </button>
        </div>
        <p v-else class="readonly-note">{{ t("auth.readonly") }}</p>
      </dialog>
    </div>
  </Teleport>
</template>
