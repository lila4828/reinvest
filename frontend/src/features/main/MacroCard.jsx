import React from 'react';

function MacroCard({ title, value, change, suffix = '', featured = false, href }) {
  const rawChange = typeof change === 'string' ? change.trim() : 'N/A';
  const hasValidChange = rawChange && rawChange !== 'N/A';

  const isNegative = hasValidChange && rawChange.startsWith('-');
  const isPositive = hasValidChange && !rawChange.startsWith('-');

  const changeColorClass = isNegative ? 'text-primary' : isPositive ? 'text-danger' : 'text-muted';
  const changeArrow = isNegative ? '▼' : isPositive ? '▲' : '';

  const displayChange = hasValidChange ? rawChange.replace('-', '') : 'N/A';
  const CardTag = href ? 'a' : 'div';

  return (
    <div className={`col-6 col-lg macro-card-col ${featured ? 'macro-card-featured' : ''}`}>
      <CardTag
        className={`card macro-card h-100 border-0 shadow-sm ${href ? 'macro-card-link' : ''}`}
        href={href}
        target={href ? '_blank' : undefined}
        rel={href ? 'noreferrer' : undefined}
        title={href ? `${title} 상세 차트 보기` : undefined}
      >
        <div className="card-body macro-card-body">
          <div className="text-muted mb-1 macro-card-title">
            {title}
          </div>

          <div
            className="fw-bold text-dark macro-card-value"
          >
            {value || 'N/A'}
            {suffix}
          </div>

          <div
            className={`fw-semibold mt-1 macro-card-change ${changeColorClass}`}
          >
            {hasValidChange ? (
              <>
                <span>{changeArrow}</span>
                <span>{displayChange}</span>
                <span className="text-muted macro-card-period">
                  (1개월)
                </span>
              </>
            ) : (
              <span className="text-muted">(변화율 없음)</span>
            )}
          </div>
        </div>
      </CardTag>
    </div>
  );
}

export default MacroCard;
