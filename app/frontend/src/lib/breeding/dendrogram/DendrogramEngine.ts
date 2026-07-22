/**
 * DendrogramEngine — framework-agnostic D3 dendrogram renderer for ONE chain.
 *
 * Renders a single breeding chain as a left-to-right binary tree: the target
 * pal on the LEFT (root), source pals as leaves on the RIGHT, intermediate
 * bred pals in the middle. Every bred node has exactly two parents — this is
 * a proper tree, not a merged DAG, so each chain gets its own clear picture.
 *
 * Layout uses `d3-hierarchy`'s `tree()` (Reingold-Tilford) which produces clean,
 * non-overlapping sibling placement — the look palcalc gets from its custom
 * 2-child layout. We rotate the layout 90° so depth → X (left-to-right) and
 * sibling axis → Y.
 *
 * Edges are orthogonal (right-angle elbow) connectors: source right-edge →
 * horizontal stub → vertical → horizontal into target left-edge. Each edge
 * gets a unique midpoint to guarantee no horizontal segment overlap.
 *
 * Mirrors `MapEngine`: a pure TS class owning the SVG + D3 state, with a thin
 * Svelte wrapper (`ChainDendrogram.svelte`) handling DOM events and lifecycle.
 * Zoom/pan is via `d3.zoom()` applied to the root `<svg>`.
 */
import { select, type Selection } from 'd3-selection';
import { hierarchy, tree, type HierarchyPointNode } from 'd3-hierarchy';
import { zoom, zoomIdentity, zoomTransform, type D3ZoomEvent, type ZoomBehavior } from 'd3-zoom';
import { transition } from 'd3-transition';

import { DENDRO_CONFIG, DENDRO_COLORS } from './constants';
import type {
  NodeHoverCallback,
  NodeSelectCallback,
  TreeNode,
} from './types';
import { assetUrl } from '$lib/utils/assetUrl';

/** A laid-out node enriched with its screen position. */
interface PositionedNode {
  node: TreeNode;
  x: number; // screen X (left → right, depth)
  y: number; // screen Y (top → bottom, sibling axis)
  /** Effective node width for this node (target nodes are wider). */
  w: number;
}

/** A laid-out link — source/target attach points for orthogonal routing. */
interface PositionedLink {
  source: PositionedNode;
  target: PositionedNode;
  sx: number;
  sy: number;
  tx: number;
  ty: number;
  /** Unique midpoint offset to guarantee no horizontal segment overlap. */
  midX: number;
}

export class DendrogramEngine {
  private svg: Selection<SVGSVGElement, unknown, null, undefined>;
  private zoomLayer: Selection<SVGGElement, unknown, null, undefined>;
  private linksLayer: Selection<SVGGElement, unknown, null, undefined>;
  private nodesLayer: Selection<SVGGElement, unknown, null, undefined>;
  private zoomBehavior: ZoomBehavior<SVGSVGElement, unknown>;

  private layoutNodes: PositionedNode[] = [];
  private layoutLinks: PositionedLink[] = [];
  private layoutIndex = new Map<string, PositionedNode>();
  private currentTransform = zoomIdentity;

  selectedId: string | null = null;
  hoveredId: string | null = null;

  /** Passive IDs that matched the user's required filter (tinted green). */
  matchedPassives: Set<string> = new Set();

  /** Display-name resolver for passives ("CraftSpeed_up1" → "Serious"). */
  passiveName: (asset: string) => string = (s) => s;

  callbacks: {
    onSelect?: NodeSelectCallback;
    onHover?: NodeHoverCallback;
  } = {};

  constructor(svgEl: SVGSVGElement) {
    this.svg = select(svgEl);
    this.zoomLayer = this.svg.append('g').attr('class', 'dendro-zoom-layer');
    this.linksLayer = this.zoomLayer.append('g').attr('class', 'dendro-links');
    this.nodesLayer = this.zoomLayer.append('g').attr('class', 'dendro-nodes');

    this.zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([DENDRO_CONFIG.zoom.min, DENDRO_CONFIG.zoom.max])
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        this.currentTransform = event.transform;
        this.zoomLayer.attr('transform', event.transform.toString());
      });
    this.svg.call(this.zoomBehavior);
    this.svg.on('dblclick.zoom', null);
  }

  /**
   * Render one chain's tree. Replaces any prior content.
   */
  render(treeRoot: TreeNode): void {
    this.selectedId = null;
    this.hoveredId = null;
    this.layoutIndex.clear();
    this.layoutNodes = [];
    this.layoutLinks = [];

    // Build d3 hierarchy with custom children accessor: TreeNode.parents holds
    // the two parents for bred nodes; null for leaves.
    const root = hierarchy<TreeNode>(treeRoot, (d) =>
      d.parents ? [...d.parents] : [],
    );

    // d3.tree assigns x = sibling axis, y = depth. nodeSize is
    // [siblingStep, depthStep] so we get vertical spacing between siblings and
    // horizontal spacing between generations.
    const layout = tree<TreeNode>()
      .nodeSize([
        DENDRO_CONFIG.nodeHeight + DENDRO_CONFIG.siblingGap,
        DENDRO_CONFIG.nodeWidth + DENDRO_CONFIG.levelGap,
      ])
      .separation((a, b) => (a.parent === b.parent ? 1 : 1.25));

    const laidOut = layout(root);

    laidOut.each((d: HierarchyPointNode<TreeNode>) => {
      const isTarget = d.data.isTarget === true;
      const w = isTarget ? DENDRO_CONFIG.targetNodeWidth : DENDRO_CONFIG.nodeWidth;
      const positioned: PositionedNode = {
        node: d.data,
        x: d.y,
        y: d.x,
        w,
      };
      this.layoutNodes.push(positioned);
      this.layoutIndex.set(d.data.id, positioned);
    });

    // Build orthogonal links from parent → child.
    // Unique per-edge midpoints: we assign a lane based on the source
    // node index + link index to guarantee no horizontal overlap.
    // Additionally, we track per-target incoming link indices so that
    // links entering the same node don't share the final horizontal
    // segment (which would cause overlapping lines, especially when
    // both parents of a node are identical species with identical trees).
    const targetLinkCount = new Map<string, number>();
    const targetLinkIdx = new Map<string, number>();
    for (const link of laidOut.links()) {
      const tid = link.target.data.id;
      targetLinkCount.set(tid, (targetLinkCount.get(tid) ?? 0) + 1);
    }

    let linkIdx = 0;
    for (const link of laidOut.links()) {
      const sourceData = link.source.data;
      const targetData = link.target.data;
      const source = this.layoutIndex.get(sourceData.id);
      const target = this.layoutIndex.get(targetData.id);
      if (!source || !target) continue;

      const sx = source.x + source.w;
      const sy = source.y;
      const tx = target.x;
      const ty = target.y;

      // Unique midpoint: distribute along the horizontal span between
      // source-right and target-left, offset by link index so sibling
      // edges don't share a horizontal segment.
      const span = tx - sx;
      const laneOffset = (linkIdx % 3) * 6 - 6; // -6, 0, +6
      const midX = sx + span * 0.5 + laneOffset;

      // Spread entry points vertically along the target's left edge so
      // multiple incoming links don't share the same final horizontal
      // segment. For a binary tree, two parents → -3px and +3px offset.
      const tIdx = targetLinkIdx.get(targetData.id) ?? 0;
      targetLinkIdx.set(targetData.id, tIdx + 1);
      const totalIncoming = targetLinkCount.get(targetData.id) ?? 1;
      const entryOffset =
        totalIncoming > 1
          ? ((tIdx / (totalIncoming - 1)) - 0.5) * 8
          : 0;
      const tyAdj = ty + entryOffset;

      this.layoutLinks.push({ source, target, sx, sy, tx, ty: tyAdj, midX });
      linkIdx++;
    }

    this.drawLinks();
    this.drawNodes();
  }

  private drawLinks(): void {
    const sel = this.linksLayer
      .selectAll<SVGPathElement, PositionedLink>('path.dendro-link')
      .data(this.layoutLinks, (d) => `${d.source.node.id}->${d.target.node.id}`);

    sel.exit().remove();
    const enter = sel
      .enter()
      .append('path')
      .attr('class', 'dendro-link')
      .attr('fill', 'none')
      .attr('stroke', DENDRO_COLORS.link)
      .attr('stroke-width', 1.5)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');

    enter
      .merge(sel)
      .attr('d', (d) => orthogonalPath(d.sx, d.sy, d.tx, d.ty, d.midX))
      .attr('stroke', (d) => {
        if (d.source.node.id === this.selectedId || d.target.node.id === this.selectedId) {
          return DENDRO_COLORS.linkHighlight;
        }
        return DENDRO_COLORS.link;
      })
      .attr('stroke-width', (d) => {
        if (d.source.node.id === this.selectedId || d.target.node.id === this.selectedId) {
          return 2.5;
        }
        return 1.5;
      })
      .attr('opacity', (d) => {
        // Dim links not connected to the hovered or selected node.
        if (!this.selectedId && !this.hoveredId) return 0.7;
        if (
          d.source.node.id === this.selectedId ||
          d.target.node.id === this.selectedId ||
          d.source.node.id === this.hoveredId ||
          d.target.node.id === this.hoveredId
        ) {
          return 1;
        }
        return 0.2;
      });
  }

  private drawNodes(): void {
    const sel = this.nodesLayer
      .selectAll<SVGGElement, PositionedNode>('g.dendro-node')
      .data(this.layoutNodes, (d) => d.node.id);

    sel.exit().remove();

    const enter = sel
      .enter()
      .append('g')
      .attr('class', 'dendro-node')
      .style('cursor', 'pointer');

    // Card background.
    enter
      .append('rect')
      .attr('class', 'dendro-card')
      .attr('width', (d) => d.w)
      .attr('height', DENDRO_CONFIG.nodeHeight)
      .attr('rx', 8)
      .attr('ry', 8)
      .attr('stroke-width', 2);

    // Icon clip-path (rounded square).
    enter
      .append('clipPath')
      .attr('class', 'dendro-icon-clip')
      .attr('id', (d) => `clip-${cssEscape(d.node.id)}`)
      .append('rect')
      .attr('x', DENDRO_CONFIG.iconPadding)
      .attr('y', DENDRO_CONFIG.iconPadding)
      .attr('width', DENDRO_CONFIG.iconSize)
      .attr('height', DENDRO_CONFIG.iconSize)
      .attr('rx', 6);

    // Pal icon.
    enter
      .append('image')
      .attr('class', 'dendro-icon')
      .attr('x', DENDRO_CONFIG.iconPadding)
      .attr('y', DENDRO_CONFIG.iconPadding)
      .attr('width', DENDRO_CONFIG.iconSize)
      .attr('height', DENDRO_CONFIG.iconSize)
      .attr('preserveAspectRatio', 'xMidYMid slice')
      .attr('clip-path', (d) => `url(#clip-${cssEscape(d.node.id)})`)
      .attr('href', (d) => assetUrl(d.node.icon));

    // Display name.
    enter
      .append('text')
      .attr('class', 'dendro-name')
      .attr('x', DENDRO_CONFIG.iconPadding * 2 + DENDRO_CONFIG.iconSize + 5)
      .attr('y', 20)
      .attr('fill', DENDRO_COLORS.inkPrimary)
      .attr('font-size', 11)
      .attr('font-weight', 600)
      .attr('dominant-baseline', 'middle');

    // Gender glyph.
    enter
      .append('text')
      .attr('class', 'dendro-gender')
      .attr('y', 20)
      .attr('font-size', 11)
      .attr('dominant-baseline', 'middle');

    // Passive chip row (children redrawn on update).
    enter.append('g').attr('class', 'dendro-passives');

    // Source-type dot (leaves only).
    enter
      .append('circle')
      .attr('class', 'dendro-source-dot')
      .attr('cx', (d) => d.w - 8)
      .attr('cy', DENDRO_CONFIG.nodeHeight - 8)
      .attr('r', 4);

    // Step badge (bred nodes only).
    enter
      .append('text')
      .attr('class', 'dendro-step')
      .attr('x', (d) => d.w - 8)
      .attr('y', 13)
      .attr('text-anchor', 'end')
      .attr('font-size', 8)
      .attr('fill', DENDRO_COLORS.inkDim)
      .attr('dominant-baseline', 'middle');

    // ── Target badge (accent label on the root node) ──
    enter
      .append('text')
      .attr('class', 'dendro-target-badge')
      .attr('x', (d) => d.w - 8)
      .attr('y', DENDRO_CONFIG.nodeHeight - 8)
      .attr('text-anchor', 'end')
      .attr('font-size', 8)
      .attr('font-weight', 700)
      .attr('fill', DENDRO_COLORS.accentTarget)
      .attr('dominant-baseline', 'middle')
      .attr('opacity', 0);

    const merged = enter.merge(sel);

    // Position each node — rect is drawn at top-left corner, so shift the
    // whole <g> by (x, y - nodeHeight/2) so (x, y) is the node's center.
    merged.attr(
      'transform',
      (d) => `translate(${d.x},${d.y - DENDRO_CONFIG.nodeHeight / 2})`,
    );

    // Card styling — target node gets accent border & wider card;
    // bred nodes get a subtly darker background for visual tiering.
    merged
      .select<SVGRectElement>('.dendro-card')
      .attr('fill', (d) => {
        if (d.node.id === this.selectedId) return DENDRO_COLORS.bgCardSelected;
        if (d.node.id === this.hoveredId) return DENDRO_COLORS.bgCardHover;
        if (d.node.isBred && !d.node.isTarget) return DENDRO_COLORS.bgCardBred;
        return DENDRO_COLORS.bgCard;
      })
      .attr('stroke', (d) => {
        if (d.node.isTarget) return DENDRO_COLORS.accentTarget;
        if (d.node.id === this.selectedId) return DENDRO_COLORS.accent;
        if (d.node.id === this.hoveredId) return DENDRO_COLORS.accentLight;
        return DENDRO_COLORS.line;
      })
      .attr('stroke-width', (d) => (d.node.isTarget ? 2.5 : 2));

    // Display name + gender glyph.
    merged
      .select<SVGTextElement>('.dendro-name')
      .text((d) => truncate(d.node.display, 14));

    merged
      .select<SVGTextElement>('.dendro-gender')
      .attr('x', (d) => this.genderGlyphX(d.node.display))
      .text((d) => genderGlyph(d.node.gender))
      .attr('fill', (d) => genderColor(d.node.gender));

    // Target badge — show "TARGET" label on the root node.
    merged
      .select<SVGTextElement>('.dendro-target-badge')
      .text((d) => (d.node.isTarget ? 'TARGET' : ''))
      .attr('opacity', (d) => (d.node.isTarget ? 1 : 0));

    // Redraw passive chips.
    const passiveName = this.passiveName;
    const matchedPassives = this.matchedPassives;
    merged.each(function (this: SVGGElement, d: PositionedNode) {
      const g = select(this).select<SVGGElement>('g.dendro-passives');
      const chipX0 = DENDRO_CONFIG.iconPadding * 2 + DENDRO_CONFIG.iconSize + 5;
      const chipY = 38;
      const visible = d.node.passives.slice(0, 3);
      const overflow = d.node.passives.length - visible.length;

      if (overflow > 0) {
        // Show "+N more" compactly instead of comma-separated names.
        const first = visible[0];
        const name = first ? passiveName(first) : '';
        const label =
          name && name.length > 10 ? name.slice(0, 9) + '…' : name;
        const allMatched = visible.every((p) => matchedPassives.has(p));

        g.selectAll<SVGTextElement, string>('text').remove();
        if (label) {
          g.append('text')
            .attr('x', chipX0)
            .attr('y', chipY)
            .attr('font-size', 8)
            .attr('font-weight', allMatched ? 600 : 400)
            .attr('fill', allMatched ? DENDRO_COLORS.passiveMatched : DENDRO_COLORS.inkSecondary)
            .attr('dominant-baseline', 'middle')
            .text(`${label} +${overflow}`);
        }
      } else {
        // Show passives as a compact comma-separated line.
        g.selectAll<SVGTextElement, string>('text').remove();
        if (visible.length) {
          const parts = visible.map((p) => {
            const name = passiveName(p);
            return name.length > 10 ? name.slice(0, 9) + '…' : name;
          });
          const label = parts.join(', ');
          const allMatched = visible.every((p) => matchedPassives.has(p));
          g.append('text')
            .attr('x', chipX0)
            .attr('y', chipY)
            .attr('font-size', 8)
            .attr('font-weight', allMatched ? 600 : 400)
            .attr('fill', allMatched ? DENDRO_COLORS.passiveMatched : DENDRO_COLORS.inkSecondary)
            .attr('dominant-baseline', 'middle')
            .text(label);
        }
      }
    });

    // Source-type dot for leaves.
    merged
      .select<SVGCircleElement>('.dendro-source-dot')
      .attr('fill', (d) =>
        d.node.sourceType
          ? DENDRO_COLORS[d.node.sourceType]
          : DENDRO_COLORS.bgDeep,
      )
      .attr('opacity', (d) => (d.node.sourceType ? 1 : 0));

    // Step badge for bred nodes.
    merged
      .select<SVGTextElement>('.dendro-step')
      .text((d) =>
        d.node.isBred && d.node.stepIndex !== undefined ? `#${d.node.stepIndex + 1}` : '',
      )
      .attr('opacity', (d) => (d.node.isBred ? 1 : 0));
  }

  /** Recompute gender glyph X so it sits just after the display name. */
  private genderGlyphX(display: string): number {
    const nameWidth = truncate(display, 14).length * 6.5;
    return (
      DENDRO_CONFIG.iconPadding * 2 +
      DENDRO_CONFIG.iconSize +
      5 +
      nameWidth +
      5
    );
  }

  /**
   * Hit test a screen point (in SVG client coords, BEFORE zoom transform) and
   * return the node under it, if any.
   */
  hitTestNode(clientX: number, clientY: number): TreeNode | null {
    const t = this.currentTransform;
    const lx = (clientX - t.x) / t.k;
    const ly = (clientY - t.y) / t.k;
    for (const positioned of this.layoutNodes) {
      const nx = positioned.x;
      const ny = positioned.y - DENDRO_CONFIG.nodeHeight / 2;
      if (
        lx >= nx &&
        lx <= nx + positioned.w &&
        ly >= ny &&
        ly <= ny + DENDRO_CONFIG.nodeHeight
      ) {
        return positioned.node;
      }
    }
    return null;
  }

  setHovered(id: string | null): void {
    if (this.hoveredId === id) return;
    this.hoveredId = id;
    this.refreshNodeStyles();
    const node = id ? this.layoutIndex.get(id)?.node ?? null : null;
    this.callbacks.onHover?.(node as any, 0, 0);
  }

  setSelected(id: string | null): void {
    this.selectedId = id;
    this.refreshNodeStyles();
    const node = id ? this.layoutIndex.get(id)?.node ?? null : null;
    this.callbacks.onSelect?.(node as any);
  }

  /** Re-apply selection/hover-dependent styling without re-running layout. */
  private refreshNodeStyles(): void {
    if (!this.layoutNodes.length) return;
    this.nodesLayer
      .selectAll<SVGGElement, PositionedNode>('g.dendro-node')
      .select<SVGRectElement>('.dendro-card')
      .attr('fill', (d) => {
        if (d.node.id === this.selectedId) return DENDRO_COLORS.bgCardSelected;
        if (d.node.id === this.hoveredId) return DENDRO_COLORS.bgCardHover;
        if (d.node.isBred && !d.node.isTarget) return DENDRO_COLORS.bgCardBred;
        return DENDRO_COLORS.bgCard;
      })
      .attr('stroke', (d) => {
        if (d.node.isTarget) return DENDRO_COLORS.accentTarget;
        if (d.node.id === this.selectedId) return DENDRO_COLORS.accent;
        if (d.node.id === this.hoveredId) return DENDRO_COLORS.accentLight;
        return DENDRO_COLORS.line;
      })
      .attr('stroke-width', (d) => (d.node.isTarget ? 2.5 : 2));

    this.linksLayer
      .selectAll<SVGPathElement, PositionedLink>('path.dendro-link')
      .attr('stroke', (d) => {
        if (d.source.node.id === this.selectedId || d.target.node.id === this.selectedId) {
          return DENDRO_COLORS.linkHighlight;
        }
        return DENDRO_COLORS.link;
      })
      .attr('stroke-width', (d) => {
        if (d.source.node.id === this.selectedId || d.target.node.id === this.selectedId) {
          return 2.5;
        }
        return 1.5;
      })
      .attr('opacity', (d) => {
        if (!this.selectedId && !this.hoveredId) return 0.7;
        if (
          d.source.node.id === this.selectedId ||
          d.target.node.id === this.selectedId ||
          d.source.node.id === this.hoveredId ||
          d.target.node.id === this.hoveredId
        ) {
          return 1;
        }
        return 0.2;
      });
  }

  /** Get a node by id (for tooltips / detail panels). */
  getNode(id: string): TreeNode | null {
    return this.layoutIndex.get(id)?.node ?? null;
  }

  /** Fit the whole tree inside the SVG viewport. */
  fit(): void {
    if (!this.layoutNodes.length) return;
    const xs = this.layoutNodes.map((n) => n.x);
    const ys = this.layoutNodes.map((n) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs) + Math.max(...this.layoutNodes.map((n) => n.w));
    const minY = Math.min(...ys) - DENDRO_CONFIG.nodeHeight / 2;
    const maxY = Math.max(...ys) + DENDRO_CONFIG.nodeHeight / 2;
    const treeW = Math.max(maxX - minX, 1);
    const treeH = Math.max(maxY - minY, 1);

    const svgEl = this.svg.node();
    if (!svgEl) return;
    const w = svgEl.clientWidth;
    const h = svgEl.clientHeight;
    if (!w || !h) return;

    const scale = Math.min(
      (w - DENDRO_CONFIG.fitMargin * 2) / treeW,
      (h - DENDRO_CONFIG.fitMargin * 2) / treeH,
      DENDRO_CONFIG.zoom.max,
    );
    const clamped = Math.max(scale, DENDRO_CONFIG.zoom.min);
    const tx = (w - treeW * clamped) / 2 - minX * clamped;
    const ty = (h - treeH * clamped) / 2 - minY * clamped;
    const t = zoomIdentity.translate(tx, ty).scale(clamped);
    this.svg
      .transition()
      .duration(DENDRO_CONFIG.animation.durationMs)
      .call(this.zoomBehavior.transform, t);
  }

  /** Zoom by a factor around the center of the viewport. */
  zoomBy(factor: number): void {
    this.zoomBehavior.scaleBy(
      this.svg.transition().duration(DENDRO_CONFIG.animation.durationMs),
      factor,
    );
  }

  /** Reset zoom + pan to fit. */
  reset(): void {
    this.fit();
  }

  /** Current zoom scale. */
  getZoomScale(): number {
    return zoomTransform(this.svg.node()!).k;
  }

  /** Tear down — removes all SVG children. */
  destroy(): void {
    this.svg.selectAll('*').remove();
    this.svg.on('.zoom', null);
  }
}

// ---- helpers --------------------------------------------------------------

/**
 * Build an orthogonal "elbow" SVG path between two points.
 *
 * Shape: start → horizontal to unique midpoint X → vertical to target Y →
 * horizontal into target. Every edge gets its own `midX` (computed in render())
 * so sibling edges never share a horizontal segment.
 */
function orthogonalPath(
  sx: number,
  sy: number,
  tx: number,
  ty: number,
  midX: number,
): string {
  return `M${sx},${sy} H${midX} V${ty} H${tx}`;
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max - 1) + '…';
}

function genderGlyph(gender?: string | null): string {
  switch (gender) {
    case 'Male':
      return '♂';
    case 'Female':
      return '♀';
    default:
      return ''; // bred children are WILDCARD — no glyph
  }
}

function genderColor(gender?: string | null): string {
  switch (gender) {
    case 'Male':
      return DENDRO_COLORS.male;
    case 'Female':
      return DENDRO_COLORS.female;
    default:
      return DENDRO_COLORS.wildcard;
  }
}

/**
 * DOM-safe id escape for `url(#clip-...)` references. `CSS.escape` handles all
 * edge cases; fall back to a sanitizing regex on older browsers.
 */
function cssEscape(s: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(s);
  }
  return s.replace(/[^a-zA-Z0-9_-]/g, '_');
}
