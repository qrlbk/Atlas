"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { api, getStoredToken } from "@/lib/api";

export function useDashboardState() {
  const [schoolId, setSchoolId] = useState<number>(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const bump = useCallback(() => {
    setIsAuthenticated(Boolean(getStoredToken()));
    setRefreshKey((prev) => prev + 1);
  }, []);

  useLayoutEffect(() => {
    setIsAuthenticated(Boolean(getStoredToken()));
  }, []);

  useEffect(() => {
    function handleAuthExpired() {
      setIsAuthenticated(false);
      setRefreshKey((prev) => prev + 1);
    }
    window.addEventListener("atlas-auth-expired", handleAuthExpired as EventListener);
    return () => window.removeEventListener("atlas-auth-expired", handleAuthExpired as EventListener);
  }, []);

  useEffect(() => {
    if (!getStoredToken()) return;
    void api
      .listSchools()
      .then((schools) => {
        if (schools.length && schools[0]?.id) setSchoolId(schools[0].id);
      })
      .catch(() => {});
  }, [refreshKey]);

  return { schoolId, refreshKey, isAuthenticated, bump };
}
