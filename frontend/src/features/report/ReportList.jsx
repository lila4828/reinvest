import React, { useEffect, useMemo, useState } from 'react';

function getReportTitle(report) {
  if (!report) return '리포트';

  const displayName = report.display_name || report.filename || '개별 리포트';
  const baseName = displayName.replace(/\.md$/i, '');
  const separatorIndex = baseName.lastIndexOf('_');

  if (separatorIndex > 0 && separatorIndex < baseName.length - 1) {
    return baseName
      .slice(0, separatorIndex)
      .replace(/\([^)]*\)/g, '')
      .replace(/_/g, ' ')
      .trim();
  }

  return baseName
    .replace(/\([^)]*\)/g, '')
    .replace(/_/g, ' ')
    .trim();
}

function getReportTicker(report) {
  const source = report?.filename || report?.display_name || '';
  const baseName = source.replace(/\.md$/i, '');
  const separatorIndex = baseName.lastIndexOf('_');

  if (separatorIndex <= 0 || separatorIndex >= baseName.length - 1) {
    return '';
  }

  return baseName.slice(separatorIndex + 1).toUpperCase();
}

function getReportMarketLabel(report) {
  if (report?.market_label) {
    return report.market_label;
  }

  const ticker = getReportTicker(report);

  if (ticker.endsWith('.KS')) return '코스피';
  if (ticker.endsWith('.KQ')) return '코스닥';
  if (ticker) return '미국';

  return '';
}

function getSearchableStockName(report) {
  if (!report) return '';

  return [
    report.display_name,
    report.filename,
    getReportTitle(report),
    report.exchange,
    getReportMarketLabel(report),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function groupReportsByDate(reports) {
  return reports.reduce((acc, report) => {
    const date = report.date || '날짜 없음';

    if (!acc[date]) {
      acc[date] = [];
    }

    acc[date].push(report);
    return acc;
  }, {});
}

function ReportList({
  reports,
  isLoading,
  onReportClick,
  selectedReport = null,
  initialStockKeyword = '',
}) {
  const [stockKeyword, setStockKeyword] = useState(initialStockKeyword);
  const [selectedDate, setSelectedDate] = useState('');

  useEffect(() => {
    setStockKeyword(initialStockKeyword);
  }, [initialStockKeyword]);

  const filteredReports = useMemo(() => {
    const normalizedStockKeyword = stockKeyword.trim().toLowerCase();

    return reports.filter((report) => {
      const matchesStock =
        !normalizedStockKeyword ||
        getSearchableStockName(report).includes(normalizedStockKeyword);

      const matchesDate =
        !selectedDate ||
        String(report.date || '') === selectedDate;

      return matchesStock && matchesDate;
    });
  }, [reports, stockKeyword, selectedDate]);

  const dateGroups = useMemo(() => {
    const grouped = groupReportsByDate(reports);

    return Object.entries(grouped)
      .sort(([dateA], [dateB]) => String(dateB).localeCompare(String(dateA)))
      .map(([date, dateReports]) => ({
        date,
        count: dateReports.length,
      }));
  }, [reports]);

  const sortedReports = useMemo(() => {
    return [...filteredReports].sort((a, b) => {
      const dateCompare = String(b.date || '').localeCompare(String(a.date || ''));

      if (dateCompare !== 0) {
        return dateCompare;
      }

      return getReportTitle(a).localeCompare(getReportTitle(b), 'ko');
    });
  }, [filteredReports]);

  const hasActiveFilter =
    stockKeyword.trim() !== '' ||
    selectedDate !== '';

  const resetFilters = () => {
    setStockKeyword('');
    setSelectedDate('');
  };

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
    <div className="report-list-shell">
      <div className="card border-0 shadow-sm mb-3">
        <div className="card-body">
          <div className="row g-3 align-items-end">
            <div className="col-md-7">
              <label className="form-label fw-bold">종목 검색</label>
              <input
                type="text"
                className="form-control"
                placeholder="예: 삼성전자, 테슬라"
                value={stockKeyword}
                onChange={(event) => setStockKeyword(event.target.value)}
              />
            </div>

            <div className="col-md-5">
              <label className="form-label fw-bold">날짜 선택</label>
              <input
                type="date"
                className="form-control"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
              />
            </div>
          </div>

          {hasActiveFilter && (
            <div className="d-flex justify-content-between align-items-center mt-3 pt-3 border-top">
              <span className="text-muted small">
                검색 결과 {filteredReports.length}개
              </span>
              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={resetFilters}
              >
                필터 초기화
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="report-date-strip mb-3">
        <button
          type="button"
          className={`report-date-chip ${selectedDate === '' ? 'active' : ''}`}
          onClick={() => setSelectedDate('')}
        >
          전체
          <span>{reports.length}</span>
        </button>

        {dateGroups.map((group) => (
          <button
            type="button"
            className={`report-date-chip ${selectedDate === group.date ? 'active' : ''}`}
            key={group.date}
            onClick={() => setSelectedDate(group.date)}
          >
            {group.date}
            <span>{group.count}</span>
          </button>
        ))}
      </div>

      {sortedReports.length === 0 ? (
        <div className="alert alert-warning">
          조건에 맞는 리포트가 없습니다.
        </div>
      ) : (
        <div className="report-list-panel border rounded shadow-sm">
          <div className="report-list-panel-header">
            <strong>리포트 {sortedReports.length}개</strong>
            <span className="text-muted small">
              최신 날짜순
            </span>
          </div>

          <div className="report-list-scroll">
            {sortedReports.map((report, reportIndex) => {
              const title = getReportTitle(report);
              const marketLabel = getReportMarketLabel(report);

              return (
                <button
                  type="button"
                  key={`${report.date}-${report.filename}-${reportIndex}`}
                  className={`report-list-item ${
                    selectedReport?.date === report.date &&
                    selectedReport?.filename === report.filename
                      ? 'active'
                      : ''
                  }`}
                  onClick={() => onReportClick(report)}
                >
                  <span className="report-list-item-main">
                    <span className="report-list-title">
                      <span>{title}</span>
                      {marketLabel && (
                        <span className="report-list-market">
                          {marketLabel}
                        </span>
                      )}
                    </span>
                    <span className="report-list-date">{report.date || '날짜 없음'}</span>
                  </span>

                  <span className="report-list-action">
                    상세 리포트
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default ReportList;
