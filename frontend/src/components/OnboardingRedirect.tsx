"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { api, hasAuthToken } from "@/lib/api";

const SKIP_PATHS = ["/start", "/pricing"];

export function OnboardingRedirect({ schoolId }: { schoolId: number }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!hasAuthToken()) return;
    if (SKIP_PATHS.some((p) => pathname.startsWith(p))) return;
    void api
      .schoolReadiness(schoolId)
      .then((r) => {
        const done = Boolean(r.summary.onboarding_completed);
        if (!done && r.status === "unknown") {
          router.replace("/start");
        }
      })
      .catch(() => {});
  }, [schoolId, pathname, router]);

  return null;
}
