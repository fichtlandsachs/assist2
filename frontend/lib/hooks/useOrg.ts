import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { Organization } from "@/types";

export function useOrg(slug: string) {
  const { data, error, isLoading, mutate } = useSWR<Organization[]>(
    "/api/v1/organizations",
    fetcher
  );
  const org = data?.find((o) => o.slug === slug);
  return { org, error, isLoading, mutate };
}

export function useOrgs() {
  const { data, error, isLoading, mutate } = useSWR<Organization[]>(
    "/api/v1/organizations",
    fetcher
  );
  return { orgs: data ?? [], error, isLoading, mutate };
}
