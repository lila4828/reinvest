import React from 'react';

function ReportList({ reports, isLoading, onReportClick }) {
  if (isLoading) {
    return (
      <div className="text-center my-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading...</span>
        </div>
        <p className="mt-2 text-muted fw-bold">리포트 목록을 동기화 중입니다...</p>
      </div>
    );
  }

  if (reports.length === 0) {
    return <p className="text-muted">아직 생성된 리포트가 없습니다.</p>;
  }

  return (
    <div className="list-group">
      {reports.map((report, index) => (
        <button
          type="button"
          key={`${report.date}-${report.filename}-${index}`}
          className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
          onClick={() => onReportClick(report)}
        >
          <span>
            📄 <strong>{report.date}</strong> {report.display_name}
          </span>
          <span className={`badge rounded-pill ${report.is_summary ? 'bg-primary' : 'bg-secondary'}`}>
            {report.is_summary ? '종합' : '개별'}
          </span>
        </button>
      ))}
    </div>
  );
}

export default ReportList;