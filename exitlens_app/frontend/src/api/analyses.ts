import { apiClient } from './client';
import {
  CreateAnalysisRequest,
  CreateAnalysisResponse,
  AnalysisStatusResponse,
  DependencyListResponse,
  DependencyDetailResponse,
  RecommendationRequest,
  RecommendationResponse,
  VerificationRequest,
  VerificationResponse,
  DependencyExitCapsule,
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
  return apiClient<AnalysisStatusResponse>(`/analyses/${encodeURIComponent(analysisId)}`);
}

/**
 * Retrieves all discovered dependencies for an analysis run.
 * GET /api/v1/analyses/{analysis_id}/dependencies
 */
export async function getDependencies(
  analysisId: string
): Promise<DependencyListResponse> {
  return apiClient<DependencyListResponse>(
    `/analyses/${encodeURIComponent(analysisId)}/dependencies`
  );
}

/**
 * Retrieves full detail and all nine capsule sections for one dependency.
 * GET /api/v1/analyses/{analysis_id}/dependencies/{dependency_id}
 */
export async function getDependencyDetail(
  analysisId: string,
  dependencyId: string
): Promise<DependencyDetailResponse> {
  return apiClient<DependencyDetailResponse>(
    `/analyses/${encodeURIComponent(analysisId)}/dependencies/${encodeURIComponent(dependencyId)}`
  );
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
 * Queue explicitly approved allow-listed verification profiles.
 * POST /api/v1/analyses/{analysis_id}/verification
 */
export async function postVerification(
  analysisId: string,
  payload: VerificationRequest
): Promise<VerificationResponse> {
  return apiClient<VerificationResponse>(
    `/analyses/${encodeURIComponent(analysisId)}/verification`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Retrieves the canonical JSON capsule.
 * GET /api/v1/analyses/{analysis_id}/capsule?format=json
 */
export async function getCapsuleJson(
  analysisId: string
): Promise<DependencyExitCapsule> {
  return apiClient<DependencyExitCapsule>(
    `/analyses/${encodeURIComponent(analysisId)}/capsule?format=json`,
    {
      headers: {
        Accept: 'application/json',
      },
    }
  );
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

