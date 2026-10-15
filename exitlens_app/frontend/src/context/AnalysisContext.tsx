import React, { useState, useEffect, useCallback } from 'react';
import { getHealth } from '../api/health';
import { createAnalysis, getAnalysis } from '../api/analyses';
import {
  HealthResponse,
  CreateAnalysisRequest,
  AnalysisStatusResponse,
  RunStatus,
} from '../types/api';
import { ApiClientError } from '../api/client';
import { AnalysisContext, StoredRun } from './analysisContextDef';

const STORAGE_KEY_RECENT_RUNS = 'exitlens_recent_runs_v1';
const STORAGE_KEY_ACTIVE_ID = 'exitlens_active_analysis_id';

export function AnalysisProvider({ children }: { children: React.ReactNode }) {
  // Health state
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [isHealthLoading, setIsHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [lastHealthCheck, setLastHealthCheck] = useState<Date | null>(null);

  // Analysis state
  const [activeAnalysis, setActiveAnalysis] = useState<AnalysisStatusResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [submissionError, setSubmissionError] = useState<ApiClientError | null>(null);
  const [selectedDependencyIds, setSelectedDependencyIds] = useState<string[]>([]);

  // Recent runs
  const [recentRuns, setRecentRuns] = useState<StoredRun[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY_RECENT_RUNS);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Save recent runs
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY_RECENT_RUNS, JSON.stringify(recentRuns));
    } catch {
      // Ignore storage errors
    }
  }, [recentRuns]);

  // Fetch health
  const checkHealth = useCallback(async () => {
    setIsHealthLoading(true);
    try {
      const res = await getHealth();
      setHealthData(res);
      setHealthError(null);
    } catch (err: unknown) {
      setHealthData(null);
      if (err instanceof ApiClientError) {
        setHealthError(err.message);
      } else {
        setHealthError('Unable to reach backend health endpoint.');
      }
    } finally {
      setIsHealthLoading(false);
      setLastHealthCheck(new Date());
    }
  }, []);

  // Poll health on mount and periodically (every 30s)
  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, 30000);
    return () => clearInterval(timer);
  }, [checkHealth]);

  // Derived health indicators
  const isBackendAvailable = Boolean(
    healthData &&
      (healthData.status === 'ok' || healthData.status === 'healthy' || healthData.api_ready === true)
  );

  const isModelAvailable = Boolean(
    isBackendAvailable && healthData?.model?.ready === true
  );

  // Poll active analysis
  useEffect(() => {
    if (!activeAnalysis?.analysis_id) {
      setIsPolling(false);
      return;
    }

    const terminalStatuses: RunStatus[] = [
      'completed',
      'completed_with_warnings',
      'failed',
      'ready_for_verification',
    ];

    if (terminalStatuses.includes(activeAnalysis.status)) {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    let isCancelled = false;

    const pollInterval = setInterval(async () => {
      try {
        const updated = await getAnalysis(activeAnalysis.analysis_id);
        if (!isCancelled) {
          setActiveAnalysis(updated);
          // Update recent runs status
          setRecentRuns((prev) =>
            prev.map((r) =>
              r.analysisId === updated.analysis_id
                ? { ...r, status: updated.status, stage: updated.stage }
                : r
            )
          );

          if (terminalStatuses.includes(updated.status)) {
            setIsPolling(false);
          }
        }
      } catch {
        if (!isCancelled) {
          setIsPolling(false);
        }
      }
    }, 2000);

    return () => {
      isCancelled = true;
      clearInterval(pollInterval);
    };
  }, [activeAnalysis?.analysis_id, activeAnalysis?.status]);

  // Restore active analysis from storage on mount if present
  useEffect(() => {
    const activeId = localStorage.getItem(STORAGE_KEY_ACTIVE_ID);
    if (activeId && !activeAnalysis) {
      getAnalysis(activeId)
        .then((data) => {
          setActiveAnalysis(data);
        })
        .catch(() => {
          localStorage.removeItem(STORAGE_KEY_ACTIVE_ID);
        });
    }
  }, [activeAnalysis]);

  // Start analysis
  const startAnalysis = async (request: CreateAnalysisRequest): Promise<string | null> => {
    setIsSubmitting(true);
    setSubmissionError(null);

    try {
      const response = await createAnalysis(request);
      const initialStatus: AnalysisStatusResponse = {
        analysis_id: response.analysis_id,
        status: response.status,
        stage: response.stage,
        created_at: response.created_at,
        repository: request.repository,
      };

      setActiveAnalysis(initialStatus);
      localStorage.setItem(STORAGE_KEY_ACTIVE_ID, response.analysis_id);

      // Add to recent runs
      const newRun: StoredRun = {
        analysisId: response.analysis_id,
        repositoryValue: request.repository.value,
        kind: request.repository.kind,
        status: response.status,
        stage: response.stage,
        createdAt: response.created_at,
      };

      setRecentRuns((prev) => [newRun, ...prev.filter((r) => r.analysisId !== response.analysis_id)]);
      return response.analysis_id;
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setSubmissionError(err);
      } else {
        setSubmissionError(
          new ApiClientError('An unexpected error occurred while starting the analysis.', 500)
        );
      }
      return null;
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectRun = async (analysisId: string) => {
    setIsSubmitting(true);
    try {
      const data = await getAnalysis(analysisId);
      setActiveAnalysis(data);
      localStorage.setItem(STORAGE_KEY_ACTIVE_ID, analysisId);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        setSubmissionError(err);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetActiveAnalysis = () => {
    setActiveAnalysis(null);
    setSelectedDependencyIds([]);
    localStorage.removeItem(STORAGE_KEY_ACTIVE_ID);
    setSubmissionError(null);
  };

  const clearSubmissionError = () => {
    setSubmissionError(null);
  };

  return (
    <AnalysisContext.Provider
      value={{
        health: {
          data: healthData,
          isLoading: isHealthLoading,
          isBackendAvailable,
          isModelAvailable,
          error: healthError,
          lastChecked: lastHealthCheck,
          refetch: checkHealth,
        },
        activeAnalysis,
        isSubmitting,
        isPolling,
        submissionError,
        recentRuns,
        selectedDependencyIds,
        setSelectedDependencyIds,
        startAnalysis,
        clearSubmissionError,
        selectRun,
        resetActiveAnalysis,
      }}
    >
      {children}
    </AnalysisContext.Provider>
  );
}

