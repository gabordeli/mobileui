import { t } from "./i18n";

export function formatBytes(value: number): string {
  if (!value || value <= 0) return "0 B";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  let digits = 2;
  if (size >= 100) digits = 0;
  else if (size >= 10) digits = 1;
  return `${size.toFixed(digits)} ${units[unit]}`;
}

export function formatRate(value: number): string {
  return `${formatBytes(value)}/s`;
}

export function formatEta(seconds: number): string {
  if (seconds < 0) return "∞";
  if (seconds === 0) return "—";
  if (seconds < 60) return `${Math.round(seconds)} ${t("unit.second")}`;
  if (seconds < 3600) {
    return `${Math.round(seconds / 60)} ${t("unit.minute")}`;
  }
  if (seconds < 86400) {
    return `${Math.round(seconds / 3600)} ${t("unit.hour")}`;
  }
  return `${Math.round(seconds / 86400)} ${t("unit.day")}`;
}

export function formatRatio(ratio: number): string {
  if (ratio < 0) return "∞";
  return ratio.toFixed(2);
}

export function stateClass(state: string): string {
  return `state-${state.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}
