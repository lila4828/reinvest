import React from 'react';
import './MainTop.css';

function MainTop() {
  return (
    <div className="main-top-panel p-4 mb-4 shadow-sm border rounded">
      <h4 className="fw-bold text-primary mb-3">🌍 오늘의 거시경제 요약</h4>
      <div className="row">
        <div className="col-md-4">
          <div className="p-3 bg-light rounded">
            <h6 className="text-muted">환율 (원/달러)</h6>
            <h4 className="mb-0">1,480.98 <span className="text-danger fs-6">▼ 1.33%</span></h4>
          </div>
        </div>
        <div className="col-md-4">
          <div className="p-3 bg-light rounded">
            <h6 className="text-muted">미국 10년물 금리</h6>
            <h4 className="mb-0">4.29% <span className="text-danger fs-6">▼ 2.23%</span></h4>
          </div>
        </div>
        <div className="col-md-4">
          <div className="p-3 bg-light rounded">
            <h6 className="text-muted">나스닥 지수</h6>
            <h4 className="mb-0">24,657.57 <span className="text-success fs-6">▲ 13.31%</span></h4>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MainTop;