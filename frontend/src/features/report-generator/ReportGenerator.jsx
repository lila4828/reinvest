import React, { useEffect, useMemo, useRef, useState } from 'react';
import './ReportGenerator.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

function ReportGenerator({
    onStartReportJob,
    isWorking = false,
    jobStatus = '',
    statusMessage = '',
}) {
    const [keyword, setKeyword] = useState('');
    const [stockOptions, setStockOptions] = useState([]);
    const [searchResults, setSearchResults] = useState([]);
    const [selectedStocks, setSelectedStocks] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);

    const searchTimerRef = useRef(null);

    const visibleStockOptions =
        searchResults.length > 0 ? searchResults : stockOptions;

    const selectedStockKeys = useMemo(
        () => new Set(selectedStocks.map((stock) => stock.ticker)),
        [selectedStocks],
    );

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
                },
            );

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || '종목 검색에 실패했습니다.');
            }

            setSearchResults(data.results || []);

            if (!data.results || data.results.length === 0) {
                setErrorMessage(data.message || '검색 결과가 없습니다. 종목명이나 티커로 다시 검색해 주세요.');
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
        if (!stock?.ticker) return;

        if (selectedStockKeys.has(stock.ticker)) {
            setKeyword('');
            setSearchResults([]);
            setIsDropdownOpen(false);
            setErrorMessage('이미 선택한 종목입니다.');
            return;
        }

        setSelectedStocks((prev) => [
            ...prev,
            stock,
        ]);

        setKeyword('');
        setSearchResults([]);
        setIsDropdownOpen(false);
        setErrorMessage('');
    };

    const handleRemoveStock = (ticker) => {
        setSelectedStocks((prev) =>
            prev.filter((stock) => stock.ticker !== ticker)
        );
        setErrorMessage('');
    };

    const handleClearSelectedStocks = () => {
        setSelectedStocks([]);
        setErrorMessage('');
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (selectedStocks.length === 0) {
            setErrorMessage('분석할 종목을 1개 이상 선택해 주세요.');
            return;
        }

        if (typeof onStartReportJob !== 'function') {
            setErrorMessage('리포트 생성 함수가 연결되지 않았습니다.');
            return;
        }

        setErrorMessage('');

        try {
            await onStartReportJob(selectedStocks);
        } catch (error) {
            setErrorMessage(error.message);
        }
    };

    useEffect(() => {
        fetchStockOptions();

        return () => {
            if (searchTimerRef.current) {
                clearTimeout(searchTimerRef.current);
            }
        };
    }, []);

    return (
        <div className="report-generator-card p-4 mb-4 shadow-sm border rounded">
            <div className="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-3">
                <div>
                    <h4 className="fw-bold text-primary mb-1">AI 리포트 생성</h4>
                </div>

                {isWorking && jobStatus && (
                    <span className={`badge report-job-badge status-${jobStatus}`}>
                        {jobStatus}
                    </span>
                )}
            </div>

            <form onSubmit={handleSubmit}>
                <div className="row g-3 align-items-end">
                    <div className="col-md-9">
                        <div className="stock-search-wrapper">
                            <input
                                type="text"
                                className="form-control"
                                placeholder="종목명를 입력한 뒤 검색 결과를 선택해 주세요"
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

                            {isDropdownOpen && visibleStockOptions.length > 0 && keyword.trim() && (
                                <div className="stock-search-results shadow-sm border rounded">
                                    {visibleStockOptions.map((stock) => {
                                        const isSelected = selectedStockKeys.has(stock.ticker);

                                        return (
                                            <button
                                                type="button"
                                                key={`${stock.ticker}-${stock.company}`}
                                                className={`stock-search-item ${isSelected ? 'selected' : ''}`}
                                                onClick={() => handleSelectStock(stock)}
                                                disabled={isSelected || isWorking}
                                            >
                                                <div className="d-flex justify-content-between gap-2">
                                                    <div>
                                                        <div className="fw-bold">
                                                            {stock.company}
                                                        </div>
                                                        <div className="small text-muted">
                                                            {stock.ticker}
                                                            {stock.exchange ? ` · ${stock.exchange}` : ''}
                                                        </div>
                                                    </div>

                                                    {isSelected && (
                                                        <span className="stock-selected-label">
                                                            선택됨
                                                        </span>
                                                    )}
                                                </div>
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="col-md-3 d-grid">
                        <button
                            type="submit"
                            className="btn btn-primary fw-bold"
                            disabled={isWorking || selectedStocks.length === 0}
                        >
                            {isWorking
                                ? '생성 중...'
                                : `${selectedStocks.length || ''}${selectedStocks.length ? '개 ' : ''}리포트 생성`}
                        </button>
                    </div>
                </div>
            </form>

            {selectedStocks.length > 0 && (
                <div className="selected-stock-panel mt-3">
                    <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
                        <strong className="small">
                            선택 종목 {selectedStocks.length}개
                        </strong>

                        <button
                            type="button"
                            className="btn btn-sm btn-outline-secondary"
                            onClick={handleClearSelectedStocks}
                            disabled={isWorking}
                        >
                            전체 해제
                        </button>
                    </div>

                    <div className="selected-stock-list">
                        {selectedStocks.map((stock) => (
                            <div
                                key={`${stock.ticker}-${stock.company}`}
                                className="selected-stock-chip"
                            >
                                <div>
                                    <strong>{stock.company}</strong>
                                    <span className="text-muted ms-1">
                                        ({stock.ticker})
                                    </span>
                                </div>

                                <button
                                    type="button"
                                    className="selected-stock-remove"
                                    onClick={() => handleRemoveStock(stock.ticker)}
                                    disabled={isWorking}
                                    aria-label={`${stock.company} 선택 해제`}
                                >
                                    ×
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {statusMessage && isWorking && (
                <div className="small text-muted mt-3">
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