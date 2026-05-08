import React, { useEffect, useMemo, useState } from 'react';

const READ_REPORTS_STORAGE_KEY = 'ai-reinvest-read-reports';

function getReportReadKey(report) {
  if (!report?.date || !report?.filename) return '';
  return `${report.date}/${report.filename}`;
}

function getTodayDateString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
}

function loadReadReports() {
  try {
    const rawValue = localStorage.getItem(READ_REPORTS_STORAGE_KEY);
    const parsedValue = rawValue ? JSON.parse(rawValue) : [];
    return Array.isArray(parsedValue) ? parsedValue : [];
  } catch (error) {
    console.warn('읽은 리포트 상태를 불러오지 못했습니다.', error);
    return [];
  }
}

function saveReadReports(readReports) {
  try {
    localStorage.setItem(
      READ_REPORTS_STORAGE_KEY,
      JSON.stringify(Array.from(readReports)),
    );
  } catch (error) {
    console.warn('읽은 리포트 상태를 저장하지 못했습니다.', error);
  }
}

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
  const ticker = getReportTicker(report);
  const marketText = [
    report?.market_label,
    report?.exchange,
    report?.market,
  ]
    .filter(Boolean)
    .join(' ')
    .toUpperCase();

  if (
    ticker.endsWith('.KS') ||
    ticker.endsWith('.KQ') ||
    marketText.includes('KOSPI') ||
    marketText.includes('KOSDAQ') ||
    marketText.includes('코스피') ||
    marketText.includes('코스닥')
  ) {
    return '국내 주식';
  }

  if (
    ticker ||
    marketText.includes('NASDAQ') ||
    marketText.includes('NYSE') ||
    marketText.includes('AMEX') ||
    marketText.includes('미국')
  ) {
    return '미국 주식';
  }

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
  const [readReports, setReadReports] = useState(() => new Set(loadReadReports()));
  const todayDate = getTodayDateString();

  useEffect(() => {
    setStockKeyword(initialStockKeyword);
  }, [initialStockKeyword]);

  useEffect(() => {
    const readKey = getReportReadKey(selectedReport);

    if (!readKey || readReports.has(readKey)) {
      return;
    }

    setReadReports((prev) => {
      const next = new Set(prev);
      next.add(readKey);
      saveReadReports(next);
      return next;
    });
  }, [selectedReport?.date, selectedReport?.filename, readReports]);

  const markReportAsRead = (report) => {
    const readKey = getReportReadKey(report);

    if (!readKey) {
      return;
    }

    setReadReports((prev) => {
      if (prev.has(readKey)) {
        return prev;
      }

      const next = new Set(prev);
      next.add(readKey);
      saveReadReports(next);
      return next;
    });
  };

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
              const readKey = getReportReadKey(report);
              const isTodayReport = String(report.date || '') === todayDate;
              const isUnread = Boolean(isTodayReport && readKey && !readReports.has(readKey));

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
                  onClick={() => {
                    markReportAsRead(report);
                    onReportClick(report);
                  }}
                >
                  <span className="report-list-item-main">
                    <span className="report-list-title">
                      {marketLabel && (
                        <span className="report-list-market">
                          {marketLabel}
                        </span>
                      )}
                      <span className="report-list-stock-name">{title}</span>
                      {isUnread && (
                        <span className="report-list-new">
                          NEW
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
