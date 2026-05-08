import React, { useEffect } from 'react';
import './ReportBody.css';
import ReportList from './ReportList';
import ReportDetail from './ReportDetail';
import { useReports } from './useReports';

function ReportBody({ refreshKey = 0 }) {
  const {
    reports,
    selectedReport,
    reportContent,
    macroData,
    isLoadingList,
    isLoadingDetail,
    errorMsg,
    stockKeywordParam,
    handleReportClick,
    handleBack
  } = useReports(refreshKey);

  useEffect(() => {
    if (!selectedReport) {
      return;
    }

    requestAnimationFrame(() => {
      window.scrollTo({
        top: 0,
        behavior: 'smooth',
      });
    });
  }, [selectedReport?.date, selectedReport?.filename]);

  return (
    <div className="container-fluid report-workspace mt-4">
      <div className="report-workspace-title">
        <div>
          <h2 className="fw-bold mb-1">투자 분석 리포트</h2>
        </div>

        {selectedReport && (
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary report-clear-selection"
            onClick={handleBack}
          >
            선택 해제
          </button>
        )}
      </div>
      <hr />

      {errorMsg && (
        <div className="alert alert-danger" role="alert">
          {errorMsg}
        </div>
      )}

      <div className={`report-workspace-grid ${selectedReport ? 'has-selection' : ''}`}>
        <aside className="report-workspace-list">
          <ReportList
            reports={reports}
            isLoading={isLoadingList}
            onReportClick={handleReportClick}
            selectedReport={selectedReport}
            initialStockKeyword={stockKeywordParam}
          />
        </aside>

        <section className="report-workspace-detail">
          {selectedReport ? (
            <ReportDetail
              report={selectedReport}
              content={reportContent}
              macroData={macroData}
              isLoading={isLoadingDetail}
              onBack={handleBack}
              showBackButton={false}
            />
          ) : (
            <div className="report-empty-detail border rounded shadow-sm">
              <strong>리포트를 선택해 주세요.</strong>
              <p className="text-muted mb-0">
                왼쪽 목록에서 종목을 선택하면 이 영역에 상세 리포트와 실적 차트가 표시됩니다.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export default ReportBody;
