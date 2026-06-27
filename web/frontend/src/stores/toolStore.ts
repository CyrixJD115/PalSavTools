import { writable, get } from 'svelte/store';
import type { ToolInfo } from '$types/index';

export const tools = writable<ToolInfo[]>([]);
export const currentTool = writable<ToolInfo | null>(null);
export const isModalOpen = writable(false);
export const isRunning = writable(false);
export const output = writable<string>('');
export const error = writable<string | null>(null);

export function openTool(tool: ToolInfo): void {
  currentTool.set(tool);
  error.set(null);
  output.set('');
  isModalOpen.set(true);
}

export function closeModal(): void {
  isModalOpen.set(false);
  currentTool.set(null);
  error.set(null);
  output.set('');
}

export function resetState(): void {
  tools.set([]);
  currentTool.set(null);
  isModalOpen.set(false);
  isRunning.set(false);
  output.set('');
  error.set(null);
}
