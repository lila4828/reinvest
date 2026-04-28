import React, { useEffect, useRef, useState } from 'react';

function TradingViewTicker() {
  const containerRef = useRef(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    // 스크립트 중복 렌더링 방지 (script 태그 유무로 확인)
    if (containerRef.current && !containerRef.current.querySelector('script')) {
      const script = document.createElement('script');
      script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
      script.type = 'text/javascript';
      script.async = true;
      
      // 브라우저 확장 프로그램(Adblock 등)에 의해 스크립트 로드가 차단되었을 때의 예외 처리
      script.onerror = () => {
        setHasError(true);
      };
      
      // 백엔드 MacroAgent가 주시하는 5대 지표를 동일하게 세팅
      script.innerHTML = JSON.stringify({
        symbols: [
          { proName: "FX_IDC:USDKRW", title: "원/달러 환율" },
          { proName: "NASDAQ:IXIC", title: "나스닥 종합" },
          { proName: "TVC:US10Y", title: "미 국채 10년물" },
          { proName: "NYMEX:CL1!", title: "WTI 원유" },
          { proName: "CBOE:VIX", title: "VIX 공포지수" }
        ],
        showSymbolLogo: true,
        isTransparent: false,
        displayMode: "regular",
        colorTheme: "light",
        locale: "kr"
      });
      
      containerRef.current.appendChild(script);
    }
  }, []);

  // 차단 에러 발생 시 렌더링될 Fallback (대체) UI
  if (hasError) {
    return (
      <div className="bg-light text-center text-muted py-2 border-bottom" style={{ fontSize: '0.85rem' }}>
        ⚠️ 실시간 지표를 불러올 수 없습니다. (AdBlock 등 광고 차단 확장 프로그램을 해제해 주세요)
      </div>
    );
  }

  return (
    <div className="tradingview-widget-container" ref={containerRef}>
      <div className="tradingview-widget-container__widget"></div>
    </div>
  );
}

export default TradingViewTicker;