<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import * as api from "../api";
import { t } from "../i18n";
import * as push from "../push";

const supported = push.pushSupported();
const state = ref<"loading" | "off" | "on" | "denied">("loading");
const busy = ref(false);
const error = ref("");
const testState = ref("");

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
  } catch {
    state.value = "off";
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
  <p v-if="state === 'denied'" class="limits-hint">{{ t("push.deniedHint") }}</p>
  <p v-if="testState" class="limits-hint">{{ testState }}</p>
  <p v-if="error" class="limits-hint">{{ error }}</p>
</template>
