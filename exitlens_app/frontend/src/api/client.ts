import { ApiErrorResponse } from '../types/api';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }
  return DEFAULT_BASE_URL;
}

export class ApiClientError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown> | null;
  requestId?: string;

  constructor(
    message: string,
    status = 500,
    code = 'INTERNAL_ERROR',
    details?: Record<string, unknown> | null,
    requestId?: string
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

export async function apiClient<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${baseUrl}${cleanPath}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Check if the response body has JSON
    const contentType = response.headers.get('content-type');
    const isJson = contentType && contentType.includes('application/json');

    if (!response.ok) {
      if (isJson) {
        try {
          const errorBody = (await response.json()) as ApiErrorResponse;
          if (errorBody && errorBody.error) {
            throw new ApiClientError(
              errorBody.error.message || `Request failed with status ${response.status}`,
              response.status,
              errorBody.error.code || `HTTP_${response.status}`,
              errorBody.error.details,
              errorBody.error.request_id
            );
          }
        } catch (parseErr) {
          if (parseErr instanceof ApiClientError) throw parseErr;
        }
      }

      const rawText = await response.text().catch(() => '');
      throw new ApiClientError(
        rawText || `Request failed with status ${response.status}`,
        response.status,
        `HTTP_${response.status}`
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    if (isJson) {
      return (await response.json()) as T;
    }

    return (await response.text()) as unknown as T;
  } catch (err: unknown) {
    if (err instanceof ApiClientError) {
      throw err;
    }

    const message = err instanceof Error ? err.message : 'Unknown network failure';
    throw new ApiClientError(
      `Unable to connect to ExitLens backend at ${baseUrl}. Ensure the FastAPI server is running. (${message})`,
      0,
      'NETWORK_ERROR'
    );
  }
}
