"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, getTenantId, setTenantId } from "./api";
import { setRegion } from "./region";
import type { CurrentTenant, SessionInfo } from "./types";

interface AuthState {
  status: "loading" | "anonymous" | "authenticated";
  session: SessionInfo | null;
  tenant: CurrentTenant | null;
  tenantId: string | null;
  can: (permission: string) => boolean;
  setSession: (session: SessionInfo) => void;
  switchTenant: (tenantId: string) => void;
  signOut: () => Promise<void>;
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function pickTenant(session: SessionInfo, preferred: string | null): string | null {
  const ids = session.memberships.map((m) => m.tenant_id);
  if (preferred && ids.includes(preferred)) return preferred;
  return ids[0] ?? null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthState["status"]>("loading");
  const [session, setSessionState] = useState<SessionInfo | null>(null);
  const [tenantId, setTenantState] = useState<string | null>(null);

  const applySession = useCallback((s: SessionInfo) => {
    const t = pickTenant(s, getTenantId());
    setTenantId(t);
    setTenantState(t);
    setSessionState(s);
    setStatus("authenticated");
  }, []);

  const reload = useCallback(async () => {
    try {
      applySession(await api<SessionInfo>("/auth/me", { tenant: false }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setSessionState(null);
        setStatus("anonymous");
      } else {
        setStatus("anonymous");
      }
    }
  }, [applySession]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const tenantQuery = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => api<CurrentTenant>("/tenant"),
    enabled: status === "authenticated" && !!tenantId,
    staleTime: 60_000,
  });

  const switchTenant = useCallback(
    (id: string) => {
      setTenantId(id);
      setTenantState(id);
      queryClient.clear();
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    try {
      await api("/auth/logout", { method: "POST", tenant: false });
    } finally {
      setSessionState(null);
      setStatus("anonymous");
      queryClient.clear();
    }
  }, [queryClient]);

  // Region conventions (dates, labels) follow the active organization. Set during render so children
  // formatting in the same render already use the right locale.
  setRegion(tenantQuery.data?.tenant.country_code);

  const value = useMemo<AuthState>(() => {
    const perms = new Set(tenantQuery.data?.permissions ?? []);
    return {
      status,
      session,
      tenant: tenantQuery.data ?? null,
      tenantId,
      can: (p: string) => perms.has(p),
      setSession: applySession,
      switchTenant,
      signOut,
      reload,
    };
  }, [status, session, tenantQuery.data, tenantId, applySession, switchTenant, signOut, reload]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
