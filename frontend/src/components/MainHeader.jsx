import React from 'react';
import { Link } from 'react-router-dom';

function MainHeader() {
  return (
    <header className="p-3 mb-3 border-bottom bg-white shadow-sm">
      <div className="container">
        <div className="d-flex flex-wrap align-items-center justify-content-center justify-content-lg-start">
          <span className="fs-4 fw-bold me-auto text-primary">AI-Reinvest</span>
          
          <ul className="nav col-12 col-lg-auto mb-2 justify-content-center mb-md-0 me-4">
            <li><Link to="/" className="nav-link px-2 link-dark">Main</Link></li>
            <li><Link to="/report" className="nav-link px-2 link-dark">Report</Link></li>
          </ul>
        </div>
      </div>
    </header>
  );
}

export default MainHeader;