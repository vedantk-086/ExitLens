/**
 * API Contract Types for ExitLens
 * Strictly adhering to docs/API_CONTRACT.md and backend README
 */

// ─── Run status vocabulary ──────────────────────────────────────────────────

export type RunStatus =
  | 'queued'
  | 'validating_repository'
  | 'scanning'
  | 'mapping_usage'
  | 'assessing_risk'
  | 'generating_recommendations'
  | 'ready_for_verification'
  | 'verifying'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed';

export type RepositoryKind = 'local_path' | 'git_url';

// ─── Evidence provenance ────────────────────────────────────────────────────

export type EvidenceProvenance =
  | 'OBSERVED'
  | 'INFERRED'
  | 'AI_RECOMMENDATION'
  | 'EXECUTION_RESULT'
  | 'NOT_VERIFIED';

export type VerificationStatus =
  | 'PASSED'
  | 'FAILED'
  | 'ERROR'
  | 'TIMED_OUT'
  | 'SKIPPED'
  | 'NOT_RUN';

// ─── Risk severity ──────────────────────────────────────────────────────────

export type RiskSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info' | string;

// ─── Recommendation status ──────────────────────────────────────────────────

export type RecommendationStatus =
  | 'available'
  | 'pending'
  | 'generating'
  | 'unavailable'
  | 'error'
  | 'no_candidate_identified'
  | 'not_requested'
  | string;

// ─── Repository target ─────────────────────────────────────────────────────

export interface RepositoryTarget {
  kind: RepositoryKind;
  value: string;
  git_ref?: string | null;
}

export interface AnalysisOptions {
  exclude_paths?: string[];
  include_tests?: boolean;
  use_git_history?: boolean;
  generate_recommendations?: boolean;
}

// ─── Create analysis ────────────────────────────────────────────────────────

export interface CreateAnalysisRequest {
  repository: RepositoryTarget;
  options?: AnalysisOptions;
}

export interface CreateAnalysisResponse {
  analysis_id: string;
  status: RunStatus;
  stage: string;
  created_at: string;
}

// ─── Analysis status ────────────────────────────────────────────────────────

export interface AnalysisSummary {
  dependencies_discovered: number;
  dependencies_flagged: number;
  recommendations_available: number;
  baseline_checks: number;
  replacement_checks: number;
  checks_passed: number;
  checks_failed: number;
  checks_skipped_or_unverified: number;
}

export interface AnalysisArtifacts {
  capsule_json?: boolean;
  capsule_md?: boolean;
}

export interface AnalysisStatusResponse {
  analysis_id: string;
  status: RunStatus;
  stage: string;
  created_at: string;
  updated_at?: string;
  summary?: AnalysisSummary;
  progress?: {
    stage?: string;
    percent?: number;
    message?: string;
  };
  warnings?: string[];
  errors?: string[];
  artifacts?: AnalysisArtifacts;
  repository?: RepositoryTarget;
}

// ─── Health ─────────────────────────────────────────────────────────────────

export interface ModelHealth {
  configured_id?: string;
  provider?: string;
  ready?: boolean;
  error?: string;
}

export interface HealthResponse {
  status: 'ok' | 'healthy' | 'degraded' | 'error' | string;
  api_ready?: boolean;
  python_version?: string;
  storage_ready?: boolean;
  model?: ModelHealth;

  // Real backend schema fields
  timestamp_utc?: string;
  api?: { status: string; version: string; environment: string };
  python?: { version: string; is_compatible: boolean; details?: string };
  ai?: { provider: string; configured_model: string; available: boolean; details?: string };
  storage?: { ready: boolean; writable: boolean; details?: string };
}

export interface TestProfile {
  profile_id: string;
  framework: string;
  display_name: string;
  description: string;
  server_argv?: string[];
  is_detected?: boolean;
  detection_reason?: string;
}

// ─── Error ──────────────────────────────────────────────────────────────────

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown> | null;
  request_id?: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

// ─── Evidence record ────────────────────────────────────────────────────────

export interface EvidenceRecord {
  evidence_id: string;
  kind: string;
  provenance: EvidenceProvenance;
  path?: string;
  line_start?: number;
  line_end?: number;
  excerpt?: string;
  sha256?: string;
  observed_at_utc?: string;
}

// ─── Risk indicator ─────────────────────────────────────────────────────────

export interface RiskIndicator {
  rule_id: string;
  severity: RiskSeverity;
  signal: string;
  explanation: string;
  title?: string;
  evidence_ids?: string[];
  evidence_refs?: string[];
  limitations?: string;
}

// ─── Usage location ─────────────────────────────────────────────────────────

export interface UsageLocation {
  file_path: string;
  path?: string;
  line_start: number;
  line_end?: number;
  import_name?: string;
  import_statement?: string;
  pattern?: string;
  excerpt?: string;
  provenance?: EvidenceProvenance;
  evidence_id?: string;
  is_test_file?: boolean;
}

// ─── Dependency list item (inventory) ───────────────────────────────────────

export interface DependencyListItem {
  dependency_id: string;
  name: string;
  declared_version?: string | null;
  resolved_version?: string | null;
  manifest_path?: string;
  highest_severity?: RiskSeverity | null;
  risk_rule_ids?: string[];
  usage_count?: number;
  recommendation_status?: RecommendationStatus;
  verification_status?: VerificationStatus | string | null;
  is_flagged?: boolean;
}

export interface DependencyListResponse {
  analysis_id: string;
  dependencies: DependencyListItem[];
  total_count?: number;
  warnings?: string[];
}

// ─── Dependency detail (all 9 capsule sections) ─────────────────────────────

export interface ProposedReplacement {
  status: string;
  candidate_distribution?: string | null;
  distribution_name?: string | null;
  candidate_specifier?: string | null;
  specifier?: string | null;
  rationale?: string | null;
  provenance?: EvidenceProvenance;
  evidence_ids?: string[];
  limitations?: string | null;
}

export interface MigrationStep {
  step_number: number;
  description: string;
  action?: string;
  code_example?: string | null;
  provenance?: EvidenceProvenance;
}

export interface SuggestedTest {
  description: string;
  objective?: string;
  test_id?: string;
  suggested_profile?: string;
  expected_signal?: string;
  test_type?: string;
  code_example?: string | null;
  provenance?: EvidenceProvenance;
}

export interface ExecutedTestResult {
  profile_id?: string;
  command?: string;
  command_args?: string[];
  status: VerificationStatus | string;
  exit_code?: number | null;
  stdout_excerpt?: string | null;
  stderr_excerpt?: string | null;
  duration_seconds?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  skip_reason?: string | null;
  error_reason?: string | null;
  runtime_differences?: string[] | string | null;
  provenance?: EvidenceProvenance;
  is_baseline?: boolean;
}

export interface CompatibilityGap {
  title?: string;
  description: string;
  severity?: RiskSeverity;
  provenance?: EvidenceProvenance;
  evidence_ids?: string[];
}

export interface OpenConcern {
  description: string;
  category?: string;
  provenance?: EvidenceProvenance;
}

export interface DependencyDetailResponse {
  dependency_id: string;
  analysis_id: string;

  // Section 1: dependency_details
  dependency_details: {
    name: string;
    declared_version?: string | null;
    resolved_version?: string | null;
    manifest_path?: string;
    manifest_paths?: string[];
    is_flagged?: boolean;
    distribution_name?: string | null;
    summary?: string | null;
    [key: string]: unknown;
  };

  // Section 2: risk_indicators
  risk_indicators: RiskIndicator[];

  // Section 3: usage_locations
  usage_locations: UsageLocation[];

  // Section 4: proposed_replacement
  proposed_replacement: ProposedReplacement | null;

  // Section 5: migration_steps
  migration_steps: MigrationStep[];

  // Section 6: suggested_tests
  suggested_tests: SuggestedTest[];

  // Section 7: executed_test_results
  executed_test_results: ExecutedTestResult[];

  // Section 8: compatibility_gaps
  compatibility_gaps: CompatibilityGap[];

  // Section 9: open_concerns_limitations
  open_concerns_limitations: OpenConcern[];

  // Additional metadata
  evidence?: EvidenceRecord[];
  warnings?: string[];
}

// ─── Recommendation request ─────────────────────────────────────────────────

export interface RecommendationRequest {
  dependency_ids: string[];
  force_regenerate?: boolean;
}

export interface RecommendationResponse {
  analysis_id: string;
  status: string;
  queued_count?: number;
  message?: string;
}

// ─── Verification request & response ────────────────────────────────────────

export interface VerificationRequest {
  dependency_ids: string[];
  baseline_profile_id?: string;
  replacement_profile_id?: string;
  confirm_repository_code_execution: boolean;
  allow_network?: boolean;
  timeout_seconds?: number;
}

export interface VerificationExecutionRecord {
  profile_id?: string;
  command?: string;
  command_args?: string[];
  status: VerificationStatus | string;
  exit_code?: number | null;
  stdout_excerpt?: string | null;
  stderr_excerpt?: string | null;
  duration_seconds?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  skip_reason?: string | null;
  error_reason?: string | null;
  runtime_differences?: string[] | string | null;
  compatibility_gaps?: string[] | CompatibilityGap[];
  open_concerns?: string[] | OpenConcern[];
  provenance?: EvidenceProvenance;
  is_baseline?: boolean;
}

export interface VerificationResponse {
  analysis_id: string;
  verification_id?: string;
  status: 'queued' | 'running' | 'completed' | 'completed_with_warnings' | 'failed' | VerificationStatus | string;
  message?: string;
  baseline_result?: VerificationExecutionRecord | null;
  replacement_result?: VerificationExecutionRecord | null;
  results?: VerificationExecutionRecord[];
  warnings?: string[];
  errors?: string[];
}

// ─── Dependency Exit Capsule (Canonical Contract) ───────────────────────────

export interface AiProvenance {
  provider?: string;
  model_tag?: string;
  inference_method?: string;
  prompt_version?: string;
  status?: string;
  model_terms?: string;
  error?: string | null;
  [key: string]: unknown;
}

export interface CapsuleDependencyRecord {
  dependency_id: string;
  name?: string;
  dependency_details: DependencyDetailResponse['dependency_details'];
  risk_indicators: RiskIndicator[];
  usage_locations: UsageLocation[];
  proposed_replacement: ProposedReplacement | null;
  migration_steps: MigrationStep[];
  suggested_tests: SuggestedTest[];
  executed_test_results: ExecutedTestResult[];
  compatibility_gaps: CompatibilityGap[];
  open_concerns_limitations: OpenConcern[];
  evidence_ids?: string[];
  completeness_status?: string;
  notes?: string;
}

export interface DependencyExitCapsule {
  schema_version: string;
  capsule_id?: string;
  analysis_id: string;
  created_at?: string;
  generated_at_utc?: string;
  tool_version?: string;
  repository?: RepositoryTarget;
  runtime_version?: string;
  analysis_scope?: string[] | { exclude_paths?: string[]; include_tests?: boolean };
  summary_counts?: AnalysisSummary | Record<string, number>;
  evidence?: EvidenceRecord[] | Record<string, EvidenceRecord>;
  ai_provenance?: AiProvenance;
  provenance_legend?: Record<string, string>;
  known_limitations?: string[];
  validation_warnings?: string[];
  is_complete?: boolean;
  flagged_dependencies?: CapsuleDependencyRecord[];
  dependencies?: CapsuleDependencyRecord[];
}
