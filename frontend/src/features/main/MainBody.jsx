import React from 'react';
import './MainBody.css';

function MainBody() {
  return (
    <div className="main-body-panel p-4 shadow-sm border rounded">
      <h4 className="fw-bold mb-3">🏭 타겟 종목 스캔 현황</h4>
      <div className="row g-3">
        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body">
              <h5 className="card-title fw-bold">삼성전자</h5>
              <h6 className="card-subtitle mb-2 text-muted">005930.KS</h6>
              <p className="card-text text-secondary fw-bold">의견: Hold</p>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body">
              <h5 className="card-title fw-bold">테슬라</h5>
              <h6 className="card-subtitle mb-2 text-muted">TSLA</h6>
              <p className="card-text text-secondary fw-bold">의견: Hold</p>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card h-100">
            <div className="card-body">
              <h5 className="card-title fw-bold">폴라리스오피스</h5>
              <h6 className="card-subtitle mb-2 text-muted">041020.KQ</h6>
              <p className="card-text text-secondary fw-bold">의견: Hold</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MainBody;