import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export function useReports() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const dateParam = searchParams.get('date');
  const filenameParam = searchParams.get('filename');

  useEffect(() => {
    setIsLoadingList(true);

    axios.get(`${API_BASE_URL}/api/reports`)
      .then(response => {
        const singleReports = (response.data.reports || []).filter(
          report => !report.is_summary
        );

        setReports(singleReports);
        setIsLoadingList(false);
      })
      .catch(error => {
        console.error('리포트 목록을 불러오지 못했습니다.', error);
        setErrorMsg('리포트 목록을 불러오는 중 문제가 발생했습니다. 서버 상태를 확인해주세요.');
        setIsLoadingList(false);
      });
  }, []);

  const fetchReportDetail = useCallback((report) => {
    if (!report?.date || !report?.filename) return;

    setSelectedReport(report);
    setIsLoadingDetail(true);
    setErrorMsg('');

    const date = encodeURIComponent(report.date);
    const filename = encodeURIComponent(report.filename);

    axios.get(`${API_BASE_URL}/api/reports/${date}/${filename}`)
      .then(response => {
        setReportContent(response.data.content);
        setIsLoadingDetail(false);
      })
      .catch(error => {
        console.error('리포트 상세 내용을 불러오지 못했습니다.', error);
        setErrorMsg('리포트 상세 내용을 불러오는 중 문제가 발생했습니다.');
        setIsLoadingDetail(false);
      });
  }, []);

  useEffect(() => {
    if (isLoadingList) return;

    // URL에 상세 파라미터가 없으면 리스트 화면
    if (!dateParam || !filenameParam) {
      setSelectedReport(null);
      setReportContent('');
      setIsLoadingDetail(false);
      return;
    }

    // URL 파라미터에 해당하는 리포트 찾기
    const matchedReport = reports.find(
      report => report.date === dateParam && report.filename === filenameParam
    );

    if (!matchedReport) {
      setSelectedReport(null);
      setReportContent('');
      setErrorMsg('해당 리포트를 찾을 수 없습니다.');
      return;
    }

    fetchReportDetail(matchedReport);
  }, [dateParam, filenameParam, reports, isLoadingList, fetchReportDetail]);

  const handleReportClick = (report) => {
    if (!report?.date || !report?.filename) return;

    // 중요: replace를 쓰지 않으면 브라우저 히스토리에 상세 화면이 쌓임
    // 그래서 크롬 뒤로가기 시 /report 리스트로 돌아갈 수 있음
    setSearchParams({
      date: report.date,
      filename: report.filename,
    });
  };

  const handleBack = () => {
    // 앱 내부 버튼도 /report 리스트 상태로 복귀
    setSearchParams({});
    setSelectedReport(null);
    setErrorMsg('');
    setReportContent('');
  };

  return {
    reports,
    selectedReport,
    reportContent,
    isLoadingList,
    isLoadingDetail,
    errorMsg,
    handleReportClick,
    handleBack,
  };
}