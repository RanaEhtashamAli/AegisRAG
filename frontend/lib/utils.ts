import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString();
}

export function classificationColor(level: string): string {
  const map: Record<string, string> = {
    public: "bg-green-100 text-green-800",
    internal: "bg-blue-100 text-blue-800",
    confidential: "bg-yellow-100 text-yellow-800",
    restricted: "bg-red-100 text-red-800",
  };
  return map[level] ?? "bg-gray-100 text-gray-800";
}

/**
 * Extracts a human-readable message from an Axios-style API error.
 *
 * FastAPI's `detail` field is a plain string for 400/401/403/409 errors,
 * but a Pydantic 422 validation error returns `detail` as an array of
 * `{ msg, loc, type }` objects — stringifying that array directly yields
 * the useless literal "[object Object]".
 */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;

  if (typeof detail === "string" && detail.length > 0) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    if (typeof first?.msg === "string" && first.msg.length > 0) {
      return first.msg;
    }
  }

  return fallback;
}

export function roleColor(role: string): string {
  const map: Record<string, string> = {
    tenant_admin: "bg-purple-100 text-purple-800",
    compliance_officer: "bg-blue-100 text-blue-800",
    analyst: "bg-teal-100 text-teal-800",
    viewer: "bg-gray-100 text-gray-800",
  };
  return map[role] ?? "bg-gray-100 text-gray-800";
}
