"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { User, TokenResponse } from "@/types";
import { apiRequest, setTokens, clearTokens, getAccessToken } from "@/lib/api/client";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithAtlassian: () => void;
  loginWithGitHub: () => void;
  register: (email: string, password: string, displayName: string, organizationName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const _noop = async () => {};
const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: _noop,
  loginWithAtlassian: () => {},
  loginWithGitHub: () => {},
  register: _noop,
  logout: _noop,
  refreshUser: _noop,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    try {
      const me = await apiRequest<User>("/api/v1/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      fetchUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiRequest<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    setTokens(data.access_token, data.refresh_token);
    await fetchUser();
    const orgs = await apiRequest<{ slug: string }[]>("/api/v1/organizations");
    if (orgs.length > 0) {
      router.push(`/${orgs[0].slug}/dashboard`);
    } else {
      router.push("/setup");
    }
  };

  const _handleOAuthPopup = useCallback((startUrl: string, popupName: string) => {
    const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "";

    const handleMessage = async (e: MessageEvent) => {
      if (e.origin !== APP_URL) return;
      if (e.data?.type !== "workspace_login") return;
      window.removeEventListener("message", handleMessage);

      const { access_token, refresh_token } = e.data as {
        access_token: string;
        refresh_token: string;
        user: { email: string; name: string };
      };
      setTokens(access_token, refresh_token ?? "");
      await fetchUser();
      const orgs = await apiRequest<{ slug: string }[]>("/api/v1/organizations");
      if (orgs.length > 0) {
        router.push(`/${orgs[0].slug}/dashboard`);
      } else {
        router.push("/setup");
      }
    };

    apiRequest<{ auth_url: string }>(startUrl)
      .then(({ auth_url }) => {
        window.open(auth_url, popupName, "width=600,height=700");
        window.addEventListener("message", handleMessage);
      })
      .catch(console.error);
  }, [router, fetchUser]);

  const loginWithAtlassian = useCallback(() => {
    _handleOAuthPopup("/api/v1/auth/atlassian/start", "atlassian_login");
  }, [_handleOAuthPopup]);

  const loginWithGitHub = useCallback(() => {
    _handleOAuthPopup("/api/v1/auth/github/start", "github_login");
  }, [_handleOAuthPopup]);

  const register = async (email: string, password: string, displayName: string, organizationName: string) => {
    const data = await apiRequest<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName, organization_name: organizationName })
    });
    setTokens(data.access_token, data.refresh_token);
    await fetchUser();
    router.push("/");
  };

  const logout = async () => {
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) {
      await apiRequest("/api/v1/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh })
      }).catch(() => {});
    }
    clearTokens();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{
      user, isLoading,
      isAuthenticated: !!user,
      login, loginWithAtlassian, loginWithGitHub, register, logout,
      refreshUser: fetchUser
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
