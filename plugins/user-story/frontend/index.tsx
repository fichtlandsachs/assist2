"use client";

// Plugin Entry Point
// Registriert alle Plugin-Komponenten in der globalen Plugin-Registry

import { registerPluginComponent } from "@/lib/plugins/registry";
import { StoryList } from "./components/StoryList";
import { StoryDetail } from "./components/StoryDetail";
import { StoryDashboardWidget } from "./components/StoryDashboardWidget";

// Registrierung beim Import
registerPluginComponent(
  "user-story",
  "StoryList",
  StoryList as React.ComponentType<Record<string, unknown>>
);
registerPluginComponent(
  "user-story",
  "StoryDetail",
  StoryDetail as React.ComponentType<Record<string, unknown>>
);
registerPluginComponent(
  "user-story",
  "StoryDashboardWidget",
  StoryDashboardWidget as React.ComponentType<Record<string, unknown>>
);

export { StoryList, StoryDetail, StoryDashboardWidget };
