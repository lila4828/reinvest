import React from 'react';
import MainTop from './MainTop';
import MainBody from './MainBody';
import ReportGenerator from '../report-generator/ReportGenerator';

function Main({
  reportRefreshKey = 0,
  onStartReportJob,
  isReportWorking = false,
  reportJobStatus = '',
  reportStatusMessage = '',
  reportTargetsStatus = [],
}) {
  return (
    <div className="container main-page-container mt-4">
      <MainTop refreshKey={reportRefreshKey} />

      <MainBody
        refreshKey={reportRefreshKey}
        onStartReportJob={onStartReportJob}
        isReportWorking={isReportWorking}
        reportTargetsStatus={reportTargetsStatus}
        sideContent={
          <ReportGenerator
            onStartReportJob={onStartReportJob}
            isWorking={isReportWorking}
            jobStatus={reportJobStatus}
            statusMessage={reportStatusMessage}
          />
        }
      />
    </div>
  );
}

export default Main;
