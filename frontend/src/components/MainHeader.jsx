import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import TradingViewTicker from './TradingViewTicker';
import './MainHeader.css';

function MainHeader() {
  const location = useLocation();

  return (
    <>
      <header className="p-3 border-bottom bg-white shadow-sm">
        <div className="container">
          <div className="d-flex flex-wrap align-items-center justify-content-center justify-content-lg-start">
            <Link to="/" className="logo-link fs-4 fw-bold me-auto text-primary text-decoration-none">
              AI-Reinvest
            </Link>
            
            <div className="text-end">
              {location.pathname === '/' ? (
                <Link to="/report" className="btn btn-outline-primary fw-bold shadow-sm">📄 상세 리포트 보러가기 &rarr;</Link>
              ) : (
                <Link to="/" className="btn btn-outline-primary fw-bold shadow-sm">🏠 메인 화면으로</Link>
              )}
            </div>
          </div>
        </div>
      </header>
      {/* 헤더 바로 아래에 실시간 지표 티커 배치 */}
      <TradingViewTicker />
    </>
  );
}

export default MainHeader;