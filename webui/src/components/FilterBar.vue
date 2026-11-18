<script setup lang="ts">
import { computed } from "vue";

import { stateLabel, t } from "../i18n";
import type { LabelInfo, TorrentFilters } from "../types";

const props = defineProps<{
  filters: TorrentFilters;
  labels: LabelInfo[];
  noLabelCount: number;
  total: number;
  loaded: number;
}>();
const emit = defineEmits<{
  update: [partial: Partial<TorrentFilters>];
  manageLabels: [];
}>();

const states = [
  "All",
  "Downloading",
  "Seeding",
  "Paused",
  "Queued",
  "Checking",
  "Error",
  "Moving",
];
const sorts = [
  { value: "name", key: "sort.name" },
  { value: "-time_added", key: "sort.added" },
  { value: "-progress", key: "sort.progress" },
  { value: "-download_payload_rate", key: "sort.download" },
  { value: "-ratio", key: "sort.ratio" },
  { value: "eta", key: "sort.eta" },
  { value: "-total_size", key: "sort.size" },
];

const q = computed({
  get: () => props.filters.q,
  set: (value: string) => emit("update", { q: value }),
});
const state = computed({
  get: () => props.filters.state || "All",
  set: (value: string) => emit("update", { state: value === "All" ? "" : value }),
});
const label = computed({
  get: () => props.filters.label,
  set: (value: string) => emit("update", { label: value }),
});
const sort = computed({
  get: () => props.filters.sort,
  set: (value: string) => emit("update", { sort: value }),
});
</script>

<template>
  <section class="filters">
    <input
      v-model="q"
      class="search"
      type="search"
      :placeholder="t('filters.search')"
      autocomplete="off"
      :aria-label="t('filters.search')"
    />
    <div class="filter-row">
      <select v-model="state" :aria-label="t('filters.state')">
        <option value="All">{{ t("filters.allStates") }}</option>
        <option v-for="item in states.slice(1)" :key="item" :value="item">
          {{ stateLabel(item) }}
        </option>
      </select>
      <select v-model="label" :aria-label="t('filters.label')">
        <option value="">{{ t("filters.allLabels") }}</option>
        <option v-for="item in labels" :key="item.id" :value="item.id">
          {{ item.id }} ({{ item.count }})
        </option>
        <option v-if="noLabelCount > 0" value="No Label">
          {{ t("add.noLabel") }} ({{ noLabelCount }})
        </option>
      </select>
      <select v-model="sort" :aria-label="t('filters.sort')">
        <option v-for="item in sorts" :key="item.value" :value="item.value">
          {{ t(item.key) }}
        </option>
      </select>
    </div>
    <div class="filter-meta">
      <span>{{ t("filters.total", { count: total }) }}</span>
      <span>{{ t("filters.loaded", { count: loaded }) }}</span>
      <button
        class="filter-labels"
        type="button"
        @click="emit('manageLabels')"
      >
        🏷 {{ t("labels.manage") }}
      </button>
    </div>
  </section>
</template>
