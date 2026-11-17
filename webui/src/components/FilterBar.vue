<script setup lang="ts">
import { computed } from "vue";

import type { LabelInfo, TorrentFilters } from "../types";

const props = defineProps<{
  filters: TorrentFilters;
  labels: LabelInfo[];
  noLabelCount: number;
  total: number;
  loaded: number;
}>();
const emit = defineEmits<{ update: [partial: Partial<TorrentFilters>] }>();

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
  { value: "name", label: "Név" },
  { value: "-progress", label: "Progress" },
  { value: "-download_payload_rate", label: "Letöltés" },
  { value: "-ratio", label: "Ratio" },
  { value: "eta", label: "ETA" },
  { value: "-total_size", label: "Méret" },
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
      placeholder="Keresés névben…"
      autocomplete="off"
      aria-label="Keresés"
    />
    <div class="filter-row">
      <select v-model="state" aria-label="Állapot szűrő">
        <option value="All">Minden állapot</option>
        <option v-for="item in states.slice(1)" :key="item" :value="item">
          {{ item }}
        </option>
      </select>
      <select v-model="label" aria-label="Label szűrő">
        <option value="">Minden label</option>
        <option v-for="item in labels" :key="item.id" :value="item.id">
          {{ item.id }} ({{ item.count }})
        </option>
        <option v-if="noLabelCount > 0" value="No Label">
          No Label ({{ noLabelCount }})
        </option>
      </select>
      <select v-model="sort" aria-label="Rendezés">
        <option v-for="item in sorts" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
    </div>
    <div class="filter-meta">
      <span>{{ total }} torrent</span>
      <span>{{ loaded }} betöltve</span>
    </div>
  </section>
</template>
