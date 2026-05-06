import React from 'react';
import ReportBody from './ReportBody';

function Report({ refreshKey = 0 }) {
  return (
    <ReportBody refreshKey={refreshKey} />
  );
}

export default Report;