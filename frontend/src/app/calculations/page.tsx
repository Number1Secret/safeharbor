"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import Link from "next/link";
import type { CalculationRun } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  syncing: "bg-blue-100 text-blue-700",
  calculating: "bg-purple-100 text-purple-700",
  pending_approval: "bg-yellow-100 text-yellow-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  finalized: "bg-emerald-100 text-emerald-800",
  error: "bg-red-100 text-red-700",
};

export default function CalculationsPage() {
  const orgId = useOrganizationId();
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const { data, isLoading } = useQuery({
    queryKey: ["calculations", orgId],
    queryFn: () => api.listCalculationRuns(orgId),
  });

  const runs: CalculationRun[] = data?.runs || [];

  const filtered =
    statusFilter === "all"
      ? runs
      : runs.filter((r) => r.status === statusFilter);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Calculations</h1>
          <p className="text-sm text-gray-500 mt-1">
            Pay period calculation runs and qualified amount results
          </p>
        </div>
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          New Calculation Run
        </button>
      </div>

      {/* Status Filters */}
      <div className="flex gap-2 flex-wrap">
        {["all", "pending", "calculating", "pending_approval", "approved", "finalized", "error"].map(
          (s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                statusFilter === s
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {s === "all"
                ? "All"
                : s
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (c) => c.toUpperCase())}
            </button>
          )
        )}
      </div>

      {/* Calculation Runs */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-50 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">
              {runs.length === 0
                ? "No calculation runs yet. Create one to calculate qualified amounts for a pay period."
                : "No runs match the selected filter."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map((run) => (
              <div
                key={run.id}
                className="px-6 py-5 hover:bg-gray-50/50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        Pay Period: {new Date(run.period_start).toLocaleDateString()} &ndash;{" "}
                        {new Date(run.period_end).toLocaleDateString()}
                      </p>
                      <div className="flex items-center gap-3 mt-1">
                        <span
                          className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                            STATUS_STYLES[run.status] || "bg-gray-100 text-gray-700"
                          }`}
                        >
                          {run.status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                        <span className="text-xs text-gray-400">
                          {run.processed_employees}/{run.total_employees} employees
                        </span>
                        <span className="text-xs text-gray-400">
                          Created {new Date(run.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    <div className="text-right">
                      <p className="text-xs text-gray-400">Qualified OT</p>
                      <p className="text-sm font-semibold text-gray-900">
                        {run.total_qualified_ot_premium
                          ? `$${Number(run.total_qualified_ot_premium).toLocaleString()}`
                          : "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-400">Qualified Tips</p>
                      <p className="text-sm font-semibold text-gray-900">
                        {run.total_qualified_tips
                          ? `$${Number(run.total_qualified_tips).toLocaleString()}`
                          : "—"}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-400">Total Credits</p>
                      <p className="text-sm font-bold text-blue-600">
                        {run.total_combined_credit
                          ? `$${Number(run.total_combined_credit).toLocaleString()}`
                          : "—"}
                      </p>
                    </div>

                    {run.status === "pending_approval" && (
                      <Link
                        href="/approvals"
                        className="px-3 py-1.5 text-xs font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        Review
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Summary Stats */}
      {runs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500">Total Runs</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{runs.length}</p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500">Pending Approval</p>
            <p className="text-2xl font-bold text-yellow-600 mt-1">
              {runs.filter((r) => r.status === "pending_approval").length}
            </p>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500">Finalized</p>
            <p className="text-2xl font-bold text-green-600 mt-1">
              {runs.filter((r) => r.status === "finalized").length}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
