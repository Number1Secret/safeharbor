"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/utils/api";
import { useOrganizationId } from "@/lib/hooks/useOrganization";
import { clsx } from "clsx";
import type { Integration } from "@/types";

const statusConfig: Record<string, { label: string; className: string }> = {
  connected: { label: "Connected", className: "bg-green-100 text-green-700" },
  pending: { label: "Pending", className: "bg-blue-100 text-blue-700" },
  error: { label: "Error", className: "bg-red-100 text-red-700" },
  expired: { label: "Expired", className: "bg-yellow-100 text-yellow-700" },
  revoked: { label: "Revoked", className: "bg-gray-100 text-gray-700" },
};

export function IntegrationStatusWidget() {
  const orgId = useOrganizationId();
  const { data, isLoading } = useQuery({
    queryKey: ["integrations", orgId],
    queryFn: () => api.listIntegrations(orgId),
  });

  const integrations: Integration[] = data?.integrations || [];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
        <Link
          href="/integrations"
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          Manage
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-10 bg-gray-50 rounded animate-pulse" />
          ))}
        </div>
      ) : integrations.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-sm text-gray-500">No integrations connected</p>
          <Link
            href="/integrations"
            className="text-sm text-blue-600 hover:text-blue-700 mt-2 inline-block"
          >
            Connect your first integration
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {integrations.map((integration) => {
            const status = statusConfig[integration.status] || statusConfig.pending;
            return (
              <div
                key={integration.id}
                className="flex items-center justify-between py-2"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center text-xs font-bold text-gray-600 uppercase">
                    {integration.provider.slice(0, 2)}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900 capitalize">
                      {integration.provider}
                    </p>
                    <p className="text-xs text-gray-400 capitalize">
                      {integration.provider_category}
                    </p>
                  </div>
                </div>
                <span
                  className={clsx(
                    "text-xs px-2 py-1 rounded-full font-medium",
                    status.className
                  )}
                >
                  {status.label}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
