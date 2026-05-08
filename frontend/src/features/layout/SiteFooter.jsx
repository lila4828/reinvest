import React from 'react';
import './SiteFooter.css';

function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-brand">
          <strong>AI-Reinvest</strong>
          <span>AI 기반 투자 리포트 자동 생성 시스템</span>
        </div>

        <nav className="site-footer-links" aria-label="Footer navigation">
          <a href="#about">About</a>
          <a href="#reports">Reports</a>
          <a href="#disclaimer">Disclaimer</a>
          <a href="#contact">Contact</a>
        </nav>

        <p className="site-footer-disclaimer">
          데이터는 투자 참고용이며, 최종 투자 판단은 사용자 본인에게 있습니다.
        </p>

        <p className="site-footer-copy">
          © 2026 AI-Reinvest. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

export default SiteFooter;
