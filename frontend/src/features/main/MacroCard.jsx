import React from 'react';

// Helper to determine color based on change (▲ or + is green, ▼ or - is red)
const getChangeColor = (change) => {
  if (!change || change === 'N/A') return 'text-muted';
  return change.includes('▲') || (change.includes('+') && !change.includes('-')) ? 'text-success' : 'text-danger';
};

// Helper to format the change string (e.g., +1.2% -> ▲ 1.2%)
const formatChange = (change) => {
  if (!change || change === 'N/A') return '...';
  return change.replace('+', '▲ ').replace('-', '▼ ');
};

function MacroCard({ title, value, change, suffix = '' }) {
  const displayValue = (value && value !== 'N/A') ? `${value}${suffix}` : (value || 'N/A');

  return (
    <div className="col-lg col-md-4 col-6">
      <div className="p-3 bg-light rounded h-100">
        <h6 className="text-muted">{title}</h6>
        <h4 className="mb-0">
          {displayValue}
          {change && change !== 'N/A' && (
            <span className={`fs-6 ms-2 ${getChangeColor(change)}`}>
              {formatChange(change)} <span className="text-muted fw-normal" style={{ fontSize: '0.75rem' }}>(1개월)</span>
            </span>
          )}
        </h4>
      </div>
    </div>
  );
}

export default MacroCard;