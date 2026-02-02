"use client";

import { clsx } from "clsx";
import type { ComplianceAlert } from "@/types";

// Mock alerts for initial render - in production, fetched from API
const mockAlerts: ComplianceAlert[] = [
  {
    id: "1",
    type: "missing_classification",
    severity: "medium",
    title: "3 employees need TTOC classification",
    description: "New hires require occupation code assignment",
    created_at: new Date().toISOString(),
    resolved: false,
  },
];

const severityConfig = {
  low: { bg: "bg-gray-50", border: "border-gray-200", dot: "bg-gray-400" },
  medium: { bg: "bg-yellow-50", border: "border-yellow-200", dot: "bg-yellow-400" },
  high: { bg: "bg-orange-50", border: "border-orange-200", dot: "bg-orange-500" },
  critical: { bg: "bg-red-50", border: "border-red-200", dot: "bg-red-500" },
};

export function ComplianceAlerts() {
  const alerts = mockAlerts.filter((a) => !a.resolved);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Alerts</h2>
        {alerts.length > 0 && (
          <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500">No active alerts</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const config = severityConfig[alert.severity];
            return (
              <div
                key={alert.id}
                className={clsx(
                  "p-3 rounded-lg border",
                  config.bg,
                  config.border
                )}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={clsx("w-2 h-2 rounded-full mt-1.5", config.dot)}
                  />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {alert.title}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {alert.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
