"use client";

import { useAuth } from "@/hooks/useAuth";
import { cn, roleColor } from "@/lib/utils";

interface HeaderProps {
  title: string;
}

export function Header({ title }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      {user && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-600">{user.full_name || user.email}</span>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
              roleColor(user.role)
            )}
          >
            {user.role.replace("_", " ")}
          </span>
        </div>
      )}
    </header>
  );
}
