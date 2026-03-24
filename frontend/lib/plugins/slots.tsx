"use client";

// Slot-Renderer: rendert Plugin-Komponenten in definierten Shell-Slots

import React from "react";
import { usePluginRegistry } from "./registry";
import { getPluginComponent } from "./registry";

interface SlotProps {
  slotId: string;
  orgSlug: string;
  orgId?: string;
  [key: string]: unknown;
}

export function SlotRenderer({ slotId, orgSlug, orgId, ...props }: SlotProps) {
  const { plugins } = usePluginRegistry(orgId ?? "");

  const mounts = plugins
    .filter(p => p.is_enabled)
    .flatMap(p => {
      const manifest = (p.plugin as unknown as { manifest?: { slots?: Array<{ slot: string; component: string; id: string }> } }).manifest;
      return (manifest?.slots ?? [])
        .filter(s => s.slot === slotId)
        .map(s => ({ pluginSlug: p.plugin.slug, component: s.component, id: s.id }));
    });

  if (mounts.length === 0) return null;

  return (
    <>
      {mounts.map(mount => {
        const Component = getPluginComponent(mount.pluginSlug, mount.component);
        if (!Component) return null;
        return <Component key={mount.id} orgSlug={orgSlug} {...props} />;
      })}
    </>
  );
}

// Definierte Slot-IDs
export const SLOTS = {
  SIDEBAR_MAIN: "sidebar_main",
  SIDEBAR_BOTTOM: "sidebar_bottom",
  TOPBAR_RIGHT: "topbar_right",
  PANEL_RIGHT: "panel_right",
  PANEL_BOTTOM: "panel_bottom",
  DASHBOARD_WIDGET: "dashboard_widget",
  COMMAND_PALETTE: "command_palette",
  CONTEXT_MENU: "context_menu"
} as const;

export type SlotId = (typeof SLOTS)[keyof typeof SLOTS];
