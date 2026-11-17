<script setup lang="ts">
import { ref } from "vue";

import { t } from "../i18n";

const props = defineProps<{
  initialToken: string;
  error: string;
  cancelable: boolean;
  pluginVersion: string;
}>();
const emit = defineEmits<{ submit: [token: string]; cancel: [] }>();

const token = ref(props.initialToken);
</script>

<template>
  <div class="gate">
    <form class="gate-card" @submit.prevent="emit('submit', token.trim())">
      <div class="gate-brand">Deluge <strong>Mobile</strong></div>
      <p class="gate-copy">{{ t("token.copy") }}</p>
      <input
        v-model="token"
        type="password"
        autocomplete="current-password"
        :placeholder="t('token.placeholder')"
        :aria-label="t('token.placeholder')"
        autofocus
      />
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
      <p v-if="pluginVersion" class="gate-version">MobileUi v{{ pluginVersion }}</p>
    </form>
  </div>
</template>
