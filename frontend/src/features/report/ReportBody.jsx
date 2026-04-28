import React from 'react';
import './ReportBody.css';
import ReportList from './ReportList.jsx';
import ReportDetail from './ReportDetail.jsx';
import { useReports } from './useReports';

function ReportBody() {
  const {
    reports,
    selectedReport,
    reportContent,
    isLoadingList,
    isLoadingDetail,
    errorMsg,
    handleReportClick,
    handleBack
  } = useReports();

  return (
    <div className="container mt-4 report-body-panel">
      <h2 className="fw-bold">{selectedReport ? '투자 분석 리포트 상세' : '투자 분석 리포트 목록'}</h2>
      <hr />
      
      {/* 에러 발생 시 안내창 */}
      {errorMsg && (
        <div className="alert alert-danger" role="alert">
          {errorMsg}
        </div>
      )}

      {/* 선택된 리포트가 있으면 마크다운 화면 렌더링, 없으면 리스트 렌더링 */}
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
