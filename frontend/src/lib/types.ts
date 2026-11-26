/** Types mirroring the API contract (docs/API_SPECIFICATION.md). Money fields are decimal strings. */

export type Money = string;

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  mfa_enabled: boolean;
  last_login_at: string | null;
}

export interface MembershipSummary {
  tenant_id: string;
  tenant_name: string;
  tenant_slug: string;
  role_key: string | null;
  role_name: string | null;
}

export interface SessionInfo {
  user: User;
  memberships: MembershipSummary[];
}

export interface LoginResult {
  mfa_required: boolean;
  mfa_token: string | null;
  session: SessionInfo | null;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  default_currency: string;
  measurement_system: string;
  home_state: string | null;
  timezone: string;
  country_code: string;
  data_region: string;
}

export interface RoleRef {
  id: string;
  key: string;
  name: string;
}

export interface CurrentTenant {
  tenant: Tenant;
  role: RoleRef;
  permissions: string[];
}

export interface Address {
  line1: string | null;
  line2: string | null;
  city: string | null;
  state_code: string | null;
  postal_code: string | null;
  county: string | null;
  country_code: string;
}

export interface CompanyRef {
  id: string;
  name: string;
  company_type: string;
}

export interface Company extends CompanyRef {
  legal_name: string | null;
  trades: string[];
  website: string | null;
  phone: string | null;
  email: string | null;
  notes: string | null;
  is_active: boolean;
  address: Address | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  company_id: string | null;
  first_name: string;
  last_name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  notes: string | null;
  created_at: string;
}

export interface ProjectListItem {
  id: string;
  number: string;
  name: string;
  status: string;
  sector: string;
  delivery_method: string;
  contract_type: string;
  client_company: CompanyRef | null;
  city: string | null;
  state_code: string | null;
  start_date: string | null;
  planned_completion_date: string | null;
  original_contract_value: Money | null;
  currency: string;
  archived_at: string | null;
  updated_at: string;
}

export interface Project {
  id: string;
  number: string;
  name: string;
  description: string | null;
  status: string;
  sector: string;
  project_type: string | null;
  delivery_method: string;
  contract_type: string;
  our_role: string;
  client_company: CompanyRef | null;
  site_address: Address | null;
  start_date: string | null;
  planned_completion_date: string | null;
  actual_completion_date: string | null;
  original_contract_value: Money | null;
  currency: string;
  is_public_works: boolean;
  prevailing_wage: boolean;
  retainage_percent: string | null;
  reporting_period_end_day: number;
  archived_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  financials_visible: boolean;
  can_edit: boolean;
}

export interface ProjectMember {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  project_role: string;
  created_at: string;
}

export interface ProjectParty {
  id: string;
  company: CompanyRef;
  party_role: string;
  notes: string | null;
}

export interface ProjectPhase {
  id: string;
  name: string;
  sequence: number;
  status: string;
  start_date: string | null;
  end_date: string | null;
}

export interface DocumentVersion {
  id: string;
  version_number: number;
  revision_label: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  scan_status: string;
  notes: string | null;
  uploaded_by_id: string | null;
  created_at: string;
}

export interface DocumentItem {
  id: string;
  project_id: string | null;
  title: string;
  category: string;
  discipline: string | null;
  document_number: string | null;
  description: string | null;
  tags: string[] | null;
  current_version_number: number;
  current_version: DocumentVersion | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentDetail extends DocumentItem {
  versions: DocumentVersion[];
}

export interface AuditEvent {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  project_id: string | null;
  summary: string;
  changes: Record<string, unknown> | null;
  actor_user_id: string | null;
  actor_name: string | null;
  occurred_at: string;
}

export interface CurrencyTotal {
  currency: string;
  amount: Money;
  project_count: number;
  projects_without_value: number;
}

export interface DashboardSummary {
  total_projects: number;
  by_status: Record<string, number>;
  by_sector: Record<string, number>;
  live_contract_value: CurrencyTotal[] | null;
  pursuit_value: CurrencyTotal[] | null;
  original_budget: CurrencyTotal[] | null;
  committed_cost: CurrencyTotal[] | null;
  pending_changes: { currency: string; amount: string; count: number; overdue_count: number }[] | null;
  forecast: DashboardForecast[] | null;
  payments: DashboardPayments[] | null;
  upcoming_completions: ProjectListItem[];
  recent_projects: ProjectListItem[];
  recent_activity: AuditEvent[];
  financials_visible: boolean;
  unavailable_metrics: string[];
  unavailable_reason: string;
}

export interface Vocabulary {
  project_statuses: Record<string, string>;
  sectors: Record<string, string>;
  delivery_methods: Record<string, string>;
  contract_types: Record<string, string>;
  our_roles: Record<string, string>;
  project_member_roles: Record<string, string>;
  party_roles: Record<string, string>;
  phase_statuses: Record<string, string>;
  us_states: Record<string, string>;
  company_types: Record<string, string>;
  document_categories: Record<string, string>;
  disciplines: Record<string, string>;
  currencies: string[];
  countries: Record<string, string>;
  measurement_systems: Record<string, string>;
}

export interface Member {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  mfa_enabled: boolean;
  role: RoleRef;
  status: string;
  job_title: string | null;
  created_at: string;
}

export interface Role {
  id: string;
  key: string;
  name: string;
  description: string | null;
  is_system: boolean;
  permission_keys: string[];
  member_count: number;
}

export interface PermissionDef {
  key: string;
  category: string;
  description: string;
}

export interface Invitation {
  id: string;
  email: string;
  role: RoleRef;
  expires_at: string;
  created_at: string;
  status: string;
  accept_url?: string;
  email_sent?: boolean;
}

// --- Phase 2.1: cost codes, estimates, budgets ---------------------------------------------------------
export interface CostCodeSet {
  id: string;
  name: string;
  description: string | null;
  template_key: string;
  level_names: string[];
  is_active: boolean;
  version: number;
  code_count: number;
  created_at: string;
  updated_at: string;
}

export interface CostCode {
  id: string;
  set_id: string;
  parent_id: string | null;
  code: string;
  title: string;
  level: number;
  unit: string | null;
  is_active: boolean;
}

export interface CostCodeRef {
  id: string;
  code: string;
  title: string;
}

export interface CostCodeTemplate {
  key: string;
  name: string;
  level_names: string[];
}

export interface LineCalc {
  labour_unit: string;
  material_unit: string;
  equipment_unit: string;
  subcontract_unit: string;
  other_unit: string;
  unit_cost: string;
  labour_total: string;
  material_total: string;
  equipment_total: string;
  subcontract_total: string;
  other_total: string;
  total: string;
  labour_hours: string;
}

export interface EstimateLine {
  id: string;
  sequence: number;
  cost_code: CostCodeRef | null;
  line_type: string;
  inclusion: "base" | "alternate" | "excluded";
  alternate_label: string | null;
  description: string;
  quantity: string;
  unit: string;
  labour_hours_per_unit: string;
  labour_rate: string;
  material_rate: string;
  material_waste_percent: string;
  equipment_rate: string;
  subcontract_rate: string;
  other_rate: string;
  notes: string | null;
  calc: LineCalc;
}

export interface Markup {
  name: string;
  percent: string;
  basis: "direct_cost" | "cumulative";
  include_in_budget: boolean;
  base_amount: string;
  amount: string;
}

export interface VersionSummary {
  id: string;
  version_number: number;
  status: "draft" | "issued" | "approved";
  label: string | null;
  total: string | null;
  issued_at: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface EstimateVersion extends VersionSummary {
  notes: string | null;
  price_base_date: string | null;
  is_editable: boolean;
  lines: EstimateLine[];
  markups: Markup[];
  totals: {
    direct_cost: string;
    markup_total: string;
    total: string;
    alternates: { label: string; amount: string }[];
    excluded_total: string;
    labour_hours: string;
    components: Record<string, string>;
  };
}

export interface Estimate {
  id: string;
  project_id: string;
  project_number: string;
  project_name: string;
  name: string;
  estimate_type: string;
  cost_code_set_id: string | null;
  currency: string;
  current_version_number: number;
  versions: VersionSummary[];
  can_edit: boolean;
  created_at: string;
  updated_at: string;
}

export interface EstimateCompare {
  from_version: number;
  to_version: number;
  rows: { cost_code: string | null; title: string; from_amount: string; to_amount: string; change: string }[];
  from_total: string;
  to_total: string;
  change: string;
}

export interface BudgetLine {
  id: string;
  sequence: number;
  cost_code: CostCodeRef | null;
  description: string;
  amount: string;
  notes: string | null;
}

export interface Budget {
  id: string;
  project_id: string;
  name: string;
  kind: string;
  status: "draft" | "approved";
  currency: string;
  cost_code_set_id: string | null;
  source_estimate_version_id: string | null;
  source_description: string | null;
  total: string;
  approved_at: string | null;
  created_at: string;
  is_editable: boolean;
  lines: BudgetLine[];
}

// --- Phase 2.2: contracts and commitments --------------------------------------------------------------
export type ContractKind = "contracts" | "commitments";

export interface ContractLineItem {
  id: string;
  sequence: number;
  cost_code: CostCodeRef | null;
  description: string;
  quantity: string | null;
  unit: string | null;
  unit_rate: string | null;
  amount: string;
}

export interface ContractRecord {
  id: string;
  project_id: string;
  project_number: string;
  project_name: string;
  number: string;
  title: string;
  contract_form: string;
  status: "draft" | "executed" | "closed" | "void";
  currency: string;
  cost_code_set_id: string | null;
  retention_percent: string | null;
  retention_terms: string | null;
  payment_terms_days: number | null;
  start_date: string | null;
  completion_date: string | null;
  scope_summary: string | null;
  original_sum: string | null;
  current_total: string;
  approved_changes: string;
  pending_changes: string;
  revised_sum: string | null;
  executed_date: string | null;
  executed_at: string | null;
  closed_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  is_editable: boolean;
  can_execute: boolean;
  lines: ContractLineItem[];
  // prime contracts
  client_company?: CompanyRef | null;
  defects_period_months?: number | null;
  liquidated_damages_amount?: string | null;
  liquidated_damages_period?: "day" | "week" | null;
  bond_required?: boolean;
  bond_percent?: string | null;
  insurance_notes?: string | null;
  // commitments
  commitment_type?: "subcontract" | "purchase_order";
  vendor?: CompanyRef;
  exclusions?: string | null;
}

export interface ContractListItem {
  id: string;
  project_id: string;
  project_number: string;
  project_name: string;
  number: string;
  title: string;
  status: string;
  currency: string;
  counterparty: string | null;
  commitment_type: string | null;
  current_total: string;
  original_sum: string | null;
  revised_sum: string | null;
  executed_date: string | null;
  updated_at: string;
}

export interface ContractVocab {
  prime_forms: Record<string, string>;
  subcontract_forms: Record<string, string>;
  commitment_types: Record<string, string>;
  statuses: Record<string, string>;
}

export interface SummaryRow {
  cost_code_id: string | null;
  code: string | null;
  title: string;
  budget: string;
  budget_changes: string;
  revised_budget: string;
  committed: string;
  pending: string;
  uncommitted: string;
  contract_value: string;
  cost_to_date: string;
}

export interface CommercialSummary {
  currency: string;
  has_approved_budget: boolean;
  rows: SummaryRow[];
  totals: SummaryRow;
  warnings: string[];
}

// --- Phase 2.3: change orders ---------------------------------------------------------------------------
export interface ChangeTarget {
  type: "contract" | "commitment";
  id: string;
  number: string;
  title: string;
  counterparty: string | null;
  contract_form: string;
}

export interface ChangeOrderLine {
  id: string;
  sequence: number;
  cost_code: CostCodeRef | null;
  description: string;
  quantity: string | null;
  unit: string | null;
  unit_rate: string | null;
  amount: string;
  budget_amount: string | null;
}

export interface ChangeOrder {
  id: string;
  project_id: string;
  project_number: string;
  project_name: string;
  target: ChangeTarget;
  label: string;
  number: string;
  title: string;
  description: string | null;
  reason: string;
  reference: string | null;
  status: "draft" | "submitted" | "approved" | "rejected" | "withdrawn";
  currency: string;
  schedule_impact_days: number | null;
  notified_date: string | null;
  response_due_date: string | null;
  overdue: boolean;
  submitted_at: string | null;
  decided_at: string | null;
  decision_notes: string | null;
  total: string;
  budget_total: string;
  version: number;
  created_at: string;
  updated_at: string;
  is_editable: boolean;
  can_approve: boolean;
  lines: ChangeOrderLine[];
}

export interface ChangeOrderListItem {
  id: string;
  project_id: string;
  project_number: string;
  project_name: string;
  target: ChangeTarget;
  label: string;
  number: string;
  title: string;
  status: string;
  currency: string;
  total: string;
  response_due_date: string | null;
  overdue: boolean;
  updated_at: string;
}

// --- Phase 2.4: cost ledger and forecasts ---------------------------------------------------------------
export interface CostTransactionItem {
  id: string;
  transaction_type: "actual" | "accrual";
  transaction_date: string;
  description: string;
  reference: string | null;
  amount: string;
  cost_code: CostCodeRef | null;
  commitment_number: string | null;
  vendor_name: string | null;
  reverses_id: string | null;
  reversed: boolean;
  imported: boolean;
  created_at: string;
}

export interface CostTransactionPage {
  items: CostTransactionItem[];
  total: number;
  amount_total: string;
  limit: number;
  offset: number;
}

export interface ForecastLineItem {
  id: string;
  cost_code: CostCodeRef | null;
  method: "greater_of" | "budget_remaining" | "committed_remaining" | "manual";
  manual_ctc: string | null;
  notes: string | null;
  revised_budget: string;
  committed: string;
  cost_to_date: string;
  cost_to_complete: string;
  final_cost: string;
  variance: string;
}

export interface ForecastSummaryItem {
  id: string;
  period: string;
  status: "draft" | "approved";
  currency: string;
  revenue: string | null;
  final_cost: string | null;
  gross_profit: string | null;
  margin_percent: string | null;
  approved_at: string | null;
}

export interface ForecastDetail {
  id: string;
  project_id: string;
  period: string;
  period_end: string;
  status: "draft" | "approved";
  currency: string;
  revenue_adjustment: string;
  revenue_adjustment_note: string | null;
  notes: string | null;
  version: number;
  approved_at: string | null;
  is_editable: boolean;
  can_approve: boolean;
  revised_contract: string;
  revenue: string;
  revised_budget: string;
  committed: string;
  cost_to_date: string;
  cost_to_complete: string;
  final_cost: string;
  variance: string;
  gross_profit: string;
  margin_percent: string | null;
  percent_complete: string | null;
  earned_revenue: string | null;
  lines: ForecastLineItem[];
}

export interface DashboardForecast {
  currency: string;
  revenue: string;
  cost_to_date: string;
  final_cost: string;
  gross_profit: string;
  margin_percent: string | null;
  projects_forecast: number;
  projects_without_forecast: number;
  latest_period: string | null;
}

// --- Phase 3.1: payment applications (US) / interim valuations (UK) ------------------------------------------------
export interface PaymentApplicationSummary {
  id: string;
  project_id: string;
  contract_id: string;
  contract_number: string;
  contract_title: string;
  number: number;
  label: string;
  status: "draft" | "submitted" | "certified" | "paid";
  currency: string;
  period_to: string;
  application_date: string;
  due_date: string | null;
  final_payment_date: string | null;
  pay_less_notice_date: string | null;
  amount_due: string | null;
  certified_amount: string | null;
  paid_amount: string | null;
  outstanding: string;
  is_overdue: boolean;
}

export interface PaymentLine {
  id: string;
  item: string;
  description: string;
  source: "contract" | "change_order";
  scheduled_value: string;
  previous_work: string;
  this_period: string;
  materials_stored: string;
  completed_to_date: string;
  percent_complete: string | null;
  balance_to_finish: string;
  retention: string;
}

export interface PaymentTotals {
  original_sum: string;
  net_changes: string;
  contract_sum_to_date: string;
  work_to_date: string;
  materials_stored: string;
  completed_to_date: string;
  retention: string;
  earned_less_retention: string;
  previous_certified: string;
  amount_due: string;
  balance_to_finish: string;
  percent_complete: string | null;
}

export interface PaymentApplicationDetail extends PaymentApplicationSummary {
  retention_percent: string;
  notes: string | null;
  submitted_at: string | null;
  certified_date: string | null;
  certification_note: string | null;
  paid_date: string | null;
  payment_reference: string | null;
  version: number;
  is_editable: boolean;
  can_certify: boolean;
  totals: PaymentTotals;
  lines: PaymentLine[];
}

export interface BillingSummary {
  currency: string;
  billed_to_date: string | null;
  earned_revenue: string | null;
  forecast_period: string | null;
  over_billed: string | null;
  under_billed: string | null;
  certified_to_date: string;
  paid_to_date: string;
  outstanding: string;
  awaiting_certification: string;
  retention_held: string;
  overdue_count: number;
}

export interface DashboardPayments {
  currency: string;
  outstanding: string;
  overdue_count: number;
  awaiting_certification: string;
  retention_held: string;
  over_billed: string;
  under_billed: string;
  projects_billed: number;
}
