import { create } from "zustand";
import { persist } from "zustand/middleware";

import { appConfig } from "@/lib/config";
import type { UserRole } from "@/lib/types";

const FALLBACK_ROLES: UserRole[] = ["admin", "hr_admin", "manager", "analyst", "employee"];

function resolveUserRole(input: string | undefined | null): UserRole {
  if (!input) {
    return "admin";
  }
  const normalized = input.trim().toLowerCase();
  return FALLBACK_ROLES.includes(normalized as UserRole) ? (normalized as UserRole) : "admin";
}

type SessionStore = {
  apiKey: string;
  accessToken: string;
  refreshToken: string;
  userRole: UserRole;
  loginEmail: string;
  setApiKey: (value: string) => void;
  setUserRole: (value: UserRole) => void;
  setLoginEmail: (value: string) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  clearTokens: () => void;
};

export const useSessionStore = create<SessionStore>()(
  persist(
    (set) => ({
      apiKey: appConfig.defaultApiKey ?? "",
      accessToken: "",
      refreshToken: "",
      userRole: resolveUserRole(appConfig.defaultUserRole),
      loginEmail: "admin@dattamsha.local",
      setApiKey: (value) => set({ apiKey: value }),
      setUserRole: (value) => set({ userRole: value }),
      setLoginEmail: (value) => set({ loginEmail: value }),
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      clearTokens: () => set({ accessToken: "", refreshToken: "" }),
    }),
    {
      name: "dattamsha.session",
      partialize: (state) => ({
        apiKey: state.apiKey,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        userRole: state.userRole,
        loginEmail: state.loginEmail,
      }),
    },
  ),
);

