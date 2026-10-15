import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  ShieldCheck,
  ArrowRight,
  ChevronDown,
  AlertTriangle,
  Menu,
  X,
  Sparkles,
  Code2,
  FolderGit2,
  Globe,
  Sliders,
  Download,
  Search,
  FileDown,
  RotateCcw,
  Loader2,
  CheckCircle2,
  HelpCircle,
  FileCode,
  Play,
  Pause,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { AnimatedBeamNetwork } from '../components/network/AnimatedBeamNetwork';
import { AnalysisProgress } from '../components/network/AnalysisProgress';
import { DependencyDetailDrawer } from '../components/ui/DependencyDetailDrawer';
import { useAnalysisContext } from '../context/useAnalysisContext';
import { useDependencyList, useDependencyDetail } from '../hooks/useDependencies';
import { downloadCapsuleFile } from '../api/analyses';
import { RepositoryKind, DependencyListItem } from '../types/api';

export function LandingPage() {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [isPlayingWalkthrough, setIsPlayingWalkthrough] = useState(false);

  // Analysis context hooks
  const {
    health,
    activeAnalysis,
    isSubmitting,
    isPolling,
    submissionError,
    startAnalysis,
    clearSubmissionError,
    resetActiveAnalysis,
  } = useAnalysisContext();

  // Repository form state
  const [sourceKind, setSourceKind] = useState<RepositoryKind>('git_url');
  const [repoValue, setRepoValue] = useState('https://github.com/rishrek/LinkWatch');
  const [includeTests, setIncludeTests] = useState(true);
  const [useGitHistory, setUseGitHistory] = useState(true);
  const [generateRecommendations, setGenerateRecommendations] = useState(true);
  const [localValidationError, setLocalValidationError] = useState<string | null>(null);

  // Dependency filtering state
  const [depSearch, setDepSearch] = useState('');
  const [depSeverityFilter, setDepSeverityFilter] = useState<'all' | 'high' | 'medium' | 'low'>('all');
  const [selectedDepId, setSelectedDepId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [downloadingJson, setDownloadingJson] = useState(false);
  const [downloadingMd, setDownloadingMd] = useState(false);

  // Query dependency list for active analysis
  const { state: depListState } = useDependencyList(activeAnalysis?.analysis_id ?? null);
  const dependencies: DependencyListItem[] = depListState.status === 'loaded' ? depListState.items : [];
  const totalCount = dependencies.length;
  const isDepsLoading = depListState.status === 'loading';

  // Query dependency detail for drawer
  const detailState = useDependencyDetail(activeAnalysis?.analysis_id ?? null, selectedDepId);
  const selectedDepName = detailState.status === 'loaded' ? detailState.detail.dependency_details.name : undefined;

  // Auto-play walkthrough timer
  useEffect(() => {
    if (!isPlayingWalkthrough) return;
    const interval = setInterval(() => {
      setActiveStageIndex((prev) => (prev + 1) % 5);
    }, 3500);
    return () => clearInterval(interval);
  }, [isPlayingWalkthrough]);

  // Tracing beam and scroll synchronization for the 5-step workflow section
  const workflowSectionRef = useRef<HTMLElement>(null);
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const handleScroll = () => {
      if (!workflowSectionRef.current || isPlayingWalkthrough) return;
      const rect = workflowSectionRef.current.getBoundingClientRect();
      const windowHeight = window.innerHeight;

      // Check if section is in view
      if (rect.top > windowHeight || rect.bottom < 0) return;

      // Determine active step based on scroll position of step containers
      stepRefs.current.forEach((el, index) => {
        if (!el) return;
        const stepRect = el.getBoundingClientRect();
        if (stepRect.top <= windowHeight * 0.5 && stepRect.bottom >= windowHeight * 0.25) {
          setActiveStageIndex(index);
        }
      });
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isPlayingWalkthrough]);

  // Five stages of How ExitLens works
  const stages = [
    {
      id: 'inspect',
      stepNum: '01',
      title: 'Inspect',
      cardTitle: 'Inspect Repository Manifests, Lockfiles & Code',
      sublabel: 'Stage 01 · Static AST Discovery',
      description:
        'Non-executing static discovery walks your Python repository to parse requirements.txt, pyproject.toml, and lockfiles. Traverses code and test files to map concrete import call-sites and build an observed dependency inventory without running manifest scripts.',
      technicalDetails:
        'Safe AST traversal · Strict path allow-listing · Excludes virtualenvs, node_modules, and git caches',
    },
    {
      id: 'assess',
      stepNum: '02',
      title: 'Assess',
      cardTitle: 'Assess Maintenance & Compatibility Risks',
      sublabel: 'Stage 02 · Deterministic Ledger',
      description:
        'A transparent deterministic maintenance engine evaluates versioned risk rules, including unpinned wide constraints, manifest drift, and unmapped imports. Every triggered signal is linked directly to observed file paths and line numbers.',
      technicalDetails:
        'Deterministic rule ledger · Cryptographic SHA-256 evidence hashing · Zero hallucinated risks',
    },
    {
      id: 'recommend',
      stepNum: '03',
      title: 'Recommend',
      cardTitle: 'Generate Usage-Aware Migration Recommendations',
      sublabel: 'Stage 03 · Local Gemma 4',
      description:
        'Local Gemma 4 receives observed call-sites, usage patterns, and risk signals to propose concrete replacement packages, breaking API difference mappings, step-by-step code edits, and counterfactual test profiles.',
      technicalDetails:
        'Ollama local inference · Enforces Pydantic schema validation · Tagged strictly as AI_RECOMMENDATION',
    },
    {
      id: 'verify',
      stepNum: '04',
      title: 'Verify',
      cardTitle: 'Execute Approved Verification Profiles',
      sublabel: 'Stage 04 · Disposable Sandbox',
      description:
        'Verification is strictly optional and requires explicit human approval. Executes allow-listed test profiles in disposable copies of the repository to compare baseline against candidate outcomes, capturing bounded runtime and raw logs.',
      technicalDetails:
        'Mandatory human approval modal · Network disabled by default · Server-allowlisted argument arrays',
    },
    {
      id: 'package',
      stepNum: '05',
      title: 'Package',
      cardTitle: 'Compile the Canonical Dependency Exit Capsule',
      sublabel: 'Stage 05 · Dual Export Artifact',
      description:
        'Assembles a self-contained, versioned migration capsule containing all nine required sections, an immutable provenance ledger, and remaining architectural limitations. Exportable in parity JSON and Markdown representations.',
      technicalDetails:
        'Schema version 1.0.0 · Dual export parity · Completeness validation gate before download',
    },
  ];

  // Smooth scroll to anchor handler
  const scrollToAnchor = (id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      const yOffset = -70;
      const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: 'smooth' });
    }
  };

  // Submit repository handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalValidationError(null);
    clearSubmissionError();

    const trimmed = repoValue.trim();
    if (!trimmed) {
      setLocalValidationError(
        sourceKind === 'local_path'
          ? 'Please enter a valid local repository directory path.'
          : 'Please enter a valid public HTTPS Git repository URL.'
      );
      return;
    }

    if (sourceKind === 'git_url') {
      try {
        const url = new URL(trimmed);
        if (url.protocol !== 'https:') {
          setLocalValidationError('Only secure HTTPS Git URLs are supported.');
          return;
        }
      } catch {
        setLocalValidationError('Invalid URL format. Please provide a valid HTTPS Git URL.');
        return;
      }
    }

    const analysisId = await startAnalysis({
      repository: {
        kind: sourceKind,
        value: trimmed,
        git_ref: null,
      },
      options: {
        exclude_paths: ['.git', '.venv', 'venv', 'node_modules', 'reports', 'exitlens_app'],
        include_tests: includeTests,
        use_git_history: useGitHistory,
        generate_recommendations: generateRecommendations,
      },
    });

    if (analysisId) {
      // Smoothly scroll to progress section
      setTimeout(() => {
        scrollToAnchor('analysis-progress');
      }, 100);
    }
  };

  // Populate LinkWatch helper
  const handleUseLinkWatch = () => {
    setSourceKind('git_url');
    setRepoValue('https://github.com/rishrek/LinkWatch');
    setLocalValidationError(null);
  };

  // Download capsule handlers
  const handleDownload = async (format: 'json' | 'md') => {
    if (!activeAnalysis?.analysis_id) return;
    if (format === 'json') setDownloadingJson(true);
    else setDownloadingMd(true);

    try {
      await downloadCapsuleFile(activeAnalysis.analysis_id, format);
    } catch {
      // Handled in API client
    } finally {
      if (format === 'json') setDownloadingJson(false);
      else setDownloadingMd(false);
    }
  };

  // Filter dependencies
  const filteredDependencies = dependencies.filter((dep: DependencyListItem) => {
    if (depSearch && !dep.name.toLowerCase().includes(depSearch.toLowerCase())) {
      return false;
    }
    if (depSeverityFilter === 'high') {
      return dep.highest_severity === 'critical' || dep.highest_severity === 'high';
    }
    if (depSeverityFilter === 'medium') {
      return dep.highest_severity === 'medium';
    }
    if (depSeverityFilter === 'low') {
      return dep.highest_severity === 'low' || dep.highest_severity === 'info';
    }
    return true;
  });

  return (
    <div className="min-h-screen bg-[#F5F7FA] text-[#172033] flex flex-col font-sans selection:bg-[#EEF3FF] selection:text-[#315BE8]">
      {/* ─── Top Navigation Header (Simplified & Clean) ──────────────────── */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-[#E1E6EE] transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Subtitle */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#315BE8] flex items-center justify-center text-white shadow-xs">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-base tracking-tight text-[#172033]">
                ExitLens
              </span>
              <span className="text-[10px] text-[#718096] font-mono leading-none">
                Gemma 4 · Dependency Resilience
              </span>
            </div>
          </div>

          {/* Simple Clean Section Nav */}
          <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-[#526176]">
            <button
              type="button"
              onClick={() => scrollToAnchor('how-it-works')}
              className="hover:text-[#315BE8] transition-colors cursor-pointer"
            >
              How It Works
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('analyze-repository')}
              className="hover:text-[#315BE8] transition-colors cursor-pointer"
            >
              Analyze Repository
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('evidence-trust')}
              className="hover:text-[#315BE8] transition-colors cursor-pointer"
            >
              Evidence & Trust
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('exit-capsule')}
              className="hover:text-[#315BE8] transition-colors cursor-pointer"
            >
              Exit Capsule
            </button>
          </nav>

          {/* Desktop Primary Action */}
          <div className="hidden md:flex items-center gap-3">
            <Button
              variant="primary"
              size="sm"
              onClick={() => scrollToAnchor('analyze-repository')}
              icon={<ArrowRight className="w-3.5 h-3.5" />}
              iconPosition="right"
            >
              Start Analysis
            </Button>
          </div>

          {/* Mobile Menu Toggle */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen((v) => !v)}
            className="md:hidden p-2 text-[#526176] hover:text-[#172033] rounded-md focus:outline-none"
            aria-label="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-[#E1E6EE] bg-white px-4 pt-2 pb-4 flex flex-col gap-3 text-xs animate-in fade-in slide-in-from-top-2 duration-150">
            <button
              type="button"
              onClick={() => scrollToAnchor('how-it-works')}
              className="text-left py-2 font-medium text-[#526176] hover:text-[#315BE8]"
            >
              How It Works
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('analyze-repository')}
              className="text-left py-2 font-medium text-[#526176] hover:text-[#315BE8]"
            >
              Analyze Repository
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('evidence-trust')}
              className="text-left py-2 font-medium text-[#526176] hover:text-[#315BE8]"
            >
              Evidence & Trust
            </button>
            <button
              type="button"
              onClick={() => scrollToAnchor('exit-capsule')}
              className="text-left py-2 font-medium text-[#526176] hover:text-[#315BE8]"
            >
              Exit Capsule
            </button>
            <div className="pt-2">
              <Button
                variant="primary"
                size="sm"
                className="w-full justify-center"
                onClick={() => scrollToAnchor('analyze-repository')}
                icon={<ArrowRight className="w-3.5 h-3.5" />}
                iconPosition="right"
              >
                Start Analysis
              </Button>
            </div>
          </div>
        )}
      </header>

      {/* ─── Hero Section (Centered Brand + Scribble Animation + Circuit Network) ─── */}
      <section className="relative overflow-hidden pt-12 pb-16 lg:pt-16 lg:pb-24 border-b border-[#E1E6EE] bg-gradient-to-b from-white via-[#F8FAFC] to-[#F1F4F9]">
        {/* Subtle background circuit grid */}
        <div className="absolute inset-0 circuit-grid-bg opacity-50 pointer-events-none" />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center">
          {/* Top pill badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs bg-[#EEF3FF] border border-[#C6D8FF] text-[#2648C7] shadow-xs mb-6 animate-soft-pulse">
            <Sparkles className="w-3.5 h-3.5 text-[#315BE8]" />
            <span className="font-semibold">Evidence-Linked Dependency Resilience</span>
            <span className="text-[#94A3B8]">·</span>
            <span className="text-[#526176]">Local Gemma 4 Intelligence</span>
          </div>

          {/* Central Title with Hand-drawn SVG Scribble Underline */}
          <div className="relative mb-6 inline-block group">
            <h1 className="text-5xl sm:text-6xl lg:text-8xl font-black tracking-tight text-[#0F172A] drop-shadow-xs">
              Exit<span className="text-[#315BE8]">Lens</span>
            </h1>

            {/* Hand-drawn dynamic SVG Scribble loop with gradient & glow */}
            <svg
              className="absolute -bottom-4 left-1/2 -translate-x-1/2 w-56 sm:w-72 lg:w-96 h-8 overflow-visible pointer-events-none"
              viewBox="0 0 320 28"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="scribbleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2563EB" />
                  <stop offset="50%" stopColor="#315BE8" />
                  <stop offset="100%" stopColor="#6366F1" />
                </linearGradient>
              </defs>
              {/* Soft glow underlying trace */}
              <path
                d="M 12 18 C 65 26, 175 28, 308 14 C 220 22, 95 24, 22 20 C 75 14, 215 12, 298 17"
                stroke="#315BE8"
                strokeWidth="7"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="opacity-25 blur-[3px] animate-scribble"
              />
              {/* Crisp vivid ink stroke */}
              <path
                d="M 12 18 C 65 26, 175 28, 308 14 C 220 22, 95 24, 22 20 C 75 14, 215 12, 298 17"
                stroke="url(#scribbleGrad)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="animate-scribble"
              />
            </svg>
          </div>

          {/* Subtitle & Mission */}
          <p className="text-xl sm:text-2xl font-bold text-[#1E293B] max-w-3xl mt-2 mb-3 tracking-tight">
            Know what you depend on.{' '}
            <span className="text-[#315BE8]">Know how to move on.</span>
          </p>

          <p className="text-sm sm:text-base text-[#526176] max-w-2xl leading-relaxed mb-8">
            Trace dependency risks to concrete Python call-sites, plan safe replacements with Gemma 4, verify what can be executed in isolated sandboxes, and export a canonical Dependency Exit Capsule.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-3.5 mb-8">
            <Button
              variant="primary"
              size="lg"
              onClick={() => scrollToAnchor('analyze-repository')}
              icon={<ArrowRight className="w-4 h-4" />}
              iconPosition="right"
            >
              Analyze a Repository
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => scrollToAnchor('how-it-works')}
              icon={<ChevronDown className="w-4 h-4" />}
            >
              Explore 5-Step Architecture
            </Button>
          </div>

          {/* 3 Core Trust Pillars */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl w-full text-xs mb-10">
            <div className="p-3 bg-white/90 backdrop-blur-xs border border-[#E1E6EE] rounded-xl shadow-xs flex flex-col items-center">
              <span className="font-bold text-[#0F172A]">100% Local Intelligence</span>
              <span className="text-[11px] text-[#718096] font-mono">Ollama · Gemma 4</span>
            </div>
            <div className="p-3 bg-white/90 backdrop-blur-xs border border-[#E1E6EE] rounded-xl shadow-xs flex flex-col items-center">
              <span className="font-bold text-[#0F172A]">Deterministic Rules</span>
              <span className="text-[11px] text-[#718096] font-mono">Versioned Risk Ledger</span>
            </div>
            <div className="p-3 bg-white/90 backdrop-blur-xs border border-[#E1E6EE] rounded-xl shadow-xs flex flex-col items-center">
              <span className="font-bold text-[#0F172A]">Zero Fabricated Passes</span>
              <span className="text-[11px] text-[#718096] font-mono">Verified Disposable Runs</span>
            </div>
          </div>

          {/* Animated Scroll Down Motion Cue */}
          <button
            type="button"
            onClick={() => scrollToAnchor('how-it-works')}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium text-[#526176] hover:text-[#315BE8] hover:bg-white/80 transition-colors cursor-pointer mb-8 animate-gentle-bounce"
          >
            <span>Scroll to see sequential 5-step workflow</span>
            <ChevronDown className="w-4 h-4 text-[#315BE8]" />
          </button>

          {/* Full Animated Beam Circuit Illustration */}
          <div className="w-full max-w-5xl bg-white border border-[#E1E6EE] rounded-2xl p-4 sm:p-6 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-3 mb-3 text-xs text-[#718096]">
              <span className="font-semibold text-[#0F172A] flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#315BE8] animate-ping" />
                Live Architecture Network
              </span>
              <span className="font-mono text-[11px]">Orthogonal Traces · Animated Beams</span>
            </div>
            <AnimatedBeamNetwork className="w-full" />
          </div>
        </div>
      </section>

      {/* ─── Section A: Five-Step Architecture (With Auto-Play Motion Flow) ─── */}
      <section
        id="how-it-works"
        ref={workflowSectionRef}
        className="py-16 lg:py-24 border-b border-[#E1E6EE] bg-white scroll-mt-16"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-10">
            <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
              Step-by-Step Architecture
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#172033] mt-2 tracking-tight">
              From Brittle Manifest to Verified Exit Plan
            </h2>
            <p className="text-xs sm:text-sm text-[#526176] mt-3 leading-relaxed">
              ExitLens guides you through five transparent stages. Every finding is grounded in static source evidence, verified where possible, and compiled into a permanent artifact.
            </p>
          </div>

          {/* Visual Step Pipeline Header with Connected Indicator Track */}
          <div className="max-w-3xl mx-auto mb-8 hidden md:block">
            <div className="relative flex items-center justify-between">
              {/* Connecting background line */}
              <div className="absolute top-1/2 left-0 right-0 -translate-y-1/2 h-1 bg-[#E1E6EE] z-0" />
              {/* Active animated progress line */}
              <div
                className="absolute top-1/2 left-0 -translate-y-1/2 h-1 bg-[#315BE8] transition-all duration-300 z-0"
                style={{ width: `${(activeStageIndex / 4) * 100}%` }}
              />

              {stages.map((stageItem, index) => {
                const isActive = activeStageIndex === index;
                const isPassed = activeStageIndex > index;
                return (
                  <button
                    key={stageItem.id}
                    type="button"
                    onClick={() => {
                      setIsPlayingWalkthrough(false);
                      setActiveStageIndex(index);
                    }}
                    className="relative z-10 flex flex-col items-center gap-1.5 cursor-pointer group focus:outline-none"
                  >
                    <div
                      className={`w-9 h-9 rounded-full flex items-center justify-center font-mono text-xs font-bold transition-all duration-200 border-2 ${
                        isActive
                          ? 'bg-[#315BE8] border-[#315BE8] text-white shadow-md ring-4 ring-[#EEF3FF]'
                          : isPassed
                          ? 'bg-[#EEF3FF] border-[#315BE8] text-[#315BE8]'
                          : 'bg-white border-[#E1E6EE] text-[#718096] group-hover:border-[#94A3B8]'
                      }`}
                    >
                      {stageItem.stepNum}
                    </div>
                    <span
                      className={`text-[11px] font-semibold transition-colors ${
                        isActive ? 'text-[#315BE8]' : 'text-[#718096]'
                      }`}
                    >
                      {stageItem.title}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Auto-Play Flow Controller */}
          <div className="flex items-center justify-center gap-3 mb-10">
            <button
              type="button"
              onClick={() => setIsPlayingWalkthrough((v) => !v)}
              className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-colors border ${
                isPlayingWalkthrough
                  ? 'bg-[#EEF3FF] border-[#315BE8] text-[#315BE8]'
                  : 'bg-white border-[#E1E6EE] text-[#526176] hover:bg-[#FAFBFC]'
              }`}
            >
              {isPlayingWalkthrough ? (
                <>
                  <Pause className="w-3.5 h-3.5 fill-current" />
                  <span>Pause Step-by-Step Flow</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Watch 5-Step Flow</span>
                </>
              )}
            </button>
            <span className="text-xs font-mono text-[#718096]">
              Stage {activeStageIndex + 1} of 5 Active
            </span>
          </div>

          {/* Interactive Scroll-Driven Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Clean list of 5 steps with live progress indicator */}
            <div className="lg:col-span-5 flex flex-col gap-2.5">
              {stages.map((stageItem, index) => {
                const isActive = activeStageIndex === index;
                return (
                  <div
                    key={stageItem.id}
                    ref={(el) => { stepRefs.current[index] = el; }}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        setIsPlayingWalkthrough(false);
                        setActiveStageIndex(index);
                      }}
                      className={`w-full p-4 rounded-xl border text-left transition-all duration-200 flex items-center justify-between cursor-pointer relative overflow-hidden ${
                        isActive
                          ? 'bg-[#EEF3FF] border-[#315BE8] shadow-xs ring-1 ring-[#315BE8]/20'
                          : 'bg-white border-[#E1E6EE] hover:bg-[#FAFBFC]'
                      }`}
                    >
                      <div className="flex items-center gap-3.5">
                        <span
                          className={`font-mono text-xs font-bold w-6 h-6 rounded flex items-center justify-center transition-colors ${
                            isActive
                              ? 'bg-[#315BE8] text-white'
                              : 'bg-[#F1F4F9] text-[#718096]'
                          }`}
                        >
                          {stageItem.stepNum}
                        </span>
                        <div className="flex flex-col">
                          <span
                            className={`font-bold text-sm transition-colors ${
                              isActive ? 'text-[#315BE8]' : 'text-[#172033]'
                            }`}
                          >
                            {stageItem.title}
                          </span>
                          <span className="text-[11px] text-[#718096]">
                            {stageItem.sublabel}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {isActive && (
                          <span className="w-2 h-2 rounded-full bg-[#315BE8] animate-pulse" />
                        )}
                        <ArrowRight
                          className={`w-4 h-4 transition-transform duration-200 ${
                            isActive
                              ? 'text-[#315BE8] translate-x-0.5'
                              : 'text-[#94A3B8]'
                          }`}
                        />
                      </div>

                      {/* Walking progress line on active button when auto-playing */}
                      {isActive && isPlayingWalkthrough && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#315BE8]/30">
                          <div className="h-full bg-[#315BE8] animate-step-fill" />
                        </div>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Right Column: Sticky synchronized detail panel with interactive live preview */}
            <div className="lg:col-span-7 sticky top-24">
              <div
                key={activeStageIndex}
                className="bg-[#F8FAFC] border-2 border-[#E1E6EE] rounded-2xl p-6 lg:p-8 shadow-xs flex flex-col gap-5 transition-all duration-200 ease-out animate-in fade-in slide-in-from-bottom-1"
              >
                <div className="flex items-center justify-between border-b border-[#E1E6EE] pb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-[#315BE8] text-white flex items-center justify-center font-bold text-sm shadow-xs font-mono">
                      {stages[activeStageIndex].stepNum}
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-[#172033]">
                        {stages[activeStageIndex].cardTitle}
                      </h3>
                      <span className="text-xs font-mono text-[#526176]">
                        {stages[activeStageIndex].sublabel}
                      </span>
                    </div>
                  </div>
                  <span className="text-xs font-mono text-[#315BE8] font-semibold bg-[#EEF3FF] px-2.5 py-1 rounded-full border border-[#C6D8FF]">
                    Stage {activeStageIndex + 1} of 5
                  </span>
                </div>

                <p className="text-sm text-[#172033] leading-relaxed">
                  {stages[activeStageIndex].description}
                </p>

                {/* Live Concrete Stage Visual Output Preview */}
                <div className="rounded-xl border border-[#E1E6EE] bg-white overflow-hidden shadow-xs">
                  <div className="bg-[#172033] text-white px-3.5 py-2 text-[11px] font-mono flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[#10B981]" />
                      Stage {stages[activeStageIndex].stepNum} Output Evidence
                    </span>
                    <span className="text-[#94A3B8]">ExitLens Engine</span>
                  </div>

                  {activeStageIndex === 0 && (
                    <div className="p-3.5 font-mono text-xs flex flex-col gap-2 bg-[#FAFBFC]">
                      <div className="text-[11px] text-[#526176]">
                        Parsed manifest requirements & mapped concrete AST call-sites:
                      </div>
                      <div className="p-2.5 bg-[#0F172A] text-[#E2E8F0] rounded-lg text-[11px] leading-relaxed">
                        <span className="text-[#38BDF8]">requirements.txt:</span> requests&gt;=2.25.0<br />
                        <span className="text-[#A78BFA]">AST Trace:</span> app/services/client.py:42<br />
                        <span className="text-[#34D399]">Call-site:</span> response = requests.get(target_url, timeout=5)
                      </div>
                    </div>
                  )}

                  {activeStageIndex === 1 && (
                    <div className="p-3.5 font-mono text-xs flex flex-col gap-2 bg-[#FAFBFC]">
                      <div className="text-[11px] text-[#526176]">
                        Deterministic Risk Ledger Signals:
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <div className="p-2 bg-[#FFF5DE] border border-[#FEE4A6] rounded-lg text-[11px] text-[#925C08] flex items-center justify-between">
                          <span className="font-bold">UNPINNED_UPPER_BOUND</span>
                          <span className="font-mono text-[10px]">Severity: HIGH · sha256:4b21..</span>
                        </div>
                        <div className="p-2 bg-[#EEF1F5] border border-[#E1E6EE] rounded-lg text-[11px] text-[#526176] flex items-center justify-between">
                          <span className="font-bold">MANIFEST_DRIFT</span>
                          <span className="font-mono text-[10px]">Severity: MEDIUM · sha256:7a90..</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {activeStageIndex === 2 && (
                    <div className="p-3.5 font-mono text-xs flex flex-col gap-2 bg-[#FAFBFC]">
                      <div className="text-[11px] text-[#526176]">
                        Gemma 4 Migration Diff & API Translation:
                      </div>
                      <div className="p-2.5 bg-[#0F172A] text-[#E2E8F0] rounded-lg text-[11px] leading-relaxed">
                        <span className="text-[#F87171]">- import requests</span><br />
                        <span className="text-[#F87171]">- response = requests.get(target_url, timeout=5)</span><br />
                        <span className="text-[#34D399]">+ import httpx</span><br />
                        <span className="text-[#34D399]">+ with httpx.Client(timeout=5.0) as client:</span><br />
                        <span className="text-[#34D399]">+     response = client.get(target_url)</span>
                      </div>
                    </div>
                  )}

                  {activeStageIndex === 3 && (
                    <div className="p-3.5 font-mono text-xs flex flex-col gap-2 bg-[#FAFBFC]">
                      <div className="text-[11px] text-[#526176]">
                        Disposable Isolated Sandbox Execution:
                      </div>
                      <div className="p-2.5 bg-[#0F172A] text-[#E2E8F0] rounded-lg text-[11px] leading-relaxed">
                        <span className="text-[#94A3B8]">[SANDBOX] allow_network=false · timeout=120s</span><br />
                        <span className="text-[#38BDF8]">$ pytest tests/test_client.py -q</span><br />
                        <span className="text-[#34D399]">.. [100%] 2 passed in 0.41s</span><br />
                        <span className="text-[#A78BFA]">[VERIFIED] Baseline & candidate test profiles completed</span>
                      </div>
                    </div>
                  )}

                  {activeStageIndex === 4 && (
                    <div className="p-3.5 font-mono text-xs flex flex-col gap-2 bg-[#FAFBFC]">
                      <div className="text-[11px] text-[#526176]">
                        Canonical Dependency Exit Capsule Artifact:
                      </div>
                      <div className="p-2.5 bg-[#0F172A] text-[#E2E8F0] rounded-lg text-[11px] leading-relaxed">
                        <span className="text-[#38BDF8]">&#123;</span><br />
                        &nbsp;&nbsp;<span className="text-[#A78BFA]">"schema_version":</span> "1.0.0",<br />
                        &nbsp;&nbsp;<span className="text-[#A78BFA]">"inventory_count":</span> 14,<br />
                        &nbsp;&nbsp;<span className="text-[#A78BFA]">"recommendations":</span> 3,<br />
                        &nbsp;&nbsp;<span className="text-[#A78BFA]">"status":</span> "verified_sandbox_passed",<br />
                        &nbsp;&nbsp;<span className="text-[#A78BFA]">"capsule_hash":</span> "sha256:7f83b165..."<br />
                        <span className="text-[#38BDF8]">&#125;</span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="p-3 bg-white border border-[#E1E6EE] rounded-lg text-xs flex flex-col gap-1">
                  <span className="font-semibold text-[#172033] flex items-center gap-1.5">
                    <Code2 className="w-4 h-4 text-[#315BE8]" />
                    Engine Implementation Guardrails
                  </span>
                  <span className="text-[#526176] font-mono text-[11px] leading-relaxed">
                    {stages[activeStageIndex].technicalDetails}
                  </span>
                </div>

                <div className="pt-2 flex items-center justify-between text-xs text-[#718096]">
                  <span>Ready to run this workflow on your repository?</span>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => scrollToAnchor('analyze-repository')}
                    icon={<ArrowRight className="w-3.5 h-3.5" />}
                    iconPosition="right"
                  >
                    Start Analysis
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Section B: Repository Input (The Real Workflow Beginning) ──────── */}
      <section id="analyze-repository" className="py-16 lg:py-24 border-b border-[#E1E6EE] bg-[#F8FAFC] scroll-mt-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="text-center max-w-2xl mx-auto mb-8">
            <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
              Execute Real Migration Intelligence
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#172033] mt-2 tracking-tight">
              Start with your repository
            </h2>
            <p className="text-xs sm:text-sm text-[#526176] mt-3 leading-relaxed">
              Enter a Python repository to discover dependency risks, map actual usage and generate a migration plan grounded in evidence.
            </p>
          </div>

          <div className="bg-white border-2 border-[#E1E6EE] rounded-2xl p-6 lg:p-8 shadow-sm flex flex-col gap-6">
            {/* Backend readiness header */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-[#E1E6EE]">
              <div className="flex items-center gap-2">
                <StatusBadge
                  variant={health.isBackendAvailable ? (health.isModelAvailable ? 'success' : 'warning') : 'neutral'}
                  size="sm"
                  dot
                >
                  {health.isBackendAvailable
                    ? health.isModelAvailable
                      ? 'Backend & Gemma 4 Ready'
                      : 'Backend Connected · Model Offline'
                    : 'Backend Offline'}
                </StatusBadge>
                {health.data?.python_version && (
                  <span className="text-[11px] font-mono text-[#718096]">
                    Python {health.data.python_version}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={handleUseLinkWatch}
                className="text-xs text-[#315BE8] hover:text-[#2648C7] font-medium flex items-center gap-1 cursor-pointer"
              >
                <FolderGit2 className="w-3.5 h-3.5" />
                Use LinkWatch example repository
              </button>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              {/* Source type selector */}
              <div className="flex flex-col gap-2">
                <label className="text-xs font-semibold text-[#172033]">
                  Repository Source
                </label>
                <div className="grid grid-cols-2 gap-3" role="radiogroup">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={sourceKind === 'git_url'}
                    onClick={() => {
                      setSourceKind('git_url');
                      setLocalValidationError(null);
                    }}
                    className={`p-3 rounded-lg border text-left text-xs flex items-center gap-2 cursor-pointer transition-all ${
                      sourceKind === 'git_url'
                        ? 'bg-[#EEF3FF] border-[#315BE8] text-[#172033] font-medium'
                        : 'bg-white border-[#E1E6EE] text-[#526176] hover:bg-[#FAFBFC]'
                    }`}
                  >
                    <Globe className="w-4 h-4 text-[#315BE8]" />
                    <span>Public HTTPS Git URL</span>
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={sourceKind === 'local_path'}
                    onClick={() => {
                      setSourceKind('local_path');
                      setLocalValidationError(null);
                    }}
                    className={`p-3 rounded-lg border text-left text-xs flex items-center gap-2 cursor-pointer transition-all ${
                      sourceKind === 'local_path'
                        ? 'bg-[#EEF3FF] border-[#315BE8] text-[#172033] font-medium'
                        : 'bg-white border-[#E1E6EE] text-[#526176] hover:bg-[#FAFBFC]'
                    }`}
                  >
                    <FolderGit2 className="w-4 h-4 text-[#315BE8]" />
                    <span>Local Repository Path</span>
                  </button>
                </div>
              </div>

              {/* Target input */}
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-[#172033]">
                  {sourceKind === 'git_url' ? 'Git Repository URL' : 'Local Directory Path'}
                </label>
                <input
                  type="text"
                  value={repoValue}
                  onChange={(e) => {
                    setRepoValue(e.target.value);
                    setLocalValidationError(null);
                  }}
                  placeholder={
                    sourceKind === 'git_url'
                      ? 'e.g., https://github.com/rishrek/LinkWatch.git'
                      : 'e.g., C:\\work\\LinkWatch or /home/developer/LinkWatch'
                  }
                  className="w-full px-3.5 py-2.5 bg-white border border-[#E1E6EE] rounded-lg text-xs font-mono text-[#172033] placeholder:text-[#94A3B8] focus:outline-none focus:border-[#315BE8] focus:ring-1 focus:ring-[#315BE8]"
                />
                <span className="text-[11px] text-[#718096]">
                  {sourceKind === 'git_url'
                    ? 'Cloned securely to a disposable local directory for non-executing static discovery.'
                    : 'Path is resolved on the machine running the ExitLens FastAPI backend service.'}
                </span>
              </div>

              {/* Validation or error display */}
              {localValidationError && (
                <div className="p-3 bg-[#FEF0F0] border border-[#FECDCA] rounded-lg text-xs text-[#B42318] flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{localValidationError}</span>
                </div>
              )}

              {submissionError && (
                <div className="p-3 bg-[#FEF0F0] border border-[#FECDCA] rounded-lg text-xs text-[#B42318] flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <div>
                    <span className="font-semibold">Backend Connection Issue: </span>
                    <span>{submissionError.message}</span>
                  </div>
                </div>
              )}

              {/* Analysis options toggles */}
              <div className="p-3.5 bg-[#F8FAFC] rounded-lg border border-[#E1E6EE] flex flex-wrap items-center justify-between gap-4 text-xs">
                <span className="font-semibold text-[#172033] flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-[#526176]" />
                  Analysis Options
                </span>
                <div className="flex flex-wrap items-center gap-4 text-xs text-[#526176]">
                  <label className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={includeTests}
                      onChange={(e) => setIncludeTests(e.target.checked)}
                      className="rounded text-[#315BE8] focus:ring-[#315BE8]"
                    />
                    <span>Include test call-sites</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={useGitHistory}
                      onChange={(e) => setUseGitHistory(e.target.checked)}
                      className="rounded text-[#315BE8] focus:ring-[#315BE8]"
                    />
                    <span>Inspect git history</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={generateRecommendations}
                      onChange={(e) => setGenerateRecommendations(e.target.checked)}
                      className="rounded text-[#315BE8] focus:ring-[#315BE8]"
                    />
                    <span>Gemma 4 migration plans</span>
                  </label>
                </div>
              </div>

              {/* Submit button */}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-[11px] text-[#718096]">
                  Safe static discovery · Zero execution of arbitrary code
                </span>
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  disabled={isSubmitting || isPolling || !repoValue.trim()}
                  icon={
                    isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ArrowRight className="w-4 h-4" />
                    )
                  }
                  iconPosition="right"
                >
                  {isSubmitting ? 'Submitting Repository...' : 'Analyze Repository'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      </section>

      {/* ─── Section C: Live Circuit Progress (Truthful 5-Stage Visualization) ─ */}
      {activeAnalysis && (
        <section id="analysis-progress" className="py-12 border-b border-[#E1E6EE] bg-white scroll-mt-16">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 flex flex-col gap-6">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
                  Live Execution Circuit
                </span>
                <h3 className="text-xl font-bold text-[#172033]">
                  Status: {activeAnalysis.stage || activeAnalysis.status}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={resetActiveAnalysis}
                  icon={<RotateCcw className="w-3.5 h-3.5" />}
                >
                  Reset Analysis
                </Button>
              </div>
            </div>

            {/* 5-Stage Live horizontal pipeline component */}
            <div className="p-6 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl shadow-xs">
              <AnalysisProgress analysis={activeAnalysis} />
            </div>

            {/* Factual summary notice if available */}
            {activeAnalysis.summary && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <div className="p-3.5 bg-white border border-[#E1E6EE] rounded-lg">
                  <span className="text-xl font-bold text-[#172033]">
                    {activeAnalysis.summary.dependencies_discovered}
                  </span>
                  <p className="text-[11px] text-[#718096]">Discovered</p>
                </div>
                <div className="p-3.5 bg-white border border-[#E1E6EE] rounded-lg">
                  <span className="text-xl font-bold text-[#315BE8]">
                    {activeAnalysis.summary.dependencies_flagged}
                  </span>
                  <p className="text-[11px] text-[#718096]">Flagged Risks</p>
                </div>
                <div className="p-3.5 bg-white border border-[#E1E6EE] rounded-lg">
                  <span className="text-xl font-bold text-[#18794E]">
                    {activeAnalysis.summary.recommendations_available}
                  </span>
                  <p className="text-[11px] text-[#718096]">Recommendations</p>
                </div>
                <div className="p-3.5 bg-white border border-[#E1E6EE] rounded-lg">
                  <span className="text-xl font-bold text-[#172033]">
                    {activeAnalysis.summary.checks_passed} / {activeAnalysis.summary.baseline_checks + activeAnalysis.summary.replacement_checks}
                  </span>
                  <p className="text-[11px] text-[#718096]">Checks Passed</p>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* ─── Section D: Evidence-Linked Results & Inventory ────────────────── */}
      {activeAnalysis && (
        <section id="analysis-results" className="py-16 border-b border-[#E1E6EE] bg-[#F8FAFC]">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col gap-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
                  Evidence-Linked Dependency Inventory
                </span>
                <h3 className="text-2xl font-bold text-[#172033]">
                  Discovered Dependencies ({filteredDependencies.length} of {totalCount})
                </h3>
              </div>

              {/* Action shortcuts */}
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload('json')}
                  disabled={downloadingJson}
                  icon={downloadingJson ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileDown className="w-3.5 h-3.5" />}
                >
                  Download JSON
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDownload('md')}
                  disabled={downloadingMd}
                  icon={downloadingMd ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                >
                  Download Markdown
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate('/analysis')}
                  icon={<ArrowRight className="w-3.5 h-3.5" />}
                  iconPosition="right"
                >
                  Full Inventory Workbench
                </Button>
              </div>
            </div>

            {/* Search & filter toolbar */}
            <div className="p-4 bg-white border border-[#E1E6EE] rounded-xl flex flex-wrap items-center justify-between gap-3 shadow-xs">
              <div className="flex items-center gap-2 flex-1 max-w-sm">
                <Search className="w-4 h-4 text-[#718096]" />
                <input
                  type="text"
                  placeholder="Filter dependencies by package name..."
                  value={depSearch}
                  onChange={(e) => setDepSearch(e.target.value)}
                  className="w-full text-xs text-[#172033] focus:outline-none placeholder:text-[#94A3B8]"
                />
              </div>

              <div className="flex items-center gap-1.5 text-xs">
                <span className="text-[#718096]">Severity:</span>
                {(['all', 'high', 'medium', 'low'] as const).map((sev) => (
                  <button
                    key={sev}
                    type="button"
                    onClick={() => setDepSeverityFilter(sev)}
                    className={`px-2.5 py-1 rounded text-xs font-medium cursor-pointer transition-colors ${
                      depSeverityFilter === sev
                        ? 'bg-[#EEF3FF] text-[#315BE8] border border-[#315BE8]'
                        : 'bg-[#F8FAFC] text-[#526176] border border-[#E1E6EE] hover:bg-white'
                    }`}
                  >
                    {sev.charAt(0).toUpperCase() + sev.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Dependency list table */}
            <div className="bg-white border border-[#E1E6EE] rounded-xl overflow-hidden shadow-xs">
              {isDepsLoading ? (
                <div className="p-12 flex flex-col items-center justify-center gap-3 text-xs text-[#718096]">
                  <Loader2 className="w-6 h-6 animate-spin text-[#315BE8]" />
                  <span>Loading dependency inventory from backend...</span>
                </div>
              ) : filteredDependencies.length === 0 ? (
                <div className="p-12 text-center text-xs text-[#718096]">
                  No dependencies match your current filter.
                </div>
              ) : (
                <div className="divide-y divide-[#E1E6EE]">
                  {filteredDependencies.slice(0, 8).map((dep: DependencyListItem) => (
                    <div
                      key={dep.dependency_id}
                      className="p-4 hover:bg-[#FAFBFC] transition-colors flex items-center justify-between gap-4 text-xs"
                    >
                      <div className="flex flex-col gap-1 min-w-[200px]">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-[#172033]">
                            {dep.name}
                          </span>
                          <span className="font-mono text-[11px] text-[#718096]">
                            {dep.declared_version || dep.resolved_version || 'unpinned'}
                          </span>
                        </div>
                        <span className="text-[11px] font-mono text-[#526176] truncate max-w-xs">
                          {dep.manifest_path}
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        <StatusBadge
                          variant={
                            dep.highest_severity === 'critical' || dep.highest_severity === 'high'
                              ? 'failure'
                              : dep.highest_severity === 'medium'
                              ? 'warning'
                              : 'info'
                          }
                          size="sm"
                        >
                          {dep.highest_severity || 'info'}
                        </StatusBadge>

                        <span className="text-[11px] text-[#718096]">
                          {dep.usage_count} call-sites
                        </span>

                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedDepId(dep.dependency_id);
                            setDrawerOpen(true);
                          }}
                        >
                          Inspect Evidence
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* ─── Section E: Evidence & Trust (Restrained Editorial Flow) ───────── */}
      <section id="evidence-trust" className="py-16 lg:py-24 border-b border-[#E1E6EE] bg-white scroll-mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
              Epistemological Integrity
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#172033] mt-2 tracking-tight">
              Evidence should never be confused with a recommendation.
            </h2>
            <p className="text-xs sm:text-sm text-[#526176] mt-3 leading-relaxed">
              ExitLens maintains strict epistemological boundaries across the migration lifecycle. Every claim carries an immutable provenance category so engineering teams can trust the evidence.
            </p>
          </div>

          {/* Clean 4 Core Distinctions Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="p-5 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl flex flex-col gap-2.5 shadow-xs">
              <div className="flex items-center justify-between">
                <StatusBadge variant="info" size="sm">OBSERVED</StatusBadge>
                <FileCode className="w-4 h-4 text-[#315BE8]" />
              </div>
              <span className="font-bold text-sm text-[#172033]">Repository Facts</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Concrete manifest lines, lockfile hashes, and static import call-sites directly discovered from source files.
              </p>
            </div>

            <div className="p-5 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl flex flex-col gap-2.5 shadow-xs">
              <div className="flex items-center justify-between">
                <StatusBadge variant="warning" size="sm">INFERRED</StatusBadge>
                <AlertTriangle className="w-4 h-4 text-[#D97706]" />
              </div>
              <span className="font-bold text-sm text-[#172033]">Deterministic Inferences</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Transparent maintenance-risk indicators triggered by versioned engine rules and linked directly to code lines.
              </p>
            </div>

            <div className="p-5 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl flex flex-col gap-2.5 shadow-xs">
              <div className="flex items-center justify-between">
                <StatusBadge variant="info" size="sm">AI_RECOMMENDATION</StatusBadge>
                <Sparkles className="w-4 h-4 text-[#315BE8]" />
              </div>
              <span className="font-bold text-sm text-[#172033]">Gemma 4 Proposals</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Structured candidate migration steps, API difference mapping, and suggested tests generated by local AI.
              </p>
            </div>

            <div className="p-5 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl flex flex-col gap-2.5 shadow-xs">
              <div className="flex items-center justify-between">
                <StatusBadge variant="success" size="sm">EXECUTION_RESULT</StatusBadge>
                <CheckCircle2 className="w-4 h-4 text-[#18794E]" />
              </div>
              <span className="font-bold text-sm text-[#172033]">Verified Outcomes</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Real trial outcomes with bounded execution runtimes, exit codes, and raw stdout/stderr from disposable runs.
              </p>
            </div>
          </div>

          {/* Honest Notice on NOT_VERIFIED states */}
          <div className="max-w-3xl mx-auto p-4 bg-[#F8FAFC] border border-[#E1E6EE] rounded-xl flex items-center gap-3 text-xs text-[#526176]">
            <div className="w-8 h-8 rounded-lg bg-white border border-[#E1E6EE] flex items-center justify-center shrink-0">
              <HelpCircle className="w-4 h-4 text-[#718096]" />
            </div>
            <div>
              <span className="font-semibold text-[#172033]">Explicit NOT_VERIFIED Standard: </span>
              Unattempted tests, untried migrations, or skipped runs remain permanently tagged as <code className="text-[#172033] bg-white px-1.5 py-0.5 rounded border border-[#E1E6EE]">NOT_VERIFIED</code>. ExitLens never disguises an AI conjecture as a verified trial run.
            </div>
          </div>
        </div>
      </section>

      {/* ─── Section F: Dependency Exit Capsule ────────────────────────────── */}
      <section id="exit-capsule" className="py-16 lg:py-24 border-b border-[#E1E6EE] bg-[#F8FAFC] scroll-mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <span className="text-xs font-mono uppercase tracking-wider text-[#315BE8] font-semibold">
              Canonical Migration Artifact
            </span>
            <h2 className="text-2xl sm:text-3xl font-bold text-[#172033] mt-2 tracking-tight">
              The Dependency Exit Capsule
            </h2>
            <p className="text-xs sm:text-sm text-[#526176] mt-3 leading-relaxed">
              Every flagged dependency is codified into an exportable capsule containing nine mandatory sections. Available in dual JSON and Markdown representations rendered from a single schema.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">01 · Dependency Details</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Declared constraint, resolved version, manifest path, and package summary.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">02 · Risk Indicators</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Deterministic rule signals, severity levels, explanations, and evidence links.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">03 · Usage Locations</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                File paths, line numbers, import names, and source excerpts where code calls the package.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">04 · Proposed Replacement</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Candidate package distribution, specifier, rationale, and specific limitations.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">05 · Migration Steps</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Step-by-step code modifications with import rewrites and example snippets.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">06 · Suggested Tests</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Counterfactual test cases and validation commands suggested by Gemma 4.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">07 · Executed Test Results</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Real trial outcomes comparing baseline against candidate replacement runs.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">08 · Compatibility Gaps</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Breaking API signatures, parameter differences, and behavior divergences.
              </p>
            </div>

            <div className="p-4 rounded-xl border border-[#E1E6EE] bg-white flex flex-col gap-2 shadow-xs">
              <span className="font-bold text-xs text-[#315BE8]">09 · Open Concerns</span>
              <p className="text-xs text-[#526176] leading-relaxed">
                Unresolved architectural questions, performance caveats, and long-term risks.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Section G: Final Call to Action ──────────────────────────────── */}
      <section className="py-16 lg:py-24 bg-gradient-to-b from-[#F8FAFC] to-white">
        <div className="max-w-4xl mx-auto px-4 text-center flex flex-col items-center gap-6">
          <div className="w-12 h-12 rounded-2xl bg-[#EEF3FF] border border-[#C6D8FF] flex items-center justify-center text-[#315BE8] shadow-xs">
            <ShieldCheck className="w-6 h-6" />
          </div>

          <h2 className="text-3xl sm:text-4xl font-extrabold text-[#172033] tracking-tight">
            Understand the risk. Plan the exit. Preserve the evidence.
          </h2>

          <p className="text-sm sm:text-base text-[#526176] max-w-2xl leading-relaxed">
            Take control of brittle, deprecated, and unmaintained Python dependencies with evidence-grounded intelligence and local Gemma 4.
          </p>

          <Button
            variant="primary"
            size="lg"
            onClick={() => scrollToAnchor('analyze-repository')}
            icon={<ArrowRight className="w-4 h-4" />}
            iconPosition="right"
          >
            Start with your repository
          </Button>
        </div>
      </section>

      {/* ─── Footer (With Application Links for Complete Navigation) ──────── */}
      <footer className="border-t border-[#E1E6EE] bg-white py-8 text-xs text-[#718096]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[#172033]">ExitLens</span>
            <span>—</span>
            <span>Gemma 4 Dependency Resilience Workbench</span>
          </div>

          <div className="flex items-center gap-6">
            <Link to="/workspace" className="hover:text-[#315BE8] transition-colors">
              Workspace
            </Link>
            <Link to="/analysis" className="hover:text-[#315BE8] transition-colors">
              Inventory
            </Link>
            <Link to="/verification" className="hover:text-[#315BE8] transition-colors">
              Verification
            </Link>
            <Link to="/capsule" className="hover:text-[#315BE8] transition-colors">
              Capsule
            </Link>
          </div>
        </div>
      </footer>

      {/* ─── Dependency Detail Drawer ──────────────────────────────────────── */}
      <DependencyDetailDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        dependencyName={selectedDepName}
        detailState={detailState}
      />
    </div>
  );
}
