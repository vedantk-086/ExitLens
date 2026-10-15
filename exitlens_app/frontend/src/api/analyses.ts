import { apiClient } from './client';
import {
  CreateAnalysisRequest,
  CreateAnalysisResponse,
  AnalysisStatusResponse,
  DependencyListResponse,
  DependencyListItem,
  DependencyDetailResponse,
  RecommendationRequest,
  RecommendationResponse,
  VerificationRequest,
  VerificationResponse,
  DependencyExitCapsule,
  TestProfile,
} from '../types/api';

/**
 * Creates a new repository analysis run.
 * POST /api/v1/analyses
 */
export async function createAnalysis(
  payload: CreateAnalysisRequest
): Promise<CreateAnalysisResponse> {
  return apiClient<CreateAnalysisResponse>('/analyses', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Retrieves the current status, stage, progress summary, and artifact availability.
 * GET /api/v1/analyses/{analysis_id}
 */
export async function getAnalysis(
  analysisId: string
): Promise<AnalysisStatusResponse> {
  const raw = await apiClient<any>(`/analyses/${encodeURIComponent(analysisId)}`);
  return {
    ...raw,
    created_at: raw.created_at_utc || raw.created_at,
    updated_at: raw.updated_at_utc || raw.updated_at,
    completed_at: raw.completed_at_utc || raw.completed_at,
  };
}

/**
 * Retrieves all discovered dependencies for an analysis run.
 * Normalizes backend List[CapsuleDependencyRecord] or object response.
 * GET /api/v1/analyses/{analysis_id}/dependencies
 */
export async function getDependencies(
  analysisId: string
): Promise<DependencyListResponse> {
  const raw = await apiClient<unknown>(
    `/analyses/${encodeURIComponent(analysisId)}/dependencies`
  );

  let rawList: any[] = [];
  if (Array.isArray(raw)) {
    rawList = raw;
  } else if (raw && typeof raw === 'object' && 'dependencies' in raw && Array.isArray((raw as any).dependencies)) {
    rawList = (raw as any).dependencies;
  }

  const dependencies: DependencyListItem[] = rawList.map((item: any) => {
    const details = item.dependency_details || {};
    const name = details.distribution_name || details.name || item.name || item.distribution_name || 'unknown';
    const declared = details.declared_specifier ?? details.declared_version ?? item.declared_version ?? item.declared_specifier ?? null;
    const resolved = details.resolved_version ?? item.resolved_version ?? null;
    const manifest = details.manifest_path ?? item.manifest_path ?? '';
    const risks = item.risk_indicators || [];
    
    // Determine highest severity
    let highestSev: 'critical' | 'high' | 'medium' | 'low' | null = null;
    if (item.highest_severity) {
      const s = String(item.highest_severity).toLowerCase();
      if (s === 'critical' || s === 'high' || s === 'medium' || s === 'low') {
        highestSev = s as any;
      }
    }
    if (!highestSev && risks.length > 0) {
      if (risks.some((r: any) => String(r.severity).toLowerCase() === 'critical')) highestSev = 'critical';
      else if (risks.some((r: any) => String(r.severity).toLowerCase() === 'high')) highestSev = 'high';
      else if (risks.some((r: any) => String(r.severity).toLowerCase() === 'medium')) highestSev = 'medium';
      else highestSev = 'low';
    }
    if (!highestSev) highestSev = 'low';

    return {
      dependency_id: item.dependency_id,
      name,
      declared_version: declared,
      resolved_version: resolved,
      manifest_path: manifest,
      highest_severity: highestSev,
      risk_rule_ids: item.risk_rule_ids ?? risks.map((r: any) => r.rule_id),
      usage_count: item.usage_locations?.length ?? item.usage_count ?? 0,
      recommendation_status: item.proposed_replacement?.status ?? item.recommendation_status ?? 'unknown',
      verification_status:
        item.verification_status ??
        (item.executed_test_results?.length
          ? item.executed_test_results.some((r: any) => String(r.status).toUpperCase() === 'PASSED')
            ? 'passed'
            : 'failed'
          : 'unverified'),
      is_flagged: item.is_flagged ?? true,
      dependency_details: {
        ...details,
        name,
        distribution_name: name,
        declared_version: declared,
        declared_specifier: declared,
      },
      ...item,
    };
  });

  return {
    analysis_id: analysisId,
    dependencies,
    total_count: dependencies.length,
    warnings: (raw as any)?.warnings ?? [],
  };
}

/**
 * Normalizes a raw dependency record from backend schemas to frontend interfaces.
 * Maps field name variances:
 * - proposed_replacement: distribution_name -> candidate_distribution, specifier -> candidate_specifier
 * - usage_locations: path -> file_path, import_statement -> import_name, pattern -> excerpt
 * - migration_steps: action/target_file -> code_example
 * - suggested_tests: objective/expected_signal -> description/code_example
 * - open_concerns_limitations: string[] -> { description, category }[]
 */
export function normalizeDependencyRecord(raw: any, analysisId: string = ''): any {
  if (!raw) return raw;
  const details = raw.dependency_details || {};
  const name = details.distribution_name || details.name || raw.name || raw.dependency_id || 'unknown';
  const declared = details.declared_specifier ?? details.declared_version ?? null;
  const resolved = details.resolved_version ?? null;

  // Normalize risk_indicators
  const rawRisks = raw.risk_indicators || [];
  const normalizedRisks = rawRisks.map((r: any) => ({
    ...r,
    signal: r.signal || r.title || r.signal_source || r.rule_id || 'Risk signal detected',
    title: r.title || r.signal || r.rule_id,
    evidence_ids: r.evidence_ids || r.evidence_refs || [],
    evidence_refs: r.evidence_refs || r.evidence_ids || [],
    severity: String(r.severity || 'medium').toLowerCase(),
    explanation: r.explanation || r.signal || '',
  }));

  // Normalize usage_locations
  const rawUsages = raw.usage_locations || [];
  const normalizedUsages = rawUsages.map((loc: any) => ({
    ...loc,
    path: loc.path || loc.file_path || '',
    file_path: loc.file_path || loc.path || '',
    line_start: loc.line_start ?? 1,
    line_end: loc.line_end,
    import_name: loc.import_name || loc.import_statement || loc.symbol || '',
    import_statement: loc.import_statement || loc.import_name || '',
    excerpt: loc.excerpt || loc.pattern || loc.import_statement || '',
    pattern: loc.pattern || loc.excerpt || '',
  }));

  // Normalize proposed_replacement
  let normalizedReplacement = null;
  if (raw.proposed_replacement) {
    const rep = raw.proposed_replacement;
    normalizedReplacement = {
      ...rep,
      candidate_distribution: rep.candidate_distribution || rep.distribution_name || null,
      distribution_name: rep.distribution_name || rep.candidate_distribution || null,
      candidate_specifier: rep.candidate_specifier || rep.specifier || null,
      specifier: rep.specifier || rep.candidate_specifier || null,
      rationale: rep.rationale || null,
      status: rep.status || 'proposed',
      limitations: rep.limitations || null,
    };
  }

  // Normalize migration_steps
  const rawSteps = raw.migration_steps || [];
  const normalizedSteps = rawSteps.map((s: any, idx: number) => ({
    ...s,
    step_number: s.step_number ?? (idx + 1),
    description: s.description || s.action || '',
    action: s.action || s.description || 'Update',
    code_example: s.code_example || (s.target_file ? `${s.action || 'Action'}: ${s.target_file}` : null),
  }));

  // Normalize suggested_tests
  const rawTests = raw.suggested_tests || [];
  const normalizedTests = rawTests.map((t: any) => ({
    ...t,
    description: t.description || t.objective || 'Verification test',
    objective: t.objective || t.description || 'Verify compatibility',
    test_type: t.test_type || t.suggested_profile || 'pytest',
    suggested_profile: t.suggested_profile || t.test_type || 'pytest-default',
    code_example: t.code_example || (t.expected_signal ? `Expected signal: ${t.expected_signal}` : null),
  }));

  // Normalize executed_test_results
  const rawExecuted = raw.executed_test_results || [];
  const normalizedExecuted = rawExecuted.map((r: any, idx: number) => ({
    ...r,
    profile_id: r.profile_id || 'pytest-default',
    status: String(r.status || 'UNVERIFIED').toUpperCase(),
    duration_seconds: r.duration_seconds ?? null,
    exit_code: r.exit_code ?? null,
    stdout_excerpt: r.stdout_excerpt ?? null,
    stderr_excerpt: r.stderr_excerpt ?? null,
    is_baseline: r.is_baseline ?? (r.run_kind === 'baseline' || idx === 0),
  }));

  // Normalize compatibility_gaps
  const rawGaps = raw.compatibility_gaps || raw.compatibility_concerns || [];
  const normalizedGaps = rawGaps.map((g: any) => {
    if (typeof g === 'string') {
      return {
        description: g,
        title: g,
        severity: 'medium',
        evidence_ids: [],
      };
    }
    return {
      ...g,
      description: g.description || g.title || String(g),
      title: g.title || g.description || '',
      severity: g.severity || 'medium',
      evidence_ids: g.evidence_ids || g.evidence_refs || [],
    };
  });

  // Normalize open_concerns_limitations
  const rawConcerns = raw.open_concerns_limitations || raw.open_concerns || [];
  const normalizedConcerns = rawConcerns.map((c: any) => {
    if (typeof c === 'string') return { description: c, category: 'limitation' };
    return {
      description: c.description || String(c),
      category: c.category || 'limitation',
      provenance: c.provenance,
    };
  });

  return {
    ...raw,
    analysis_id: raw.analysis_id ?? analysisId,
    dependency_id: raw.dependency_id,
    name,
    dependency_details: {
      ...details,
      name,
      distribution_name: details.distribution_name || name,
      declared_version: declared || 'None specified',
      declared_specifier: declared || '',
      resolved_version: resolved || 'Unresolved',
      manifest_path: details.manifest_path ?? 'requirements.txt',
      summary: details.summary || `${name} Python dependency declared in ${details.manifest_path || 'manifest'}`,
    },
    risk_indicators: normalizedRisks,
    usage_locations: normalizedUsages,
    proposed_replacement: normalizedReplacement,
    migration_steps: normalizedSteps,
    suggested_tests: normalizedTests,
    executed_test_results: normalizedExecuted,
    compatibility_gaps: normalizedGaps,
    open_concerns_limitations: normalizedConcerns,
  };
}

/**
 * Retrieves full detail and all nine capsule sections for one dependency.
 * GET /api/v1/analyses/{analysis_id}/dependencies/{dependency_id}
 */
export async function getDependencyDetail(
  analysisId: string,
  dependencyId: string
): Promise<DependencyDetailResponse> {
  const raw = await apiClient<any>(
    `/analyses/${encodeURIComponent(analysisId)}/dependencies/${encodeURIComponent(dependencyId)}`
  );
  return normalizeDependencyRecord(raw, analysisId);
}

/**
 * Queue/retry recommendations for selected dependency IDs.
 * POST /api/v1/analyses/{analysis_id}/recommendations
 */
export async function postRecommendations(
  analysisId: string,
  payload: RecommendationRequest
): Promise<RecommendationResponse> {
  return apiClient<RecommendationResponse>(
    `/analyses/${encodeURIComponent(analysisId)}/recommendations`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Discovers available allow-listed test profiles for an analysis target.
 * GET /api/v1/analyses/{analysis_id}/test-profiles
 */
export async function getTestProfiles(
  analysisId: string
): Promise<TestProfile[]> {
  try {
    return await apiClient<TestProfile[]>(
      `/analyses/${encodeURIComponent(analysisId)}/test-profiles`
    );
  } catch {
    return [];
  }
}

/**
 * Queue explicitly approved allow-listed verification profiles.
 * Safely resolves placeholder profile IDs to allow-listed server profiles.
 * POST /api/v1/analyses/{analysis_id}/verification
 */
export async function postVerification(
  analysisId: string,
  payload: VerificationRequest
): Promise<VerificationResponse> {
  // Normalize placeholder profile IDs to server-allowlisted standard
  const safeBaseline =
    !payload.baseline_profile_id || payload.baseline_profile_id === 'server-detected-profile-id'
      ? 'pytest-default'
      : payload.baseline_profile_id;

  const safeReplacement =
    !payload.replacement_profile_id || payload.replacement_profile_id === 'server-detected-profile-id'
      ? 'pytest-default'
      : payload.replacement_profile_id;

  const safePayload = {
    ...payload,
    baseline_profile_id: safeBaseline,
    replacement_profile_id: safeReplacement,
    confirm_repository_code_execution: true,
  };

  const raw = await apiClient<any>(
    `/analyses/${encodeURIComponent(analysisId)}/verification`,
    {
      method: 'POST',
      body: JSON.stringify(safePayload),
    }
  );

  // Normalize VerificationRecord response
  const results: any[] = raw.results || [];
  const baseline = results.find((r: any) => r.run_kind === 'baseline');
  const replacement = results.find((r: any) => r.run_kind === 'replacement');

  const normalizeExecution = (r: any) => {
    if (!r) return null;
    return {
      ...r,
      command: Array.isArray(r.argv) ? r.argv.join(' ') : r.command,
      status: String(r.status || 'UNVERIFIED').toLowerCase(),
      is_baseline: r.run_kind === 'baseline',
    };
  };

  const hasFailed = results.some((r: any) => String(r.status).toUpperCase() === 'FAILED' || String(r.status).toUpperCase() === 'ERROR');
  const hasPassed = results.some((r: any) => String(r.status).toUpperCase() === 'PASSED');
  const overallStatus = raw.status ?? (hasFailed ? 'failed' : hasPassed ? 'completed' : 'completed');

  return {
    analysis_id: raw.analysis_id ?? analysisId,
    verification_id: raw.verification_id,
    status: overallStatus,
    results: results.map(normalizeExecution),
    baseline_result: normalizeExecution(baseline),
    replacement_result: normalizeExecution(replacement),
    message: raw.message,
    warnings: raw.warnings ?? [],
    errors: raw.errors ?? [],
  };
}

/**
 * Retrieves the canonical JSON capsule.
 * GET /api/v1/analyses/{analysis_id}/capsule?format=json
 */
export async function getCapsuleJson(
  analysisId: string
): Promise<DependencyExitCapsule> {
  const data = await apiClient<any>(
    `/analyses/${encodeURIComponent(analysisId)}/capsule?format=json`,
    {
      headers: {
        Accept: 'application/json',
      },
    }
  );

  const rawDeps: any[] = data.dependencies || data.flagged_dependencies || [];
  const normalizedDeps = rawDeps.map((dep: any) => normalizeDependencyRecord(dep, analysisId));

  return {
    ...data,
    dependencies: normalizedDeps,
    flagged_dependencies: normalizedDeps,
  };
}

/**
 * Retrieves the human-readable Markdown capsule.
 * GET /api/v1/analyses/{analysis_id}/capsule?format=md
 */
export async function getCapsuleMarkdown(
  analysisId: string
): Promise<string> {
  return apiClient<string>(
    `/analyses/${encodeURIComponent(analysisId)}/capsule?format=md`,
    {
      headers: {
        Accept: 'text/markdown',
      },
    }
  );
}

/**
 * Downloads the server-generated capsule artifact as a file.
 */
export async function downloadCapsuleFile(
  analysisId: string,
  format: 'json' | 'md'
): Promise<void> {
  const isJson = format === 'json';
  const mimeType = isJson ? 'application/json;charset=utf-8' : 'text/markdown;charset=utf-8';
  const filename = `exitlens-capsule-${analysisId}.${format}`;

  let content: string;
  if (isJson) {
    const data = await getCapsuleJson(analysisId);
    content = JSON.stringify(data, null, 2);
  } else {
    content = await getCapsuleMarkdown(analysisId);
  }

  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

