"use client";

import { registerPluginComponent } from "@/lib/plugins/registry";
import { UpcomingEventsWidget } from "./components/UpcomingEventsWidget";

registerPluginComponent(
  "calendar",
  "UpcomingEventsWidget",
  UpcomingEventsWidget as React.ComponentType<Record<string, unknown>>
);

export { UpcomingEventsWidget };
