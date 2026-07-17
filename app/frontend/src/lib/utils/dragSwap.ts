// HTML5 drag-and-drop helpers for pal slot swapping.
//
// Usage in Svelte 5 runes mode (no DOM CustomEvent — uses callbacks instead):
//
//   <div use:draggablePal={pal.instance_id}
//        use:dropTargetPal={{ targetId: pal.instance_id, ondrop: (src) => handleSwap(src, pal.instance_id) }}>
//
// `draggablePal` makes the element a drag source carrying the pal's instance_id.
// `dropTargetPal` listens for dragover/drop and calls `ondrop(sourceId)` when
// another pal is dropped on it. Visual feedback (drag-over class) is toggled
// on the element when a valid drag hovers over it.

export function draggablePal(node: HTMLElement, instanceId: string) {
  node.draggable = true;
  node.style.cursor = 'grab';

  function onDragStart(e: DragEvent) {
    if (!e.dataTransfer) return;
    e.dataTransfer.setData('text/pal-instance-id', instanceId);
    e.dataTransfer.effectAllowed = 'move';
    const el = e.currentTarget as HTMLElement | null;
    if (el) el.style.opacity = '0.5';
  }
  function onDragEnd(e: DragEvent) {
    const el = e.currentTarget as HTMLElement | null;
    if (el) el.style.opacity = '';
  }
  node.addEventListener('dragstart', onDragStart);
  node.addEventListener('dragend', onDragEnd);

  return {
    update(newId: string) {
      instanceId = newId;
    },
    destroy() {
      node.removeEventListener('dragstart', onDragStart);
      node.removeEventListener('dragend', onDragEnd);
      node.draggable = false;
    },
  };
}

export interface DropTargetOptions {
  targetId: string;
  ondrop: (sourceId: string) => void;
}

export function dropTargetPal(node: HTMLElement, opts: DropTargetOptions) {
  function onDragOver(e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    node.classList.add('drag-over');
  }
  function onDragLeave() {
    node.classList.remove('drag-over');
  }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    node.classList.remove('drag-over');
    const sourceId = e.dataTransfer?.getData('text/pal-instance-id');
    if (!sourceId || sourceId === opts.targetId) return;
    opts.ondrop(sourceId);
  }
  node.addEventListener('dragover', onDragOver);
  node.addEventListener('dragleave', onDragLeave);
  node.addEventListener('drop', onDrop);

  return {
    update(newOpts: DropTargetOptions) {
      opts = newOpts;
    },
    destroy() {
      node.removeEventListener('dragover', onDragOver);
      node.removeEventListener('dragleave', onDragLeave);
      node.removeEventListener('drop', onDrop);
    },
  };
}
