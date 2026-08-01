import axios from "axios";
import { useAuthStore } from "@/stores/authStore";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("aegis_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

export function logoutAndRedirect() {
  if (typeof window === "undefined") return;
  useAuthStore.getState().clearAuth();
  window.location.href = "/login";
}

// Shared across concurrent 401s so a burst of failed requests triggers exactly
// one refresh call, not one per request. A plain axios.post (not `api`) so
// this never re-enters this same response interceptor.
let refreshPromise: Promise<string> | null = null;

export async function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const currentRefreshToken = useAuthStore.getState().refreshToken;
      if (!currentRefreshToken) throw new Error("No refresh token available");
      const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: currentRefreshToken,
      });
      useAuthStore.getState().setTokens(data.access_token, data.refresh_token);
      return data.access_token as string;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const config = err.config;
    const skipRefresh = config?.headers?.["X-Skip-Auth-Refresh"];

    if (err.response?.status === 401 && typeof window !== "undefined" && !skipRefresh && !config?._retried) {
      config._retried = true;
      try {
        const newAccessToken = await refreshAccessToken();
        config.headers.Authorization = `Bearer ${newAccessToken}`;
        return api(config);
      } catch {
        logoutAndRedirect();
        return Promise.reject(err);
      }
    }

    if (err.response?.status === 401 && typeof window !== "undefined") {
      logoutAndRedirect();
    }

    return Promise.reject(err);
  }
);

export const streamUrl = (path: string) =>
  `${BASE_URL}/api/v1${path}`;
