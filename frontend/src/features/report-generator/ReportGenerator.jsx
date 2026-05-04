import React, { useEffect, useRef, useState } from 'react';
import './ReportGenerator.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function ReportGenerator({ onReportGenerated }) {
    const [keyword, setKeyword] = useState('');
    const [stockOptions, setStockOptions] = useState([]);
    const [searchResults, setSearchResults] = useState([]);
    const [selectedStock, setSelectedStock] = useState(null);
    const [isSearching, setIsSearching] = useState(false);

    const [jobId, setJobId] = useState('');
    const [jobStatus, setJobStatus] = useState('');
    const [statusMessage, setStatusMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const pollingTimerRef = useRef(null);
    const searchTimerRef = useRef(null);

    const stopPolling = () => {
        if (pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
        }
    };

    const fetchStockOptions = async () => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/stock-options`, {
                method: 'GET',
                credentials: 'include',
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || '기본 종목 목록을 불러오지 못했습니다.');
            }

            setStockOptions(data.results || []);
        } catch (error) {
            setStockOptions([]);
            setErrorMessage(error.message);
        }
    };

    const fetchJobStatus = async (targetJobId) => {
        try {
            const res = await fetch(`${API_BASE_URL}/api/report-status/${targetJobId}`, {
                method: 'GET',
                credentials: 'include',
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || '작업 상태를 확인하지 못했습니다.');
            }

            setJobStatus(data.status);

            if (data.status === 'pending') {
                setStatusMessage('리포트 생성 대기 중...');
                return;
            }

            if (data.status === 'running') {
                setStatusMessage('리포트 생성 중...');
                return;
            }

            if (data.status === 'success') {
                stopPolling();
                setIsSubmitting(false);
                setStatusMessage('리포트 생성이 완료되었습니다. 최신 리포트를 자동으로 불러옵니다.');

                if (typeof onReportGenerated === 'function') {
                    onReportGenerated();
                }

                return;
            }

            if (data.status === 'failed') {
                stopPolling();
                setIsSubmitting(false);
                setErrorMessage(data.error || '리포트 생성 중 오류가 발생했습니다.');
                setStatusMessage('');
            }
        } catch (error) {
            stopPolling();
            setIsSubmitting(false);
            setErrorMessage(error.message);
            setStatusMessage('');
        }
    };

    const startPolling = (targetJobId) => {
        stopPolling();

        fetchJobStatus(targetJobId);

        pollingTimerRef.current = setInterval(() => {
            fetchJobStatus(targetJobId);
        }, 3000);
    };

    const searchStocks = async (searchKeyword) => {
        const cleanKeyword = searchKeyword.trim();

        if (cleanKeyword.length < 2) {
            setSearchResults([]);
            return;
        }

        setIsSearching(true);
        setErrorMessage('');

        try {
            const res = await fetch(
                `${API_BASE_URL}/api/stock-search?q=${encodeURIComponent(cleanKeyword)}`,
                {
                    method: 'GET',
                    credentials: 'include',
                }
            );

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || '종목 검색에 실패했습니다.');
            }

            setSearchResults(data.results || []);

            if (!data.results || data.results.length === 0) {
                setErrorMessage('검색 결과가 없습니다. 영문명 또는 티커로 다시 검색해 주세요.');
            }
        } catch (error) {
            setSearchResults([]);
            setErrorMessage(error.message);
        } finally {
            setIsSearching(false);
        }
    };

    const handleKeywordChange = (event) => {
        const value = event.target.value;

        setKeyword(value);
        setSelectedStock(null);
        setErrorMessage('');
        setIsDropdownOpen(true);

        if (searchTimerRef.current) {
            clearTimeout(searchTimerRef.current);
        }

        if (!value.trim()) {
            setSearchResults([]);
            return;
        }

        searchTimerRef.current = setTimeout(() => {
            searchStocks(value);
        }, 350);
    };

    const handleSelectStock = (stock) => {
        setSelectedStock(stock);
        setKeyword(`${stock.company} (${stock.ticker})`);
        setSearchResults([]);
        setIsDropdownOpen(false);
        setErrorMessage('');
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (!selectedStock) {
            setErrorMessage('검색 결과에서 분석할 종목을 선택해 주세요.');
            return;
        }

        setIsSubmitting(true);
        setErrorMessage('');
        setStatusMessage('리포트 생성 요청 중...');
        setJobStatus('');
        setJobId('');

        try {
            const res = await fetch(`${API_BASE_URL}/api/run-report`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    stocks: [
                        {
                            ticker: selectedStock.ticker,
                            company: selectedStock.company,
                            exchange: selectedStock.exchange,
                            quote_type: selectedStock.quote_type,
                        },
                    ],
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || '리포트 생성 요청에 실패했습니다.');
            }

            setJobId(data.job_id);
            setJobStatus(data.status);
            setStatusMessage('리포트 생성 작업이 시작되었습니다.');

            startPolling(data.job_id);
        } catch (error) {
            setIsSubmitting(false);
            setErrorMessage(error.message);
            setStatusMessage('');
        }
    };

    useEffect(() => {
        fetchStockOptions();

        return () => {
            stopPolling();

            if (searchTimerRef.current) {
                clearTimeout(searchTimerRef.current);
            }
        };
    }, []);

    const isWorking =
        isSubmitting ||
        jobStatus === 'pending' ||
        jobStatus === 'running';

    const visibleStockOptions =
        searchResults.length > 0 ? searchResults : stockOptions;

    return (
        <div className="report-generator-card p-4 mb-4 shadow-sm border rounded">
            <div className="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                <div>
                    <h4 className="fw-bold text-primary mb-1">🧾 새 리포트 생성</h4>
                    <p className="text-muted mb-0 small">
                        종목명을 검색해서 선택하면 백그라운드에서 리포트를 생성합니다.
                    </p>
                </div>

                {jobStatus && (
                    <span className={`badge report-job-badge status-${jobStatus}`}>
                        {jobStatus}
                    </span>
                )}
            </div>

            <form onSubmit={handleSubmit}>
                <div className="row g-3 align-items-end">
                    <div className="col-md-9">
                        <label className="form-label fw-bold">종목 검색</label>

                        <div className="stock-search-wrapper">
                            <input
                                type="text"
                                className="form-control"
                                placeholder="종목명을 입력하거나 선택하세요"
                                value={keyword}
                                onChange={handleKeywordChange}
                                onFocus={() => {
                                    setIsDropdownOpen(true);
                                }}
                                disabled={isWorking}
                            />

                            {isSearching && (
                                <div className="stock-search-status small text-muted">
                                    검색 중...
                                </div>
                            )}

                            {isDropdownOpen && visibleStockOptions.length > 0 && !selectedStock && (
                                <div className="stock-search-results shadow-sm border rounded">
                                    {visibleStockOptions.map((stock) => (
                                        <button
                                            type="button"
                                            key={`${stock.ticker}-${stock.company}`}
                                            className="stock-search-item"
                                            onClick={() => handleSelectStock(stock)}
                                        >
                                            <div className="fw-bold">
                                                {stock.company}
                                            </div>
                                            <div className="small text-muted">
                                                {stock.ticker}
                                                {stock.exchange ? ` · ${stock.exchange}` : ''}
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="col-md-3 d-grid">
                        <button
                            type="submit"
                            className="btn btn-primary fw-bold"
                            disabled={isWorking || !selectedStock}
                        >
                            {isWorking ? '생성 중...' : '리포트 생성'}
                        </button>
                    </div>
                </div>
            </form>

            {selectedStock && (
                <div className="alert alert-light border py-2 mt-3 mb-0 small">
                    선택 종목:{' '}
                    <strong>{selectedStock.company}</strong>{' '}
                    <span className="text-muted">({selectedStock.ticker})</span>
                </div>
            )}

            {statusMessage && (
                <div className="alert alert-info py-2 mt-3 mb-0">
                    {isWorking && (
                        <span className="spinner-border spinner-border-sm me-2" role="status">
                            <span className="visually-hidden">Loading...</span>
                        </span>
                    )}
                    {statusMessage}
                </div>
            )}

            {errorMessage && (
                <div className="alert alert-danger py-2 mt-3 mb-0">
                    {errorMessage}
                </div>
            )}
        </div>
    );
}

export default ReportGenerator;