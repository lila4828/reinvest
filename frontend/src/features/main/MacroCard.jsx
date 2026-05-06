import React from 'react';

function MacroCard({ title, value, change, suffix = '', featured = false }) {
  const rawChange = typeof change === 'string' ? change.trim() : 'N/A';
  const hasValidChange = rawChange && rawChange !== 'N/A';

  const isNegative = hasValidChange && rawChange.startsWith('-');
  const isPositive = hasValidChange && !rawChange.startsWith('-');

  const changeColorClass = isNegative ? 'text-primary' : isPositive ? 'text-danger' : 'text-muted';
  const changeArrow = isNegative ? '▼' : isPositive ? '▲' : '';

  const displayChange = hasValidChange ? rawChange.replace('-', '') : 'N/A';

  return (
    <div className={`col-6 col-lg macro-card-col ${featured ? 'macro-card-featured' : ''}`}>
      <div className="card macro-card h-100 border-0 shadow-sm">
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
      </div>
    </div>
  );
}

export default MacroCard;
