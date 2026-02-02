"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";

interface AuditLogProps {
  employeeId: string;
}

export function AuditLog({ employeeId }: AuditLogProps) {
  const orgId = useOrganizationId();

  const { data, isLoading } = useQuery({
    queryKey: ["vault-entries", orgId, employeeId],
    queryFn: () =>
      api.getVaultEntries(orgId, { employee_id: employeeId }),
  });

  const entries = data?.entries || [];

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="h-48 bg-gray-50 rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Audit Log</h3>
      <p className="text-xs text-gray-500 mb-4">
        Immutable compliance vault entries for this employee
      </p>

      {entries.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-8">
          No audit entries yet
        </p>
      ) : (
        <div className="space-y-2">
          {entries.map((entry: any) => (
            <div
              key={entry.id}
              className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
            >
              <div className="w-6 h-6 bg-gray-200 rounded flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[10px] font-bold text-gray-500">
                  #{entry.sequence_number}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-gray-900">
                    {formatEntryType(entry.entry_type)}
                  </p>
                  <span className="text-xs text-gray-400">
                    {formatDate(entry.created_at)}
                  </span>
                </div>
                {entry.summary && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    {entry.summary}
                  </p>
                )}
                <p className="text-[10px] text-gray-300 mt-1 font-mono truncate">
                  Hash: {entry.entry_hash}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatEntryType(type: string): string {
  const labels: Record<string, string> = {
    calculation: "Calculation Completed",
    classification: "TTOC Classification",
    approval: "Approval Decision",
    write_back: "Write-Back to Payroll",
  };
  return labels[type] || type;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
