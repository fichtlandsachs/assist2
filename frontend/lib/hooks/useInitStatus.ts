import useSWR from "swr";
import type { OrgInitStatus } from "@/types";
import { fetcher } from "@/lib/api/client";

export function useInitStatus(orgId: string | undefined) {
  const { data, error, isLoading, mutate } = useSWR<OrgInitStatus>(
    orgId ? `/api/v1/capabilities/orgs/${orgId}/init-status` : null,
    fetcher,
    { revalidateOnFocus: false },
  );
  return {
    initStatus: data,
    isLoading,
    error,
    mutate,
    needsSetup:
      data?.initialization_status === "not_initialized" ||
      data?.initialization_status === "capability_setup_in_progress",
  };
}
