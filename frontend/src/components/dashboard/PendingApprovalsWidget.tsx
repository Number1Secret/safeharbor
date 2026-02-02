"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import type { CalculationRun } from "@/types";

export function PendingApprovalsWidget() {
  const orgId = useOrganizationId();
  const { data, isLoading } = useQuery({
    queryKey: ["calculation-runs", orgId],
    queryFn: () => api.listCalculationRuns(orgId),
  });

  const pendingRuns: CalculationRun[] = (data?.runs || []).filter(
    (r: CalculationRun) => r.status === "pending_approval"
  );

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Pending Approvals
        </h2>
        <Link
          href="/approvals"
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          View all
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-50 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : pendingRuns.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <p className="text-sm">No pending approvals</p>
          <p className="text-xs mt-1">All calculation runs are up to date</p>
        </div>
      ) : (
        <div className="space-y-3">
          {pendingRuns.slice(0, 5).map((run) => (
            <div
              key={run.id}
              className="flex items-center justify-between p-4 bg-amber-50 border border-amber-200 rounded-lg"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">
                  {run.period_start} - {run.period_end}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {run.total_employees} employees &middot;{" "}
                  {formatCurrency(run.total_combined_credit)} total credits
                </p>
              </div>
              <div className="flex gap-2">
                <Link
                  href={`/calculations/${run.id}`}
                  className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Review
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatCurrency(value: string | null | undefined): string {
  if (!value) return "$0";
  const num = parseFloat(value);
  if (isNaN(num)) return "$0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(num);
}
