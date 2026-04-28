import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css'; // Bootstrap 전역 적용
import './css/root.css'; // AI-Reinvest 공통 스타일

import MainHeader from './components/MainHeader';
// Features
import Main from './features/main/Main';
import Report from './features/report/Report';

function App() {
  return (
    <BrowserRouter>
      <MainHeader />
      <div className="main-content">
        <Routes>
          <Route path="/" element={<Main />} />
          <Route path="/report" element={<Report />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
