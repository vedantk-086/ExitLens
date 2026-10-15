import { createContext } from 'react';
import { HealthResponse, CreateAnalysisRequest, AnalysisStatusResponse, RunStatus } from '../types/api';
import { ApiClientError } from '../api/client';

export interface HealthState {
  data: HealthResponse | null;
  isLoading: boolean;
  isBackendAvailable: boolean;
  isModelAvailable: boolean;
  error: string | null;
  lastChecked: Date | null;
  refetch: () => Promise<void>;
}

export interface StoredRun {
  analysisId: string;
  repositoryValue: string;
  kind: string;
  status: RunStatus;
  stage: string;
  createdAt: string;
}

export interface AnalysisContextType {
  health: HealthState;
  activeAnalysis: AnalysisStatusResponse | null;
  isSubmitting: boolean;
  isPolling: boolean;
  submissionError: ApiClientError | null;
  recentRuns: StoredRun[];
  selectedDependencyIds: string[];
  setSelectedDependencyIds: (ids: string[]) => void;
  startAnalysis: (request: CreateAnalysisRequest) => Promise<string | null>;
  clearSubmissionError: () => void;
  selectRun: (analysisId: string) => Promise<void>;
  resetActiveAnalysis: () => void;
}

export const AnalysisContext = createContext<AnalysisContextType | undefined>(undefined);
