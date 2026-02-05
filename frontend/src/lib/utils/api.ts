const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("safeharbor_token");
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options?: RequestInit
  ): Promise<T> {
    const token = getAuthToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options?.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Token expired or invalid — clear token
      if (typeof window !== "undefined") {
        localStorage.removeItem("safeharbor_token");
      }
      throw new Error("Authentication required");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // Auth
  async login(email: string, password: string) {
    return this.request<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    );
  }

  async register(data: { org_name: string; ein: string; email: string; password: string; name: string }) {
    return this.request<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/register",
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  async googleAuth(credential: string) {
    return this.request<{ access_token: string; refresh_token: string; token_type: string }>(
      "/auth/google",
      { method: "POST", body: JSON.stringify({ credential }) }
    );
  }

  async getMe() {
    return this.request<any>("/auth/me");
  }

  // Organizations
  async getOrganization(orgId: string) {
    return this.request<any>(`/organizations/${orgId}`);
  }

  async getDashboardSummary(orgId: string) {
    return this.request<any>(`/organizations/${orgId}/summary`);
  }

  // Employees
  async listEmployees(orgId: string, params?: Record<string, string>) {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    const data = await this.request<any>(`/organizations/${orgId}/employees/${query}`);
    return { employees: data.items, total: data.total, page: data.page, pages: data.pages };
  }

  async getEmployee(orgId: string, empId: string) {
    return this.request<any>(`/organizations/${orgId}/employees/${empId}`);
  }

  // Calculations
  async listCalculationRuns(orgId: string) {
    const data = await this.request<any>(`/organizations/${orgId}/calculations/`);
    return { runs: data.items, total: data.total, page: data.page, pages: data.pages };
  }

  async getCalculationRun(orgId: string, runId: string) {
    return this.request<any>(`/organizations/${orgId}/calculations/${runId}`);
  }

  async createCalculationRun(orgId: string, data: any) {
    return this.request<any>(`/organizations/${orgId}/calculations`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async approveCalculationRun(orgId: string, runId: string, data: any) {
    return this.request<any>(
      `/organizations/${orgId}/calculations/${runId}/approve`,
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  // Integrations
  async listIntegrations(orgId: string) {
    const data = await this.request<any>(`/organizations/${orgId}/integrations/`);
    return { integrations: Array.isArray(data) ? data : data.items || [] };
  }

  async connectIntegration(orgId: string, provider: string, data: any) {
    return this.request<any>(`/organizations/${orgId}/integrations/connect`, {
      method: "POST",
      body: JSON.stringify({ provider, ...data }),
    });
  }

  async syncIntegration(orgId: string, integrationId: string) {
    return this.request<any>(
      `/organizations/${orgId}/integrations/${integrationId}/sync`,
      { method: "POST" }
    );
  }

  // Compliance
  async generateRetroAudit(orgId: string, data: any) {
    return this.request<any>(
      `/organizations/${orgId}/retro-audit`,
      { method: "POST", body: JSON.stringify(data) }
    );
  }

  async getVaultEntries(orgId: string, params?: Record<string, string>) {
    const query = params ? "?" + new URLSearchParams(params).toString() : "";
    const data = await this.request<any>(
      `/organizations/${orgId}/vault/${query}`
    );
    return { entries: Array.isArray(data) ? data : data.entries || [] };
  }

  async verifyVaultIntegrity(orgId: string) {
    return this.request<any>(
      `/organizations/${orgId}/vault/integrity`
    );
  }

  async generateAuditPack(orgId: string, data: any) {
    return this.request<any>(
      `/organizations/${orgId}/audit-pack`,
      { method: "POST", body: JSON.stringify(data) }
    );
  }
}

export const api = new ApiClient(API_BASE);
