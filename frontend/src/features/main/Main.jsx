import React, { useState } from 'react';
import MainTop from './MainTop';
import MainBody from './MainBody';
import ReportGenerator from '../report-generator/ReportGenerator';

function Main() {
  const [reportRefreshKey, setReportRefreshKey] = useState(0);

  const handleReportGenerated = () => {
    setReportRefreshKey((prev) => prev + 1);
  };

  return (
    <div className="container mt-4">
      <MainTop refreshKey={reportRefreshKey} />
      <ReportGenerator onReportGenerated={handleReportGenerated} />
      <MainBody refreshKey={reportRefreshKey} />
    </div>
  );
}

export default Main;