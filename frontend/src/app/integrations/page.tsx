"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import type { Integration } from "@/types";

const PROVIDERS: Record<
  string,
  { name: string; category: string; description: string }
> = {
  adp: { name: "ADP", category: "Payroll", description: "Workforce Now payroll and HR data" },
  gusto: { name: "Gusto", category: "Payroll", description: "Modern payroll, benefits, and HR" },
  paychex: { name: "Paychex", category: "Payroll", description: "Payroll and HR services" },
  quickbooks: { name: "QuickBooks", category: "Payroll", description: "QuickBooks Payroll and accounting" },
  toast: { name: "Toast", category: "POS", description: "Restaurant POS and tip management" },
  square: { name: "Square", category: "POS", description: "Payments, POS, and team management" },
  clover: { name: "Clover", category: "POS", description: "POS system for restaurants and retail" },
  deputy: { name: "Deputy", category: "Timekeeping", description: "Shift scheduling and time tracking" },
  bamboohr: { name: "BambooHR", category: "HRIS", description: "HR information system" },
  rippling: { name: "Rippling", category: "HRIS", description: "Unified workforce platform" },
};

const STATUS_STYLES: Record<string, { dot: string; label: string; bg: string }> = {
  connected: { dot: "bg-green-500", label: "Connected", bg: "bg-green-50 border-green-200" },
  pending: { dot: "bg-blue-500 animate-pulse", label: "Pending", bg: "bg-blue-50 border-blue-200" },
  error: { dot: "bg-red-500", label: "Error", bg: "bg-red-50 border-red-200" },
  expired: { dot: "bg-yellow-500", label: "Expired", bg: "bg-yellow-50 border-yellow-200" },
  revoked: { dot: "bg-gray-400", label: "Revoked", bg: "bg-gray-50 border-gray-200" },
};

export default function IntegrationsPage() {
  const orgId = useOrganizationId();
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const { data, isLoading } = useQuery({
    queryKey: ["integrations", orgId],
    queryFn: () => api.listIntegrations(orgId),
  });

  const integrations: Integration[] = data?.integrations || [];
  const connectedProviders = new Set(integrations.map((i) => i.provider));

  const allProviders = Object.entries(PROVIDERS).filter(
    ([, p]) => categoryFilter === "all" || p.category.toLowerCase() === categoryFilter
  );

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
          <p className="text-sm text-gray-500 mt-1">
            Connect payroll, POS, timekeeping, and HRIS systems
          </p>
        </div>
      </div>

      {/* Connected Integrations */}
      {integrations.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">Connected</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {integrations.map((integration) => {
              const provider = PROVIDERS[integration.provider];
              const status = STATUS_STYLES[integration.status] || STATUS_STYLES.pending;

              return (
                <div
                  key={integration.id}
                  className={`p-5 rounded-xl border ${status.bg}`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-white rounded-lg border border-gray-200 flex items-center justify-center text-sm font-bold text-gray-700">
                        {(provider?.name || integration.provider)[0]}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">
                          {provider?.name || integration.provider}
                        </p>
                        <p className="text-xs text-gray-500">
                          {provider?.category || integration.provider_category}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <div className={`w-2 h-2 rounded-full ${status.dot}`} />
                      <span className="text-xs font-medium text-gray-600">
                        {status.label}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>
                      {integration.last_sync_at
                        ? `Last sync: ${new Date(integration.last_sync_at).toLocaleString()}`
                        : "Never synced"}
                    </span>
                    <button className="text-blue-600 hover:text-blue-700 font-medium">
                      Sync Now
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Available Integrations */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">
          {integrations.length > 0 ? "Available" : "Connect an Integration"}
        </h2>

        <div className="flex gap-2">
          {["all", "payroll", "pos", "timekeeping", "hris"].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                categoryFilter === cat
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {cat === "all"
                ? "All"
                : cat === "pos"
                ? "POS"
                : cat === "hris"
                ? "HRIS"
                : cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {allProviders.map(([key, provider]) => {
            const isConnected = connectedProviders.has(key);

            return (
              <div
                key={key}
                className="p-5 bg-white rounded-xl border border-gray-200 hover:border-gray-300 transition-colors"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-10 h-10 bg-gray-50 rounded-lg border border-gray-200 flex items-center justify-center text-sm font-bold text-gray-500">
                    {provider.name[0]}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {provider.name}
                    </p>
                    <span className="text-xs text-gray-400">
                      {provider.category}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mb-4">
                  {provider.description}
                </p>
                <button
                  disabled={isConnected}
                  className={`w-full py-2 text-xs font-medium rounded-lg transition-colors ${
                    isConnected
                      ? "bg-green-50 text-green-700 border border-green-200 cursor-default"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {isConnected ? "Connected" : "Connect"}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
