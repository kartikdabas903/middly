// Shapes returned by the Middly API (see backend OpenAPI at /docs).

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface FormField {
  name: string
  label: string
  type: "select" | "text" | "textarea"
  required?: boolean
  options?: { value: string; label: string }[]
  minLength?: number
  maxLength?: number
}

export interface ServiceInfo {
  code: string
  name: string
  description: string
  department: string
  department_code: string
  required_categories: string[]
  consent_purpose: string
  consent_validity_days: number
  workflow_code: string
  form_schema: { fields: FormField[] }
  eligibility: {
    ruleset: string
    demo: boolean
    disclaimer?: string
    rules: { id: string; description: string }[]
  } | null
}

export interface ApplicationSummary {
  id: string
  application_number: string
  citizen_id: string
  applicant_name: string | null
  service_code: string
  service: string
  department: string
  department_code: string
  status: string
  current_step: string | null
  current_step_label: string | null
  workflow_status: string | null
  submitted_at: string
  updated_at: string
  decision: string | null
  eligible: boolean | null
  data_quality: string | null
  expected_next_action: string
  department_reference: string | null
}

export interface TimelineStep {
  key: string
  type: string
  label: string
  status: string
  state: "done" | "current" | "blocked" | "skipped" | "pending" | "failed"
  attempts: number
  started_at: string | null
  completed_at: string | null
  error: string | null
  detail: Record<string, unknown>
}

export interface SourceState {
  step: string
  category: string
  system: string
  connector: string | null
  state: "VERIFIED" | "UNAVAILABLE" | "NOT_FOUND" | "PENDING" | "SKIPPED"
  fetched_at: string | null
  attempts: number
  error: string | null
  retry_after_seconds: number | null
}

export interface Provenance {
  source: string
  connector: string
  category: string
}

export interface Profile {
  citizen_id: string
  full_name?: string
  date_of_birth?: string
  gender?: string
  mobile?: string
  email?: string
  address?: string
  district?: string
  state?: string
  pincode?: string
  education?: { highest_qualification: string; qualification_level: string; passing_year?: number; institution?: string; stream?: string }
  employment_status?: string
  employment?: { registration_id?: string; registered_on?: string; skills?: string[]; last_employer?: string }
  provenance: Record<string, Provenance>
  sources?: { category: string; system: string; connector: string; found: boolean; fetched_at: string; source_updated_at?: string; source_reference?: string }[]
  department_record?: { reference: string; status: string; batch_code?: string; remarks?: string }
}

export interface QualityIssueItem {
  source_system: string
  issue_type: string
  severity: string
  message: string
  field?: string | null
  details?: Record<string, unknown>
}

export interface QualityReport {
  overall: string
  sources: Record<string, { status: string; category: string; reason: string | null }>
  issues: QualityIssueItem[]
  counts: { critical: number; warning: number; info: number }
}

export interface EligibilityResult {
  eligible: boolean
  ruleset: string
  demo: boolean
  passed_rules: string[]
  failed_rules: string[]
  reasons: string[]
  outcomes: { id: string; passed: boolean; description: string; reason: string; actual: unknown }[]
  evaluated_on: string
}

export interface Consent {
  consent_id: string
  citizen_id: string
  requesting_department: string
  requesting_department_code: string
  application_id: string | null
  application_number: string | null
  data_categories: string[]
  purpose: string
  status: "ACTIVE" | "REVOKED" | "EXPIRED"
  timestamp: string
  expiry: string
  revoked_at: string | null
  revocation_reason: string | null
  access_count: number
  access_logs?: { accessed_at: string; data_category: string; accessor: string; purpose: string; connector: string; decision: string }[]
}

export interface ApplicationDetail extends ApplicationSummary {
  form_data: Record<string, string>
  decision_reason: string | null
  decided_by: string | null
  decided_at: string | null
  processing_seconds: number | null
  eligibility: EligibilityResult | null
  data_quality_report: QualityReport | null
  profile: Profile | null
  profile_hidden_reason: string | null
  timeline: TimelineStep[]
  sources: SourceState[]
  history: { from_status: string | null; to_status: string; step: string | null; actor: string; actor_role: string; note: string | null; at: string }[]
  workflow: { instance_id: string | null; definition: string | null; version: number | null; status: string | null; last_error: string | null }
  consent: Consent | null
  consent_request: { department: string; categories: string[]; purpose: string; validity_days: number } | null
  clarifications: { question: string; asked_by: string; asked_at: string; response: string | null; responded_at?: string }[]
  permissions: {
    can_grant_consent: boolean
    can_retry: boolean
    can_decide: boolean
    can_respond: boolean
    can_withdraw: boolean
    can_sync: boolean
  }
}

export interface NotificationItem {
  id: string
  title: string
  message: string
  category: string
  severity: "info" | "success" | "warning" | "error"
  application_id: string | null
  read: boolean
  read_at: string | null
  created_at: string
}

export interface CitizenProfile {
  citizen_id: string
  full_name: string | null
  date_of_birth: string | null
  gender: string | null
  mobile: string | null
  email: string | null
  address: string | null
  district: string | null
  state: string | null
  pincode: string | null
  education: Profile["education"] | null
  employment_status: string | null
  provenance: Record<string, Provenance>
  sources: Record<string, { status: string; category: string; reason: string | null }>
  quality_status: string
  last_synced_at: string | null
  open_issues: DQIssue[]
  unavailable_sources?: Record<string, string>
}

export interface ConnectorCard {
  id: string
  key: string
  name: string
  system_name: string
  description: string
  department: string | null
  base_url: string
  auth_type: string
  data_format: string
  data_categories: string[]
  capabilities: string[]
  enabled: boolean
  timeout_seconds: number
  max_retries: number
  plugin_module: string
  version: string
  status: "HEALTHY" | "DEGRADED" | "DOWN" | "UNKNOWN"
  last_checked_at: string | null
  latency_ms: number | null
  message: string | null
  circuit_state: "CLOSED" | "OPEN" | "HALF_OPEN" | "UNKNOWN"
  calls_24h: number
  success_rate_24h: number | null
  failures_24h: number
  avg_latency_ms_24h: number | null
  last_call_at: string | null
  fault_mode?: string | null
}

export interface AuditEntry {
  id: number
  timestamp: string
  actor: string
  role: string
  action: string
  resource: string
  resource_id: string | null
  source_system: string | null
  destination_system: string | null
  status: string
  ip_address?: string | null
  correlation_id?: string | null
  details?: Record<string, unknown>
  hash?: string
}

export interface EventItem {
  id: string
  event_type: string
  routing_key: string
  aggregate_type: string
  aggregate_id: string
  payload: Record<string, unknown>
  status: string
  correlation_id: string | null
  attempts: number
  last_error: string | null
  processed_by: string[]
  created_at: string
  published_at: string | null
  processed_at: string | null
}

export interface DQIssue {
  id: string
  citizen_id: string
  application_id: string | null
  source_system: string
  issue_type: string
  severity: string
  field: string | null
  message: string
  details: Record<string, unknown>
  status: string
  detected_at: string
  resolved_at: string | null
  resolved_by: string | null
}

export interface WorkflowDefinition {
  id: string
  code: string
  version: number
  name: string
  description: string
  is_active: boolean
  definition: { steps: { key: string; type: string; label: string; connector?: string; category?: string; categories?: string[]; on_ineligible?: string }[] }
  created_at: string
}

export interface WorkflowInstanceItem {
  id: string
  application_id: string
  application_number: string | null
  workflow: string
  workflow_name: string
  version: number
  status: string
  current_step: string | null
  last_error: string | null
  started_at: string
  completed_at: string | null
  updated_at: string
  progress: { completed: number; total: number }
  steps?: { key: string; type: string; label: string; sequence: number; status: string; attempts: number; started_at: string | null; completed_at: string | null; error: string | null; output: Record<string, unknown> }[]
}

export interface AdminOverview {
  generated_at: string
  api: { requests: number; failures: number; client_errors: number; server_errors: number; avg_latency_ms: number }
  connectors: ConnectorCard[]
  connector_calls: { total: number; failed: number; avg_latency_ms: number }
  applications: {
    total: number
    by_status: Record<string, number>
    by_department: { department: string; total: number; approved: number; rejected: number; pending: number }[]
    trend: { date: string; applications: number }[]
  }
  avg_processing_seconds: number | null
  workflows: Record<string, number>
  events: { by_status: Record<string, number>; by_type: { event_type: string; count: number }[]; dead_letter_depth: number | null }
  consents: { by_status: Record<string, number>; access_allowed: number; access_denied: number }
  data_quality: { open_issues: { issue_type: string; severity: string; count: number }[]; open_total: number }
  recent_connector_calls: { connector: string; success: number; failure: number }[]
  recent_audit: AuditEntry[]
}

export interface Me {
  subject: string
  username: string
  name: string | null
  email: string | null
  roles: string[]
  primary_role: string
  citizen_id: string | null
  department_code: string | null
}
