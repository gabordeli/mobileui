<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  initialToken: string;
  error: string;
  cancelable: boolean;
}>();
const emit = defineEmits<{ submit: [token: string]; cancel: [] }>();

const token = ref(props.initialToken);
</script>

<template>
  <div class="gate">
    <form class="gate-card" @submit.prevent="emit('submit', token.trim())">
      <div class="gate-brand">Deluge <strong>Mobile</strong></div>
      <p class="gate-copy">
        Add meg a plugin API-tokenjét. A token a Deluge host
        <code>mobileui.conf</code> fájljában van.
      </p>
      <input
        v-model="token"
        type="password"
        autocomplete="current-password"
        placeholder="API token"
        aria-label="API token"
        autofocus
      />
      <p v-if="error" class="gate-error" role="alert">{{ error }}</p>
      <div class="gate-actions">
        <button class="action primary" type="submit">Belépés</button>
        <button
          v-if="cancelable"
          class="action"
          type="button"
          @click="emit('cancel')"
        >
          Mégse
        </button>
      </div>
    </form>
  </div>
</template>
