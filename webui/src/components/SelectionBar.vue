<script setup lang="ts">
import { ref } from "vue";

import { t } from "../i18n";
import type { LabelInfo } from "../types";

const props = defineProps<{
  count: number;
  busy: boolean;
  canWrite: boolean;
  labels: LabelInfo[];
}>();
const emit = defineEmits<{
  close: [];
  selectAll: [];
  action: [
    payload:
      | { kind: "pause" | "resume" | "remove" }
      | { kind: "label"; label: string },
  ];
}>();

const labelOpen = ref(false);
const label = ref("");

function remove(): void {
  if (confirm(t("bulk.confirmRemove", { count: props.count }))) {
    emit("action", { kind: "remove" });
  }
}

function applyLabel(): void {
  if (!label.value) return;
  emit("action", { kind: "label", label: label.value });
  labelOpen.value = false;
}
</script>

<template>
  <section class="selection-bar" :aria-label="t('bulk.title')">
    <div class="selection-head">
      <button
        class="icon-button"
        :aria-label="t('bulk.cancel')"
        @click="emit('close')"
      >
        ✕
      </button>
      <strong>{{ t("bulk.selected", { count }) }}</strong>
      <button class="action compact" :disabled="busy" @click="emit('selectAll')">
        {{ t("bulk.all") }}
      </button>
    </div>

    <div v-if="canWrite" class="selection-actions">
      <button class="action" :disabled="busy" @click="emit('action', { kind: 'pause' })">
        {{ t("bulk.pause") }}
      </button>
      <button class="action" :disabled="busy" @click="emit('action', { kind: 'resume' })">
        {{ t("bulk.resume") }}
      </button>
      <button class="action" :disabled="busy" @click="labelOpen = !labelOpen">
        {{ t("bulk.label") }}
      </button>
      <button class="action danger" :disabled="busy" @click="remove">
        {{ t("bulk.remove") }}
      </button>
    </div>
    <p v-else class="readonly-note">{{ t("auth.readonly") }}</p>

    <div v-if="labelOpen && canWrite" class="selection-label">
      <select v-model="label" :aria-label="t('bulk.label')">
        <option value="" disabled>{{ t("bulk.labelPlaceholder") }}</option>
        <option value="No Label">{{ t("add.noLabel") }}</option>
        <option v-for="item in labels" :key="item.id" :value="item.id">
          {{ item.id }}
        </option>
      </select>
      <button
        class="action primary"
        :disabled="busy || !label"
        @click="applyLabel"
      >
        {{ t("sheet.save") }}
      </button>
    </div>
  </section>
</template>
