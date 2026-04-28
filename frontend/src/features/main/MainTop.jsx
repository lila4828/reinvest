import React, { useState, useEffect } from 'react';
import './MainTop.css';
import MacroCard from './MacroCard';

function MainTop() {
  const [macroData, setMacroData] = useState({
    exchangeRate: null,
    us10y: null,
    nasdaq: null,
    wti: null,
    vix: null,
    updateTime: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    const fetchMacroData = async () => {
      try {
        // 1. Get the list of reports to find the latest one
        const reportListRes = await fetch('http://localhost:8000/api/reports');
        if (!reportListRes.ok) {
          throw new Error(`리포트 목록 로딩 실패 (HTTP ${reportListRes.status})`);
        }
        const reportListData = await reportListRes.json();
        
        if (!reportListData.reports || reportListData.reports.length === 0) {
          throw new Error('분석된 리포트가 없습니다. 백엔드를 실행해주세요.');
        }
        
        const latestReportFilename = reportListData.reports[0].filename;
        
        // 2. Get the content of the latest report
        const reportDetailRes = await fetch(`http://localhost:8000/api/reports/${latestReportFilename}`);
        if (!reportDetailRes.ok) {
          throw new Error(`최신 리포트 로딩 실패 (HTTP ${reportDetailRes.status})`);
        }
        const reportDetailData = await reportDetailRes.json();
        const content = reportDetailData.content;
        
        // 3. Parse the markdown content to extract macro data
        // 최상단 업데이트 일시 추출
        const updateTimeMatch = content.match(/> \*\*최근 업데이트 일시:\*\* (.+)/);
        const updateTime = updateTimeMatch ? updateTimeMatch[1].trim() : null;

        const parseLine = (line) => {
          if (!line) return { value: 'N/A', change: 'N/A' };
          // Example: - **원/달러 환율 1,472.5원 (-2.88% MoM)**
          
          // '10년물'의 '10'이 먼저 매칭되는 것을 방지하기 위해 텍스트 임시 제거
          const cleanLine = line.replace('10년물', '');
          const valueMatch = cleanLine.match(/(\d{1,3}(?:,\d{3})*(?:\.\d+)?)/);
          // MoM 텍스트를 제외하고 괄호 안의 수치(예: -2.88%)만 캡처
          const changeMatch = line.match(/\((.+?) MoM\)/);
          
          const value = valueMatch ? valueMatch[0] : 'N/A';
          const change = changeMatch ? changeMatch[1] : 'N/A';
          
          return { value, change };
        };

        const lines = content.split('\n');
        // 수치가 없는 헤더 라인을 건너뛰기 위해 'MoM'이 포함된 실제 데이터 라인만 검색
        const findDataLine = (keyword) => lines.find(line => line.includes(keyword) && line.includes('MoM'));

        setMacroData({
          exchangeRate: parseLine(findDataLine('원/달러 환율')),
          us10y: parseLine(findDataLine('미국 10년물 국채금리')),
          nasdaq: parseLine(findDataLine('미국 나스닥')),
          wti: parseLine(findDataLine('WTI')),
          vix: parseLine(findDataLine('VIX')),
          updateTime: updateTime,
          loading: false,
          error: null,
        });

      } catch (err) {
        setMacroData({ loading: false, error: err.message });
      }
    };
    
    fetchMacroData();
  }, []); // Empty dependency array ensures this runs only once on mount

  if (macroData.loading) {
    return (
      <div className="main-top-panel p-4 mb-4 shadow-sm border rounded">
        <h4 className="fw-bold text-primary mb-3">🌍 AI 분석 거시경제 현황</h4>
        <div className="text-center text-muted">
          <div className="spinner-border spinner-border-sm me-2" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          AI 분석 리포트에서 최신 거시경제 데이터를 불러오는 중...
        </div>
      </div>
    );
  }

  if (macroData.error) {
    return (
      <div className="main-top-panel p-4 mb-4 shadow-sm border rounded bg-light">
        <h4 className="fw-bold text-danger mb-3">⚠️ 데이터 로딩 오류</h4>
        <div className="text-center text-danger">{macroData.error}</div>
      </div>
    );
  }

  return (
    <div className="main-top-panel p-4 mb-4 shadow-sm border rounded">
      <h4 className="fw-bold text-primary mb-3 d-flex align-items-end">
        🌍 AI 분석 거시경제 현황
        {macroData.updateTime && <span className="fs-6 text-muted ms-2 fw-normal mb-1">({macroData.updateTime} 기준)</span>}
      </h4>
      <div className="row g-3">
        <MacroCard title="환율 (원/달러)" value={macroData.exchangeRate?.value} change={macroData.exchangeRate?.change} />
        <MacroCard title="나스닥 지수" value={macroData.nasdaq?.value} change={macroData.nasdaq?.change} />
        <MacroCard title="미국 10년물 금리" value={macroData.us10y?.value} change={macroData.us10y?.change} suffix="%" />
        <MacroCard title="WTI 원유 (달러)" value={macroData.wti?.value} change={macroData.wti?.change} />
        <MacroCard title="VIX 공포지수" value={macroData.vix?.value} change={macroData.vix?.change} />
      </div>
    </div>
  );
}

export default MainTop;