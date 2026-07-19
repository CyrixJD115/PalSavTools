/**
 * Svelte action: triggers `onloadmore` when the sentinel scrolls into view.
 *
 * Usage:
 *   <div use:infiniteScroll={{ onloadmore: loadMore, hasMore, loading }}>
 *     ...items...
 *     <div class="sentinel" />  ← observed for intersection
 *   </div>
 *
 * The action sets up an IntersectionObserver on the last child element with
 * class `sentinel` (or the last child if no sentinel exists). When it
 * intersects, `onloadmore` is called — but only when `hasMore` is true and
 * `loading` is false (prevents duplicate fires).
 *
 * Re-runs whenever the params object identity changes, so updating
 * `hasMore`/`loading` flags in your component state is enough.
 */
export interface InfiniteScrollParams {
  onloadmore: () => void | Promise<void>;
  hasMore: boolean;
  loading: boolean;
  rootMargin?: string; // default '200px' — preload before reaching bottom
}

export function infiniteScroll(node: HTMLElement, params: InfiniteScrollParams) {
  let observer: IntersectionObserver | null = null;
  let currentParams = params;

  const rootMargin = params.rootMargin ?? '200px';

  function setup() {
    teardown();
    // Find the sentinel (explicit), else use the last element child.
    const sentinel =
      node.querySelector('.sentinel') ??
      Array.from(node.children).at(-1) ??
      node;
    if (!sentinel) return;

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          if (currentParams.loading || !currentParams.hasMore) continue;
          void currentParams.onloadmore();
        }
      },
      { root: null, rootMargin, threshold: 0 },
    );
    observer.observe(sentinel);
  }

  function teardown() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  }

  setup();

  return {
    update(next: InfiniteScrollParams) {
      currentParams = next;
      // No need to re-observe the same sentinel; the observer callback
      // reads `currentParams` live. But if `hasMore` flipped true again
      // (e.g. after a search change), make sure we're observing.
      if (next.hasMore && !observer) setup();
    },
    destroy() {
      teardown();
    },
  };
}
