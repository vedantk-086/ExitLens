import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('ExitLens App Shell & Navigation', () => {
  it('renders without crashing and displays Workspace in AppShell', () => {
    window.history.pushState({}, 'Test', '/workspace');
    render(<App />);

    expect(screen.getByRole('heading', { level: 1, name: /repository workspace/i })).toBeInTheDocument();
    expect(screen.getAllByText(/local-first analysis/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/gemma 4 · dependency resilience/i).length).toBeGreaterThan(0);
  });

  it('renders navigation links to all four routes', () => {
    window.history.pushState({}, 'Test', '/workspace');
    render(<App />);

    const workspaceLinks = screen.getAllByRole('link', { name: /workspace/i });
    expect(workspaceLinks.length).toBeGreaterThan(0);

    const analysisLinks = screen.getAllByRole('link', { name: /analysis/i });
    expect(analysisLinks.length).toBeGreaterThan(0);

    const verificationLinks = screen.getAllByRole('link', { name: /verification/i });
    expect(verificationLinks.length).toBeGreaterThan(0);

    const capsuleLinks = screen.getAllByRole('link', { name: /capsule/i });
    expect(capsuleLinks.length).toBeGreaterThan(0);
  });

  it('renders the landing page at root route', () => {
    window.history.pushState({}, 'Test', '/');
    render(<App />);

    expect(screen.getByText(/know what you depend on/i)).toBeInTheDocument();
    expect(screen.getAllByText(/gemma 4/i).length).toBeGreaterThan(0);
  });
});
