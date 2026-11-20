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
