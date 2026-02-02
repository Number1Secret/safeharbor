"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import { clsx } from "clsx";
import type { CalculationRun } from "@/types";

const statusConfig: Record<
  string,
  { label: string; className: string }
> = {
  pending: { label: "Pending", className: "bg-gray-100 text-gray-700" },
  syncing: { label: "Syncing", className: "bg-blue-100 text-blue-700" },
  calculating: { label: "Calculating", className: "bg-purple-100 text-purple-700" },
  pending_approval: { label: "Needs Approval", className: "bg-amber-100 text-amber-700" },
  approved: { label: "Approved", className: "bg-green-100 text-green-700" },
  rejected: { label: "Rejected", className: "bg-red-100 text-red-700" },
  finalized: { label: "Finalized", className: "bg-emerald-100 text-emerald-700" },
  error: { label: "Error", className: "bg-red-100 text-red-700" },
};

export function ApprovalQueue() {
  const orgId = useOrganizationId();
  const { data, isLoading } = useQuery({
    queryKey: ["calculation-runs", orgId],
    queryFn: () => api.listCalculationRuns(orgId),
  });

  const runs: CalculationRun[] = data?.runs || [];

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-20 bg-gray-50 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
        <p className="text-gray-500">No calculation runs yet</p>
        <p className="text-sm text-gray-400 mt-1">
          Create a calculation run from the Dashboard
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => {
        const status = statusConfig[run.status] || statusConfig.pending;
        return (
          <div
            key={run.id}
            className="flex items-center justify-between p-5 bg-white rounded-xl border border-gray-200 hover:border-gray-300 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div>
                <p className="text-sm font-semibold text-gray-900">
                  Pay Period: {run.period_start} to {run.period_end}
                </p>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-gray-500">
                    {run.total_employees} employees
                  </span>
                  {run.total_combined_credit && (
                    <span className="text-xs text-gray-500">
                      Total: {formatCurrency(run.total_combined_credit)}
                    </span>
                  )}
                  {run.processed_employees < run.total_employees && (
                    <span className="text-xs text-blue-600">
                      {run.processed_employees}/{run.total_employees} processed
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span
                className={clsx(
                  "text-xs px-3 py-1 rounded-full font-medium",
                  status.className
                )}
              >
                {status.label}
              </span>
              <Link
                href={`/calculations/${run.id}`}
                className="px-4 py-2 text-xs bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                View Details
              </Link>
              {run.status === "pending_approval" && (
                <Link
                  href={`/calculations/${run.id}?action=approve`}
                  className="px-4 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Approve
                </Link>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatCurrency(value: string | null): string {
  if (!value) return "$0";
  const num = parseFloat(value);
  if (isNaN(num)) return "$0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(num);
}
