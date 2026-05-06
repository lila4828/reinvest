import React, { useEffect, useRef, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import toast, { useToaster } from 'react-hot-toast/headless';
import 'bootstrap/dist/css/bootstrap.min.css';
import '../root.css';
import '../report-generator/ReportGenerator.css';

import MainHeader from '../layout/MainHeader';
import Login from '../login/Login';

import Main from '../main/Main';
import Report from '../report/Report';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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

function getProgress(status, pollCount) {
  if (status === 'success') return 100;
  if (status === 'failed') return 100;
  if (status === 'pending') return 18;
  if (status === 'running') return Math.min(88, 35 + pollCount * 6);

  return 0;
}

function getActiveStep(status, progress) {
  if (status === 'success') return 'done';
  if (status === 'failed') return 'writing';
  if (status === 'pending') return 'queued';
  if (status === 'running' && progress >= 62) return 'writing';
  if (status === 'running') return 'collecting';

  return '';
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
  activeStep,
  error,
  onDismiss,
}) {
  const title =
    status === 'success'
      ? '리포트 생성 완료'
      : status === 'failed'
        ? '리포트 생성 실패'
        : 'AI 리포트 생성 중';

  return (
    <div className={`report-progress-panel report-progress-toast status-${status || 'pending'}`}>
      <div className="report-progress-header">
        <div className="report-toast-main">
          <strong className="report-toast-title">{title}</strong>
          <div className="report-toast-message">
            {message || '리포트 생성 상태를 확인 중입니다.'}
          </div>

          {jobId && (
            <div className="report-progress-job small text-muted">
              Job ID: {jobId}
            </div>
          )}
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

      <div className="report-progress-steps">
        {JOB_STEPS.map((step) => (
          <div
            key={step.key}
            className={getStepClassName(step, activeStep, status)}
          >
            <span />
            <div>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
          </div>
        ))}
      </div>

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
  }) => {
    const safeStatus = status || 'pending';
    const safePollCount =
      typeof pollCountValue === 'number'
        ? pollCountValue
        : pollCountRef.current;

    const progress = getProgress(safeStatus, safePollCount);
    const activeStep = getActiveStep(safeStatus, progress);

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
        activeStep={activeStep}
        error={error}
        onDismiss={() => {
          toast.dismiss(toastId);

          if (reportToastIdRef.current === toastId) {
            reportToastIdRef.current = null;
          }
        }}
      />,
      {
        id: toastId,
        duration: safeStatus === 'success' ? 5000 : Infinity,
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

      setReportJobStatus(data.status);

      if (data.status === 'pending') {
        const message = '리포트 생성 요청을 접수했습니다.';

        setReportStatusMessage(message);

        showReportToast({
          status: data.status,
          message,
          currentJobId: targetJobId,
          pollCountValue: pollCountRef.current,
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

    setIsReportSubmitting(true);
    setReportJobId('');
    setReportJobStatus('');
    setReportStatusMessage('리포트 생성 요청을 보내는 중입니다.');

    showReportToast({
      status: 'pending',
      message: `${stocks.length}개 종목 리포트 생성 요청을 보내는 중입니다.`,
      pollCountValue: 0,
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

      showReportToast({
        status: nextStatus,
        message,
        currentJobId: data.job_id,
        pollCountValue: 0,
      });

      startReportPolling(data.job_id);

      return data;
    } catch (error) {
      setIsReportSubmitting(false);
      setReportJobStatus('failed');
      setReportStatusMessage('');

      showReportToast({
        status: 'failed',
        message: '리포트 생성 요청에 실패했습니다.',
        error: error.message,
        pollCountValue: 0,
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
        <Login onLoginSuccess={handleLoginSuccess} />
        <AppToastViewport />
      </>
    );
  }

  return (
    <>
      <BrowserRouter>
        <MainHeader username={username} onLogout={handleLogout} />
        <div className="main-content">
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
                />
              }
            />
            <Route
              path="/report"
              element={<Report refreshKey={reportRefreshKey} />}
            />
          </Routes>
        </div>
      </BrowserRouter>

      <AppToastViewport />
    </>
  );
}

export default App;