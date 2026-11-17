<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RecycleScroller } from "vue-virtual-scroller";

import * as api from "./api";
import { formatRate } from "./format";
import { locale, t, toggleLocale } from "./i18n";
import { extractMagnet } from "./share";
import { theme, toggleTheme } from "./theme";
import type {
  AuthInfo,
  AuthMode,
  BulkActionPayload,
  GatePayload,
  LabelInfo,
  LimitPayload,
  Session,
  Torrent,
  TorrentEvent,
  TorrentFilters,
} from "./types";
import AddDialog from "./components/AddDialog.vue";
import FilterBar from "./components/FilterBar.vue";
import LabelsSheet from "./components/LabelsSheet.vue";
import SelectionBar from "./components/SelectionBar.vue";
import SessionSheet from "./components/SessionSheet.vue";
import TokenGate from "./components/TokenGate.vue";
import TorrentDetail from "./components/TorrentDetail.vue";
import TorrentRow from "./components/TorrentRow.vue";

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE = 300;

const authed = ref(false);
const session = ref<Session | null>(null);
const authInfo = ref<AuthInfo | null>(null);
const authModes = ref<AuthMode[]>(["token"]);
const labels = ref<LabelInfo[]>([]);
const noLabelCount = ref(0);
const torrents = ref<Torrent[]>([]);
const total = ref(0);
const loading = ref(false);
const loadingMore = ref(false);
const listError = ref("");
const authError = ref("");
const selectionMode = ref(false);
const selectedIds = ref<Set<string>>(new Set());
const bulkBusy = ref(false);
const detail = ref<Torrent | null>(null);
const detailLive = ref<Record<string, unknown>>({});
const addOpen = ref(false);
const pendingMagnet = ref("");
const pendingTorrent = ref("");
const sessionOpen = ref(false);
const labelsOpen = ref(false);
const downHistory = ref<number[]>([]);
const upHistory = ref<number[]>([]);
const HISTORY_LEN = 60;
const online = ref(navigator.onLine);
const toast = ref("");
const sseState = ref<"off" | "live" | "reconnecting">("off");
const tokenInitial = ref(api.getToken());
const pluginVersion = ref("");
const filters = reactive<TorrentFilters>({
  q: "",
  state: "",
  label: "",
  sort: "name",
});

let source: EventSource | null = null;
let toastTimer: ReturnType<typeof setTimeout> | null = null;
let searchTimer: ReturnType<typeof setTimeout> | null = null;
let inFlight = false;
let pendingReset = false;

const downRate = computed(() => session.value?.payload_download_rate ?? 0);
const upRate = computed(() => session.value?.payload_upload_rate ?? 0);
const torrentCount = computed(() => session.value?.num_torrents ?? total.value);
const canWrite = computed(() => authInfo.value?.write !== false);
const listKey = computed(
  () => `${filters.q}|${filters.state}|${filters.label}|${filters.sort}`,
);
const sseTitle = computed(() => {
  if (sseState.value === "live") return t("header.live");
  if (sseState.value === "off") return t("header.offline");
  return t("header.reconnecting");
});

function showToast(message: string): void {
  toast.value = message;
  if (toastTimer !== null) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.value = "";
    toastTimer = null;
  }, 2500);
}

function closeEvents(): void {
  source?.close();
  source = null;
  sseState.value = "off";
}

function reportError(error: unknown, inList = false): void {
  if (error instanceof api.UnauthorizedError) {
    closeEvents();
    authError.value = t("auth.expired");
    tokenInitial.value = api.getToken();
    authed.value = false;
    return;
  }
  const message =
    error instanceof api.ForbiddenError
      ? t("auth.readonly")
      : error instanceof Error
        ? error.message
        : t("toast.error");
  if (inList) {
    listError.value = message;
  } else {
    showToast(message);
  }
}

async function loadAuthInfo(): Promise<void> {
  try {
    const info = await api.getAuthInfo();
    authInfo.value = info;
    authModes.value = info.modes;
  } catch {
    authInfo.value = null;
  }
}

async function loadPluginVersion(): Promise<void> {
  try {
    const health = await api.getHealth();
    pluginVersion.value = health.version;
  } catch {
    pluginVersion.value = "";
  }
}

async function bootstrap(): Promise<void> {
  tokenInitial.value = api.getToken();
  if (!tokenInitial.value) {
    authed.value = false;
    return;
  }
  try {
    const [sessionData, labelData, info] = await Promise.all([
      api.getSession(),
      api.getLabels(),
      api.getAuthInfo().catch(() => null),
    ]);
    session.value = sessionData;
    downHistory.value = [];
    upHistory.value = [];
    pushSpeedHistory();
    labels.value = labelData.labels;
    noLabelCount.value = labelData.no_label;
    if (info) {
      authInfo.value = info;
      authModes.value = info.modes;
    }
    authError.value = "";
    authed.value = true;
    connectEvents();
    resetList();
    void openPendingTorrent();
  } catch (error) {
    reportError(error);
  }
}

async function openPendingTorrent(): Promise<void> {
  const torrentId = pendingTorrent.value;
  if (!torrentId) return;
  pendingTorrent.value = "";
  try {
    openDetail(await api.getTorrent(torrentId));
  } catch (error) {
    reportError(error);
  }
}

function resetList(): void {
  if (!authed.value) return;
  torrents.value = [];
  total.value = 0;
  void loadPage(true);
}

async function loadPage(reset = false): Promise<void> {
  if (!authed.value) return;
  if (inFlight) {
    if (reset) pendingReset = true;
    return;
  }
  inFlight = true;
  if (reset) loading.value = true;
  else loadingMore.value = true;
  try {
    const page = await api.listTorrents(
      filters,
      reset ? 0 : torrents.value.length,
      PAGE_SIZE,
    );
    if (reset) {
      torrents.value = page.torrents;
    } else {
      torrents.value.push(...page.torrents);
    }
    total.value = page.total;
    listError.value = "";
  } catch (error) {
    reportError(error, true);
  } finally {
    inFlight = false;
    loading.value = false;
    loadingMore.value = false;
    if (pendingReset) {
      pendingReset = false;
      resetList();
    }
  }
}

function onScrollerUpdate(_start: number, end: number): void {
  if (end < torrents.value.length - 5) return;
  if (torrents.value.length >= total.value) return;
  void loadPage(false);
}

function updateFilters(partial: Partial<TorrentFilters>): void {
  Object.assign(filters, partial);
}

function startSelection(torrent: Torrent): void {
  selectionMode.value = true;
  selectedIds.value = new Set([torrent.id]);
}

function toggleSelection(torrent: Torrent): void {
  const next = new Set(selectedIds.value);
  if (next.has(torrent.id)) {
    next.delete(torrent.id);
  } else {
    next.add(torrent.id);
  }
  selectedIds.value = next;
  if (next.size === 0) selectionMode.value = false;
}

function onRowSelect(torrent: Torrent): void {
  if (selectionMode.value) {
    toggleSelection(torrent);
    return;
  }
  openDetail(torrent);
}

function clearSelection(): void {
  selectionMode.value = false;
  selectedIds.value = new Set();
}

async function selectAllMatching(): Promise<void> {
  try {
    const result = await api.listTorrentIds(filters);
    selectedIds.value = new Set(result.ids);
    selectionMode.value = result.ids.length > 0;
    if (result.total > result.ids.length) {
      showToast(t("bulk.capped", { limit: result.limit }));
    }
  } catch (error) {
    reportError(error);
  }
}

async function runBulk(
  payload:
    | { kind: "pause" | "resume" | "remove" }
    | { kind: "label"; label: string },
): Promise<void> {
  if (bulkBusy.value || selectedIds.value.size === 0) return;
  bulkBusy.value = true;
  try {
    const torrentIds = [...selectedIds.value];
    const body: BulkActionPayload =
      payload.kind === "label"
        ? { action: "label", torrent_ids: torrentIds, label: payload.label }
        : {
            action: payload.kind,
            torrent_ids: torrentIds,
            ...(payload.kind === "remove" ? { remove_data: false } : {}),
          };
    const result = await api.bulkAction(body);
    showToast(
      result.failed.length
        ? t("bulk.partial", { ok: result.ok, failed: result.failed.length })
        : t("bulk.done", { ok: result.ok }),
    );
    clearSelection();
    resetList();
  } catch (error) {
    reportError(error);
  } finally {
    bulkBusy.value = false;
  }
}

function openDetail(torrent: Torrent): void {
  detailLive.value = {};
  detail.value = torrent;
}

function onDetailUpdated(payload: { id: string; fields: Record<string, unknown> }): void {
  const row = torrents.value.find((item) => item.id === payload.id);
  if (row) api.updateTorrent(row, payload.fields);
}

function onDetailRemoved(id: string): void {
  torrents.value = torrents.value.filter((row) => row.id !== id);
  total.value = Math.max(0, total.value - 1);
  detail.value = null;
}

function onAdded(): void {
  resetList();
}

watch(
  () => filters.q,
  () => {
    if (!authed.value) return;
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = setTimeout(resetList, SEARCH_DEBOUNCE);
  },
);

watch(
  () => [filters.state, filters.label, filters.sort],
  () => resetList(),
);

function handleTorrentEvent(event: TorrentEvent): void {
  if (event.type === "added") {
    if (!filters.q && !filters.state && !filters.label) {
      total.value += 1;
    }
    return;
  }
  if (event.type === "removed") {
    const index = torrents.value.findIndex((row) => row.id === event.id);
    if (index >= 0) {
      torrents.value.splice(index, 1);
      total.value = Math.max(0, total.value - 1);
    }
    if (detail.value?.id === event.id) detail.value = null;
    return;
  }
  if (!event.id) return;
  const row = torrents.value.find((item) => item.id === event.id);
  if (row) api.updateTorrent(row, event.fields);
  if (detail.value?.id === event.id) {
    detailLive.value = { ...detailLive.value, ...event.fields };
  }
}

function pushSpeedHistory(): void {
  if (!session.value) return;
  downHistory.value = [
    ...downHistory.value,
    session.value.payload_download_rate,
  ].slice(-HISTORY_LEN);
  upHistory.value = [
    ...upHistory.value,
    session.value.payload_upload_rate,
  ].slice(-HISTORY_LEN);
}

function handleSessionEvent(event: TorrentEvent): void {
  if (session.value) {
    Object.assign(session.value, event.fields);
    pushSpeedHistory();
  }
  const count = event.fields.num_torrents;
  if (
    typeof count === "number" &&
    !filters.q &&
    !filters.state &&
    !filters.label
  ) {
    total.value = count;
  }
}

function connectEvents(): void {
  closeEvents();
  source = new EventSource(api.eventsUrl());
  sseState.value = "reconnecting";
  source.onopen = () => {
    sseState.value = "live";
  };
  source.onerror = () => {
    sseState.value = "reconnecting";
  };
  source.addEventListener("torrent", (message) => {
    try {
      handleTorrentEvent(JSON.parse((message as MessageEvent).data));
    } catch {
      // Ignore malformed deltas; the next full refresh corrects the row.
    }
  });
  source.addEventListener("session", (message) => {
    try {
      handleSessionEvent(JSON.parse((message as MessageEvent).data));
    } catch {
      // Ignore malformed deltas.
    }
  });
}

async function toggleSession(): Promise<void> {
  if (!session.value) return;
  try {
    const result = session.value.paused
      ? await api.resumeSession()
      : await api.pauseSession();
    session.value.paused = result.paused;
    showToast(
      result.paused ? t("toast.sessionPaused") : t("toast.sessionResumed"),
    );
  } catch (error) {
    reportError(error);
  }
}

async function applySessionLimits(payload: LimitPayload): Promise<void> {
  try {
    const result = await api.setSessionLimits(payload);
    if (session.value) {
      session.value.max_download_speed = result.max_download_speed;
      session.value.max_upload_speed = result.max_upload_speed;
    }
    showToast(t("toast.limits"));
  } catch (error) {
    reportError(error);
  }
}

async function reloadLabels(): Promise<void> {
  const data = await api.getLabels();
  labels.value = data.labels;
  noLabelCount.value = data.no_label;
}

async function addLabel(id: string): Promise<void> {
  try {
    await api.addLabel(id);
    await reloadLabels();
    showToast(t("labels.added"));
  } catch (error) {
    reportError(error);
  }
}

async function removeLabel(id: string): Promise<void> {
  try {
    await api.removeLabel(id);
    await reloadLabels();
    if (filters.label === id) filters.label = "";
    resetList();
    showToast(t("labels.removed"));
  } catch (error) {
    reportError(error);
  }
}

function showGate(): void {
  tokenInitial.value = api.getToken();
  authError.value = "";
  authed.value = false;
}

async function submitGate(payload: GatePayload): Promise<void> {
  authError.value = "";
  if (payload.mode === "password") {
    try {
      const result = await api.login(payload.username ?? "", payload.password ?? "");
      api.setToken(result.token);
      await bootstrap();
    } catch (error) {
      if (error instanceof api.UnauthorizedError) {
        authError.value = t("auth.invalid");
      } else if (error instanceof api.ApiError && error.status === 429) {
        authError.value = t("auth.tooMany");
      } else {
        authError.value =
          error instanceof Error ? error.message : t("toast.error");
      }
    }
    return;
  }
  if (!payload.token) return;
  api.setToken(payload.token);
  void bootstrap();
}

async function doLogout(): Promise<void> {
  try {
    await api.logout();
  } catch {
    // The static config token cannot be revoked; clearing it locally is enough.
  }
  api.setToken("");
  closeEvents();
  session.value = null;
  authInfo.value = null;
  authError.value = "";
  authed.value = false;
}

function cancelGate(): void {
  if (session.value) {
    authed.value = true;
    if (!source) connectEvents();
  }
}

function updateOnline(): void {
  online.value = navigator.onLine;
}

onMounted(() => {
  const params = new URLSearchParams(window.location.search);
  const shared = extractMagnet(window.location.search);
  if (shared) {
    pendingMagnet.value = shared;
    addOpen.value = true;
    for (const key of ["text", "url", "title"]) params.delete(key);
  }
  const torrentId = params.get("torrent");
  if (torrentId) {
    pendingTorrent.value = torrentId;
    params.delete("torrent");
  }
  if (shared || torrentId) {
    const query = params.toString();
    const suffix = query ? `?${query}` : "";
    const path =
      window.location.pathname === "/share" ? "/" : window.location.pathname;
    window.history.replaceState({}, "", `${path}${suffix}`);
  }
  window.addEventListener("online", updateOnline);
  window.addEventListener("offline", updateOnline);
  void loadPluginVersion();
  void loadAuthInfo();
  void bootstrap();
});

onBeforeUnmount(() => {
  window.removeEventListener("online", updateOnline);
  window.removeEventListener("offline", updateOnline);
  closeEvents();
  if (toastTimer !== null) clearTimeout(toastTimer);
  if (searchTimer !== null) clearTimeout(searchTimer);
});
</script>

<template>
  <TokenGate
    v-if="!authed"
    :modes="authModes"
    :initial-token="tokenInitial"
    :error="authError"
    :cancelable="Boolean(session)"
    :plugin-version="pluginVersion"
    :token-set="authInfo?.token_set ?? true"
    :username="authInfo?.username"
    :level="authInfo?.level"
    @submit="submitGate"
    @cancel="cancelGate"
    @logout="doLogout"
  />

  <div v-else class="app-shell">
    <header class="app-header">
      <div class="brand">
        Deluge <strong>Mobile</strong>
        <span
          class="sse-dot"
          :class="sseState"
          :title="sseTitle"
        />
      </div>
      <button
        class="header-stats"
        type="button"
        :aria-label="t('session.open')"
        :title="t('session.open')"
        @click="sessionOpen = true"
      >
        <span>↓ {{ formatRate(downRate) }}</span>
        <span>↑ {{ formatRate(upRate) }}</span>
        <span>{{ torrentCount }}</span>
      </button>
      <button
        class="icon-button compact"
        :aria-label="t('header.theme')"
        :title="t('header.theme')"
        @click="toggleTheme"
      >
        {{ theme === "dark" ? "☀" : "☾" }}
      </button>
      <button
        class="icon-button compact"
        :aria-label="t('header.language')"
        :title="t('header.language')"
        @click="toggleLocale"
      >
        {{ locale === "hu" ? "EN" : "HU" }}
      </button>
      <button
        v-if="canWrite"
        class="icon-button"
        :aria-label="t('header.add')"
        :title="t('header.add')"
        @click="addOpen = true"
      >
        +
      </button>
      <button
        class="icon-button"
        :aria-label="t('header.token')"
        :title="t('header.token')"
        @click="showGate"
      >
        ⚙
      </button>
    </header>

    <div v-if="!online" class="offline-banner" role="status">
      {{ t("list.offline") }}
    </div>

    <FilterBar
      :filters="filters"
      :labels="labels"
      :no-label-count="noLabelCount"
      :total="total"
      :loaded="torrents.length"
      @update="updateFilters"
      @manage-labels="labelsOpen = true"
    />

    <main class="list-pane" :class="{ selecting: selectionMode }">
      <div v-if="listError" class="error-banner">
        <span>{{ listError }}</span>
        <button class="action" @click="resetList">{{ t("list.retry") }}</button>
      </div>
      <RecycleScroller
        :key="listKey"
        class="scroller"
        :items="torrents"
        :item-size="88"
        key-field="id"
        :emit-update="true"
        @update="onScrollerUpdate"
      >
        <template #default="{ item }">
          <TorrentRow
            :torrent="item"
            :selected="selectedIds.has(item.id)"
            :selection-mode="selectionMode"
            @long-press="startSelection"
            @select="onRowSelect"
          />
        </template>
      </RecycleScroller>
      <div v-if="loading" class="skeleton-list" aria-hidden="true">
        <div v-for="index in 6" :key="index" class="skeleton-row">
          <span class="skeleton-line wide" />
          <span class="skeleton-line" />
        </div>
      </div>
      <div v-else-if="!torrents.length" class="list-state">
        {{ t("list.empty") }}
      </div>
      <div v-if="loadingMore" class="load-more">
        {{ t("list.loadMore") }}
      </div>
    </main>

    <footer v-if="pluginVersion" class="app-footer">
      MobileUi v{{ pluginVersion }}
    </footer>

    <SessionSheet
      v-if="sessionOpen && session"
      :session="session"
      :can-write="canWrite"
      :down-history="downHistory"
      :up-history="upHistory"
      @close="sessionOpen = false"
      @toggle="toggleSession"
      @limits="applySessionLimits"
    />

    <LabelsSheet
      v-if="labelsOpen"
      :labels="labels"
      :can-write="canWrite"
      @close="labelsOpen = false"
      @add="addLabel"
      @remove="removeLabel"
    />

    <SelectionBar
      v-if="selectionMode"
      :count="selectedIds.size"
      :busy="bulkBusy"
      :can-write="canWrite"
      :labels="labels"
      @close="clearSelection"
      @select-all="selectAllMatching"
      @action="runBulk"
    />

    <TorrentDetail
      v-if="detail"
      :torrent-id="detail.id"
      :live-fields="detailLive"
      :labels="labels"
      :no-label-count="noLabelCount"
      :can-write="canWrite"
      @close="detail = null"
      @updated="onDetailUpdated"
      @removed="onDetailRemoved"
      @toast="showToast"
    />

    <AddDialog
      v-if="addOpen"
      :labels="labels"
      :no-label-count="noLabelCount"
      :default-path="session?.download_location ?? ''"
      :initial-magnet="pendingMagnet"
      @close="addOpen = false; pendingMagnet = ''"
      @added="onAdded"
      @toast="showToast"
    />

    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </div>
</template>
