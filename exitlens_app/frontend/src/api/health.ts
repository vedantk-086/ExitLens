import { apiClient } from './client';
import { HealthResponse } from '../types/api';

/**
 * Checks system readiness, model availability, and storage health.
 * GET /api/v1/health
 */
export async function getHealth(): Promise<HealthResponse> {
  return apiClient<HealthResponse>('/health');
}
