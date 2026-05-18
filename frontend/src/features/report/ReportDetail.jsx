import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  LabelList,
  ReferenceLine,
} from 'recharts';
import { addKrwConversionToPriceTable } from './reportDisplayUtils';
import './ReportDetail.css';

function cleanReportContent(content) {
  if (!content || typeof content !== 'string') return '';

  return content
    .replace(/<!--\s*MACRO_DATA\s*[\s\S]*?\s*-->/g, '')
    .trim();
}

function isKoreanReport(content) {
  if (!content || typeof content !== 'string') return false;

  const currentPriceMatch = content.match(
    /\|\s*\*\*현재가\*\*\s*\|\s*\*\*([^*]+)\*\*\s*\|/
  );

  if (currentPriceMatch) {
    const currentPriceText = currentPriceMatch[1];

    if (currentPriceText.includes('$')) {
      return false;
    }

    if (currentPriceText.includes('원')) {
      return true;
    }
  }

  return content.includes('.KS') || content.includes('.KQ');
}

function getPeriodLabel(period) {
  const periodMap = {
    'T-2': '2년 전',
    'T-1': '1년 전',
    T: '최근 연도',
  };

  return periodMap[period] || period;
}

function normalizeChartValue(value, isKoreanStock) {
  const numberValue = Number(value || 0);

  if (isKoreanStock) {
    return numberValue / 1000000000000;
  }

  return numberValue / 1000000000;
}

function formatKoreanChartValue(value, includeWon = false) {
  const numberValue = Number(value || 0);
  const absValue = Math.abs(numberValue);

  if (absValue >= 1) {
    return `${Math.round(numberValue)}조${includeWon ? ' 원' : ''}`;
  }

  const eokValue = Math.round(numberValue * 10000);

  if (eokValue === 0 && numberValue !== 0) {
    return `${numberValue < 0 ? '-' : ''}1억${includeWon ? ' 원' : ''}`;
  }

  return `${eokValue.toLocaleString()}억${includeWon ? ' 원' : ''}`;
}

function formatChartValue(value, isKoreanStock) {
  const numberValue = Number(value || 0);

  if (isKoreanStock) {
    return formatKoreanChartValue(numberValue, true);
  }

  return `${Math.round(numberValue)}B`;
}

function formatBarLabelValue(value, isKoreanStock) {
  const numberValue = Number(value || 0);

  if (isKoreanStock) {
    return formatKoreanChartValue(numberValue, false);
  }

  return `${Math.round(numberValue)}B`;
}

function getYAxisDomain(chartData) {
  if (!Array.isArray(chartData) || chartData.length === 0) {
    return [0, 100];
  }

  const values = chartData.flatMap((item) => [
    Number(item.revenue || 0),
    Number(item.net_profit || 0),
    Number(item.fcf || 0),
  ]);

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const maxAbsValue = Math.max(Math.abs(minValue), Math.abs(maxValue), 1);

  const topPadding = Math.max(Math.abs(maxValue) * 0.22, maxAbsValue * 0.08, 0.25);

  const bottomPadding =
    minValue < 0
      ? Math.max(Math.abs(minValue) * 0.45, maxAbsValue * 0.08, 0.25)
      : 0;

  const yMin = minValue < 0 ? minValue - bottomPadding : 0;
  const yMax = maxValue + topPadding;

  return [
    Number(yMin.toFixed(2)),
    Number(yMax.toFixed(2)),
  ];
}

function normalizeRawChartData(chartData, isKoreanStock) {
  if (!Array.isArray(chartData)) {
    return [];
  }

  return chartData.map((item) => ({
    period: getPeriodLabel(item.period),
    revenue: normalizeChartValue(item.revenue, isKoreanStock),
    net_profit: normalizeChartValue(item.net_profit, isKoreanStock),
    fcf: normalizeChartValue(item.fcf, isKoreanStock),
  }));
}

function getMetaChartData(meta) {
  const chartData = meta?.financial_chart_data;

  return Array.isArray(chartData) && chartData.length > 0 ? chartData : [];
}

function extractChartSection(content, meta) {
  if (!content || typeof content !== 'string') {
    return {
      cleanedContent: '',
      chartData: [],
      isKoreanStock: false,
    };
  }

  const cleaned = cleanReportContent(content);
  const isKoreanStock = isKoreanReport(cleaned);
  const metaChartData = getMetaChartData(meta);

  const chartBlockRegex =
    /##\s*📎\s*실적 차트 데이터[\s\S]*?```json\s*([\s\S]*?)\s*```/m;

  const match = cleaned.match(chartBlockRegex);
  const cleanedContent = match ? cleaned.replace(chartBlockRegex, '').trim() : cleaned;

  if (metaChartData.length > 0) {
    return {
      cleanedContent,
      chartData: normalizeRawChartData(metaChartData, isKoreanStock),
      isKoreanStock,
    };
  }

  if (!match) {
    return {
      cleanedContent,
      chartData: [],
      isKoreanStock,
    };
  }

  let parsedChartData = [];

  try {
    const parsed = JSON.parse(match[1]);
    parsedChartData = Array.isArray(parsed?.chart_data) ? parsed.chart_data : [];
  } catch (error) {
    console.error('차트 JSON 파싱 실패:', error);
  }

  return {
    cleanedContent,
    chartData: normalizeRawChartData(parsedChartData, isKoreanStock),
    isKoreanStock,
  };
}

function formatReportBaseDateTime(report) {
  const source = report?.modified_at || report?.updated_at || report?.generated_at;

  if (!source) {
    return report?.date || '';
  }

  const normalizedSource = String(source).trim();
  const match = normalizedSource.match(/^(\d{4}-\d{2}-\d{2})[T\s](\d{2}:\d{2})/);

  if (match) {
    return `${match[1]} ${match[2]}`;
  }

  return report?.date || normalizedSource.slice(0, 10);
}

function addBaseDateToContent(content, report) {
  const reportBaseDateTime = formatReportBaseDateTime(report);

  if (!content || !reportBaseDateTime) return content;

  const headContent = content.slice(0, 500);

  if (/기준\s*:\s*\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?/.test(headContent)) {
    return content;
  }

  return content.replace(/^(#\s+.+)$/m, `$1\n\n기준: ${reportBaseDateTime}`);
}

function CustomTooltip({ active, payload, label, isKoreanStock }) {
  if (!active || !payload || !payload.length) return null;

  return (
    <div className="report-chart-tooltip">
      <div className="report-chart-tooltip-title">{label}</div>

      {payload.map((entry) => (
        <div key={entry.dataKey} className="report-chart-tooltip-row">
          <span
            className="report-chart-tooltip-dot"
            style={{ backgroundColor: entry.color }}
          />
          <span>
            <span className="fw-semibold">{entry.name}:</span>{' '}
            {formatChartValue(entry.value, isKoreanStock)}
          </span>
        </div>
      ))}
    </div>
  );
}

function renderBarLabel(isKoreanStock) {
  return function BarLabel(props) {
    const { x, y, width, height, value } = props;

    const numberValue = Number(value || 0);

    if (numberValue === 0) {
      return null;
    }

    const label = formatBarLabelValue(numberValue, isKoreanStock);
    const isNegative = numberValue < 0;

    const numberX = Number(x || 0);
    const numberY = Number(y || 0);
    const numberWidth = Number(width || 0);
    const numberHeight = Number(height || 0);

    const labelX = numberX + numberWidth / 2;

    /*
      핵심:
      - 양수 막대: y가 막대 상단
      - 음수 막대: y + height 쪽이 0선 기준으로 잡히는 케이스가 있어서
        두 좌표 중 더 위쪽 값을 기준으로 라벨을 배치한다.
    */
    const barTopY = Math.min(numberY, numberY + numberHeight);
    const labelY = barTopY - 8;

    return (
      <text
        x={labelX}
        y={labelY}
        textAnchor="middle"
        fontSize={11}
        fontWeight={700}
        fill={isNegative ? '#dc2626' : '#111827'}
        pointerEvents="none"
      >
        {label}
      </text>
    );
  };
}

function ReportDetail({
  report,
  content,
  meta,
  macroData,
  isLoading,
  onBack,
  showBackButton = true,
}) {
  const { cleanedContent, chartData, isKoreanStock } = useMemo(
    () => extractChartSection(content, meta),
    [content, meta]
  );
  const displayContent = useMemo(() => {
    const contentWithDate = addBaseDateToContent(cleanedContent, report);
    return addKrwConversionToPriceTable(contentWithDate, report, macroData);
  }, [cleanedContent, report, macroData]);

  if (isLoading) {
    return <div className="p-4 text-center">리포트 상세 내용을 불러오는 중...</div>;
  }

  return (
    <div>
      {showBackButton && (
        <button className="btn btn-outline-secondary mb-4" onClick={onBack}>
          &larr; 목록으로 돌아가기
        </button>
      )}

      {!content ? (
        <div className="alert alert-warning">
          리포트 내용이 비어 있습니다.
        </div>
      ) : (
        <>
          <div className="markdown-content p-4 bg-light rounded border shadow-sm mb-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {displayContent}
            </ReactMarkdown>
          </div>

          {chartData.length > 0 && (
            <div className="card report-detail-chart-card">
              <div className="card-body">
                <h4 className="report-detail-chart-title">📊 실적 차트</h4>

                <p className="report-detail-chart-unit">
                  단위: {isKoreanStock ? '조 원 / 1조 미만은 억 원 표기' : 'Billion USD (rounded)'}
                </p>

                <div className="report-chart-wrapper">
                  <ResponsiveContainer width="100%" height="100%" minHeight={360}>
                    <BarChart
                      data={chartData}
                      margin={{ top: 46, right: 24, left: 24, bottom: 24 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="period" />
                      <YAxis hide domain={getYAxisDomain(chartData)} />
                      <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} />
                      <Tooltip content={<CustomTooltip isKoreanStock={isKoreanStock} />} />
                      <Legend />
                      <Bar
                        dataKey="revenue"
                        name="매출"
                        fill="var(--chart-revenue)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList
                          position="top"
                          content={renderBarLabel(isKoreanStock)}
                        />
                      </Bar>
                      <Bar
                        dataKey="net_profit"
                        name="순이익"
                        fill="var(--chart-net-profit)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList 
                          position="top"
                          content={renderBarLabel(isKoreanStock)}
                        />
                      </Bar>
                      <Bar
                        dataKey="fcf"
                        name="잉여현금흐름"
                        fill="var(--chart-fcf)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList 
                          position="top"
                          content={renderBarLabel(isKoreanStock)}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default ReportDetail;
