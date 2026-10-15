import { apiClient } from './client';
import { HealthResponse } from '../types/api';

/**
 * Checks system readiness, model availability, and storage health.
 * GET /api/v1/health
 */
export async function getHealth(): Promise<HealthResponse> {
  const raw = await apiClient<HealthResponse>('/health');
  const isApiReady = raw.api_ready ?? (raw.api?.status === 'ready' || raw.status === 'healthy' || raw.status === 'degraded' || raw.status === 'ok');
  const pyVer = raw.python_version ?? raw.python?.version;
  const storageReady = raw.storage_ready ?? raw.storage?.ready ?? true;
  const modelReady = raw.model?.ready ?? raw.ai?.available ?? false;
  const modelConfigured = raw.model?.configured_id ?? raw.ai?.configured_model;

  return {
    ...raw,
    api_ready: isApiReady,
    python_version: pyVer,
    storage_ready: storageReady,
    model: {
      ready: modelReady,
      configured_id: modelConfigured,
      provider: raw.model?.provider ?? raw.ai?.provider,
      ...raw.model,
    },
  };
}
