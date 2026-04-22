"use client";

import { useState } from "react";
import { WelcomeScreen } from "./WelcomeScreen";
import { CapabilitySetupScreen } from "./CapabilitySetupScreen";
import type { OrgInitializationStatus } from "@/types";

type WizardScreen = "welcome" | "capability-setup";

interface Props {
  orgId: string;
  orgName: string;
  currentStatus: OrgInitializationStatus;
  onComplete: () => void;
}

export function SetupWizard({ orgId, orgName, currentStatus, onComplete }: Props) {
  const [screen, setScreen] = useState<WizardScreen>(
    currentStatus === "capability_setup_in_progress" ? "capability-setup" : "welcome",
  );

  return (
    <div className="flex flex-col min-h-full">
      {/* Progress indicator */}
      <div className="flex items-center gap-2 px-2 pb-4">
        {(["welcome", "capability-setup"] as WizardScreen[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-full border-2 border-[var(--ink)] flex items-center justify-center text-[10px] font-bold"
              style={{
                background:
                  screen === s || (s === "welcome" && screen === "capability-setup")
                    ? "var(--accent-orange)"
                    : "var(--paper-warm)",
                color: "var(--ink)",
              }}
            >
              {i + 1}
            </div>
            <span
              className="text-xs font-medium hidden sm:inline"
              style={{ color: screen === s ? "var(--ink)" : "var(--ink-faint)" }}
            >
              {s === "welcome" ? "Willkommen" : "Capability Map"}
            </span>
            {i < 1 && <div className="w-8 h-px" style={{ background: "var(--paper-rule2)" }} />}
          </div>
        ))}
      </div>

      {screen === "welcome" && (
        <WelcomeScreen
          orgId={orgId}
          orgName={orgName}
          onNext={() => setScreen("capability-setup")}
        />
      )}

      {screen === "capability-setup" && (
        <CapabilitySetupScreen orgId={orgId} onDone={onComplete} />
      )}
    </div>
  );
}
