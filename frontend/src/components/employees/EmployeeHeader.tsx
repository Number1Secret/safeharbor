"use client";

import { clsx } from "clsx";
import type { Employee } from "@/types";

interface EmployeeHeaderProps {
  employee: Employee;
}

export function EmployeeHeader({ employee }: EmployeeHeaderProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center">
            <span className="text-lg font-bold text-blue-600">
              {employee.first_name?.[0]}
              {employee.last_name?.[0]}
            </span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">
              {employee.first_name} {employee.last_name}
            </h1>
            <p className="text-sm text-gray-500">
              {employee.job_title || "No title"} &middot;{" "}
              {employee.department || "No department"}
            </p>
            <div className="flex items-center gap-3 mt-2">
              <span
                className={clsx(
                  "text-xs px-2 py-1 rounded-full font-medium",
                  employee.employment_status === "active"
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-500"
                )}
              >
                {employee.employment_status === "active" ? "Active" : "Inactive"}
              </span>
              {employee.ttoc_code && (
                <span className="text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded-full font-medium">
                  TTOC: {employee.ttoc_code}
                </span>
              )}
              {employee.filing_status && (
                <span className="text-xs text-gray-400 capitalize">
                  Filing: {employee.filing_status}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <button className="px-3 py-2 text-xs bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50">
            Edit
          </button>
          <button className="px-3 py-2 text-xs bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Download Audit Pack
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-100">
        <Stat
          label="Hourly Rate"
          value={employee.hourly_rate ? `$${employee.hourly_rate}` : "N/A"}
        />
        <Stat
          label="YTD Gross Wages"
          value={
            employee.ytd_gross_wages
              ? `$${employee.ytd_gross_wages.toLocaleString()}`
              : "N/A"
          }
        />
        <Stat
          label="TTOC Title"
          value={employee.ttoc_title || "Unclassified"}
        />
        <Stat
          label="Hire Date"
          value={employee.hire_date || "N/A"}
        />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-semibold text-gray-900 mt-0.5">{value}</p>
    </div>
  );
}
