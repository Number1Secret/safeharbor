"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useAuth } from "@/lib/providers/AuthProvider";

export function useOrganizationId(): string {
  const { user } = useAuth();
  return user?.organization_id || "";
}

export function useOrganization() {
  const orgId = useOrganizationId();
  return useQuery({
    queryKey: ["organization", orgId],
    queryFn: () => api.getOrganization(orgId),
    enabled: !!orgId,
  });
}

export function useDashboardSummary() {
  const orgId = useOrganizationId();
  return useQuery({
    queryKey: ["dashboard-summary", orgId],
    queryFn: () => api.getDashboardSummary(orgId),
    refetchInterval: 30_000, // Refresh every 30s
    enabled: !!orgId,
  });
}
