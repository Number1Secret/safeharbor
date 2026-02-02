"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import { ApprovalQueue } from "@/components/approvals/ApprovalQueue";
import { ClassificationCard } from "@/components/approvals/ClassificationCard";
import { BulkActions } from "@/components/approvals/BulkActions";

type Tab = "calculations" | "classifications";

export default function ApprovalsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("calculations");

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Approval Queue</h1>
        <p className="text-sm text-gray-500 mt-1">
          Review and approve calculation runs and TTOC classifications
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          <button
            onClick={() => setActiveTab("calculations")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "calculations"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            Calculation Runs
          </button>
          <button
            onClick={() => setActiveTab("classifications")}
            className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "classifications"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            TTOC Classifications
          </button>
        </nav>
      </div>

      {activeTab === "calculations" ? (
        <ApprovalQueue />
      ) : (
        <ClassificationReviewPanel />
      )}
    </div>
  );
}

function ClassificationReviewPanel() {
  const orgId = useOrganizationId();
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ["pending-classifications", orgId],
    queryFn: () =>
      api.listEmployees(orgId, { needs_classification: "true" }),
  });

  const employees = data?.employees || [];
  const pendingReview = employees.filter(
    (e: any) => !e.ttoc_code || e.ttoc_needs_review
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selectedIds.size === pendingReview.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pendingReview.map((e: any) => e.id)));
    }
  };

  return (
    <div className="space-y-4">
      {pendingReview.length > 0 && (
        <BulkActions
          selectedCount={selectedIds.size}
          totalCount={pendingReview.length}
          onSelectAll={selectAll}
          onBulkApprove={() => {
            // Bulk approve high-confidence classifications
            setSelectedIds(new Set());
            queryClient.invalidateQueries({
              queryKey: ["pending-classifications"],
            });
          }}
        />
      )}

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-40 bg-gray-50 rounded-xl animate-pulse"
            />
          ))}
        </div>
      ) : pendingReview.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <p className="text-gray-500">
            All classifications are up to date
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {pendingReview.map((employee: any) => (
            <ClassificationCard
              key={employee.id}
              employee={employee}
              isSelected={selectedIds.has(employee.id)}
              onToggleSelect={() => toggleSelect(employee.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
