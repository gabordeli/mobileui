const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function trapFocus(container: HTMLElement): () => void {
  const previous = document.activeElement as HTMLElement | null;
  const app = document.getElementById("app");
  app?.setAttribute("inert", "");

  const focusable = () =>
    Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
  focusable()[0]?.focus();

  const onKeyDown = (event: KeyboardEvent): void => {
    if (event.key !== "Tab") return;
    const items = focusable();
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items.at(-1)!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  container.addEventListener("keydown", onKeyDown);
  return () => {
    container.removeEventListener("keydown", onKeyDown);
    app?.removeAttribute("inert");
    previous?.focus?.();
  };
}
