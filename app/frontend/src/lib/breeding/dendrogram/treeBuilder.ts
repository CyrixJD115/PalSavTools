/**
 * Rebuild a recursive binary tree from a flattened `Chain`.
 *
 * `Chain.steps` is topologically sorted (parents before children; last step's
 * child == `chain.target`), but each step only stores tribe strings — no node
 * references. We reconstruct the tree by matching each step's `parent_a` /
 * `parent_b` to either:
 *   - an earlier bred step whose `child` matches (internal node), or
 *   - a `chain.sources` entry (leaf).
 *
 * Leaves always get fresh node ids (a tribe can appear as multiple distinct
 * leaves, e.g. when self-breeding). Bred nodes use `${tribe}#bred${stepIndex}`
 * which is unique because each step index is unique.
 *
 * The resulting tree is "upside down" relative to breeding direction — the
 * target is the root, source pals are the leaves. This matches palcalc's
 * `BreedingTree` and gives a natural left-to-right dendrogram.
 *
 * An optional `maxDepth` parameter truncates the tree at a given depth from
 * the root (target = depth 0). Nodes at maxDepth become leaves (parents are
 * stripped), which is useful for the per-generation graph view.
 */
import type { BreedablePal, Chain, ChainSource, DirectResultItem } from '$types/index';
import type { TreeNode } from './types';

export function chainToTree(
  chain: Chain,
  palMap: Map<string, BreedablePal>,
  maxDepth?: number,
): TreeNode {
  // tribe -> bred node (last step that produced this tribe wins).
  const bredNodes = new Map<string, TreeNode>();
  // tribe -> leaf counter (for unique ids when the same species appears twice).
  const leafCounter = new Map<string, number>();
  // Clone counter — ensures cloned nodes get unique ids across the tree.
  let cloneCounter = 0;

  const makeLeaf = (tribe: string, source?: ChainSource): TreeNode => {
    const n = (leafCounter.get(tribe) ?? 0) + 1;
    leafCounter.set(tribe, n);
    const pal = palMap.get(tribe);
    return {
      id: `${tribe}#leaf${n}`,
      tribe,
      display: source?.display ?? pal?.display_name ?? tribe,
      icon: pal?.icon ?? null,
      gender: source?.gender ?? null,
      passives: source?.passives ?? [],
      sourceType: source?.type,
      isBred: false,
      parents: null,
    };
  };

  // Resolve a parent reference: bred node if a prior step produced it, else a
  // fresh leaf sourced from `chain.sources`.
  const resolveParent = (tribe: string): TreeNode => {
    const bred = bredNodes.get(tribe);
    if (bred) return bred;
    const src = chain.sources.find((s) => s.pal === tribe);
    return makeLeaf(tribe, src);
  };

  for (let i = 0; i < chain.steps.length; i++) {
    const step = chain.steps[i];
    const pal = palMap.get(step.child);
    let parentA = resolveParent(step.parent_a);
    let parentB = resolveParent(step.parent_b);
    // When both parents resolve to the SAME object reference (same species,
    // same bred node), the d3 hierarchy would collapse them into one branch,
    // causing missing/overlapping connector lines. Deep-clone one parent so
    // they become independent tree branches.
    if (parentA === parentB) {
      parentB = deepCloneNode(parentB, leafCounter, cloneCounter++);
    }
    const node: TreeNode = {
      id: `${step.child}#bred${i}`,
      tribe: step.child,
      display: pal?.display_name ?? step.child,
      icon: pal?.icon ?? null,
      // Bred children are WILDCARD (solver assigns Gender.WILDCARD).
      gender: null,
      passives: [...step.inherited_passives],
      isBred: true,
      stepIndex: i,
      parents: [parentA, parentB],
    };
    bredNodes.set(step.child, node);
  }

  // 0-gen chain: target was already in the pool, no breeding required.
  if (chain.steps.length === 0) {
    const src = chain.sources.find((s) => s.pal === chain.target);
    const leaf = makeLeaf(chain.target, src);
    leaf.isTarget = true;
    return leaf;
  }

  const root = bredNodes.get(chain.target);
  if (!root) {
    // Defensive: shouldn't happen given solver contract, but avoid crashing.
    const leaf = makeLeaf(chain.target, chain.sources.find((s) => s.pal === chain.target));
    leaf.isTarget = true;
    return leaf;
  }
  root.isTarget = true;

  // Apply maxDepth pruning if specified (target = depth 0).
  if (maxDepth !== undefined && maxDepth >= 0) {
    return pruneTree(root, maxDepth, 0);
  }

  return root;
}

/**
 * Prune a tree so nodes at `maxDepth` become leaves.
 * Used by the per-generation graph view to show only up to a selected depth.
 */
function pruneTree(node: TreeNode, maxDepth: number, currentDepth: number): TreeNode {
  if (currentDepth >= maxDepth) {
    // Strip parents — this node becomes a leaf in the pruned view.
    return { ...node, parents: null, isBred: false };
  }
  if (node.parents) {
    return {
      ...node,
      parents: [
        pruneTree(node.parents[0], maxDepth, currentDepth + 1),
        pruneTree(node.parents[1], maxDepth, currentDepth + 1),
      ],
    };
  }
  return node;
}

/**
 * Convert a DirectResultItem into a simple 3-node tree (child as root,
 * parent_a and parent_b as leaves). Used by Direct mode's graph view.
 */
export function directToTreeNode(
  result: DirectResultItem,
  palMap: Map<string, BreedablePal>,
): TreeNode {
  const childPal = palMap.get(result.child);
  const parentAPal = palMap.get(result.parent_a);
  const parentBPal = palMap.get(result.parent_b);

  return {
    id: `${result.child}#direct`,
    tribe: result.child,
    display: result.child_display || childPal?.display_name || result.child,
    icon: result.child_icon || childPal?.icon || null,
    gender: null,
    passives: [],
    isBred: true,
    isTarget: true,
    parents: [
      {
        id: `${result.parent_a}#direct-leaf`,
        tribe: result.parent_a,
        display: parentAPal?.display_name || result.parent_a,
        icon: parentAPal?.icon || null,
        gender: null,
        passives: [],
        sourceType: 'selected',
        isBred: false,
        parents: null,
      },
      {
        id: `${result.parent_b}#direct-leaf`,
        tribe: result.parent_b,
        display: parentBPal?.display_name || result.parent_b,
        icon: parentBPal?.icon || null,
        gender: null,
        passives: [],
        sourceType: 'selected',
        isBred: false,
        parents: null,
      },
    ],
  };
}

/**
 * Deep-clone a TreeNode and all its descendants, generating fresh IDs
 * so the clone is independent in the d3 hierarchy.
 * Used when both parents of a step resolve to the same node (same species,
 * same bred history) — we need two distinct branches, not two references
 * to the same object.
 */
function deepCloneNode(
  node: TreeNode,
  leafCounter: Map<string, number>,
  cloneTag: number,
): TreeNode {
  if (node.parents) {
    return {
      ...node,
      id: `${node.id}#clone${cloneTag}`,
      parents: [
        deepCloneNode(node.parents[0], leafCounter, cloneTag),
        deepCloneNode(node.parents[1], leafCounter, cloneTag),
      ],
    };
  }
  // Leaf — generate a fresh unique id using the leaf counter
  const n = (leafCounter.get(node.tribe) ?? 0) + 1;
  leafCounter.set(node.tribe, n);
  return {
    ...node,
    id: `${node.tribe}#clone${cloneTag}-leaf${n}`,
  };
}

/** Count nodes + depth — useful for sizing the viewport before layout. */
export function treeStats(root: TreeNode): { nodes: number; depth: number } {
  let nodes = 0;
  let depth = 0;
  const walk = (n: TreeNode, d: number) => {
    nodes++;
    depth = Math.max(depth, d);
    if (n.parents) {
      walk(n.parents[0], d + 1);
      walk(n.parents[1], d + 1);
    }
  };
  walk(root, 0);
  return { nodes, depth };
}
