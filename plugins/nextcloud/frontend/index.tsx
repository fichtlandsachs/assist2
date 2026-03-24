"use client";

import { registerPluginComponent } from "@/lib/plugins/registry";
import { RecentFilesWidget } from "./components/RecentFilesWidget";

registerPluginComponent(
  "nextcloud",
  "RecentFilesWidget",
  RecentFilesWidget as React.ComponentType<Record<string, unknown>>
);

export { RecentFilesWidget };
