/**
 * Dendrogram layout config + colors.
 *
 * Colors are mirrored from `tailwind.config.js` tokens so the SVG nodes match
 * the surrounding HTML UI. If a Tailwind token changes, update it here too —
 * there is no build-time link between Tailwind and inline SVG attributes.
 */
export const DENDRO_CONFIG = {
  /** Per-node card size, in layout units. */
  nodeWidth: 168,
  nodeHeight: 52,
  /** Horizontal gap between bred generations (left-to-right depth). */
  levelGap: 72,
  /** Vertical gap between sibling nodes. */
  siblingGap: 14,
  /** Icon size inside each node card. */
  iconSize: 38,
  iconPadding: 7,
  zoom: { min: 0.2, max: 3, factor: 1.2 },
  animation: { durationMs: 400 },
  /** Margin around the fitted tree when calling `fit()`. */
  fitMargin: 32,
  /** Width of the target (root) node card — slightly wider for emphasis. */
  targetNodeWidth: 188,
} as const;

export const DENDRO_COLORS = {
  bgCard: '#161E2D',
  bgCardSelected: '#1A2332',
  bgCardHover: '#1E2633',
  /** Darker background for intermediate (bred) nodes — subtle visual tiering. */
  bgCardBred: '#131A28',
  bgDeep: '#0A1018',
  line: '#2A3A4A',
  lineActive: '#3A4A5A',
  accent: '#3B8ED0',
  accentLight: '#5BA3E0',
  accentCyan: '#00BCD4',
  /** Emphasized border for the target (root) node. */
  accentTarget: '#4FC3F7',
  inkPrimary: '#E3F2FD',
  inkSecondary: '#B0BEC5',
  inkDim: '#546E7A',
  // Source-type accents (matches ChainCard chip colors).
  owned: '#3B8ED0',
  selected: '#4CAF50',
  wild: '#FFB74D',
  // Gender glyph colors.
  male: '#5BA3E0',
  female: '#F48FB1',
  wildcard: '#546E7A',
  // Passive chip colors (matched = green, otherwise muted).
  passiveMatched: '#4CAF50',
  passiveOther: '#3A4A5C',
  // Link curve color — brightened for contrast against the dark background.
  link: '#3A6A9A',
  linkActive: '#5BAEE0',
  /** Brighter link for the path from a selected node to the root. */
  linkHighlight: '#7BC4F0',
} as const;
