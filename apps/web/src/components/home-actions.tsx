"use client";

import Link from "next/link";
import { Button } from "@ai-cio/ui";
import { useAuth } from "@/hooks/use-auth";

export function HomeActions() {
  const { user } = useAuth();

  if (!user) {
    return (
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/login">
          <Button className="bg-white text-slate-900 hover:bg-slate-100">Get started</Button>
        </Link>
        <Link href="/login?mode=login">
          <Button variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
            Sign in
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mt-8 flex flex-wrap gap-3">
      <Link href="/decisions">
        <Button className="bg-white text-slate-900 hover:bg-slate-100">Open decisions</Button>
      </Link>
      <Link href="/onboarding/twin">
        <Button variant="secondary" className="border-white/20 bg-white/10 text-white hover:bg-white/20">
          View profile
        </Button>
      </Link>
    </div>
  );
}
