import { useContext } from 'react';
import { AnalysisContext, AnalysisContextType } from './analysisContextDef';

export function useAnalysisContext(): AnalysisContextType {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error('useAnalysisContext must be used within an AnalysisProvider');
  }
  return context;
}
