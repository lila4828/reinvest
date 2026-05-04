import React, { useMemo, useState } from 'react';

function getReportTitle(report) {
  if (!report) return '리포트';

  const displayName = report.display_name || report.filename || '개별 리포트';

  return displayName
    .replace(/\.md$/i, '')
    .replace(/\([^)]*\)/g, '')
    .replace(/_\d{6}\.KS$/i, '')
    .replace(/_[A-Z.]+$/i, '')
    .replace(/_/g, ' ')
    .trim();
}

function getSearchableStockName(report) {
  if (!report) return '';

  return [
    report.display_name,
    report.filename,
    getReportTitle(report),
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

function ReportList({ reports, isLoading, onReportClick }) {
  const [stockKeyword, setStockKeyword] = useState('');
  const [selectedDate, setSelectedDate] = useState('');
  const [openDates, setOpenDates] = useState({});

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

  const groupedReports = useMemo(() => {
    const grouped = groupReportsByDate(filteredReports);

    return Object.entries(grouped)
      .sort(([dateA], [dateB]) => String(dateB).localeCompare(String(dateA)))
      .map(([date, dateReports]) => ({
        date,
        reports: [...dateReports].sort((a, b) =>
          getReportTitle(a).localeCompare(getReportTitle(b), 'ko')
        ),
      }));
  }, [filteredReports]);

  const hasActiveFilter =
    stockKeyword.trim() !== '' ||
    selectedDate !== '';

  const toggleDate = (date) => {
    setOpenDates((prev) => {
      const currentValue = prev[date];

      return {
        ...prev,
        [date]: currentValue === undefined ? false : !currentValue,
      };
    });
  };

  const resetFilters = () => {
    setStockKeyword('');
    setSelectedDate('');
    setOpenDates({});
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
    <div>
      <div className="card border-0 shadow-sm mb-4">
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

      {groupedReports.length === 0 ? (
        <div className="alert alert-warning">
          조건에 맞는 리포트가 없습니다.
        </div>
      ) : (
        <div className="accordion" id="reportDateAccordion">
          {groupedReports.map((group, index) => {
            const isOpen = openDates[group.date] ?? index === 0;

            return (
              <div className="accordion-item" key={group.date}>
                <h2 className="accordion-header">
                  <button
                    type="button"
                    className={`accordion-button ${isOpen ? '' : 'collapsed'}`}
                    onClick={() => toggleDate(group.date)}
                  >
                    <span className="fw-bold me-2">{group.date}</span>
                    <span className="badge bg-secondary rounded-pill">
                      {group.reports.length}개
                    </span>
                  </button>
                </h2>

                {isOpen && (
                  <div className="accordion-collapse collapse show">
                    <div className="accordion-body p-0">
                      <div className="list-group list-group-flush">
                        {group.reports.map((report, reportIndex) => {
                          const title = getReportTitle(report);

                          return (
                            <button
                              type="button"
                              key={`${report.date}-${report.filename}-${reportIndex}`}
                              className="list-group-item list-group-item-action d-flex justify-content-between align-items-center py-3"
                              onClick={() => onReportClick(report)}
                            >
                              <span className="d-flex align-items-center gap-2">
                                <span className="fs-5">📄</span>
                                <strong>{title}</strong>
                              </span>

                              <span className="text-muted small">
                                자세히 보기 &rarr;
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default ReportList;