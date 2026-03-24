"use client";

import { registerPluginComponent } from "@/lib/plugins/registry";
import { UnreadCountWidget } from "./components/UnreadCountWidget";

registerPluginComponent(
  "inbox",
  "UnreadCountWidget",
  UnreadCountWidget as React.ComponentType<Record<string, unknown>>
);

export { UnreadCountWidget };
