"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import type { VaultEntry, RetroAuditReport } from "@/types";

type Tab = "vault" | "retro-audit";

export default function CompliancePage() {
  const [activeTab, setActiveTab] = useState<Tab>("vault");

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compliance</h1>
          <p className="text-sm text-gray-500 mt-1">
            Audit vault, integrity verification, and retro-audit reports
          </p>
        </div>
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Download Audit Pack
        </button>
      </div>

      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          <button
            onClick={() => setActiveTab("vault")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "vault"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Compliance Vault
          </button>
          <button
            onClick={() => setActiveTab("retro-audit")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "retro-audit"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Retro-Audit
          </button>
        </nav>
      </div>

      {activeTab === "vault" ? <VaultPanel /> : <RetroAuditPanel />}
    </div>
  );
}

function VaultPanel() {
  const orgId = useOrganizationId();

  const { data: entries, isLoading } = useQuery({
    queryKey: ["vault-entries", orgId],
    queryFn: () => api.getVaultEntries(orgId),
  });

  const { data: integrity, isLoading: checkingIntegrity } = useQuery({
    queryKey: ["vault-integrity", orgId],
    queryFn: () => api.verifyVaultIntegrity(orgId),
  });

  const vaultEntries: VaultEntry[] = entries?.entries || [];

  return (
    <div className="space-y-6">
      {/* Integrity Status */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Chain Integrity
        </h3>
        {checkingIntegrity ? (
          <div className="h-16 bg-gray-50 rounded-lg animate-pulse" />
        ) : integrity?.is_valid ? (
          <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-green-900">Hash Chain Verified</p>
              <p className="text-sm text-green-700">
                All {integrity?.entries_checked || 0} entries verified. SHA-256 chain intact.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 p-4 bg-red-50 rounded-lg border border-red-200">
            <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <div>
              <p className="font-medium text-red-900">Integrity Issue Detected</p>
              <p className="text-sm text-red-700">
                {integrity?.error || "Chain verification failed. Contact support."}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Vault Entries */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">
            Audit Ledger Entries
          </h3>
        </div>
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-14 bg-gray-50 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : vaultEntries.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">No vault entries yet</p>
            <p className="text-sm text-gray-400 mt-1">
              Entries are created when calculations are finalized
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {vaultEntries.map((entry) => (
              <div key={entry.id} className="px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-1 rounded">
                    #{entry.sequence_number}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {entry.entry_type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {entry.summary || "No summary"}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs font-mono text-gray-400">
                    {entry.entry_hash.slice(0, 16)}...
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(entry.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RetroAuditPanel() {
  const orgId = useOrganizationId();
  const [report, setReport] = useState<RetroAuditReport | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.generateRetroAudit(orgId, { tax_year: new Date().getFullYear() - 1 }),
    onSuccess: (data) => setReport(data),
  });

  return (
    <div className="space-y-6">
      {!report ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">Retro-Audit Report</h3>
          <p className="text-sm text-gray-500 mt-2 max-w-md mx-auto">
            Analyze prior-year data to identify discrepancies between estimated and correct
            OBBB qualified amounts. Identifies penalty exposure and corrective opportunities.
          </p>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="mt-6 px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? "Generating..." : "Generate Retro-Audit Report"}
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <SummaryCard
              label="Employees Analyzed"
              value={report.total_employees_analyzed.toString()}
              color="gray"
            />
            <SummaryCard
              label="With Discrepancies"
              value={report.employees_with_discrepancies.toString()}
              color="orange"
            />
            <SummaryCard
              label="Total Discrepancy"
              value={`$${Number(report.total_discrepancy).toLocaleString()}`}
              color="red"
            />
            <SummaryCard
              label="Penalty Exposure"
              value={`$${Number(report.potential_penalty_exposure).toLocaleString()}`}
              color="red"
            />
          </div>

          {/* Risk Distribution */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Risk Distribution</h3>
            <div className="flex gap-3">
              {Object.entries(report.risk_distribution).map(([level, count]) => (
                <div
                  key={level}
                  className={`flex-1 p-4 rounded-lg border ${
                    level === "critical"
                      ? "bg-red-50 border-red-200"
                      : level === "high"
                      ? "bg-orange-50 border-orange-200"
                      : level === "medium"
                      ? "bg-yellow-50 border-yellow-200"
                      : "bg-green-50 border-green-200"
                  }`}
                >
                  <p className="text-2xl font-bold">{count}</p>
                  <p className="text-xs text-gray-600 capitalize mt-1">{level} Risk</p>
                </div>
              ))}
            </div>
          </div>

          {/* Top Issues */}
          <div className="bg-white rounded-xl border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-900">Top Issues</h3>
            </div>
            <div className="divide-y divide-gray-100">
              {report.top_issues.map((issue, i) => (
                <div key={i} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span
                        className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          issue.severity === "critical"
                            ? "bg-red-100 text-red-700"
                            : issue.severity === "high"
                            ? "bg-orange-100 text-orange-700"
                            : issue.severity === "medium"
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-green-100 text-green-700"
                        }`}
                      >
                        {issue.severity}
                      </span>
                      <p className="text-sm font-medium text-gray-900">{issue.title}</p>
                    </div>
                    <span className="text-sm font-medium text-gray-600">
                      ${issue.impact.toLocaleString()} impact
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1 ml-16">{issue.description}</p>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => setReport(null)}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Generate New Report
          </button>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: "gray" | "orange" | "red" | "green";
}) {
  const bg =
    color === "red"
      ? "bg-red-50 border-red-200"
      : color === "orange"
      ? "bg-orange-50 border-orange-200"
      : color === "green"
      ? "bg-green-50 border-green-200"
      : "bg-gray-50 border-gray-200";

  return (
    <div className={`p-4 rounded-xl border ${bg}`}>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-600 mt-1">{label}</p>
    </div>
  );
}
