"use client";

import { useState } from "react";

type Tab = "general" | "users" | "api-keys" | "sso";

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("general");

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Organization configuration and admin controls
        </p>
      </div>

      <div className="border-b border-gray-200">
        <nav className="flex gap-8">
          {([
            { id: "general", label: "General" },
            { id: "users", label: "Users" },
            { id: "api-keys", label: "API Keys" },
            { id: "sso", label: "SSO" },
          ] as const).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === "general" && <GeneralSettings />}
      {activeTab === "users" && <UsersSettings />}
      {activeTab === "api-keys" && <APIKeysSettings />}
      {activeTab === "sso" && <SSOSettings />}
    </div>
  );
}

function GeneralSettings() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
      <div className="p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Organization
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Organization Name
            </label>
            <input
              type="text"
              placeholder="Acme Corp"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              EIN
            </label>
            <input
              type="text"
              placeholder="XX-XXXXXXX"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Calculation Settings
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Workweek Start
            </label>
            <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="monday">Monday</option>
              <option value="sunday">Sunday</option>
              <option value="saturday">Saturday</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Default Filing Status
            </label>
            <select className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="single">Single</option>
              <option value="married_joint">Married Filing Jointly</option>
              <option value="head_of_household">Head of Household</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Auto-Approve Confidence Threshold
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              placeholder="0.95"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              TTOC classifications above this threshold will be auto-approved
            </p>
          </div>
        </div>
      </div>

      <div className="p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">
          Notifications
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Notification Email
            </label>
            <input
              type="email"
              placeholder="admin@company.com"
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Webhook URL
            </label>
            <input
              type="url"
              placeholder="https://..."
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="p-6 flex justify-end">
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Save Changes
        </button>
      </div>
    </div>
  );
}

function UsersSettings() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Invite User
        </button>
      </div>
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-12 text-center">
          <p className="text-gray-500">No users to display</p>
          <p className="text-sm text-gray-400 mt-1">
            Invite team members to collaborate on OBBB compliance
          </p>
        </div>
      </div>
    </div>
  );
}

function APIKeysSettings() {
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Create API Key
        </button>
      </div>
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-12 text-center">
          <p className="text-gray-500">No API keys</p>
          <p className="text-sm text-gray-400 mt-1">
            Create API keys for programmatic access to SafeHarbor
          </p>
        </div>
      </div>
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 text-xs text-gray-500">
        <p className="font-medium text-gray-700 mb-1">API Key Format</p>
        <p>
          Keys are prefixed with <code className="bg-gray-200 px-1 py-0.5 rounded">sh_</code> and
          shown only once at creation. Store them securely.
        </p>
      </div>
    </div>
  );
}

function SSOSettings() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-2">
          Single Sign-On
        </h3>
        <p className="text-sm text-gray-500 mb-6">
          Configure SAML or OIDC for enterprise authentication.
          Available on Enterprise plans.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 border border-gray-200 rounded-xl hover:border-blue-300 transition-colors cursor-pointer">
            <p className="font-semibold text-gray-900 text-sm">SAML 2.0</p>
            <p className="text-xs text-gray-500 mt-1">
              Connect Okta, Azure AD, OneLogin, or any SAML 2.0 provider
            </p>
            <button className="mt-4 px-4 py-2 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
              Configure SAML
            </button>
          </div>
          <div className="p-5 border border-gray-200 rounded-xl hover:border-blue-300 transition-colors cursor-pointer">
            <p className="font-semibold text-gray-900 text-sm">OpenID Connect</p>
            <p className="text-xs text-gray-500 mt-1">
              Connect Google Workspace, Auth0, or any OIDC provider
            </p>
            <button className="mt-4 px-4 py-2 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
              Configure OIDC
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-6 py-4 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-900">
            Configured Providers
          </h3>
        </div>
        <div className="p-12 text-center">
          <p className="text-gray-500">No SSO providers configured</p>
        </div>
      </div>
    </div>
  );
}
