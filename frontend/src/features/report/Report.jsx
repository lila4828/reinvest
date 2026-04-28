import React from 'react';
import axios from 'axios';
import ReportBody from './ReportBody';

// 전역 규칙: 세션 기반 인증을 위해 기본값 설정
axios.defaults.withCredentials = true;

function Report() {
  return (
    <ReportBody />
  );
}

export default Report;