<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import * as api from "../api";
import type { PushSubscriptionInfo } from "../api";
import { t } from "../i18n";
import * as push from "../push";

const supported = push.pushSupported();
const state = ref<"loading" | "off" | "on" | "denied">("loading");
const busy = ref(false);
const error = ref("");
const testState = ref("");
const devices = ref<PushSubscriptionInfo[]>([]);

const statusText = computed(() => {
  if (!supported) return t("push.unsupported");
  if (state.value === "on") return t("push.on");
  if (state.value === "denied") return t("push.denied");
  return t("push.off");
});

async function refresh(): Promise<void> {
  if (!supported) return;
  try {
    const subscription = await push.currentSubscription();
    if (subscription) {
      state.value = "on";
    } else if (push.notificationPermission() === "denied") {
      state.value = "denied";
    } else {
      state.value = "off";
    }
    await loadDevices();
  } catch {
    state.value = "off";
  }
}

async function loadDevices(): Promise<void> {
  try {
    devices.value = (await api.getPushSubscriptions()).subscriptions;
  } catch {
    devices.value = [];
  }
}

async function revokeDevice(id: string): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await api.removePushSubscription(id);
    await loadDevices();
    testState.value = t("push.revoked");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t("push.error");
  } finally {
    busy.value = false;
  }
}

async function enable(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    if ((await push.requestPermission()) !== "granted") {
      state.value = "denied";
      return;
    }
    const config = await api.getPushConfig();
    const subscription = await push.subscribe(config.public_key);
    await api.subscribePush(subscription.toJSON());
    state.value = "on";
    await loadDevices();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t("push.error");
  } finally {
    busy.value = false;
  }
}

async function disable(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    const endpoint = await push.unsubscribe();
    if (endpoint) await api.unsubscribePush(endpoint);
    state.value = "off";
    await loadDevices();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t("push.error");
  } finally {
    busy.value = false;
  }
}

async function sendTest(): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  testState.value = "";
  try {
    const subscription = await push.currentSubscription();
    if (!subscription) {
      state.value = "off";
      return;
    }
    await api.testPush(subscription.endpoint);
    testState.value = t("push.testSent");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : t("push.error");
  } finally {
    busy.value = false;
  }
}

onMounted(refresh);
</script>

<template>
  <div class="push-toggle">
    <div class="push-text">
      <strong>{{ t("push.title") }}</strong>
      <span>{{ statusText }}</span>
    </div>
    <button
      v-if="supported && state === 'off'"
      class="action"
      :disabled="busy"
      @click="enable"
    >
      {{ t("push.enable") }}
    </button>
    <div v-else-if="supported && state === 'on'" class="push-actions">
      <button class="action" :disabled="busy" @click="sendTest">
        {{ t("push.test") }}
      </button>
      <button class="action" :disabled="busy" @click="disable">
        {{ t("push.disable") }}
      </button>
    </div>
  </div>
  <details v-if="devices.length" class="push-devices">
    <summary>{{ t("push.devices", { count: devices.length }) }}</summary>
    <ul>
      <li v-for="device in devices" :key="device.id">
        <div>
          <strong>{{ device.host }}</strong>
          <small>{{ device.user_agent || "—" }}</small>
        </div>
        <button
          class="action"
          :disabled="busy"
          @click="revokeDevice(device.id)"
        >
          {{ t("push.revoke") }}
        </button>
      </li>
    </ul>
  </details>
  <p v-if="state === 'denied'" class="limits-hint">{{ t("push.deniedHint") }}</p>
  <p v-if="testState" class="limits-hint">{{ testState }}</p>
  <p v-if="error" class="limits-hint">{{ error }}</p>
</template>
