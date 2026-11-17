import * as Sentry from "@sentry/vue";
import { createApp } from "vue";

import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import "./styles.css";
import "./theme";
import App from "./App.vue";

const app = createApp(App);
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  Sentry.init({
    app,
    dsn: sentryDsn,
    release: `mobileui-web@${__APP_VERSION__}`,
    environment: import.meta.env.PROD ? "production" : "development",
    tracesSampleRate: 0,
  });
}

app.config.errorHandler = (error, _instance, info) => {
  Sentry.captureException(error, { extra: { info } });
  console.error(error);
};
app.mount("#app");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // HTTP LAN hosts are not a secure context; the app still works online.
    });
  });
}
