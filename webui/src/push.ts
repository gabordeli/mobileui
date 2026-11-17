export function pushSupported(): boolean {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function notificationPermission(): NotificationPermission | null {
  if (!("Notification" in window)) return null;
  return Notification.permission;
}

export function requestPermission(): Promise<NotificationPermission> {
  return Notification.requestPermission();
}

export function decodeKey(value: string): Uint8Array {
  const base64 = value.replaceAll("-", "+").replaceAll("_", "/");
  const padded = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  );
  const raw = atob(padded);
  return Uint8Array.from(raw, (char) => char.codePointAt(0) ?? 0);
}

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function subscribe(publicKey: string): Promise<PushSubscription> {
  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  if (existing) return existing;
  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: decodeKey(publicKey) as BufferSource,
  });
}

export async function unsubscribe(): Promise<string | null> {
  const current = await currentSubscription();
  if (!current) return null;
  const endpoint = current.endpoint;
  await current.unsubscribe();
  return endpoint;
}
