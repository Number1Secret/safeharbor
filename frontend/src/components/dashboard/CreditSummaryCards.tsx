"use client";

import { useDashboardSummary } from "@/lib/hooks/useOrganization";

interface MetricCardProps {
  title: string;
  value: string;
  subtitle?: string;
  trend?: { value: string; direction: "up" | "down" };
  color?: "blue" | "green" | "orange" | "purple";
}

function MetricCard({ title, value, subtitle, trend, color = "blue" }: MetricCardProps) {
  const colorClasses = {
    blue: "bg-blue-50 border-blue-200",
    green: "bg-green-50 border-green-200",
    orange: "bg-orange-50 border-orange-200",
    purple: "bg-purple-50 border-purple-200",
  };

  const textColor = {
    blue: "text-blue-700",
    green: "text-green-700",
    orange: "text-orange-700",
    purple: "text-purple-700",
  };

  return (
    <div className={`rounded-xl border p-6 ${colorClasses[color]}`}>
      <p className="text-sm font-medium text-gray-600">{title}</p>
      <p className={`text-3xl font-bold mt-2 ${textColor[color]}`}>{value}</p>
      {subtitle && (
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      )}
      {trend && (
        <div className="flex items-center gap-1 mt-2">
          <span
            className={
              trend.direction === "up" ? "text-green-600" : "text-red-600"
            }
          >
            {trend.direction === "up" ? "+" : "-"}{trend.value}
          </span>
          <span className="text-xs text-gray-400">vs last period</span>
        </div>
      )}
    </div>
  );
}

export function CreditSummaryCards() {
  const { data, isLoading } = useDashboardSummary();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="rounded-xl border bg-gray-50 p-6 animate-pulse h-32"
          />
        ))}
      </div>
    );
  }

  const summary = data || {
    ytd_total_credits: 0,
    ytd_qualified_ot_premium: 0,
    ytd_qualified_tips: 0,
    active_employees: 0,
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        title="Active Employees"
        value={String(summary.active_employees || 0)}
        subtitle="Currently tracked"
        color="green"
      />
      <MetricCard
        title="Total Credits (YTD)"
        value={formatCurrency(summary.ytd_total_credits)}
        subtitle={`${summary.active_employees || 0} active employees`}
        color="blue"
      />
      <MetricCard
        title="Qualified OT Premium"
        value={formatCurrency(summary.ytd_qualified_ot_premium)}
        subtitle="FLSA Section 7 calculations"
        color="purple"
      />
      <MetricCard
        title="Qualified Tips"
        value={formatCurrency(summary.ytd_qualified_tips)}
        subtitle="Year to date"
        color="orange"
      />
    </div>
  );
}

function formatCurrency(value: string | number | undefined): string {
  if (!value) return "$0";
  const num = typeof value === "string" ? parseFloat(value.replace(/[$,]/g, "")) : value;
  if (isNaN(num)) return "$0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(num);
}
