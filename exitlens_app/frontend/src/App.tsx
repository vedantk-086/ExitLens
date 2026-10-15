import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AnalysisProvider } from './context/AnalysisContext';
import { AppShell } from './components/layout/AppShell';
import { LandingPage } from './pages/LandingPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { AnalysisPage } from './pages/AnalysisPage';
import { VerificationPage } from './pages/VerificationPage';
import { CapsulePage } from './pages/CapsulePage';

function AppWorkbenchLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AnalysisProvider>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route element={<AppWorkbenchLayout />}>
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/analysis" element={<AnalysisPage />} />
            <Route path="/verification" element={<VerificationPage />} />
            <Route path="/capsule" element={<CapsulePage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AnalysisProvider>
    </BrowserRouter>
  );
}

export default App;
