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

export function roleColor(role: string): string {
  const map: Record<string, string> = {
    tenant_admin: "bg-purple-100 text-purple-800",
    compliance_officer: "bg-blue-100 text-blue-800",
    analyst: "bg-teal-100 text-teal-800",
    viewer: "bg-gray-100 text-gray-800",
  };
  return map[role] ?? "bg-gray-100 text-gray-800";
}
