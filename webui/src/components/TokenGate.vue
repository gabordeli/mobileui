<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { t } from "../i18n";
import type { AuthMode, GatePayload } from "../types";

const props = defineProps<{
  modes: AuthMode[];
  initialToken: string;
  error: string;
  cancelable: boolean;
  pluginVersion: string;
  tokenSet: boolean;
  username?: string;
  level?: number;
}>();
const emit = defineEmits<{
  submit: [payload: GatePayload];
  cancel: [];
  logout: [];
}>();

const available = computed<AuthMode[]>(() =>
  props.modes.length ? props.modes : ["token"],
);
const hasToken = computed(() => available.value.includes("token"));
const hasPassword = computed(() => available.value.includes("password"));
const showTabs = computed(() => hasToken.value && hasPassword.value);
const mode = ref<AuthMode>(hasPassword.value ? "password" : "token");
const token = ref(props.initialToken);
const loginName = ref("");
const password = ref("");
const displayUser = computed(() =>
  props.username === "token" ? t("auth.apiToken") : props.username,
);

watch(hasPassword, (value) => {
  if (value) mode.value = "password";
});

function submit(): void {
  if (mode.value === "password") {
    const name = loginName.value.trim();
    if (!name || !password.value) return;
    emit("submit", { mode: "password", username: name, password: password.value });
    return;
  }
  const value = token.value.trim();
  if (!value) return;
  emit("submit", { mode: "token", token: value });
}
</script>

<template>
  <div class="gate">
    <form class="gate-card" @submit.prevent="submit">
      <div class="gate-brand">Deluge <strong>Mobile</strong></div>

      <div v-if="showTabs" class="gate-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          :aria-selected="mode === 'password'"
          :class="{ active: mode === 'password' }"
          @click="mode = 'password'"
        >
          {{ t("auth.tabPassword") }}
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="mode === 'token'"
          :class="{ active: mode === 'token' }"
          @click="mode = 'token'"
        >
          {{ t("auth.tabToken") }}
        </button>
      </div>

      <template v-if="mode === 'password'">
        <p class="gate-copy">{{ t("auth.copy") }}</p>
        <input
          v-model="loginName"
          type="text"
          autocomplete="username"
          autocapitalize="none"
          :placeholder="t('auth.username')"
          :aria-label="t('auth.username')"
          autofocus
        />
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          :placeholder="t('auth.password')"
          :aria-label="t('auth.password')"
        />
      </template>

      <template v-else>
        <p class="gate-copy">{{ t("token.copy") }}</p>
        <input
          v-model="token"
          type="password"
          autocomplete="current-password"
          :placeholder="t('token.placeholder')"
          :aria-label="t('token.placeholder')"
          autofocus
        />
        <p v-if="!tokenSet" class="gate-hint">{{ t("auth.noToken") }}</p>
      </template>

      <p v-if="error" class="gate-error" role="alert">{{ error }}</p>
      <div class="gate-actions">
        <button class="action primary" type="submit">{{ t("token.login") }}</button>
        <button
          v-if="cancelable"
          class="action"
          type="button"
          @click="emit('cancel')"
        >
          {{ t("token.cancel") }}
        </button>
      </div>

      <div v-if="username" class="gate-identity">
        <p>
          {{ t("auth.loggedIn", { user: displayUser ?? "" }) }}
          <span v-if="level !== undefined && level < 5"> · {{ t("auth.readonly") }}</span>
        </p>
        <button class="action" type="button" @click="emit('logout')">
          {{ t("auth.logout") }}
        </button>
      </div>

      <p v-if="pluginVersion" class="gate-version">MobileUi v{{ pluginVersion }}</p>
    </form>
  </div>
</template>
