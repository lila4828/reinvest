import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MainBody.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

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

function MainBody({ refreshKey = 0 }) {
  const [reports, setReports] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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

        // summary.md를 우선 사용하고, 없으면 첫 번째 리포트 사용
        const latestSummary =
          listData.reports.find((report) => report.is_summary) || listData.reports[0];

        const date = encodeURIComponent(latestSummary.date);
        const filename = encodeURIComponent(latestSummary.filename);

        const detailRes = await fetch(`${API_BASE_URL}/api/reports/${date}/${filename}`, {
          credentials: 'include',
        });
        if (!detailRes.ok) throw new Error('리포트 상세 로딩 실패');

        const detailData = await detailRes.json();
        const parsedReports = parseReportsFromMarkdown(detailData.content);

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

  if (loading) {
    return <div className="p-4 text-center">종목 리포트를 분석 및 로딩하는 중...</div>;
  }

  if (error) {
    return <div className="p-4 text-center text-danger">{error}</div>;
  }

  if (reports.length === 0) return null;

  const selectedReport = reports[selectedIndex];

  return (
    <div className="main-body-panel p-4 shadow-sm border rounded">
      <h4 className="fw-bold mb-4">🏭 타겟 종목 스캔 현황</h4>

      <div className="row g-3 mb-4">
        {reports.map((report, idx) => (
          <div className="col-md-4" key={`${report.companyName}-${idx}`}>
            <div
              className={`card h-100 shadow-sm ${
                selectedIndex === idx ? 'border-primary' : 'border-light'
              }`}
              style={{
                cursor: 'pointer',
                transform: selectedIndex === idx ? 'scale(1.02)' : 'none',
                transition: 'all 0.2s ease-in-out',
                backgroundColor: selectedIndex === idx ? '#f8faff' : '#ffffff',
              }}
              onClick={() => setSelectedIndex(idx)}
            >
              <div className="card-body text-center">
                <h5 className={`card-title fw-bold ${selectedIndex === idx ? 'text-primary' : ''}`}>
                  {report.companyName}
                </h5>
                <p
                  className={`card-text fw-bold mb-0 ${
                    report.opinion.includes('Buy')
                      ? 'text-success'
                      : report.opinion.includes('Sell')
                        ? 'text-danger'
                        : 'text-secondary'
                  }`}
                >
                  의견: {report.opinion}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="report-markdown-container markdown-content p-4 bg-light rounded border" style={{ minHeight: '250px' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {selectedReport?.mdContent || ''}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export default MainBody;