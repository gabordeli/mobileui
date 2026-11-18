<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import * as api from "../api";
import { trapFocus } from "../focus";
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
  TorrentOptions,
} from "../types";
import DirectoryPicker from "./DirectoryPicker.vue";

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
const downLimit = ref(-1);
const upLimit = ref(-1);
const removeData = ref(false);
const trackersOpen = ref(false);
const optionsOpen = ref(false);
const options = ref<TorrentOptions | null>(null);
const optionsLoading = ref(false);
const optionsSaving = ref(false);
const optionsError = ref("");
const moveOpen = ref(false);
const movePath = ref("");
const moveBusy = ref(false);
const pickerOpen = ref(false);
const backButton = ref<HTMLButtonElement | null>(null);
const dialogEl = ref<HTMLElement | null>(null);
let releaseFocus: (() => void) | null = null;

const progress = computed(() =>
  Math.max(0, Math.min(100, detail.value?.progress ?? 0)),
);
const isPaused = computed(() => detail.value?.state.includes("Paused") ?? false);
const isMoving = computed(() => detail.value?.state === "Moving");
const optionsValid = computed(() => {
  const item = options.value;
  return (
    item !== null &&
    Number.isFinite(item.stop_ratio) &&
    Number.isFinite(item.max_connections) &&
    Number.isFinite(item.max_upload_slots)
  );
});
const trackerSummary = computed(() => {
  const item = detail.value;
  if (!item) return "";
  return (
    item.tracker_status ||
    item.trackers.find((tracker) => tracker.message)?.message ||
    ""
  );
});
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
    downLimit.value = detail.value.max_download_speed;
    upLimit.value = detail.value.max_upload_speed;
    await loadFiles(true);
  } catch (err) {
    error.value = messageOf(err);
  } finally {
    loading.value = false;
  }
}

const filesRequest = ref(0);
const fileSearchTimer = ref<ReturnType<typeof setTimeout>>();

async function loadFiles(reset = false): Promise<void> {
  if (filesLoading.value && !reset) return;
  const requestId = filesRequest.value + 1;
  filesRequest.value = requestId;
  filesLoading.value = true;
  try {
    const query = fileQuery.value.trim();
    const offset = reset ? 0 : files.value.length;
    const page = query
      ? await api.getTorrentFiles(props.torrentId, offset, 100, query)
      : await api.getTorrentFiles(props.torrentId, offset, 100);
    if (requestId !== filesRequest.value) return;
    files.value = reset ? page.files : [...files.value, ...page.files];
    filesTotal.value = page.total;
  } catch (err) {
    if (requestId === filesRequest.value) actionError.value = messageOf(err);
  } finally {
    if (requestId === filesRequest.value) filesLoading.value = false;
  }
}

const filteredFiles = computed(() => files.value);

watch(fileQuery, () => {
  clearTimeout(fileSearchTimer.value);
  fileSearchTimer.value = setTimeout(() => void loadFiles(true), 300);
});

onBeforeUnmount(() => clearTimeout(fileSearchTimer.value));

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

async function reannounce(): Promise<void> {
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result = await api.reannounceTorrent(props.torrentId);
    emit(
      "toast",
      result.reannounced
        ? t("detail.reannounceSent")
        : t("detail.reannounceFailed"),
    );
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function recheck(): Promise<void> {
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result = await api.recheckTorrent(props.torrentId);
    emit(
      "toast",
      result.rechecked
        ? t("detail.recheckStarted")
        : t("detail.recheckFailed"),
    );
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    actionLoading.value = false;
  }
}

async function loadOptions(): Promise<void> {
  optionsLoading.value = true;
  optionsError.value = "";
  try {
    const result = await api.getTorrentOptions(props.torrentId);
    options.value = result.options;
  } catch (err) {
    optionsError.value = messageOf(err);
  } finally {
    optionsLoading.value = false;
  }
}

async function toggleOptions(): Promise<void> {
  optionsOpen.value = !optionsOpen.value;
  if (optionsOpen.value && !options.value && !optionsLoading.value) {
    await loadOptions();
  }
}

async function saveOptions(): Promise<void> {
  if (!options.value) return;
  optionsSaving.value = true;
  optionsError.value = "";
  try {
    const result = await api.setTorrentOptions(props.torrentId, {
      ...options.value,
    });
    options.value = result.options;
    emit("toast", t("toast.options"));
  } catch (err) {
    optionsError.value = messageOf(err);
  } finally {
    optionsSaving.value = false;
  }
}

async function copyText(text: string): Promise<void> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    emit("toast", t("toast.copied"));
  } catch {
    emit("toast", t("toast.copyFailed"));
  }
}

function copyMagnet(): void {
  if (!detail.value) return;
  const name = encodeURIComponent(detail.value.name);
  void copyText(`magnet:?xt=urn:btih:${detail.value.id}&dn=${name}`);
}

function copyHash(): void {
  if (detail.value) void copyText(detail.value.id);
}

function openMove(): void {
  if (!detail.value || isMoving.value) return;
  movePath.value = detail.value.download_location || detail.value.save_path || "";
  moveOpen.value = true;
}

function pickMovePath(path: string): void {
  movePath.value = path;
  pickerOpen.value = false;
}

async function moveStorage(): Promise<void> {
  if (!detail.value || moveBusy.value) return;
  const location = movePath.value.trim();
  if (!location) return;
  moveBusy.value = true;
  actionError.value = "";
  try {
    const result = await api.moveTorrent(detail.value.id, location);
    detail.value.download_location = result.destination;
    detail.value.state = "Moving";
    moveOpen.value = false;
    emit("updated", {
      id: detail.value.id,
      fields: { state: "Moving" },
    });
    emit("toast", t("detail.moveStarted"));
  } catch (err) {
    actionError.value = messageOf(err);
  } finally {
    moveBusy.value = false;
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

async function saveLimits(): Promise<void> {
  actionLoading.value = true;
  actionError.value = "";
  try {
    const result = await api.setTorrentLimits(props.torrentId, {
      max_download_speed: Number(downLimit.value),
      max_upload_speed: Number(upLimit.value),
    });
    if (detail.value) {
      detail.value.max_download_speed = result.max_download_speed;
      detail.value.max_upload_speed = result.max_upload_speed;
    }
    emit("toast", t("toast.limits"));
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
  if (dialogEl.value) releaseFocus = trapFocus(dialogEl.value);
});
onBeforeUnmount(() => {
  releaseFocus?.();
  clearTimeout(fileSearchTimer.value);
});
</script>

<template>
  <Teleport to="body">
    <div class="detail-backdrop">
      <dialog
        ref="dialogEl"
        open
        class="detail"
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

          <div class="detail-vitals">
            <div>
              <span>↓ {{ t("detail.download") }}</span>
              <strong class="down">{{ formatRate(detail.download_payload_rate) }}</strong>
            </div>
            <div>
              <span>↑ {{ t("detail.upload") }}</span>
              <strong class="up">{{ formatRate(detail.upload_payload_rate) }}</strong>
            </div>
            <div>
              <span>{{ t("detail.eta") }}</span>
              <strong>{{ formatEta(detail.eta) }}</strong>
            </div>
          </div>

          <p class="detail-meta">
            <span>{{ t("detail.ratio") }} <strong>{{ formatRatio(detail.ratio) }}</strong></span>
            <span>{{ t("detail.peers") }} <strong>{{ peerLabel(detail.num_peers, detail.total_peers) }}</strong></span>
            <span>{{ t("detail.seeds") }} <strong>{{ peerLabel(detail.num_seeds, detail.total_seeds) }}</strong></span>
            <span>{{ t("detail.size") }} <strong>{{ formatBytes(detail.total_size) }}</strong></span>
            <span>{{ t("detail.added") }} <strong>{{ addedDate(detail.time_added) }}</strong></span>
          </p>

          <div class="detail-path">
            <span>{{ t("detail.path") }}</span>
            <code>{{ detail.download_location || detail.save_path }}</code>
            <button
              v-if="canWrite"
              class="action"
              :disabled="actionLoading || isMoving"
              @click="openMove"
            >
              {{ t("detail.move") }}
            </button>
          </div>
          <p v-if="isMoving" class="limits-hint">{{ t("detail.movingHint") }}</p>

          <div v-if="moveOpen" class="move-panel">
            <label>
              <span>{{ t("detail.moveTo") }}</span>
              <div class="inline-field">
                <input
                  v-model="movePath"
                  type="text"
                  autocapitalize="off"
                  spellcheck="false"
                />
                <button
                  class="action"
                  type="button"
                  @click="pickerOpen = true"
                >
                  {{ t("fs.browse") }}
                </button>
              </div>
            </label>
            <p class="limits-hint">{{ t("detail.moveHint") }}</p>
            <div class="move-actions">
              <button class="action" @click="moveOpen = false">
                {{ t("detail.moveCancel") }}
              </button>
              <button
                class="action primary"
                :disabled="moveBusy || !movePath.trim()"
                @click="moveStorage"
              >
                {{ t("detail.moveConfirm") }}
              </button>
            </div>
          </div>

          <DirectoryPicker
            v-if="pickerOpen"
            :initial-path="movePath || '/'"
            @select="pickMovePath"
            @close="pickerOpen = false"
          />

          <div class="detail-copy">
            <button class="action" @click="copyMagnet">
              {{ t("detail.copyMagnet") }}
            </button>
            <button class="action" @click="copyHash">
              {{ t("detail.copyHash") }}
            </button>
          </div>

          <section v-if="detail.trackers.length" class="trackers">
            <header class="trackers-head">
              <button
                class="tracker-bar"
                type="button"
                :aria-expanded="trackersOpen"
                @click="trackersOpen = !trackersOpen"
              >
                <span class="tracker-icon" aria-hidden="true">📡</span>
                <span class="tracker-name">
                  {{ detail.tracker_host || t("detail.trackers") }}
                </span>
                <span v-if="trackerSummary" class="tracker-summary">
                  {{ trackerSummary }}
                </span>
                <span class="tracker-count">{{ detail.trackers.length }}</span>
                <span class="tracker-chevron" aria-hidden="true">
                  {{ trackersOpen ? "▾" : "▸" }}
                </span>
              </button>
              <button
                v-if="canWrite"
                class="action"
                :disabled="actionLoading"
                @click="reannounce"
              >
                {{ t("detail.reannounce") }}
              </button>
            </header>
            <ul v-if="trackersOpen" class="tracker-list">
              <li
                v-for="tracker in detail.trackers"
                :key="`${tracker.tier}-${tracker.url}`"
              >
                <span class="tracker-url" :title="tracker.url">
                  {{ tracker.url }}
                </span>
                <span class="tracker-meta">
                  tier {{ tracker.tier ?? "—" }} ·
                  {{ tracker.message || (tracker.verified ? "OK" : "—") }}
                </span>
              </li>
            </ul>
            <p v-if="trackersOpen && detail.tracker_status" class="tracker-status">
              {{ detail.tracker_status }}
            </p>
          </section>

          <p v-if="actionError" class="detail-error" role="alert">{{ actionError }}</p>

          <template v-if="canWrite">
            <div class="detail-actions">
              <button
                class="action primary"
                :disabled="actionLoading || isMoving"
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
              <button
                class="action"
                :disabled="actionLoading || isMoving || detail.state === 'Checking'"
                @click="recheck"
              >
                {{ t("detail.recheck") }}
              </button>
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

            <label class="field">
              <span>{{ t("limits.title") }}</span>
              <div class="inline-field limits-inline">
                <span class="limit-label">
                  ↓
                  <input
                    v-model.number="downLimit"
                    class="limit-input"
                    type="number"
                    min="-1"
                    step="1"
                    :aria-label="t('limits.download')"
                  />
                </span>
                <span class="limit-label">
                  ↑
                  <input
                    v-model.number="upLimit"
                    class="limit-input"
                    type="number"
                    min="-1"
                    step="1"
                    :aria-label="t('limits.upload')"
                  />
                </span>
                <button class="action" :disabled="actionLoading" @click="saveLimits">
                  {{ t("sheet.save") }}
                </button>
              </div>
              <small class="limits-hint">{{ t("limits.torrentHint") }}</small>
            </label>

            <section class="torrent-options">
              <button
                class="options-bar"
                type="button"
                :aria-expanded="optionsOpen"
                @click="toggleOptions"
              >
                <span class="options-icon" aria-hidden="true">⚙️</span>
                <span>{{ t("options.title") }}</span>
                <span class="options-chevron" aria-hidden="true">
                  {{ optionsOpen ? "▾" : "▸" }}
                </span>
              </button>
              <div v-if="optionsOpen" class="options-panel">
                <p v-if="optionsLoading" class="limits-hint">
                  {{ t("detail.loading") }}
                </p>
                <p v-else-if="optionsError" class="detail-error" role="alert">
                  {{ optionsError }}
                </p>
                <template v-else-if="options">
                  <label class="option-row">
                    <input v-model="options.sequential_download" type="checkbox" />
                    <span>{{ t("options.sequential") }}</span>
                  </label>
                  <label class="option-row">
                    <input
                      v-model="options.prioritize_first_last_pieces"
                      type="checkbox"
                    />
                    <span>{{ t("options.firstLast") }}</span>
                  </label>
                  <label class="option-row">
                    <input v-model="options.auto_managed" type="checkbox" />
                    <span>{{ t("options.autoManaged") }}</span>
                  </label>
                  <label class="option-row">
                    <input v-model="options.super_seeding" type="checkbox" />
                    <span>{{ t("options.superSeeding") }}</span>
                  </label>
                  <label class="option-row">
                    <input v-model="options.stop_at_ratio" type="checkbox" />
                    <span>{{ t("options.stopAtRatio") }}</span>
                  </label>
                  <label class="option-row">
                    <input
                      v-model="options.remove_at_ratio"
                      type="checkbox"
                      :disabled="!options.stop_at_ratio"
                    />
                    <span>{{ t("options.removeAtRatio") }}</span>
                  </label>
                  <div class="options-grid">
                    <label>
                      <span>{{ t("options.stopRatio") }}</span>
                      <input
                        v-model.number="options.stop_ratio"
                        type="number"
                        min="0.5"
                        max="100"
                        step="0.1"
                      />
                    </label>
                    <label>
                      <span>{{ t("options.maxConnections") }}</span>
                      <input
                        v-model.number="options.max_connections"
                        type="number"
                        min="-1"
                        max="9000"
                        step="1"
                      />
                    </label>
                    <label>
                      <span>{{ t("options.maxSlots") }}</span>
                      <input
                        v-model.number="options.max_upload_slots"
                        type="number"
                        min="-1"
                        max="9000"
                        step="1"
                      />
                    </label>
                  </div>
                  <button
                    class="action primary"
                    :disabled="optionsSaving || isMoving || !optionsValid"
                    @click="saveOptions"
                  >
                    {{ t("sheet.save") }}
                  </button>
                  <p class="limits-hint">{{ t("options.hint") }}</p>
                </template>
              </div>
            </section>
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
              <input v-model="removeData" type="checkbox" :disabled="isMoving" />
              <span>{{ t("detail.removeData") }}</span>
            </label>
            <button
              class="action danger"
              :disabled="actionLoading || isMoving"
              @click="remove"
            >
              {{ t("detail.remove") }}
            </button>
          </div>
        </div>
      </dialog>
    </div>
  </Teleport>
</template>
