import React, { useState, useEffect } from 'react';
import './MainTop.css';
import MacroCard from './MacroCard';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function extractUpdateTime(content, fallbackDate) {
  if (!content || typeof content !== 'string') return fallbackDate || null;

  const updateTimeMatch = content.match(/> \*\*최근 업데이트 일시:\*\*\s*(.+)/);
  return updateTimeMatch ? updateTimeMatch[1].trim() : fallbackDate;
}

function extractMacroJson(content) {
  if (!content || typeof content !== 'string') return null;

  const match = content.match(/<!--\s*MACRO_DATA\s*([\s\S]*?)\s*-->/);

  if (!match) return null;

  try {
    return JSON.parse(match[1].trim());
  } catch (error) {
    console.error('MACRO_DATA JSON 파싱 실패:', error);
    return null;
  }
}

function pickNumber(data, keys) {
  for (const key of keys) {
    const value = data?.[key];

    if (typeof value === 'number') return value;
    if (typeof value === 'string' && value.trim() !== '') {
      const parsed = Number(value.replace(/,/g, ''));
      if (!Number.isNaN(parsed)) return parsed;
    }
  }

  return null;
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined) return 'N/A';

  const number = Number(value);

  if (Number.isNaN(number)) return 'N/A';

  return number.toLocaleString(undefined, {
    maximumFractionDigits: digits,
  });
}

function formatChange(value) {
  if (value === null || value === undefined) return 'N/A';

  const number = Number(value);

  if (Number.isNaN(number)) return 'N/A';

  return `${number > 0 ? '+' : ''}${number.toFixed(2).replace(/\.00$/, '')}%`;
}

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
        const reportListRes = await fetch(`${API_BASE_URL}/api/reports`);

        if (!reportListRes.ok) {
          throw new Error(`리포트 목록 로딩 실패 (HTTP ${reportListRes.status})`);
        }

        const reportListData = await reportListRes.json();

        if (!reportListData.reports || reportListData.reports.length === 0) {
          throw new Error('분석된 리포트가 없습니다. 백엔드를 실행해주세요.');
        }

        const latestSummary =
          reportListData.reports.find((report) => report.is_summary) || reportListData.reports[0];

        const date = encodeURIComponent(latestSummary.date);
        const filename = encodeURIComponent(latestSummary.filename);

        const reportDetailRes = await fetch(`${API_BASE_URL}/api/reports/${date}/${filename}`);

        if (!reportDetailRes.ok) {
          throw new Error(`최신 리포트 로딩 실패 (HTTP ${reportDetailRes.status})`);
        }

        const reportDetailData = await reportDetailRes.json();
        const content = reportDetailData.content || '';
        const macroJson = extractMacroJson(content);

        if (!macroJson) {
          throw new Error('summary.md에서 MACRO_DATA를 찾지 못했습니다. main.py에서 MACRO_DATA 주석을 추가한 뒤 리포트를 다시 생성하세요.');
        }

        const exchangeRate = pickNumber(macroJson, [
          'exchange_rate',
          'usd_krw',
          'usdkrw',
          'exchangeRate',
        ]);

        const exchangeRateChange = pickNumber(macroJson, [
          'exchange_rate_change_1mo',
          'exchange_rate_change',
          'exchange_rate_change_pct',
          'usd_krw_change',
          'exchangeRateChange',
        ]);

        const us10y = pickNumber(macroJson, [
          'us_10y_yield',
          'us10y_yield',
          'us_10y',
          'us10y',
        ]);

        const us10yChange = pickNumber(macroJson, [
          'us_10y_yield_change_1mo',
          'us_10y_change',
          'us_10y_change_pct',
          'us10y_change',
          'us10yChange',
        ]);

        const nasdaq = pickNumber(macroJson, [
          'nasdaq_index',
          'nasdaq',
          'nasdaqIndex',
        ]);

        const nasdaqChange = pickNumber(macroJson, [
          'nasdaq_index_change_1mo',
          'nasdaq_change',
          'nasdaq_change_pct',
          'nasdaqChange',
        ]);

        const wti = pickNumber(macroJson, [
          'wti_price',
          'wti',
          'wtiPrice',
        ]);

        const wtiChange = pickNumber(macroJson, [
          'wti_price_change_1mo',
          'wti_change',
          'wti_change_pct',
          'wtiChange',
        ]);

        const vix = pickNumber(macroJson, [
          'vix_index',
          'vix',
          'vixIndex',
        ]);

        const vixChange = pickNumber(macroJson, [
          'vix_index_change_1mo',
          'vix_change',
          'vix_change_pct',
          'vixChange',
        ]);

        setMacroData({
          exchangeRate: {
            value: formatNumber(exchangeRate, 2),
            change: formatChange(exchangeRateChange),
          },
          us10y: {
            value: formatNumber(us10y, 2),
            change: formatChange(us10yChange),
          },
          nasdaq: {
            value: formatNumber(nasdaq, 2),
            change: formatChange(nasdaqChange),
          },
          wti: {
            value: formatNumber(wti, 2),
            change: formatChange(wtiChange),
          },
          vix: {
            value: formatNumber(vix, 2),
            change: formatChange(vixChange),
          },
          updateTime: extractUpdateTime(content, latestSummary.date),
          loading: false,
          error: null,
        });
      } catch (err) {
        setMacroData({
          exchangeRate: null,
          us10y: null,
          nasdaq: null,
          wti: null,
          vix: null,
          updateTime: null,
          loading: false,
          error: err.message,
        });
      }
    };

    fetchMacroData();
  }, []);

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
      <h4 className="fw-bold text-primary mb-3 d-flex align-items-end flex-wrap">
        🌍 AI 분석 거시경제 현황
        {macroData.updateTime && (
          <span className="fs-6 text-muted ms-2 fw-normal mb-1">
            ({macroData.updateTime} 기준)
          </span>
        )}
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