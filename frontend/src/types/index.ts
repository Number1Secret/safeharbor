// Core domain types for SafeHarbor frontend
// Aligned with backend Pydantic schemas (backend/schemas/)

export interface Organization {
  id: string;
  name: string;
  ein: string;
  tax_year: number;
  tier: "starter" | "pro" | "enterprise";
  tip_credit_enabled: boolean;
  overtime_credit_enabled: boolean;
  penalty_guarantee_active: boolean;
  status: string;
  workweek_start: string;
  primary_contact_email: string | null;
  primary_contact_name: string | null;
  settings: Record<string, unknown>;
  onboarded_at: string | null;
  employee_count: number;
  connected_integrations: number;
  created_at: string;
  updated_at: string;
}

export interface Employee {
  id: string;
  organization_id: string;
  first_name: string;
  last_name: string;
  hire_date: string;
  employment_status: string;
  termination_date: string | null;
  job_title: string | null;
  department: string | null;
  hourly_rate: number | null;
  is_hourly: boolean;
  filing_status: string | null;
  estimated_annual_magi: number | null;
  ttoc_code: string | null;
  ttoc_title: string | null;
  ttoc_verified: boolean;
  ttoc_verified_at: string | null;
  ytd_gross_wages: number;
  ytd_overtime_hours: number;
  ytd_tips: number;
  ytd_qualified_ot_premium: number;
  ytd_qualified_tips: number;
  created_at: string;
  updated_at: string;
}

export interface CalculationRun {
  id: string;
  organization_id: string;
  run_type: string;
  period_start: string;
  period_end: string;
  tax_year: number;
  status:
    | "pending"
    | "syncing"
    | "calculating"
    | "pending_approval"
    | "approved"
    | "rejected"
    | "finalized"
    | "error";
  error_message: string | null;
  total_employees: number;
  processed_employees: number;
  failed_employees: number;
  flagged_employees: number;
  total_qualified_ot_premium: string | null;
  total_qualified_tips: string | null;
  total_combined_credit: string | null;
  total_phase_out_reduction: string | null;
  previous_run_id: string | null;
  delta_qualified_ot: string | null;
  delta_qualified_tips: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  approved_at: string | null;
  approved_by: string | null;
  finalized_at: string | null;
  rejection_reason: string | null;
  engine_versions: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface CalculationRunSummary {
  id: string;
  run_type: string;
  period_start: string;
  period_end: string;
  status: string;
  total_employees: number;
  processed_employees: number;
  total_combined_credit: string | null;
  created_at: string;
  progress_percentage: number;
}

export interface EmployeeCalculation {
  id: string;
  calculation_run_id: string;
  employee_id: string;
  total_hours: string | null;
  regular_hours: string | null;
  overtime_hours: string | null;
  state_overtime_hours: string | null;
  double_time_hours: string | null;
  gross_wages: string | null;
  hourly_rate_primary: string | null;
  regular_rate: string | null;
  regular_rate_components: Record<string, unknown>;
  overtime_premium_calculated: string | null;
  qualified_ot_premium: string | null;
  cash_tips: string | null;
  charged_tips: string | null;
  total_tips: string | null;
  qualified_tips: string | null;
  ttoc_code: string | null;
  ttoc_confidence: number | null;
  is_tipped_occupation: boolean;
  magi_estimated: string | null;
  filing_status: string | null;
  phase_out_percentage: string | null;
  phase_out_reduction_ot: string | null;
  phase_out_reduction_tips: string | null;
  ot_credit_final: string | null;
  tip_credit_final: string | null;
  combined_credit_final: string | null;
  status: string;
  error_message: string | null;
  anomaly_flags: string[];
  created_at: string;
}

export interface Integration {
  id: string;
  provider: string;
  provider_category: string;
  display_name: string;
  status: "connected" | "expired" | "revoked" | "error" | "pending";
  last_sync_at: string | null;
  last_sync_status: "success" | "partial" | "failed" | null;
  last_sync_records: number | null;
  last_error: string | null;
  created_at: string;
}

export interface TTOCClassification {
  id: string;
  employee_id: string;
  ttoc_code: string;
  ttoc_description: string | null;
  confidence_score: number;
  classification_method: string | null;
  is_tipped_occupation: boolean;
  is_verified: boolean;
  verified_by: string | null;
  created_at: string;
}

export interface RetroAuditReport {
  organization_id: string;
  tax_year: number;
  total_employees_analyzed: number;
  employees_with_discrepancies: number;
  total_estimated_credits: string;
  total_correct_credits: string;
  total_discrepancy: string;
  potential_penalty_exposure: string;
  risk_distribution: Record<string, number>;
  top_issues: Array<{
    type: string;
    severity: string;
    title: string;
    description: string;
    impact: number;
  }>;
}

export interface VaultEntry {
  id: string;
  entry_type: string;
  entry_hash: string;
  previous_hash: string | null;
  sequence_number: number;
  created_at: string;
  actor_id: string | null;
  summary: string | null;
}

// Dashboard-specific types (matches GET /organizations/{org_id}/summary)
export interface DashboardSummary {
  organization_id: string;
  organization_name: string;
  tax_year: number;
  active_employees: number;
  ytd_qualified_ot_premium: number;
  ytd_qualified_tips: number;
  ytd_total_credits: number;
  penalty_guarantee_active: boolean;
  tip_credit_enabled: boolean;
  overtime_credit_enabled: boolean;
}

export interface IntegrationHealth {
  provider: string;
  provider_category: string;
  status: "connected" | "expired" | "error" | "pending";
  last_sync_at: string | null;
}

export interface ComplianceAlert {
  id: string;
  type: "anomaly" | "phase_out" | "missing_classification" | "sync_failure";
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  description: string;
  created_at: string;
  resolved: boolean;
}
