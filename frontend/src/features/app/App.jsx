import React, { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import toast, { useToaster } from 'react-hot-toast/headless';
import 'bootstrap/dist/css/bootstrap.min.css';
import '../root.css';
import '../report-generator/ReportGenerator.css';

import MainHeader from '../layout/MainHeader';
import SiteFooter from '../layout/SiteFooter';
import Login from '../login/Login';

import Main from '../main/Main';
import Report from '../report/Report';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const STEP_LABELS = {
  initialized: '준비 중',
  pending: '대기 중',
  validate_input: '입력 확인 중',
  macro: '매크로 분석 중',
  accounting: '재무 분석 중',
  research: '뉴스 분석 중',
  youtube_rag: '유튜브 인사이트 검색 중',
  price: '가격 기준 계산 중',
  analysis: '리포트 작성 중',
  report_save: '리포트 저장 중',
  summary_save: '최종 반영 중',
  report_generated: '리포트 생성 완료',
  completed: '완료',
  success: '완료',
  failed: '실패',
  partial_failed: '일부 실패',
};

function getFriendlyStepLabel(step, status) {
  if (status === 'success') return STEP_LABELS.completed;
  if (status === 'failed') return STEP_LABELS.failed;
  return STEP_LABELS[step] || STEP_LABELS[status] || '진행 중';
}

function summarizeError(error) {
  if (!error) return '';

  const text = Array.isArray(error) ? error.join(' / ') : String(error);
  return text.length > 72 ? `${text.slice(0, 72)}...` : text;
}

function normalizeTargetStatusItems(items = [], fallbackStatus = 'pending') {
  return (items || []).map((item) => {
    const status = item.status || fallbackStatus;
    const currentStep = item.current_step || status || 'pending';

    return {
      ticker: item.ticker || '',
      company_name: item.company_name || item.company || item.name || item.ticker || '종목',
      status,
      current_step: currentStep,
      label: getFriendlyStepLabel(currentStep, status),
      errors: item.errors || (item.error ? [item.error] : []),
      summary_saved: Boolean(item.summary_saved),
    };
  });
}

function buildPendingTargetsFromStocks(stocks = []) {
  return normalizeTargetStatusItems(
    stocks.map((stock) => ({
      ticker: stock.ticker,
      company_name: stock.company || stock.company_name,
      status: 'pending',
      current_step: 'pending',
      errors: [],
      summary_saved: false,
    })),
  );
}

function hasFailedTarget(items = []) {
  return items.some((item) => ['failed', 'partial_failed'].includes(item.status));
}

function isTerminalTarget(item) {
  return ['completed', 'success', 'failed', 'partial_failed'].includes(item.status);
}

function isCommonMacroActive(items = []) {
  const activeItems = items.filter((item) => !isTerminalTarget(item));
  const preStockSteps = new Set(['initialized', 'pending', 'validate_input', 'macro']);

  return (
    activeItems.some((item) => item.current_step === 'macro') &&
    activeItems.every((item) => preStockSteps.has(item.current_step || 'pending'))
  );
}

function getDisplayTargetItems(items = []) {
  return items.map((item) => {
    if (item.current_step !== 'macro' || isTerminalTarget(item)) {
      return item;
    }

    return {
      ...item,
      label: STEP_LABELS.pending,
    };
  });
}

const STOCK_STEP_PROGRESS = {
  pending: 0,
  initialized: 0,
  validate_input: 0,
  macro: 0,
  accounting: 25,
  research: 50,
  youtube_rag: 70,
  price: 75,
  analysis: 85,
  report_generated: 90,
  report_save: 95,
  summary_save: 98,
  completed: 100,
  success: 100,
  failed: 100,
  partial_failed: 100,
};

function getStockStepProgress(item) {
  const step = item.current_step || item.status || 'pending';
  return STOCK_STEP_PROGRESS[step] ?? STOCK_STEP_PROGRESS[item.status] ?? 0;
}

function isFinishingReports(items = []) {
  return items.some((item) =>
    ['report_generated', 'report_save', 'summary_save'].includes(item.current_step),
  );
}

const JOB_STEPS = [
  {
    key: 'queued',
    label: '요청 접수',
    description: '선택한 종목을 분석 대기열에 올립니다.',
  },
  {
    key: 'collecting',
    label: '데이터 수집',
    description: '재무, 뉴스, 매크로, 유튜브 RAG 데이터를 모읍니다.',
  },
  {
    key: 'writing',
    label: '리포트 작성',
    description: 'AI가 수집한 근거를 종합해 리포트를 작성합니다.',
  },
  {
    key: 'done',
    label: '완료',
    description: '최신 리포트를 화면에 반영합니다.',
  },
];

function getProgress(status, pollCount, targetItems = []) {
  if (status === 'success') return 100;
  if (status === 'failed') return 100;
  if (status === 'pending') return 5;

  const items = targetItems || [];

  if (status === 'running' && items.length > 0) {
    if (items.every((item) => isTerminalTarget(item))) return 100;

    if (isCommonMacroActive(items)) return 10;

    const averageStockProgress =
      items.reduce((sum, item) => sum + getStockStepProgress(item), 0) / items.length;
    const progress = 20 + averageStockProgress * 0.8;

    return Math.max(20, Math.min(99, Math.round(progress)));
  }

  if (status === 'running') return Math.min(20, 10 + pollCount * 2);

  return 0;
}

function getStepClassName(step, activeStep, status) {
  const activeIndex = JOB_STEPS.findIndex((item) => item.key === activeStep);
  const stepIndex = JOB_STEPS.findIndex((item) => item.key === step.key);

  const isActive = activeStep === step.key;
  const isComplete =
    status === 'success' ||
    (activeIndex >= 0 && stepIndex < activeIndex);

  return `report-progress-step ${isActive ? 'active' : ''} ${
    isComplete ? 'complete' : ''
  }`;
}

function ReportProgressToast({
  status,
  message,
  jobId,
  progress,
  error,
  targetItems = [],
  onDismiss,
}) {
  const title =
    status === 'success'
      ? '리포트 생성 완료'
      : status === 'failed'
        ? '리포트 생성 실패'
        : 'AI 리포트 생성 중';

  const hasPartialFailure = status === 'success' && hasFailedTarget(targetItems);
  const commonMacroActive = isCommonMacroActive(targetItems);
  const finishingReports = isFinishingReports(targetItems);
  const displayTargetItems = getDisplayTargetItems(targetItems);
  const displayTitle =
    status === 'success'
      ? hasPartialFailure
        ? '리포트 생성 일부 실패'
        : '리포트 생성 완료'
      : status === 'failed'
        ? '리포트 생성 실패'
        : '리포트 생성 중';

  const finalTitle =
    status === 'success'
      ? hasPartialFailure
        ? '리포트 생성 일부 실패'
        : '리포트 생성 완료'
      : status === 'failed'
        ? '리포트 생성 실패'
        : finishingReports
          ? 'AI 리포트 마무리 중'
          : 'AI 리포트 분석 중';
  const finalMessage =
    status === 'success'
      ? hasPartialFailure
        ? '일부 종목 분석 중 문제가 발생했습니다.'
        : '최신 리포트가 화면에 반영되었습니다.'
      : status === 'failed'
        ? '분석 중 문제가 발생했습니다.'
        : commonMacroActive
          ? '공통 매크로 분석을 진행 중입니다. 종목별 분석은 이후 순차적으로 시작됩니다.'
          : finishingReports
            ? '리포트를 저장하고 화면에 반영하는 중입니다.'
            : 'AI가 종목별 데이터를 분석하고 있습니다. 아래 종목별 진행 상태를 확인해주세요.';

  return (
    <div className={`report-progress-panel report-progress-toast status-${status || 'pending'}`}>
      <div className="report-progress-header">
        <div className="report-toast-main">
          <strong className="report-toast-title">{finalTitle || displayTitle || title}</strong>
          <div className="report-toast-message">
            {finalMessage || message}
          </div>

        </div>

        <div className="report-toast-actions">
          <span className="report-toast-percent">{progress}%</span>

          {(status === 'success' || status === 'failed') && (
            <button
              type="button"
              className="report-toast-close"
              onClick={onDismiss}
              aria-label="알림 닫기"
            >
              X
            </button>
          )}
        </div>
      </div>

      <div className="report-progress-track" aria-label="리포트 생성 진행률">
        <div
          className="report-progress-bar"
          style={{ width: `${progress}%` }}
        />
      </div>

      {commonMacroActive && (
        <div className="report-common-step">
          공통 매크로 분석 중
        </div>
      )}

      {displayTargetItems.length > 0 && (
        <div className="report-target-status-list">
          {displayTargetItems.map((item) => {
            const rowStatus =
              item.status === 'completed' || item.status === 'success'
                ? 'success'
                : item.status === 'failed' || item.status === 'partial_failed'
                  ? 'failed'
                  : 'running';

            return (
              <div
                className={`report-target-status-row status-${rowStatus}`}
                key={`${item.ticker || item.company_name}-${item.company_name}`}
              >
                <span className="report-target-status-name">{item.company_name}</span>
                <span className="report-target-status-step">{item.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {error && (
        <div className="report-toast-error small">
          {error}
        </div>
      )}
    </div>
  );
}

function AppToastViewport() {
  const { toasts, handlers } = useToaster();
  const { startPause, endPause, calculateOffset, updateHeight } = handlers;

  return (
    <div
      className="app-toast-viewport"
      onMouseEnter={startPause}
      onMouseLeave={endPause}
    >
      {toasts.map((toastItem) => {
        const offset = calculateOffset(toastItem, {
          reverseOrder: false,
          gutter: 12,
        });

        const ref = (element) => {
          if (!element) return;

          const height = element.getBoundingClientRect().height;

          if (toastItem.height !== height) {
            updateHeight(toastItem.id, height);
          }
        };

        return (
          <div
            key={toastItem.id}
            ref={ref}
            className={`app-toast-item ${
              toastItem.visible ? 'app-toast-visible' : 'app-toast-hidden'
            }`}
            style={{
              transform: `translateY(-${offset}px) scale(${
                toastItem.visible ? 1 : 0.96
              })`,
            }}
            {...toastItem.ariaProps}
          >
            {toastItem.message}
          </div>
        );
      })}
    </div>
  );
}

function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');

  const [reportRefreshKey, setReportRefreshKey] = useState(0);
  const [reportJobId, setReportJobId] = useState('');
  const [reportJobStatus, setReportJobStatus] = useState('');
  const [reportStatusMessage, setReportStatusMessage] = useState('');
  const [reportTargetsStatus, setReportTargetsStatus] = useState([]);
  const [isReportSubmitting, setIsReportSubmitting] = useState(false);

  const pollingTimerRef = useRef(null);
  const reportToastIdRef = useRef(null);
  const pollCountRef = useRef(0);

  const isReportWorking =
    isReportSubmitting ||
    reportJobStatus === 'pending' ||
    reportJobStatus === 'running';

  const stopReportPolling = () => {
    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  };

  const dismissReportToast = () => {
    if (reportToastIdRef.current) {
      toast.dismiss(reportToastIdRef.current);
      reportToastIdRef.current = null;
    }
  };

  const showReportToast = ({
    status,
    message,
    currentJobId,
    error,
    pollCountValue,
    targetItems,
  }) => {
    const safeStatus = status || 'pending';
    const safePollCount =
      typeof pollCountValue === 'number'
        ? pollCountValue
        : pollCountRef.current;

    const progress = getProgress(safeStatus, safePollCount, targetItems || reportTargetsStatus);
    const toastId =
      reportToastIdRef.current ||
      `report-progress-${currentJobId || Date.now()}`;

    reportToastIdRef.current = toastId;

    toast.custom(
      <ReportProgressToast
        status={safeStatus}
        message={message}
        jobId={currentJobId}
        progress={progress}
        error={summarizeError(error)}
        targetItems={targetItems || reportTargetsStatus}
        onDismiss={() => {
          toast.dismiss(toastId);

          if (reportToastIdRef.current === toastId) {
            reportToastIdRef.current = null;
          }
        }}
      />,
      {
        id: toastId,
        duration: safeStatus === 'success' || safeStatus === 'failed' ? 5000 : Infinity,
        removeDelay: 500,
        ariaProps: {
          role: 'status',
          'aria-live': 'polite',
        },
      },
    );
  };

  const fetchReportJobStatus = async (targetJobId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/report-status/${targetJobId}`, {
        method: 'GET',
        credentials: 'include',
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || '작업 상태를 확인하지 못했습니다.');
      }

      const targetItems = normalizeTargetStatusItems(
        data.targets_status || data.report_states || data.items || data.stocks || [],
        data.status,
      );

      setReportJobStatus(data.status);
      setReportTargetsStatus(targetItems);

      if (data.status === 'pending') {
        const message = '리포트 생성 요청을 접수했습니다.';

        setReportStatusMessage(message);

        showReportToast({
          status: data.status,
          message,
          currentJobId: targetJobId,
          pollCountValue: pollCountRef.current,
          targetItems,
        });

        return;
      }

      if (data.status === 'running') {
        const nextPollCount = pollCountRef.current + 1;
        const message = '분석을 진행 중입니다. 실제 AI 리포트 생성은 몇 분 이상 걸릴 수 있습니다.';

        pollCountRef.current = nextPollCount;
        setReportStatusMessage(message);

        showReportToast({
          status: data.status,
          message,
          currentJobId: targetJobId,
          pollCountValue: nextPollCount,
          targetItems,
        });

        return;
      }

      if (data.status === 'success') {
        const message = '리포트 생성이 완료되었습니다. 최신 리포트를 불러옵니다.';

        stopReportPolling();
        setIsReportSubmitting(false);
        setReportStatusMessage(message);

        showReportToast({
          status: data.status,
          message,
          currentJobId: targetJobId,
          pollCountValue: pollCountRef.current,
          targetItems,
        });

        setReportRefreshKey((prev) => prev + 1);

        return;
      }

      if (data.status === 'failed') {
        const message = data.error || '리포트 생성 중 오류가 발생했습니다.';

        stopReportPolling();
        setIsReportSubmitting(false);
        setReportStatusMessage('');

        showReportToast({
          status: data.status,
          message: '리포트 생성 중 오류가 발생했습니다.',
          currentJobId: targetJobId,
          error: message,
          pollCountValue: pollCountRef.current,
          targetItems,
        });
      }
    } catch (error) {
      stopReportPolling();
      setIsReportSubmitting(false);
      setReportJobStatus('failed');
      setReportStatusMessage('');

      showReportToast({
        status: 'failed',
        message: '작업 상태를 확인하지 못했습니다.',
        currentJobId: targetJobId,
        error: error.message,
        pollCountValue: pollCountRef.current,
      });
    }
  };

  const startReportPolling = (targetJobId) => {
    stopReportPolling();

    pollCountRef.current = 0;

    fetchReportJobStatus(targetJobId);

    pollingTimerRef.current = setInterval(() => {
      fetchReportJobStatus(targetJobId);
    }, 3000);
  };

  const startReportJob = async (selectedStocks) => {
    const stocks = Array.isArray(selectedStocks)
      ? selectedStocks
      : selectedStocks
        ? [selectedStocks]
        : [];

    if (stocks.length === 0) {
      throw new Error('분석할 종목을 1개 이상 선택해 주세요.');
    }

    dismissReportToast();

    pollCountRef.current = 0;
    const initialTargetItems = buildPendingTargetsFromStocks(stocks);

    setIsReportSubmitting(true);
    setReportJobId('');
    setReportJobStatus('');
    setReportTargetsStatus(initialTargetItems);
    setReportStatusMessage('리포트 생성 요청을 보내는 중입니다.');

    showReportToast({
      status: 'pending',
      message: `${stocks.length}개 종목 리포트 생성 요청을 보내는 중입니다.`,
      pollCountValue: 0,
      targetItems: initialTargetItems,
    });

    try {
      const res = await fetch(`${API_BASE_URL}/api/run-report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          stocks: stocks.map((stock) => ({
            ticker: stock.ticker,
            company: stock.company,
            exchange: stock.exchange,
            quote_type: stock.quote_type,
          })),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || '리포트 생성 요청에 실패했습니다.');
      }

      const nextStatus = data.status || 'pending';
      const message = `${stocks.length}개 종목 리포트 생성 작업을 시작했습니다.`;

      setReportJobId(data.job_id);
      setReportJobStatus(nextStatus);
      setReportStatusMessage(message);
      setReportTargetsStatus(initialTargetItems);

      showReportToast({
        status: nextStatus,
        message,
        currentJobId: data.job_id,
        pollCountValue: 0,
        targetItems: initialTargetItems,
      });

      startReportPolling(data.job_id);

      return data;
    } catch (error) {
      setIsReportSubmitting(false);
      setReportJobStatus('failed');
      setReportStatusMessage('');
      const failedTargetItems = initialTargetItems.map((item) => ({
        ...item,
        status: 'failed',
        current_step: 'failed',
        label: getFriendlyStepLabel('failed', 'failed'),
        errors: [error.message],
      }));
      setReportTargetsStatus(failedTargetItems);

      showReportToast({
        status: 'failed',
        message: '리포트 생성 요청에 실패했습니다.',
        error: error.message,
        pollCountValue: 0,
        targetItems: failedTargetItems,
      });

      throw error;
    }
  };

  const checkAuth = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/me`, {
        method: 'GET',
        credentials: 'include',
      });

      if (!res.ok) {
        setIsAuthenticated(false);
        setUsername('');
        return;
      }

      const data = await res.json();

      setIsAuthenticated(Boolean(data.authenticated));
      setUsername(data.username || '');
    } catch (error) {
      setIsAuthenticated(false);
      setUsername('');
    } finally {
      setAuthChecked(true);
    }
  };

  const handleLoginSuccess = (loginData) => {
    setIsAuthenticated(true);
    setUsername(loginData.username || '');
  };

  const handleLogout = async () => {
    stopReportPolling();
    dismissReportToast();

    try {
      await fetch(`${API_BASE_URL}/api/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('로그아웃 실패:', error);
    } finally {
      setIsAuthenticated(false);
      setUsername('');
    }
  };

  useEffect(() => {
    checkAuth();

    return () => {
      stopReportPolling();
      dismissReportToast();
    };
  }, []);

  if (!authChecked) {
    return (
      <>
        <div className="min-vh-100 d-flex align-items-center justify-content-center">
          <div className="text-center text-muted">
            <div className="spinner-border spinner-border-sm me-2" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            로그인 상태 확인 중...
          </div>
        </div>

        <AppToastViewport />
      </>
    );
  }

  if (!isAuthenticated) {
    return (
      <>
        <div className="app-shell">
          <main className="main-content">
            <Login onLoginSuccess={handleLoginSuccess} />
          </main>
          <SiteFooter />
        </div>
        <AppToastViewport />
      </>
    );
  }

  return (
    <>
      <BrowserRouter>
        <div className="app-shell">
          <MainHeader username={username} onLogout={handleLogout} />
          <main className="main-content">
            <Routes>
              <Route
                path="/"
                element={
                  <Main
                    reportRefreshKey={reportRefreshKey}
                    onStartReportJob={startReportJob}
                    isReportWorking={isReportWorking}
                    reportJobStatus={reportJobStatus}
                    reportStatusMessage={reportStatusMessage}
                    reportTargetsStatus={reportTargetsStatus}
                  />
                }
              />
              <Route
                path="/report"
                element={<Report refreshKey={reportRefreshKey} />}
              />
            </Routes>
          </main>
          <SiteFooter />
        </div>
      </BrowserRouter>

      <AppToastViewport />
    </>
  );
}

export default App;
