import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function ReportDetail({ content, isLoading, onBack }) {
  return (
    <div>
      <button 
        className="btn btn-outline-secondary mb-3" 
        onClick={onBack}
      >
        ← 목록으로 돌아가기
      </button>
      {isLoading ? (
        <div className="text-center my-5">
          <div className="spinner-border text-primary" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <p className="mt-2 text-muted fw-bold">AI가 리포트를 불러오는 중입니다...</p>
        </div>
      ) : (
        <div className="card p-4 shadow-sm bg-white markdown-content" style={{ overflowX: 'auto' }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default ReportDetail;