import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
});

export function useReports(refreshKey = 0) {
  const [searchParams, setSearchParams] = useSearchParams();

  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportContent, setReportContent] = useState('');
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const dateParam = searchParams.get('date');
  const filenameParam = searchParams.get('filename');
  const stockKeywordParam = searchParams.get('q') || '';

  useEffect(() => {
    setIsLoadingList(true);
    setErrorMsg('');

    apiClient.get('/api/reports')
      .then(response => {
        const singleReports = (response.data.reports || []).filter(
          report => !report.is_summary
        );

        setReports(singleReports);
        setIsLoadingList(false);
      })
      .catch(error => {
        console.error('리포트 목록을 불러오지 못했습니다.', error);

        if (error.response?.status === 401) {
          setErrorMsg('로그인이 필요합니다. 다시 로그인해 주세요.');
        } else {
          setErrorMsg('리포트 목록을 불러오는 중 문제가 발생했습니다. 서버 상태를 확인해주세요.');
        }

        setIsLoadingList(false);
      });
  }, [refreshKey]);

  const fetchReportDetail = useCallback((report) => {
    if (!report?.date || !report?.filename) return;

    setSelectedReport(report);
    setIsLoadingDetail(true);
    setErrorMsg('');

    const date = encodeURIComponent(report.date);
    const filename = encodeURIComponent(report.filename);

    apiClient.get(`/api/reports/${date}/${filename}`)
      .then(response => {
        setReportContent(response.data.content);
        setIsLoadingDetail(false);
      })
      .catch(error => {
        console.error('리포트 상세 내용을 불러오지 못했습니다.', error);

        if (error.response?.status === 401) {
          setErrorMsg('로그인이 필요합니다. 다시 로그인해 주세요.');
        } else {
          setErrorMsg('리포트 상세 내용을 불러오는 중 문제가 발생했습니다.');
        }

        setIsLoadingDetail(false);
      });
  }, [refreshKey]);

  useEffect(() => {
    if (isLoadingList) return;

    if (!dateParam || !filenameParam) {
      setSelectedReport(null);
      setReportContent('');
      setIsLoadingDetail(false);
      return;
    }

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

    const nextParams = {
      date: report.date,
      filename: report.filename,
    };

    if (stockKeywordParam) {
      nextParams.q = stockKeywordParam;
    }

    setSearchParams(nextParams);
  };

  const handleBack = () => {
    if (stockKeywordParam) {
      setSearchParams({ q: stockKeywordParam });
    } else {
      setSearchParams({});
    }

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
    stockKeywordParam,
    handleReportClick,
    handleBack,
  };
}
