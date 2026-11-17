<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { RecycleScroller } from "vue-virtual-scroller";

import * as api from "./api";
import { formatRate } from "./format";
import { locale, t, toggleLocale } from "./i18n";
import { theme, toggleTheme } from "./theme";
import type {
  ActionPayload,
  LabelInfo,
  Session,
  Torrent,
  TorrentEvent,
  TorrentFilters,
} from "./types";
import AddDialog from "./components/AddDialog.vue";
import ContextSheet from "./components/ContextSheet.vue";
import FilterBar from "./components/FilterBar.vue";
import TokenGate from "./components/TokenGate.vue";
import TorrentDetail from "./components/TorrentDetail.vue";
import TorrentRow from "./components/TorrentRow.vue";

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE = 300;

const authed = ref(false);
const session = ref<Session | null>(null);
const labels = ref<LabelInfo[]>([]);
const noLabelCount = ref(0);
const torrents = ref<Torrent[]>([]);
const total = ref(0);
const loading = ref(false);
const loadingMore = ref(false);
const listError = ref("");
const authError = ref("");
const selected = ref<Torrent | null>(null);
const detail = ref<Torrent | null>(null);
const detailLive = ref<Record<string, unknown>>({});
const addOpen = ref(false);
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
    authError.value = t("token.invalid");
    tokenInitial.value = api.getToken();
    authed.value = false;
    return;
  }
  const message = error instanceof Error ? error.message : t("toast.error");
  if (inList) {
    listError.value = message;
  } else {
    showToast(message);
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
    const [sessionData, labelData] = await Promise.all([
      api.getSession(),
      api.getLabels(),
    ]);
    session.value = sessionData;
    labels.value = labelData.labels;
    noLabelCount.value = labelData.no_label;
    authError.value = "";
    authed.value = true;
    connectEvents();
    resetList();
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

function onLongPress(torrent: Torrent): void {
  selected.value = torrent;
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

function handleSessionEvent(event: TorrentEvent): void {
  if (session.value) Object.assign(session.value, event.fields);
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

async function applyAction(payload: ActionPayload): Promise<void> {
  const torrent = selected.value;
  if (!torrent) return;
  selected.value = null;
  try {
    if (payload.kind === "pause") {
      const result = await api.pauseTorrent(torrent.id);
      api.updateTorrent(torrent, { state: result.state });
      showToast(t("toast.paused"));
    } else if (payload.kind === "resume") {
      const result = await api.resumeTorrent(torrent.id);
      api.updateTorrent(torrent, { state: result.state });
      showToast(t("toast.resumed"));
    } else if (payload.kind === "queue") {
      await api.queueTorrent(torrent.id, payload.action ?? "");
      showToast(t("toast.queue"));
    } else if (payload.kind === "label") {
      const result = await api.setLabel(torrent.id, payload.label ?? "");
      api.updateTorrent(torrent, { label: result.label });
      showToast(t("toast.label"));
    } else if (payload.kind === "remove") {
      const result = await api.removeTorrent(torrent.id, payload.remove_data ?? false);
      if (result.removed) {
        torrents.value = torrents.value.filter((row) => row.id !== torrent.id);
        total.value = Math.max(0, total.value - 1);
        showToast(t("toast.removed"));
      }
    }
  } catch (error) {
    reportError(error);
  }
}

function showGate(): void {
  tokenInitial.value = api.getToken();
  authError.value = "";
  authed.value = false;
}

function submitToken(token: string): void {
  if (!token) return;
  api.setToken(token);
  authError.value = "";
  void bootstrap();
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
  window.addEventListener("online", updateOnline);
  window.addEventListener("offline", updateOnline);
  void loadPluginVersion();
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
    :initial-token="tokenInitial"
    :error="authError"
    :cancelable="Boolean(session)"
    :plugin-version="pluginVersion"
    @submit="submitToken"
    @cancel="cancelGate"
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
      <div class="header-stats">
        <span>↓ {{ formatRate(downRate) }}</span>
        <span>↑ {{ formatRate(upRate) }}</span>
        <span>{{ torrentCount }}</span>
      </div>
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
    />

    <main class="list-pane">
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
            @long-press="onLongPress"
            @select="openDetail"
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

    <ContextSheet
      v-if="selected"
      :torrent="selected"
      :labels="labels"
      :no-label-count="noLabelCount"
      @close="selected = null"
      @action="applyAction"
    />

    <TorrentDetail
      v-if="detail"
      :torrent-id="detail.id"
      :live-fields="detailLive"
      :labels="labels"
      :no-label-count="noLabelCount"
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
      @close="addOpen = false"
      @added="onAdded"
      @toast="showToast"
    />

    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </div>
</template>
