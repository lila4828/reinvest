import { useState, useEffect } from 'react';
import axios from 'axios';

export function useReports() {
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    setIsLoadingList(true);
    axios.get('http://localhost:8000/api/reports')
      .then(response => {
        setReports(response.data.reports);
        setIsLoadingList(false);
      })
      .catch(error => {
        console.error('리포트 목록을 불러오지 못했습니다.', error);
        setErrorMsg('리포트 목록을 불러오는 중 문제가 발생했습니다. 서버 상태를 확인해주세요.');
        setIsLoadingList(false);
      });
  }, []);

  const handleReportClick = (filename) => {
    console.log("👉 클릭된 리포트 파일명:", filename);
    setSelectedReport(filename);
    setIsLoadingDetail(true);
    setErrorMsg('');

    axios.get(`http://localhost:8000/api/reports/${filename}`)
      .then(response => {
        console.log("✅ 리포트 상세 로드 성공!");
        setReportContent(response.data.content);
        setIsLoadingDetail(false);
      })
      .catch(error => {
        console.error('리포트 상세 내용을 불러오지 못했습니다.', error);
        setErrorMsg('리포트 상세 내용을 불러오는 중 문제가 발생했습니다.');
        setIsLoadingDetail(false);
      });
  };

  const handleBack = () => {
    setSelectedReport(null);
    setErrorMsg('');
    setReportContent('');
  };

  return { reports, selectedReport, reportContent, isLoadingList, isLoadingDetail, errorMsg, handleReportClick, handleBack };
}