export function extractMacroJson(content) {
  if (!content || typeof content !== 'string') return null;

  const match = content.match(/<!--\s*MACRO_DATA\s*([\s\S]*?)\s*-->/);

  if (!match) return null;

  try {
    return JSON.parse(match[1]);
  } catch (error) {
    console.error('MACRO_DATA JSON 파싱 실패:', error);
    return null;
  }
}

export function getReportTicker(report) {
  const source = report?.filename || report?.display_name || '';
  const baseName = source.replace(/\.md$/i, '');
  const separatorIndex = baseName.lastIndexOf('_');

  if (separatorIndex > 0 && separatorIndex < baseName.length - 1) {
    return baseName.slice(separatorIndex + 1).toUpperCase();
  }

  return String(report?.ticker || '').toUpperCase();
}

export function isUsStock(report, content = '') {
  const ticker = getReportTicker(report);

  if (ticker.endsWith('.KS') || ticker.endsWith('.KQ')) {
    return false;
  }

  const marketText = [
    report?.market_label,
    report?.exchange,
    report?.market,
  ]
    .filter(Boolean)
    .join(' ')
    .toUpperCase();

  return (
    Boolean(ticker) ||
    marketText.includes('NASDAQ') ||
    marketText.includes('NYSE') ||
    marketText.includes('AMEX') ||
    marketText.includes('미국') ||
    content.includes('$')
  );
}

export function getExchangeRateFromMacroData(macroData) {
  const candidates = [
    macroData?.exchange_rate,
    macroData?.usd_krw,
    macroData?.usdKrw,
    macroData?.exchangeRate,
  ];

  const value = candidates
    .map((candidate) => Number(String(candidate ?? '').replace(/,/g, '')))
    .find((candidate) => Number.isFinite(candidate) && candidate > 0);

  return value || null;
}

export function formatKrwApproxFromUsd(usdPrice, exchangeRate) {
  const krwValue = Number(usdPrice) * Number(exchangeRate);

  if (!Number.isFinite(krwValue)) {
    return '';
  }

  const roundedValue = Math.round(krwValue / 100) * 100;
  return `약 ${roundedValue.toLocaleString('ko-KR')}원`;
}

export function formatUsdWithKrwApprox(priceText, exchangeRate) {
  const dollarPrice = Number(String(priceText || '').replace(/,/g, ''));
  const krwApprox = formatKrwApproxFromUsd(dollarPrice, exchangeRate);

  if (!krwApprox) {
    return `$${priceText}`;
  }

  return `$${priceText} (${krwApprox})`;
}

export function addKrwConversionToPriceTable(content, report, macroData) {
  if (!content) {
    return content;
  }

  const exchangeRate = getExchangeRateFromMacroData(macroData);

  if (!exchangeRate || !isUsStock(report, content)) {
    return content;
  }

  let converted = false;
  const priceRowRegex =
    /(\|\s*\*\*(?:현재가|권장 매수가|목표 매수가|하락 시 방어선\/저항선|방어선)\*\*\s*\|\s*\*\*)\$([0-9,]+(?:\.\d+)?)(?:\s*\(약\s*[^)]*원\))?(\*\*)/g;

  const nextContent = content.replace(priceRowRegex, (match, prefix, priceText, suffix) => {
    converted = true;
    return `${prefix}${formatUsdWithKrwApprox(priceText, exchangeRate)}${suffix}`;
  });

  if (!converted || /환산 기준\s*:/.test(nextContent)) {
    return nextContent;
  }

  return nextContent.replace(
    /((?:\|.*\|\n?)+)/,
    `$1\n환산 기준: 1달러 = ${exchangeRate.toLocaleString('ko-KR', {
      maximumFractionDigits: 2,
    })}원\n`,
  );
}
