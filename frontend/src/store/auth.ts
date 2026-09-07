import axios from "axios";
import { create } from "zustand";
import { persist } from "zustand/middleware";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
  refresh: () => Promise<string | null>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      setTokens: (access, refresh) => set({ accessToken: access, refreshToken: refresh }),
      logout: () => set({ accessToken: null, refreshToken: null }),
      refresh: async () => {
        const rt = get().refreshToken;
        if (!rt) return null;
        try {
          const { data } = await axios.post(`${baseURL}/api/auth/refresh`, {
            refresh_token: rt,
          });
          set({ accessToken: data.access_token, refreshToken: data.refresh_token });
          return data.access_token as string;
        } catch {
          set({ accessToken: null, refreshToken: null });
          return null;
        }
      },
    }),
    { name: "paper-trading-auth" },
  ),
);
