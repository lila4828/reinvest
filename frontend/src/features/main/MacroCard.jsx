import React from 'react';

function MacroCard({ title, value, change, suffix = '' }) {
  const rawChange = typeof change === 'string' ? change.trim() : 'N/A';
  const hasValidChange = rawChange && rawChange !== 'N/A';

  const isNegative = hasValidChange && rawChange.startsWith('-');
  const isPositive = hasValidChange && !rawChange.startsWith('-');

  const changeColorClass = isNegative ? 'text-primary' : isPositive ? 'text-danger' : 'text-muted';
  const changeArrow = isNegative ? '▼' : isPositive ? '▲' : '';

  const displayChange = hasValidChange ? rawChange.replace('-', '') : 'N/A';

  return (
    <div className="col">
      <div className="card h-100 border-0 shadow-sm">
        <div className="card-body">
          <div className="text-muted mb-2" style={{ fontSize: '0.95rem' }}>
            {title}
          </div>

          <div
            className="fw-bold text-dark"
            style={{
              fontSize: '2rem',
              lineHeight: 1.2,
              whiteSpace: 'nowrap',
            }}
          >
            {value || 'N/A'}
            {suffix}
          </div>

          <div
            className={`fw-semibold mt-2 ${changeColorClass}`}
            style={{
              fontSize: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flexWrap: 'wrap',
            }}
          >
            {hasValidChange ? (
              <>
                <span>{changeArrow}</span>
                <span>{displayChange}</span>
                <span className="text-muted" style={{ fontSize: '0.9rem' }}>
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