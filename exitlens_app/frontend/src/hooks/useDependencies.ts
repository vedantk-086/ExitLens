import { useState, useEffect, useCallback } from 'react';
import { getDependencies, getDependencyDetail } from '../api/analyses';
import {
  DependencyListItem,
  DependencyDetailResponse,
} from '../types/api';
import { ApiClientError } from '../api/client';

// ─── useDependencyList ───────────────────────────────────────────────────────

export type DependencyListState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'loaded'; items: DependencyListItem[]; warnings: string[] }
  | { status: 'error'; error: string; code: string };

export function useDependencyList(
  analysisId: string | null,
  statusTrigger?: string | number | null
) {
  const [state, setState] = useState<DependencyListState>({ status: 'idle' });

  const load = useCallback(async (id: string) => {
    setState({ status: 'loading' });
    try {
      const res = await getDependencies(id);
      setState({
        status: 'loaded',
        items: res.dependencies ?? [],
        warnings: res.warnings ?? [],
      });
    } catch (err) {
      if (err instanceof ApiClientError) {
        setState({ status: 'error', error: err.message, code: err.code });
      } else {
        setState({ status: 'error', error: 'Failed to load dependency inventory.', code: 'UNKNOWN' });
      }
    }
  }, []);

  useEffect(() => {
    if (analysisId) {
      load(analysisId);
    } else {
      setState({ status: 'idle' });
    }
  }, [analysisId, statusTrigger, load]);

  const refresh = useCallback(() => {
    if (analysisId) load(analysisId);
  }, [analysisId, load]);

  return { state, refresh };
}

// ─── useDependencyDetail ─────────────────────────────────────────────────────

export type DependencyDetailState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'loaded'; detail: DependencyDetailResponse }
  | { status: 'error'; error: string; code: string };

export function useDependencyDetail(
  analysisId: string | null,
  dependencyId: string | null
) {
  const [state, setState] = useState<DependencyDetailState>({ status: 'idle' });

  useEffect(() => {
    if (!analysisId || !dependencyId) {
      setState({ status: 'idle' });
      return;
    }
    setState({ status: 'loading' });
    let cancelled = false;
    getDependencyDetail(analysisId, dependencyId)
      .then((detail) => {
        if (!cancelled) setState({ status: 'loaded', detail });
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof ApiClientError) {
            setState({ status: 'error', error: err.message, code: err.code });
          } else {
            setState({ status: 'error', error: 'Failed to load dependency detail.', code: 'UNKNOWN' });
          }
        }
      });
    return () => { cancelled = true; };
  }, [analysisId, dependencyId]);

  return state;
}
