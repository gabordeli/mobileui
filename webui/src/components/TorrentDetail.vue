<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import * as api from "../api";
import {
  formatBytes,
  formatEta,
  formatRatio,
  formatRate,
  stateClass,
} from "../format";
import type { LabelInfo, TorrentDetail, TorrentFile } from "../types";

const props = defineProps<{
  torrentId: string;
  liveFields: Record<string, unknown>;
  labels: LabelInfo[];
  noLabelCount: number;
}>();
const emit = defineEmits<{
  close: [];
  updated: [payload: { id: string; fields: Record<string, unknown> }];
  removed: [id: string];
  toast: [message: string];
}>();

const detail = ref<TorrentDetail | null>(null);
const files = ref<TorrentFile[]>([]);
const filesTotal = ref(0);
const filesLoading = ref(false);
const loading = ref(true);
const error = ref("");
const actionError = ref("");
const actionLoading = ref(false);
const selectedLabel = ref("");
const removeData = ref(false);

const progress = computed(() =>
  Math.max(0, Math.min(100, detail.value?.progress ?? 0)),
);
const isPaused = computed(() => detail.value?.state.includes("Paused") ?? false);
const labelOptions = computed(() => {
  const options = props.labels.map((label) => label.id);
  const current = detail.value?.label;
  if (current && current !== "No Label" && !options.includes(current)) {
    options.push(current);
  }
  if (props.noLabelCount > 0 || current === "No Label") {
    options.push("No Label");
  }
  return options;
});

function messageOf(value: unknown): string {
  return value instanceof Error ? value.message : "Ismeretlen hiba";
}

async function loadDetail(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await api.getTorrent(props.torrentId);
    selectedLabel.value = detail.value.label;
    await loadFiles(true);
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

async function loadFiles(reset = false): Promise<void> {
  if (filesLoading.value) return;
  filesLoading.value = true;
  try {
    const page = await api.getTorrentFiles(
      props.torrentId,
      reset ? 0 : files.value.length,
      100,
    );
    files.value = reset ? page.files : [...files.value, ...page.files];
    filesTotal.value = page.total;
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    filesLoading.value = false;
  }
}

async function act(kind: "pause" | "resume"): Promise<void> {
  if (!detail.value) return;
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result =
      kind === "pause"
        ? await api.pauseTorrent(props.torrentId)
        : await api.resumeTorrent(props.torrentId);
    detail.value.state = result.state;
    emit("updated", { id: props.torrentId, fields: { state: result.state } });
    emit("toast", kind === "pause" ? "Szüneteltetve" : "Folytatva");
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function queue(action: string): Promise<void> {
  actionLoading.value = true;
  actionError.value = "";
  try {
    await api.queueTorrent(props.torrentId, action);
    emit("toast", "Sorrend frissítve");
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function saveLabel(): Promise<void> {
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result = await api.setLabel(props.torrentId, selectedLabel.value);
    if (detail.value) detail.value.label = result.label;
    emit("updated", { id: props.torrentId, fields: { label: result.label } });
    emit("toast", "Label frissítve");
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function remove(): Promise<void> {
  if (!detail.value) return;
  if (!confirm(`Eltávolítod: ${detail.value.name}?`)) return;
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result = await api.removeTorrent(props.torrentId, removeData.value);
    if (result.removed) {
      emit("removed", props.torrentId);
      emit("close");
    }
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

function addedDate(seconds: number): string {
  if (!seconds) return "—";
  return new Date(seconds * 1000).toLocaleDateString("hu-HU");
}

function peerLabel(current: number, total: number): string {
  return total >= 0 ? `${current} / ${total}` : String(current);
}

watch(
  () => props.liveFields,
  (fields) => {
    if (detail.value && fields) Object.assign(detail.value, fields);
  },
  { deep: true },
);

onMounted(loadDetail);
</script>

<template>
  <Teleport to="body">
    <div class="detail-backdrop">
      <section class="detail" role="dialog" aria-modal="true" aria-label="Torrent részletek">
        <header class="detail-head">
          <button class="icon-button" aria-label="Vissza" @click="emit('close')">←</button>
          <div class="detail-title">
            <h2>{{ detail?.name ?? "Betöltés…" }}</h2>
            <p v-if="detail">
              <span class="state-pill" :class="stateClass(detail.state)">
                {{ detail.state }}
              </span>
              <span>{{ detail.label }}</span>
              <span v-if="detail.tracker_host">· {{ detail.tracker_host }}</span>
            </p>
          </div>
          <button class="icon-button" aria-label="Bezárás" @click="emit('close')">✕</button>
        </header>

        <div v-if="loading" class="detail-state">Betöltés…</div>
        <div v-else-if="error" class="detail-state">
          <p>{{ error }}</p>
          <button class="action" @click="loadDetail">Újrapróbálás</button>
        </div>

        <div v-else-if="detail" class="detail-body">
          <div class="detail-progress">
            <div class="detail-progress-head">
              <strong>{{ progress.toFixed(1) }}%</strong>
              <span>{{ formatBytes(detail.total_done) }} / {{ formatBytes(detail.total_size) }}</span>
            </div>
            <div class="progress-track">
              <div
                class="progress-fill"
                :class="{ complete: progress >= 100 }"
                :style="{ width: `${progress}%` }"
              />
            </div>
            <p v-if="detail.message" class="detail-message">{{ detail.message }}</p>
          </div>

          <div class="stats-grid">
            <div><span>Letöltés</span><strong class="down">{{ formatRate(detail.download_payload_rate) }}</strong></div>
            <div><span>Feltöltés</span><strong class="up">{{ formatRate(detail.upload_payload_rate) }}</strong></div>
            <div><span>ETA</span><strong>{{ formatEta(detail.eta) }}</strong></div>
            <div><span>Ratio</span><strong>{{ formatRatio(detail.ratio) }}</strong></div>
            <div><span>Peers</span><strong>{{ peerLabel(detail.num_peers, detail.total_peers) }}</strong></div>
            <div><span>Seeds</span><strong>{{ peerLabel(detail.num_seeds, detail.total_seeds) }}</strong></div>
            <div><span>Méret</span><strong>{{ formatBytes(detail.total_size) }}</strong></div>
            <div><span>Hozzáadva</span><strong>{{ addedDate(detail.time_added) }}</strong></div>
          </div>

          <div class="detail-path">
            <span>Mentési útvonal</span>
            <code>{{ detail.download_location || detail.save_path }}</code>
          </div>

          <p v-if="actionError" class="detail-error" role="alert">{{ actionError }}</p>

          <div class="detail-actions">
            <button
              class="action primary"
              :disabled="actionLoading"
              @click="act(isPaused ? 'resume' : 'pause')"
            >
              {{ isPaused ? "Folytatás" : "Szüneteltetés" }}
            </button>
            <div class="queue-grid">
              <button class="action" :disabled="actionLoading" @click="queue('top')">Legfelülre</button>
              <button class="action" :disabled="actionLoading" @click="queue('up')">Fel</button>
              <button class="action" :disabled="actionLoading" @click="queue('down')">Le</button>
              <button class="action" :disabled="actionLoading" @click="queue('bottom')">Legalulra</button>
            </div>
          </div>

          <label class="field">
            <span>Label</span>
            <div class="inline-field">
              <select v-model="selectedLabel">
                <option v-for="option in labelOptions" :key="option" :value="option">
                  {{ option }}
                </option>
              </select>
              <button class="action" :disabled="actionLoading" @click="saveLabel">
                Mentés
              </button>
            </div>
          </label>

          <section class="files">
            <header class="files-head">
              <h3>Fájlok <small v-if="filesTotal">({{ filesTotal }})</small></h3>
              <span v-if="filesTotal">{{ files.length }} betöltve</span>
            </header>
            <div v-if="filesLoading && !files.length" class="detail-state small">Fájlok betöltése…</div>
            <p v-else-if="!files.length" class="files-empty">
              Nincs fájlinformáció (pl. magnet metaadat nélkül).
            </p>
            <ul v-else class="file-list">
              <li v-for="file in files" :key="file.index" class="file-row">
                <div class="file-main">
                  <span class="file-path" :title="file.path">{{ file.path }}</span>
                  <span class="file-size">{{ formatBytes(file.size) }}</span>
                </div>
                <div class="file-progress">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: `${file.progress * 100}%` }" />
                  </div>
                  <span>{{ (file.progress * 100).toFixed(0) }}%</span>
                </div>
              </li>
            </ul>
            <button
              v-if="files.length < filesTotal"
              class="action files-more"
              :disabled="filesLoading"
              @click="loadFiles(false)"
            >
              {{ filesLoading ? "Betöltés…" : "További fájlok" }}
            </button>
          </section>

          <div class="detail-remove">
            <label class="checkbox">
              <input v-model="removeData" type="checkbox" />
              <span>Letöltött adatok törlése is</span>
            </label>
            <button class="action danger" :disabled="actionLoading" @click="remove">
              Eltávolítás
            </button>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>
