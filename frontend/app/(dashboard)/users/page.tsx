"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usersService } from "@/services/users";
import { useAuth } from "@/hooks/useAuth";
import { cn, roleColor } from "@/lib/utils";
import type { User } from "@/types";

const ROLES = ["analyst", "viewer", "compliance_officer", "tenant_admin"];

export default function UsersPage() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("analyst");
  const [inviteToken, setInviteToken] = useState<string | null>(null);

  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ["users"],
    queryFn: () => usersService.list(),
  });

  const inviteMutation = useMutation({
    mutationFn: () => usersService.invite(inviteEmail, inviteRole),
    onSuccess: (data) => {
      setInviteToken(data.invite_token);
      setInviteEmail("");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });

  const roleUpdateMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) =>
      usersService.updateRole(id, role),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => usersService.deactivate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });

  const isAdmin = me?.role === "tenant_admin";

  return (
    <div className="flex flex-col">
      <Header title="User Management" />
      <div className="p-6 space-y-4">
        {isAdmin && (
          <Card>
            <CardHeader>
              <CardTitle>Invite User</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Input
                  className="w-64"
                  placeholder="email@company.com"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  type="email"
                />
                <select
                  className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900"
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                <Button
                  onClick={() => inviteMutation.mutate()}
                  disabled={!inviteEmail || inviteMutation.isPending}
                  size="sm"
                >
                  {inviteMutation.isPending ? "Inviting…" : "Send Invite"}
                </Button>
              </div>
              {inviteToken && (
                <div className="rounded-md bg-slate-50 p-3 text-sm">
                  <p className="font-medium text-slate-700 mb-1">Invite token (share with user):</p>
                  <code className="break-all text-xs text-slate-600">{inviteToken}</code>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => setInviteToken(null)}
                  >
                    Dismiss
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">User</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Role</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-600">Status</th>
                  {isAdmin && (
                    <th className="px-4 py-3 text-right font-medium text-slate-600">Actions</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{u.full_name || u.email}</div>
                      <div className="text-slate-400 text-xs">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
                          roleColor(u.role)
                        )}
                      >
                        {u.role.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                          u.is_active
                            ? "bg-green-100 text-green-800"
                            : "bg-red-100 text-red-800"
                        )}
                      >
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    {isAdmin && (
                      <td className="px-4 py-3 text-right">
                        {u.id !== me?.id && (
                          <div className="flex items-center justify-end gap-2">
                            <select
                              className="h-8 rounded border border-slate-200 bg-white px-2 text-xs text-slate-900"
                              defaultValue={u.role}
                              onChange={(e) =>
                                roleUpdateMutation.mutate({ id: u.id, role: e.target.value })
                              }
                            >
                              {ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </select>
                            {u.is_active && (
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => {
                                  if (confirm("Deactivate this user?"))
                                    deactivateMutation.mutate(u.id);
                                }}
                              >
                                Deactivate
                              </Button>
                            )}
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
