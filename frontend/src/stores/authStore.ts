import { create } from "zustand";
import type { CurrentUser } from "@/api/auth";

interface AuthState {
  user: CurrentUser | null;
  setUser: (user: CurrentUser | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
}));
