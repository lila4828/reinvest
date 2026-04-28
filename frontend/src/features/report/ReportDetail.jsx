import React, { useState, useMemo, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function ReportDetail({ content, isLoading, onBack }) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  // 마크다운 파싱 로직 (content가 바뀔 때만 재계산)
  const { macroContent, parsedReports } = useMemo(() => {
    if (!content) return { macroContent: '', parsedReports: [] };
    
    // 에이전트가 쓴 '📈 [' 기호를 기준으로 전체 텍스트 분리
    const parts = content.split('📈 [');
    
    // 첫 번째 요소는 종목 분석이 시작되기 전의 '최근 업데이트 일시' 등 공통 파트 (별표 구분선 제거)
    const macro = parts[0].replace(/★+/g, '').trim(); 
    const parsed = [];
    
    for (let i = 1; i < parts.length; i++) {
      const part = parts[i];
      const titleEnd = part.indexOf(']');
      if (titleEnd !== -1) {
        // 종목명 추출
        const companyName = part.substring(0, titleEnd).replace('최종 리포트', '').trim();
        const mdContent = part.substring(titleEnd + 1).trim();
        
        // 투자의견(Buy/Hold/Sell) 추출
        const opinionMatch = mdContent.match(/\|\s*\*\*현재가\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|\s*\*\*(.*?)\*\*\s*\|/);
        const opinion = opinionMatch ? opinionMatch[2].replace(/\[|\]/g, '') : 'N/A';

        parsed.push({ companyName, opinion, mdContent });
      }
    }
    return { macroContent: macro, parsedReports: parsed };
  }, [content]);

  // 드롭다운 영역 외부 클릭 시 닫히도록 처리
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 검색어로 필터링된 종목 목록 (원본 인덱스를 기억하기 위해 map 먼저 실행)
  const filteredReports = parsedReports
    .map((report, index) => ({ ...report, originalIndex: index }))
    .filter((report) => report.companyName.toLowerCase().includes(searchTerm.toLowerCase()));

  if (isLoading) {
    return <div className="p-4 text-center">리포트 상세 내용을 불러오는 중...</div>;
  }

  return (
    <div>
      <button className="btn btn-outline-secondary mb-4" onClick={onBack}>
        &larr; 목록으로 돌아가기
      </button>
      
      {/* 1. 공통 거시경제 파트 (종목 탭 위에 항상 고정 표시) */}
      {macroContent && (
        <div className="mb-4 p-4 bg-white rounded border shadow-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {macroContent}
          </ReactMarkdown>
        </div>
      )}

      {parsedReports.length > 0 ? (
        <>
          <h5 className="fw-bold mb-3 text-primary">🏭 분석된 타겟 종목 ({parsedReports.length}개)</h5>
          {/* 2. 검색 가능한 커스텀 종목 선택 드롭다운 */}
          <div className="mb-4 position-relative" ref={dropdownRef}>
            <div 
              className="form-select form-select-lg shadow-sm border-primary fw-bold text-primary bg-white" 
              style={{ cursor: 'pointer' }}
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            >
              {parsedReports[selectedIndex]?.companyName} <span className="fs-6 text-muted fw-normal ms-1">(의견: {parsedReports[selectedIndex]?.opinion})</span>
            </div>
            
            {isDropdownOpen && (
              <div className="position-absolute w-100 bg-white border border-primary rounded shadow mt-1" style={{ zIndex: 1050, maxHeight: '350px', overflowY: 'auto' }}>
                <div className="p-2 sticky-top bg-light border-bottom">
                  <input 
                    type="text" 
                    className="form-control" 
                    placeholder="🔍 종목명 검색..." 
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    autoFocus
                  />
                </div>
                <div className="list-group list-group-flush">
                  {filteredReports.length > 0 ? (
                    filteredReports.map((report) => (
                      <button
                        key={report.originalIndex}
                        type="button"
                        className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${selectedIndex === report.originalIndex ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedIndex(report.originalIndex);
                          setIsDropdownOpen(false);
                          setSearchTerm(''); // 선택 시 검색어 초기화
                        }}
                      >
                        <span className="fw-bold">{report.companyName}</span>
                        <span className={`badge ${report.opinion.includes('Buy') ? 'bg-success' : report.opinion.includes('Sell') ? 'bg-danger' : 'bg-secondary'}`}>
                          {report.opinion}
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="p-3 text-center text-muted">검색 결과가 없습니다.</div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 3. 선택된 종목의 마크다운 리포트 본문 */}
          <div className="p-4 bg-light rounded border shadow-sm" style={{ minHeight: '400px' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {parsedReports[selectedIndex]?.mdContent}
            </ReactMarkdown>
          </div>
        </>
      ) : (
        /* 파싱이 안 되는 옛날 포맷의 리포트일 경우 마크다운 전체 출력 안전장치 */
        <div className="p-4 bg-light rounded border shadow-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default ReportDetail;