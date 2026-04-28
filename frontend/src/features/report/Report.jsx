import React from 'react';
import MainHeader from '../../components/MainHeader';
import axios from 'axios';
import ReportBody from './ReportBody';

// OncoCare 규칙: 세션 기반 인증을 위해 기본값 설정
axios.defaults.withCredentials = true;

function Report() {
  return (
    <>
      <MainHeader />
      <ReportBody />
    </>
  );
}

export default Report;