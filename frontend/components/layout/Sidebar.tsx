"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  ClipboardList,
  Users,
  Shield,
  BarChart3,
  Activity,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: [] },
  { href: "/dashboard/documents", label: "Documents", icon: FileText, roles: [] },
  { href: "/dashboard/chat", label: "Chat", icon: MessageSquare, roles: [] },
  {
    href: "/dashboard/audit",
    label: "Audit Log",
    icon: ClipboardList,
    roles: ["tenant_admin", "compliance_officer"],
  },
  {
    href: "/dashboard/users",
    label: "Users",
    icon: Users,
    roles: ["tenant_admin", "compliance_officer"],
  },
  {
    href: "/dashboard/pii",
    label: "PII Findings",
    icon: Shield,
    roles: ["tenant_admin", "compliance_officer"],
  },
  {
    href: "/dashboard/evals",
    label: "Evaluations",
    icon: BarChart3,
    roles: ["tenant_admin"],
  },
  {
    href: "/dashboard/monitoring",
    label: "Monitoring",
    icon: Activity,
    roles: ["tenant_admin"],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const visibleItems = navItems.filter(
    (item) => item.roles.length === 0 || (user && item.roles.includes(user.role))
  );

  return (
    <aside className="flex h-screen w-56 flex-col border-r border-slate-200 bg-white">
      <div className="flex h-16 items-center border-b border-slate-200 px-4">
        <span className="text-lg font-bold text-slate-900">AegisRAG</span>
      </div>

      <nav className="flex-1 overflow-y-auto p-3 space-y-1">
        {visibleItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname === href
                ? "bg-slate-100 text-slate-900"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      <div className="border-t border-slate-200 p-3">
        <div className="mb-2 px-3 text-xs text-slate-500 truncate">{user?.email}</div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}
