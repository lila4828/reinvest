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
import './ReportDetail.css';

function cleanReportContent(content) {
  if (!content || typeof content !== 'string') return '';

  return content
    .replace(/<!--\s*MACRO_DATA\s*[\s\S]*?\s*-->/g, '')
    .trim();
}

function isKoreanReport(content) {
  if (!content || typeof content !== 'string') return false;

  // 가격표의 현재가 기준으로 판단
  // 한국 주식: | **현재가** | **80,000원** |
  // 미국 주식: | **현재가** | **$381.63** |
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

  // fallback
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

function formatChartValue(value, isKoreanStock) {
  const numberValue = Math.round(Number(value || 0));

  if (isKoreanStock) {
    return `${numberValue}조 원`;
  }

  return `${numberValue}B`;
}

function formatBarLabelValue(value, isKoreanStock) {
  const numberValue = Math.round(Number(value || 0));

  if (isKoreanStock) {
    return `${numberValue}조`;
  }

  return `${numberValue}B`;
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

  const topPadding = Math.max(Math.abs(maxValue) * 0.18, 5);

  // 음수 라벨이 잘리지 않도록 아래쪽 여백을 더 크게 확보
  const bottomPadding =
    minValue < 0
      ? Math.max(Math.abs(minValue) * 1.2, Math.abs(maxValue) * 0.08, 8)
      : 0;

  const yMin = minValue < 0 ? Math.floor(minValue - bottomPadding) : 0;
  const yMax = Math.ceil(maxValue + topPadding);

  return [yMin, yMax];
}

function extractChartSection(content) {
  if (!content || typeof content !== 'string') {
    return {
      cleanedContent: '',
      chartData: [],
      isKoreanStock: false,
    };
  }

  const cleaned = cleanReportContent(content);
  const isKoreanStock = isKoreanReport(cleaned);

  const chartBlockRegex =
    /##\s*📎\s*실적 차트 데이터[\s\S]*?```json\s*([\s\S]*?)\s*```/m;

  const match = cleaned.match(chartBlockRegex);

  if (!match) {
    return {
      cleanedContent: cleaned,
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

  const cleanedContent = cleaned.replace(chartBlockRegex, '').trim();

  const normalizedChartData = parsedChartData.map((item) => ({
    period: getPeriodLabel(item.period),
    revenue: normalizeChartValue(item.revenue, isKoreanStock),
    net_profit: normalizeChartValue(item.net_profit, isKoreanStock),
    fcf: normalizeChartValue(item.fcf, isKoreanStock),
  }));

  return {
    cleanedContent,
    chartData: normalizedChartData,
    isKoreanStock,
  };
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
    const { x, y, width, value } = props;

    const roundedValue = Math.round(Number(value || 0));
    const label = formatBarLabelValue(roundedValue, isKoreanStock);
    const isNegative = roundedValue < 0;

    return (
      <text
        x={x + width / 2}
        y={isNegative ? y - 20 : y - 8}
        textAnchor="middle"
        fontSize={11}
        fontWeight={700}
        fill={isNegative ? '#dc2626' : '#374151'}
      >
        {label}
      </text>
    );
  };
}

function ReportDetail({ content, isLoading, onBack }) {
  const { cleanedContent, chartData, isKoreanStock } = useMemo(
    () => extractChartSection(content),
    [content]
  );

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
        <>
          <div className="markdown-content p-4 bg-light rounded border shadow-sm mb-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanedContent}
            </ReactMarkdown>
          </div>

          {chartData.length > 0 && (
            <div className="card report-detail-chart-card">
              <div className="card-body">
                <h4 className="report-detail-chart-title">📊 실적 차트</h4>

                <p className="report-detail-chart-unit">
                  단위: {isKoreanStock ? '조 원(반올림)' : 'Billion USD (rounded)'}
                </p>

                <div className="report-chart-wrapper">
                  <ResponsiveContainer>
                    <BarChart
                      data={chartData}
                      margin={{ top: 36, right: 24, left: 24, bottom: 12 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="period" />
                      <YAxis hide domain={getYAxisDomain(chartData)} />
                      <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} />
                      <Tooltip content={ <CustomTooltip isKoreanStock={isKoreanStock} /> } />
                      <Legend />
                      <Bar
                        dataKey="revenue"
                        name="매출"
                        fill="var(--chart-revenue)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList content={renderBarLabel(isKoreanStock)} />
                      </Bar>
                      <Bar
                        dataKey="net_profit"
                        name="순이익"
                        fill="var(--chart-net-profit)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList content={renderBarLabel(isKoreanStock)} />
                      </Bar>
                      <Bar
                        dataKey="fcf"
                        name="잉여현금흐름"
                        fill="var(--chart-fcf)"
                        radius={[6, 6, 0, 0]}
                      >
                        <LabelList content={renderBarLabel(isKoreanStock)} />
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