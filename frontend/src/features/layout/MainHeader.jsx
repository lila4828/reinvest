import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import TradingViewTicker from './TradingViewTicker';
import './MainHeader.css';

function MainHeader({ username, onLogout }) {
  const location = useLocation();

  return (
    <>
      <header className="p-3 border-bottom bg-white shadow-sm">
        <div className="container">
          <div className="main-header-inner">
            <Link to="/" className="logo-link fs-4 fw-bold text-primary text-decoration-none">
              AI-Reinvest
            </Link>

            <div className="main-header-actions">
              {username && (
                <span className="main-header-user text-muted small">
                  {username}님
                </span>
              )}

              {location.pathname === '/' ? (
                <Link to="/report" className="btn btn-outline-primary fw-bold shadow-sm">
                  📄 상세 리포트 보러가기 &rarr;
                </Link>
              ) : (
                <Link to="/" className="btn btn-outline-primary fw-bold shadow-sm">
                  🏠 메인 화면으로
                </Link>
              )}

              <button
                type="button"
                className="btn btn-outline-secondary fw-bold shadow-sm"
                onClick={onLogout}
              >
                로그아웃
              </button>
            </div>
          </div>
        </div>
      </header>

      <TradingViewTicker />
    </>
  );
}

export default MainHeader;
