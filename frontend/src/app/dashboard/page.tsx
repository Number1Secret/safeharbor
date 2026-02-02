"use client";

import { CreditSummaryCards } from "@/components/dashboard/CreditSummaryCards";
import { PendingApprovalsWidget } from "@/components/dashboard/PendingApprovalsWidget";
import { IntegrationStatusWidget } from "@/components/dashboard/IntegrationStatusWidget";
import { ComplianceAlerts } from "@/components/dashboard/ComplianceAlerts";

export default function DashboardPage() {
  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            OBBB Tax Credit Overview
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            Approve &amp; Sync
          </button>
          <button className="px-4 py-2 text-sm bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors">
            Download Audit Pack
          </button>
        </div>
      </div>

      {/* Hero Metrics */}
      <CreditSummaryCards />

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <PendingApprovalsWidget />
        </div>
        <div className="space-y-6">
          <IntegrationStatusWidget />
          <ComplianceAlerts />
        </div>
      </div>
    </div>
  );
}
