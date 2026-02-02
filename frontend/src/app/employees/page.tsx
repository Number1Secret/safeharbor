"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import Link from "next/link";
import type { Employee } from "@/types";

export default function EmployeesPage() {
  const orgId = useOrganizationId();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "needs_review">("all");

  const { data, isLoading } = useQuery({
    queryKey: ["employees", orgId],
    queryFn: () => api.listEmployees(orgId),
  });

  const employees: Employee[] = data?.employees || [];

  const filtered = employees.filter((e) => {
    const matchesSearch =
      !search ||
      `${e.first_name} ${e.last_name}`.toLowerCase().includes(search.toLowerCase()) ||
      (e.job_title && e.job_title.toLowerCase().includes(search.toLowerCase()));

    const matchesFilter =
      filter === "all" ||
      (filter === "active" && e.employment_status === "active") ||
      (filter === "needs_review" && !e.ttoc_code);

    return matchesSearch && matchesFilter;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Employees</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage employees and TTOC classifications
          </p>
        </div>
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Import Employees
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          placeholder="Search by name or job title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-sm px-4 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <div className="flex gap-2">
          {(["all", "active", "needs_review"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                filter === f
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {f === "all"
                ? "All"
                : f === "active"
                ? "Active"
                : "Needs Review"}
            </button>
          ))}
        </div>
      </div>

      {/* Employee Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-14 bg-gray-50 rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-gray-500">
              {employees.length === 0
                ? "No employees yet. Connect a payroll integration to sync employees."
                : "No employees match your filters."}
            </p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50/50">
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  Employee
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  Job Title
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  TTOC Code
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  Filing Status
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  Status
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                  Hourly Rate
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((employee) => (
                <tr
                  key={employee.id}
                  className="hover:bg-gray-50/50 transition-colors"
                >
                  <td className="px-6 py-4">
                    <Link
                      href={`/employees/${employee.id}`}
                      className="flex items-center gap-3"
                    >
                      <div className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-xs font-semibold">
                        {employee.first_name[0]}
                        {employee.last_name[0]}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-gray-900 hover:text-blue-600">
                          {employee.first_name} {employee.last_name}
                        </p>
                        {employee.department && (
                          <p className="text-xs text-gray-400">{employee.department}</p>
                        )}
                      </div>
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {employee.job_title || "—"}
                  </td>
                  <td className="px-6 py-4">
                    {employee.ttoc_code ? (
                      <span className="text-xs font-mono bg-gray-100 text-gray-700 px-2 py-1 rounded">
                        {employee.ttoc_code}
                      </span>
                    ) : (
                      <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
                        Unclassified
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600 capitalize">
                    {employee.filing_status?.replace(/_/g, " ") || "—"}
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                        employee.employment_status === "active"
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {employee.employment_status === "active" ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {employee.hourly_rate
                      ? `$${Number(employee.hourly_rate).toFixed(2)}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Summary Bar */}
      {employees.length > 0 && (
        <div className="flex items-center gap-6 text-sm text-gray-500">
          <span>{employees.length} total employees</span>
          <span>{employees.filter((e) => e.employment_status === "active").length} active</span>
          <span>
            {employees.filter((e) => !e.ttoc_code).length} unclassified
          </span>
        </div>
      )}
    </div>
  );
}
