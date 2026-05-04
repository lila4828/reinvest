import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import '../root.css';

import MainHeader from '../layout/MainHeader';
import Login from '../login/Login';

import Main from '../main/Main';
import Report from '../report/Report';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function App() {
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState('');

  const checkAuth = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/me`, {
        method: 'GET',
        credentials: 'include',
      });

      if (!res.ok) {
        setIsAuthenticated(false);
        setUsername('');
        return;
      }

      const data = await res.json();

      setIsAuthenticated(Boolean(data.authenticated));
      setUsername(data.username || '');
    } catch (error) {
      setIsAuthenticated(false);
      setUsername('');
    } finally {
      setAuthChecked(true);
    }
  };

  const handleLoginSuccess = (loginData) => {
    setIsAuthenticated(true);
    setUsername(loginData.username || '');
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('로그아웃 실패:', error);
    } finally {
      setIsAuthenticated(false);
      setUsername('');
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  if (!authChecked) {
    return (
      <div className="min-vh-100 d-flex align-items-center justify-content-center">
        <div className="text-center text-muted">
          <div className="spinner-border spinner-border-sm me-2" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          로그인 상태 확인 중...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <BrowserRouter>
      <MainHeader username={username} onLogout={handleLogout} />
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