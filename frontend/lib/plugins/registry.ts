// Plugin-Registry: Lädt aktive Plugins der Org und stellt Nav-Entries bereit

import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { OrgPlugin, PluginNavEntry } from "@/types";

interface PluginRegistryState {
  plugins: OrgPlugin[];
  navEntries: PluginNavEntry[];
  isLoading: boolean;
  error: unknown;
}

export function usePluginRegistry(orgId: string): PluginRegistryState {
  const { data, error, isLoading } = useSWR<{ items: OrgPlugin[] }>(
    orgId ? `/api/v1/organizations/${orgId}/plugins` : null,
    fetcher
  );

  const plugins = data?.items ?? [];

  // Sammle alle nav_entries aus aktiven Plugin-Manifests
  const navEntries: PluginNavEntry[] = plugins
    .filter(p => p.is_enabled)
    .flatMap(p => {
      const manifest = (p.plugin as unknown as { manifest?: { nav_entries?: PluginNavEntry[] } }).manifest;
      return manifest?.nav_entries ?? [];
    })
    .sort((a, b) => a.position - b.position);

  return { plugins, navEntries, isLoading, error };
}

// Globale Plugin-Registry für dynamisch geladene Komponenten
const componentRegistry = new Map<string, React.ComponentType<Record<string, unknown>>>();

export function registerPluginComponent(
  pluginSlug: string,
  componentName: string,
  component: React.ComponentType<Record<string, unknown>>
): void {
  componentRegistry.set(`${pluginSlug}:${componentName}`, component);
}

export function getPluginComponent(
  pluginSlug: string,
  componentName: string
): React.ComponentType<Record<string, unknown>> | undefined {
  return componentRegistry.get(`${pluginSlug}:${componentName}`);
}
