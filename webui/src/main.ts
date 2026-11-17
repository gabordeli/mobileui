import { createApp } from "vue";

import "vue-virtual-scroller/dist/vue-virtual-scroller.css";
import "./styles.css";
import "./theme";
import App from "./App.vue";

createApp(App).mount("#app");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // HTTP LAN hosts are not a secure context; the app still works online.
    });
  });
}
