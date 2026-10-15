import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClientError, getApiBaseUrl } from '../src/api/client';
import { getHealth } from '../src/api/health';
import { createAnalysis, getAnalysis } from '../src/api/analyses';

describe('Centralized API Client', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('uses default base URL when environment variable is not overridden', () => {
    expect(getApiBaseUrl()).toBe('http://127.0.0.1:8000/api/v1');
  });

  it('handles successful JSON response', async () => {
    const mockHealth = {
      status: 'ok',
      api_ready: true,
      python_version: '3.13.2',
      model: { configured_id: 'gemma4', ready: true },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockHealth,
    });

    const result = await getHealth();
    expect(result.status).toBe('ok');
    expect(result.api_ready).toBe(true);
    expect(result.model?.configured_id).toBe('gemma4');
  });

  it('handles structured API error responses', async () => {
    const mockError = {
      error: {
        code: 'MODEL_UNAVAILABLE',
        message: 'The configured local Gemma provider is unavailable.',
        details: { stage: 'generating_recommendations' },
        request_id: 'req-12345',
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => mockError,
    });

    await expect(
      createAnalysis({
        repository: { kind: 'local_path', value: 'C:\\work\\LinkWatch' },
      })
    ).rejects.toThrow('The configured local Gemma provider is unavailable.');
  });

  it('maps connection failure to NETWORK_ERROR ApiClientError', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(getAnalysis('sample-id')).rejects.toThrow(ApiClientError);
    await expect(getAnalysis('sample-id')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      status: 0,
    });
  });
});
