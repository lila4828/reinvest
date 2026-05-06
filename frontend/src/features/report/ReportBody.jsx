import React from 'react';
import './ReportBody.css';
import ReportList from './ReportList';
import ReportDetail from './ReportDetail';
import { useReports } from './useReports';

function ReportBody({ refreshKey = 0 }) {
  const {
    reports,
    selectedReport,
    reportContent,
    isLoadingList,
    isLoadingDetail,
    errorMsg,
    handleReportClick,
    handleBack
  } = useReports(refreshKey);

  return (
    <div className="container mt-4 report-body-panel">
      <h2 className="fw-bold">{selectedReport ? '투자 분석 리포트 상세' : '투자 분석 리포트 목록'}</h2>
      <hr />

      {errorMsg && (
        <div className="alert alert-danger" role="alert">
          {errorMsg}
        </div>
      )}

      {selectedReport ? (
        <ReportDetail
          content={reportContent}
          isLoading={isLoadingDetail}
          onBack={handleBack}
        />
      ) : (
        <ReportList
          reports={reports}
          isLoading={isLoadingList}
          onReportClick={handleReportClick}
        />
      )}
    </div>
  );
}

export default ReportBody;