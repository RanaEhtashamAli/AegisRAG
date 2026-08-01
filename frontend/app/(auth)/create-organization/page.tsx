"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { tenantsService } from "@/services/tenants";
import { authService } from "@/services/auth";
import { useAuthStore } from "@/stores/authStore";
import { getApiErrorMessage } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SLUG_MIN_LENGTH = 3;

export default function CreateOrganizationPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const refreshToken = useAuthStore((s) => s.refreshToken);
  const setAuth = useAuthStore((s) => s.setAuth);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    }
  }, [token, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (slug.length < SLUG_MIN_LENGTH) {
      setError(`Slug must be at least ${SLUG_MIN_LENGTH} characters.`);
      return;
    }
    if (!SLUG_PATTERN.test(slug)) {
      setError("Slug must be lowercase letters, numbers, and hyphens only.");
      return;
    }
    setLoading(true);
    try {
      await tenantsService.create(name, slug);
      const me = await authService.me();
      if (token && refreshToken) setAuth(token, refreshToken, me);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(getApiErrorMessage(err, "Could not create organization"));
    } finally {
      setLoading(false);
    }
  }

  if (!token) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">AegisRAG</CardTitle>
          <CardDescription>Name your organization</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="orgName">
                Organization name
              </label>
              <Input
                id="orgName"
                type="text"
                placeholder="Acme Corp"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="orgSlug">
                Organization slug
              </label>
              <Input
                id="orgSlug"
                type="text"
                placeholder="acme-corp"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                required
                minLength={SLUG_MIN_LENGTH}
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Creating…" : "Create organization"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
