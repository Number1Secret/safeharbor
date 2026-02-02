"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import { EmployeeHeader } from "@/components/employees/EmployeeHeader";
import { CalculationTimeline } from "@/components/employees/CalculationTimeline";
import { CalculationBreakdown } from "@/components/employees/CalculationBreakdown";
import { AuditLog } from "@/components/employees/AuditLog";
import { useState } from "react";

type Tab = "calculations" | "source" | "audit";

export default function EmployeeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const orgId = useOrganizationId();
  const [activeTab, setActiveTab] = useState<Tab>("calculations");

  const { data: employee, isLoading } = useQuery({
    queryKey: ["employee", orgId, id],
    queryFn: () => api.getEmployee(orgId, id),
  });

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="h-32 bg-gray-50 rounded-xl animate-pulse" />
        <div className="h-64 bg-gray-50 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!employee) {
    return (
      <div className="max-w-5xl mx-auto text-center py-12">
        <p className="text-gray-500">Employee not found</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <EmployeeHeader employee={employee} />

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {(
            [
              { key: "calculations", label: "Calculations" },
              { key: "source", label: "Source Data" },
              { key: "audit", label: "Audit Log" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "calculations" && (
        <div className="space-y-6">
          <CalculationTimeline employeeId={id} />
          <CalculationBreakdown employeeId={id} />
        </div>
      )}

      {activeTab === "source" && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Source Data
          </h3>
          <p className="text-sm text-gray-500">
            Raw data from connected payroll, POS, and timekeeping systems.
          </p>
          <div className="mt-4 p-4 bg-gray-50 rounded-lg">
            <pre className="text-xs text-gray-600 overflow-auto">
              {JSON.stringify(employee.raw_data || {}, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {activeTab === "audit" && <AuditLog employeeId={id} />}
    </div>
  );
}
