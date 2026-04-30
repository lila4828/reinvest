import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function ReportDetail({ content, isLoading, onBack }) {
  if (isLoading) {
    return <div className="p-4 text-center">리포트 상세 내용을 불러오는 중...</div>;
  }

  return (
    <div>
      <button className="btn btn-outline-secondary mb-4" onClick={onBack}>
        &larr; 목록으로 돌아가기
      </button>

      {!content ? (
        <div className="alert alert-warning">
          리포트 내용이 비어 있습니다.
        </div>
      ) : (
        <div className="markdown-content p-4 bg-light rounded border shadow-sm">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

export default ReportDetail;