"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import { clsx } from "clsx";

interface CalculationTimelineProps {
  employeeId: string;
}

export function CalculationTimeline({ employeeId }: CalculationTimelineProps) {
  const orgId = useOrganizationId();

  // Fetch employee's calculation history
  const { data, isLoading } = useQuery({
    queryKey: ["employee-calculations", orgId, employeeId],
    queryFn: () =>
      api.getEmployee(orgId, employeeId).then((emp) => emp.calculations || []),
  });

  const calculations = data || [];

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="h-48 bg-gray-50 rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Calculation History
      </h3>

      {calculations.length === 0 ? (
        <p className="text-sm text-gray-500">
          No calculations yet for this employee
        </p>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-4 top-2 bottom-2 w-0.5 bg-gray-200" />

          <div className="space-y-6">
            {calculations.map((calc: any, index: number) => (
              <div key={calc.id || index} className="relative flex gap-4">
                {/* Timeline dot */}
                <div
                  className={clsx(
                    "w-8 h-8 rounded-full flex items-center justify-center z-10",
                    calc.status === "approved"
                      ? "bg-green-100"
                      : calc.status === "error"
                      ? "bg-red-100"
                      : "bg-blue-100"
                  )}
                >
                  <div
                    className={clsx(
                      "w-3 h-3 rounded-full",
                      calc.status === "approved"
                        ? "bg-green-500"
                        : calc.status === "error"
                        ? "bg-red-500"
                        : "bg-blue-500"
                    )}
                  />
                </div>

                {/* Content */}
                <div className="flex-1 bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-gray-900">
                      {calc.period_start} - {calc.period_end}
                    </p>
                    <span
                      className={clsx(
                        "text-xs px-2 py-0.5 rounded-full",
                        calc.status === "approved"
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-600"
                      )}
                    >
                      {calc.status}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-4 mt-3">
                    <div>
                      <p className="text-xs text-gray-500">OT Premium</p>
                      <p className="text-sm font-semibold">
                        ${calc.qualified_ot_premium || "0"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Tip Credit</p>
                      <p className="text-sm font-semibold">
                        ${calc.qualified_tips || "0"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Phase-Out</p>
                      <p className="text-sm font-semibold">
                        {calc.phase_out_percentage || "0"}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
