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
import { locale, stateLabel, t } from "../i18n";
import type {
  FilePriorityPayload,
  LabelInfo,
  TorrentDetail,
  TorrentFile,
} from "../types";

const props = defineProps<{
  torrentId: string;
  liveFields: Record<string, unknown>;
  labels: LabelInfo[];
  noLabelCount: number;
  canWrite: boolean;
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
const filesBusy = ref(false);
const fileQuery = ref("");
const loading = ref(true);
const error = ref("");
const actionError = ref("");
const actionLoading = ref(false);
const selectedLabel = ref("");
const removeData = ref(false);
const backButton = ref<HTMLButtonElement | null>(null);

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
  return value instanceof Error ? value.message : t("toast.error");
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

const filteredFiles = computed(() => {
  const needle = fileQuery.value.trim().toLowerCase();
  if (!needle) return files.value;
  return files.value.filter((file) => file.path.toLowerCase().includes(needle));
});

function applyPriorities(priorities: number[]): void {
  for (const file of files.value) {
    if (file.index < priorities.length) file.priority = priorities[file.index];
  }
}

async function saveFilePriorities(payload: FilePriorityPayload): Promise<void> {
  if (filesBusy.value) return;
  filesBusy.value = true;
  actionError.value = "";
  try {
    const result = await api.setFilePriorities(props.torrentId, payload);
    applyPriorities(result.priorities);
    emit("toast", t("toast.files"));
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    filesBusy.value = false;
  }
}

function toggleFile(file: TorrentFile): void {
  void saveFilePriorities({
    files: [{ index: file.index, priority: file.priority > 0 ? 0 : 4 }],
  });
}

function onlyFile(file: TorrentFile): void {
  void saveFilePriorities({ only: file.index });
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
    emit("toast", kind === "pause" ? t("toast.paused") : t("toast.resumed"));
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
    emit("toast", t("toast.queue"));
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
    emit("toast", t("toast.label"));
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function remove(): Promise<void> {
  if (!detail.value) return;
  if (!confirm(t("detail.confirmRemove", { name: detail.value.name }))) return;
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
  return new Date(seconds * 1000).toLocaleDateString(
    locale.value === "hu" ? "hu-HU" : "en-GB",
  );
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

onMounted(() => {
  void loadDetail();
  backButton.value?.focus();
});
</script>

<template>
  <Teleport to="body">
    <div class="detail-backdrop">
      <section
        class="detail"
        role="dialog"
        aria-modal="true"
        :aria-label="t('detail.title')"
        @keydown.esc="emit('close')"
      >
        <header class="detail-head">
          <button
            ref="backButton"
            class="icon-button"
            :aria-label="t('detail.back')"
            @click="emit('close')"
          >
            ←
          </button>
          <div class="detail-title">
            <h2>{{ detail?.name ?? t("detail.loading") }}</h2>
            <p v-if="detail">
              <span class="state-pill" :class="stateClass(detail.state)">
                {{ stateLabel(detail.state) }}
              </span>
              <span>{{ detail.label }}</span>
              <span v-if="detail.tracker_host">· {{ detail.tracker_host }}</span>
            </p>
          </div>
          <button
            class="icon-button"
            :aria-label="t('detail.close')"
            @click="emit('close')"
          >
            ✕
          </button>
        </header>

        <div v-if="loading" class="detail-state">{{ t("detail.loading") }}</div>
        <div v-else-if="error" class="detail-state">
          <p>{{ error }}</p>
          <button class="action" @click="loadDetail">{{ t("detail.retry") }}</button>
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
            <div><span>{{ t("detail.download") }}</span><strong class="down">{{ formatRate(detail.download_payload_rate) }}</strong></div>
            <div><span>{{ t("detail.upload") }}</span><strong class="up">{{ formatRate(detail.upload_payload_rate) }}</strong></div>
            <div><span>{{ t("detail.eta") }}</span><strong>{{ formatEta(detail.eta) }}</strong></div>
            <div><span>{{ t("detail.ratio") }}</span><strong>{{ formatRatio(detail.ratio) }}</strong></div>
            <div><span>{{ t("detail.peers") }}</span><strong>{{ peerLabel(detail.num_peers, detail.total_peers) }}</strong></div>
            <div><span>{{ t("detail.seeds") }}</span><strong>{{ peerLabel(detail.num_seeds, detail.total_seeds) }}</strong></div>
            <div><span>{{ t("detail.size") }}</span><strong>{{ formatBytes(detail.total_size) }}</strong></div>
            <div><span>{{ t("detail.added") }}</span><strong>{{ addedDate(detail.time_added) }}</strong></div>
          </div>

          <div class="detail-path">
            <span>{{ t("detail.path") }}</span>
            <code>{{ detail.download_location || detail.save_path }}</code>
          </div>

          <p v-if="actionError" class="detail-error" role="alert">{{ actionError }}</p>

          <template v-if="canWrite">
            <div class="detail-actions">
              <button
                class="action primary"
                :disabled="actionLoading"
                @click="act(isPaused ? 'resume' : 'pause')"
              >
                {{ isPaused ? t("sheet.resume") : t("sheet.pause") }}
              </button>
              <div class="queue-grid">
                <button class="action" :disabled="actionLoading" @click="queue('top')">{{ t("sheet.top") }}</button>
                <button class="action" :disabled="actionLoading" @click="queue('up')">{{ t("sheet.up") }}</button>
                <button class="action" :disabled="actionLoading" @click="queue('down')">{{ t("sheet.down") }}</button>
                <button class="action" :disabled="actionLoading" @click="queue('bottom')">{{ t("sheet.bottom") }}</button>
              </div>
            </div>

            <label class="field">
              <span>{{ t("sheet.label") }}</span>
              <div class="inline-field">
                <select v-model="selectedLabel">
                  <option v-for="option in labelOptions" :key="option" :value="option">
                    {{ option }}
                  </option>
                </select>
                <button class="action" :disabled="actionLoading" @click="saveLabel">
                  {{ t("sheet.save") }}
                </button>
              </div>
            </label>
          </template>
          <p v-else class="readonly-note">{{ t("auth.readonly") }}</p>

          <section class="files">
            <header class="files-head">
              <h3>{{ t("detail.files") }} <small v-if="filesTotal">({{ filesTotal }})</small></h3>
              <span v-if="filesTotal">{{ t("detail.filesLoaded", { count: files.length }) }}</span>
            </header>
            <div v-if="files.length" class="files-tools">
              <input
                v-model="fileQuery"
                class="files-search"
                type="search"
                :placeholder="t('files.search')"
                :aria-label="t('files.search')"
              />
              <span v-if="fileQuery && files.length < filesTotal" class="files-hint">
                {{ t("files.searchLoaded", { loaded: files.length, total: filesTotal }) }}
              </span>
            </div>
            <div v-if="filesLoading && !files.length" class="detail-state small">
              {{ t("detail.loadingFiles") }}
            </div>
            <p v-else-if="!files.length" class="files-empty">
              {{ t("detail.filesEmpty") }}
            </p>
            <ul v-else class="file-list">
              <li
                v-for="file in filteredFiles"
                :key="file.index"
                class="file-row"
                :class="{ skipped: file.priority === 0 }"
              >
                <div class="file-main">
                  <input
                    v-if="canWrite"
                    class="file-check"
                    type="checkbox"
                    :checked="file.priority > 0"
                    :disabled="filesBusy"
                    :aria-label="t('files.downloadFile', { path: file.path })"
                    @change="toggleFile(file)"
                  />
                  <span class="file-path" :title="file.path">{{ file.path }}</span>
                  <span v-if="file.priority === 0" class="file-skip">{{ t("files.skipped") }}</span>
                  <span class="file-size">{{ formatBytes(file.size) }}</span>
                  <button
                    v-if="canWrite"
                    class="file-only"
                    :disabled="filesBusy"
                    @click="onlyFile(file)"
                  >
                    {{ t("files.only") }}
                  </button>
                </div>
                <div class="file-progress">
                  <div class="progress-track">
                    <div class="progress-fill" :style="{ width: `${file.progress * 100}%` }" />
                  </div>
                  <span>{{ (file.progress * 100).toFixed(0) }}%</span>
                </div>
              </li>
            </ul>
            <p v-if="files.length && fileQuery && !filteredFiles.length" class="files-empty">
              {{ t("files.noMatch") }}
            </p>
            <button
              v-if="files.length < filesTotal"
              class="action files-more"
              :disabled="filesLoading"
              @click="loadFiles(false)"
            >
              {{ filesLoading ? t("add.submitting") : t("detail.moreFiles") }}
            </button>
          </section>

          <div v-if="canWrite" class="detail-remove">
            <label class="checkbox">
              <input v-model="removeData" type="checkbox" />
              <span>{{ t("detail.removeData") }}</span>
            </label>
            <button class="action danger" :disabled="actionLoading" @click="remove">
              {{ t("detail.remove") }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </Teleport>
</template>
