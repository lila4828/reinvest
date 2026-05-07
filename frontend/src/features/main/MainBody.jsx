import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MainBody.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const FAVORITES_STORAGE_KEY = 'ai-reinvest-main-report-favorites';
const OPINION_FILTERS = ['Strong Buy', 'Buy', 'Hold', 'Sell', '분석 중단'];

function parseReportMetaFromFilename(filename) {
  if (!filename || filename === 'summary.md' || !filename.endsWith('.md')) {
    return null;
  }

  const baseName = filename.replace(/\.md$/, '');
  const separatorIndex = baseName.lastIndexOf('_');

  if (separatorIndex <= 0 || separatorIndex >= baseName.length - 1) {
    return null;
  }

  return {
    companyName: baseName.slice(0, separatorIndex),
    ticker: baseName.slice(separatorIndex + 1).toUpperCase(),
  };
}

function getReportSortValue(report) {
  return `${report.date || ''}/${report.filename || ''}`;
}

function formatReportBaseTime(report) {
  const value = report?.modifiedAt || report?.modified_at || report?.date;

  if (!value) return '기준 날짜 없음';

  const normalizedValue = String(value).replace('T', ' ');

  return `기준 ${normalizedValue.slice(0, 16)}`;
}

function getTodayDateText() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');

  return `${year}-${month}-${day}`;
}

function getReportDetailPath(report) {
  if (!report?.date || !report?.filename) {
    return '/report';
  }

  const params = new URLSearchParams({
    date: report.date,
    filename: report.filename,
  });

  if (report.companyName) {
    params.set('q', report.companyName);
  }

  return `/report?${params.toString()}`;
}

function parseReportsFromMarkdown(content) {
  if (!content || typeof content !== 'string') return [];

  const cleanedContent = content.replace(/★+/g, '').trim();

  // 현재 리포트 포맷:
  // # 📈 삼성전자 심층 투자 전략 리포트
  const headingRegex = /^# 📈 (.+?) 심층 투자 전략 리포트\s*$/gm;
  const matches = [...cleanedContent.matchAll(headingRegex)];

  if (matches.length === 0) {
    return [];
  }

  return matches.map((match, index) => {
    const companyName = match[1].trim();
    const start = match.index;
    const end = index + 1 < matches.length ? matches[index + 1].index : cleanedContent.length;
    const mdContent = cleanedContent.slice(start, end).trim();

    const opinionMatch = mdContent.match(
      /\|\s*\*\*현재가\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|/
    );

    const opinion = opinionMatch ? opinionMatch[2].trim() : 'N/A';

    // 메인 화면에서는 첫 번째 구분선 전까지 요약 카드로 표시
    const summaryContent = mdContent.split('\n---')[0].trim();

    return {
      companyName,
      opinion,
      mdContent: summaryContent,
    };
  });
}

function parseSingleReportFromMarkdown(content, fallbackCompanyName) {
  const parsedReports = parseReportsFromMarkdown(content);

  if (parsedReports.length > 0) {
    return parsedReports[0];
  }

  const cleanedContent = String(content || '').replace(/★+/g, '').trim();

  if (!cleanedContent) {
    return null;
  }

  return {
    companyName: fallbackCompanyName,
    opinion: cleanedContent.includes('[분석 중단]') ? '분석 중단' : 'N/A',
    mdContent: cleanedContent,
  };
}

function MainBody({
  refreshKey = 0,
  sideContent = null,
  onStartReportJob,
  isReportWorking = false,
}) {
  const [reports, setReports] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [selectedOpinions, setSelectedOpinions] = useState([]);
  const [favoriteReports, setFavoriteReports] = useState(() => {
    try {
      const savedFavorites = window.localStorage.getItem(FAVORITES_STORAGE_KEY);
      return savedFavorites ? JSON.parse(savedFavorites) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        FAVORITES_STORAGE_KEY,
        JSON.stringify(favoriteReports),
      );
    } catch {
      // localStorage가 막힌 환경에서는 이번 세션 상태만 유지한다.
    }
  }, [favoriteReports]);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        setLoading(true);
        setError(null);

        const listRes = await fetch(`${API_BASE_URL}/api/reports`, {
          credentials: 'include',
        });

        if (!listRes.ok) {
          throw new Error('목록 로딩 실패');
        }

        const listData = await listRes.json();

        if (!listData.reports || listData.reports.length === 0) {
          throw new Error('리포트가 없습니다.');
        }

        const latestByTicker = new Map();

        (listData.reports || []).forEach((report) => {
          if (report.is_summary) return;

          const meta = parseReportMetaFromFilename(report.filename);

          if (!meta) return;

          const current = latestByTicker.get(meta.ticker);

          if (!current || getReportSortValue(report) > getReportSortValue(current)) {
            latestByTicker.set(meta.ticker, {
              ...report,
              companyName: meta.companyName,
              ticker: meta.ticker,
            });
          }
        });

        const latestReports = [...latestByTicker.values()].sort((a, b) =>
          getReportSortValue(b).localeCompare(getReportSortValue(a))
        );

        if (latestReports.length === 0) {
          throw new Error('종목별 리포트가 없습니다.');
        }

        const reportDetails = await Promise.all(
          latestReports.map(async (report) => {
            const date = encodeURIComponent(report.date);
            const filename = encodeURIComponent(report.filename);

            const detailRes = await fetch(`${API_BASE_URL}/api/reports/${date}/${filename}`, {
              credentials: 'include',
            });

            if (!detailRes.ok) {
              throw new Error('리포트 상세 로딩 실패');
            }

            const detailData = await detailRes.json();
            const parsedReport = parseSingleReportFromMarkdown(
              detailData.content,
              report.companyName,
            );

            if (!parsedReport) return null;

            return {
              ...parsedReport,
              ticker: report.ticker,
              date: report.date,
              modifiedAt: detailData.modified_at || report.modified_at || null,
              filename: report.filename,
            };
          }),
        );

        const parsedReports = reportDetails.filter(Boolean);

        if (parsedReports.length === 0) {
          throw new Error('리포트 내용을 파싱하지 못했습니다.');
        }

        setReports(parsedReports);
        setSelectedIndex(0);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchReports();
  }, [refreshKey]);

  useEffect(() => {
    if (reports.length === 0) return;

    const normalizedKeyword = searchKeyword.trim().toLowerCase();
    const favoriteSet = new Set(favoriteReports);
    const matchingIndexes = reports
      .map((report, index) => ({ ...report, sourceIndex: index }))
      .filter((report) => {
        const matchesKeyword =
          !normalizedKeyword ||
          report.companyName.toLowerCase().includes(normalizedKeyword) ||
          report.opinion.toLowerCase().includes(normalizedKeyword);
        const matchesFavorite =
          !showFavoritesOnly || favoriteSet.has(report.companyName);
        const matchesOpinion =
          selectedOpinions.length === 0 ||
          selectedOpinions.includes(report.opinion);

        return matchesKeyword && matchesFavorite && matchesOpinion;
      })
      .map((report) => report.sourceIndex);

    if (
      matchingIndexes.length > 0 &&
      !matchingIndexes.includes(selectedIndex)
    ) {
      setSelectedIndex(matchingIndexes[0]);
    }
  }, [
    reports,
    searchKeyword,
    showFavoritesOnly,
    favoriteReports,
    selectedOpinions,
    selectedIndex,
  ]);

  if (loading) {
    return <div className="p-4 text-center">종목 리포트를 분석 및 로딩하는 중...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-danger">{error}</div>;
  }

  if (reports.length === 0) return null;

  const selectedReport = reports[selectedIndex];
  const selectedReportKey = selectedReport?.companyName || '';
  const todayDateText = getTodayDateText();
  const hasTodaySelectedReport = selectedReport?.date === todayDateText;
  const normalizedKeyword = searchKeyword.trim().toLowerCase();
  const favoriteSet = new Set(favoriteReports);
  const filteredReports = reports
    .map((report, index) => ({ ...report, sourceIndex: index }))
    .filter((report) => {
      const matchesKeyword =
        !normalizedKeyword ||
        report.companyName.toLowerCase().includes(normalizedKeyword) ||
        report.opinion.toLowerCase().includes(normalizedKeyword);
      const matchesFavorite =
        !showFavoritesOnly || favoriteSet.has(report.companyName);
      const matchesOpinion =
        selectedOpinions.length === 0 ||
        selectedOpinions.includes(report.opinion);

      return matchesKeyword && matchesFavorite && matchesOpinion;
    });

  const getOpinionClassName = (opinion) => {
    if (opinion.includes('Strong Buy')) return 'status-strong-buy';
    if (opinion.includes('Buy')) return 'status-buy';
    if (opinion.includes('Sell')) return 'status-sell';
    if (opinion.includes('분석 중단')) return 'status-stop';
    return 'status-hold';
  };

  const handleToggleFavorite = (companyName) => {
    setFavoriteReports((prev) => {
      if (prev.includes(companyName)) {
        return prev.filter((name) => name !== companyName);
      }

      return [...prev, companyName];
    });
  };

  const handleToggleOpinion = (opinion) => {
    setSelectedOpinions((prev) => {
      if (prev.includes(opinion)) {
        return prev.filter((item) => item !== opinion);
      }

      return [...prev, opinion];
    });
  };

  const handleCreateSelectedTodayReport = async () => {
    if (!selectedReport || typeof onStartReportJob !== 'function') return;

    await onStartReportJob([{
      ticker: selectedReport.ticker,
      company: selectedReport.companyName,
    }]);
  };

  return (
    <>
      <div className="main-operations-grid">
        {sideContent && (
          <div className="main-operation-panel">
            {sideContent}
          </div>
        )}

        <div className="main-body-panel main-scan-panel p-4 shadow-sm border rounded">
          <div className="main-body-header">
            <div>
              <h4 className="fw-bold mb-1">🏭 타겟 종목 스캔 현황</h4>
              <p className="text-muted mb-0 small">
                {selectedReport.companyName} 리포트를 보고 있습니다.
              </p>
            </div>
          </div>

          <div className="report-selector-toolbar">
            <input
              type="search"
              className="form-control report-selector-search"
              placeholder="종목명 또는 의견 검색"
              value={searchKeyword}
              onChange={(event) => setSearchKeyword(event.target.value)}
            />

            <label className="report-favorite-filter">
              <input
                type="checkbox"
                checked={showFavoritesOnly}
                onChange={(event) => setShowFavoritesOnly(event.target.checked)}
              />
              <span>★ 즐겨찾기</span>
            </label>
          </div>

          <div className="report-opinion-filter-row">
            {OPINION_FILTERS.map((opinion) => (
              <label
                className={`report-opinion-filter ${getOpinionClassName(opinion)}`}
                key={opinion}
              >
                <input
                  type="checkbox"
                  checked={selectedOpinions.includes(opinion)}
                  onChange={() => handleToggleOpinion(opinion)}
                />
                <span>{opinion}</span>
              </label>
            ))}
          </div>

          <div className="report-selector-list">
            {filteredReports.length === 0 ? (
              <div className="report-selector-empty">
                조건에 맞는 종목이 없습니다.
              </div>
            ) : (
              filteredReports.map((report) => {
                const isSelected = selectedIndex === report.sourceIndex;
                const isFavorite = favoriteSet.has(report.companyName);

                return (
                  <div
                    className={`report-selector-item ${isSelected ? 'active' : ''}`}
                    key={`${report.companyName}-${report.sourceIndex}`}
                  >
                    <button
                      type="button"
                      className="report-selector-star"
                      onClick={() => handleToggleFavorite(report.companyName)}
                      aria-label={`${report.companyName} 즐겨찾기 ${isFavorite ? '해제' : '추가'}`}
                      title={isFavorite ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                    >
                      {isFavorite ? '★' : '☆'}
                    </button>

                    <button
                      type="button"
                      className="report-selector-main"
                      onClick={() => setSelectedIndex(report.sourceIndex)}
                    >
                      <span className="report-selector-name">{report.companyName}</span>
                      <span className="report-selector-meta">
                        <span className={`report-selector-opinion ${getOpinionClassName(report.opinion)}`}>
                          {report.opinion}
                        </span>
                      </span>
                    </button>
                  </div>
                );
              })
            )}
          </div>

          {searchKeyword && !filteredReports.some((report) => report.companyName === selectedReportKey) && filteredReports.length > 0 && (
            <div className="report-selector-hint small text-muted">
              검색 결과에서 종목을 선택하면 아래 상세 리포트가 바뀝니다.
            </div>
          )}
        </div>
      </div>

      <div className="report-markdown-container markdown-content p-4 bg-light rounded border">
        <div className="report-detail-context">
          <div className="report-detail-heading">
            <span className="report-detail-title">{selectedReport.companyName}</span>
            <span className="report-detail-date">{formatReportBaseTime(selectedReport)}</span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-outline-primary report-today-create-button"
            onClick={handleCreateSelectedTodayReport}
            disabled={
              isReportWorking ||
              hasTodaySelectedReport ||
              typeof onStartReportJob !== 'function'
            }
            title={
              hasTodaySelectedReport
                ? '오늘 기준 리포트가 이미 있습니다.'
                : `${selectedReport.companyName} 오늘 기준 리포트 생성`
            }
          >
            {hasTodaySelectedReport ? '오늘 리포트 있음' : '오늘 기준 생성'}
          </button>
        </div>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {selectedReport?.mdContent || ''}
        </ReactMarkdown>
        <div className="report-more-actions">
          <Link
            to={getReportDetailPath(selectedReport)}
            className="btn btn-sm btn-primary report-more-button"
          >
            더보기
          </Link>
        </div>
      </div>
    </>
  );
}

export default MainBody;
