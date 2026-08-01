"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuthStore } from "@/stores/authStore";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const router = useRouter();

  // Guard: an authenticated user with no tenant (abandoned before creating
  // an organization) has no dashboard to see — send them back to finish setup.
  useEffect(() => {
    if (user && !user.tenant_id) {
      router.replace("/create-organization");
    }
  }, [user, router]);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
