import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './MainBody.css';

function MainBody() {
  const [reports, setReports] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0); // 2. 기본값: 0번째(최상단) 종목 선택
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const listRes = await fetch('http://localhost:8000/api/reports');
        if (!listRes.ok) throw new Error('목록 로딩 실패');
        const listData = await listRes.json();
        
        if (!listData.reports || listData.reports.length === 0) {
          throw new Error('리포트가 없습니다.');
        }
        
        const detailRes = await fetch(`http://localhost:8000/api/reports/${listData.reports[0].filename}`);
        if (!detailRes.ok) throw new Error('리포트 상세 로딩 실패');
        const detailData = await detailRes.json();
        const content = detailData.content;

        // 1. 마크다운 분리 (에이전트가 쓴 '📈 [' 기호를 기준으로 종목별 분리)
        const parts = content.split('📈 [');
        const parsedReports = [];
        
        for (let i = 1; i < parts.length; i++) {
          const part = parts[i];
          const titleEnd = part.indexOf(']');
          if (titleEnd !== -1) {
            // 종목명 추출 (예: '폴라리스오피스')
            const companyName = part.substring(0, titleEnd).replace('최종 리포트', '').trim();
            // 마크다운 본문 추출
            const mdContent = part.substring(titleEnd + 1).trim();
            
            // 본문에서 투자의견(Buy/Hold/Sell) 정규식으로 파싱하여 카드에 표시
            const opinionMatch = mdContent.match(/\|\s*\*\*현재가\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|/);
            const opinion = opinionMatch ? opinionMatch[2].replace(/\[|\]/g, '') : 'N/A';

            // 메인 화면용 요약본 추출: 테이블 내의 '| :--- |'에서 잘리는 것을 방지하기 위해 줄바꿈(\n)이 포함된 '\n---'를 기준으로 분리
            const summaryContent = mdContent.split('\n---')[0].trim();

            parsedReports.push({ companyName, opinion, mdContent: summaryContent });
          }
        }

        setReports(parsedReports);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    fetchReports();
  }, []);

  if (loading) return <div className="p-4 text-center">종목 리포트를 분석 및 로딩하는 중...</div>;
  if (error) return <div className="p-4 text-center text-danger">{error}</div>;
  if (reports.length === 0) return null;

  return (
    <div className="main-body-panel p-4 shadow-sm border rounded">
      <h4 className="fw-bold mb-4">🏭 타겟 종목 스캔 현황</h4>
      
      {/* 상단 종목 선택 카드 (버튼 역할) */}
      <div className="row g-3 mb-4">
        {reports.map((report, idx) => (
          <div className="col-md-4" key={idx}>
            <div 
              className={`card h-100 shadow-sm ${selectedIndex === idx ? 'border-primary' : 'border-light'}`}
              style={{ 
                cursor: 'pointer', 
                transform: selectedIndex === idx ? 'scale(1.02)' : 'none',
                transition: 'all 0.2s ease-in-out',
                backgroundColor: selectedIndex === idx ? '#f8faff' : '#ffffff'
              }}
              onClick={() => setSelectedIndex(idx)}
            >
              <div className="card-body text-center">
                <h5 className={`card-title fw-bold ${selectedIndex === idx ? 'text-primary' : ''}`}>
                  {report.companyName}
                </h5>
                <p className={`card-text fw-bold mb-0 ${
                  report.opinion.includes('Buy') ? 'text-success' : 
                  report.opinion.includes('Sell') ? 'text-danger' : 'text-secondary'
                }`}>
                  의견: {report.opinion}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 선택된 종목의 마크다운 리포트 본문 */}
      <div className="report-markdown-container p-4 bg-light rounded border" style={{ minHeight: '250px' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {reports[selectedIndex]?.mdContent}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export default MainBody;