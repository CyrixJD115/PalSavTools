// Svelte action: calls `handler` when a click lands outside the bound element.
// Used by dropdown-style components (PalPicker, etc.) to close on outside click
// without each one re-implementing the window listener.
//
//   <div use:clickOutside={() => (open = false)}>…</div>
//
export function clickOutside(node: HTMLElement, handler: () => void) {
  const onPointer = (event: PointerEvent) => {
    if (!event.composedPath().includes(node)) {
      handler();
    }
  };
  // Listen on the next tick so the opening click itself doesn't immediately
  // close the dropdown.
  setTimeout(() => document.addEventListener('pointerdown', onPointer), 0);

  return {
    update(newHandler: () => void) {
      handler = newHandler;
    },
    destroy() {
      document.removeEventListener('pointerdown', onPointer);
    },
  };
}
