"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { apiRequest } from "@/lib/api/client";

export default function RootPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    apiRequest<{ slug: string }[]>("/api/v1/organizations")
      .then((orgs) => {
        if (orgs.length > 0) {
          router.replace(`/${orgs[0].slug}/dashboard`);
        } else {
          router.replace("/setup");
        }
      })
      .catch(() => router.replace("/login"));
  }, [isAuthenticated, isLoading, router]);

  return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
    </div>
  );
}
