export const ANALYSTS = [
  { id: "price", name: "Technical Analyst", reads: "Price charts", icon: "📈", task: "reading two years of price action", pulling: "Pulling 2 years of daily prices" },
  { id: "financials", name: "Fundamental Analyst", reads: "Financial statements", icon: "💰", task: "working through the latest 10-Q", pulling: "Pulling 10-Q and 10-K financials from SEC EDGAR" },
  { id: "analysts", name: "Sell-Side Tracker", reads: "Analyst ratings", icon: "🎯", task: "tallying Wall Street ratings", pulling: "Pulling Wall Street ratings and price targets" },
  { id: "earnings", name: "Earnings Analyst", reads: "Earnings & estimates", icon: "📊", task: "comparing results to expectations", pulling: "Pulling reported earnings and estimates" },
  { id: "insiders", name: "Insider Activity Analyst", reads: "Insider trades", icon: "🕵️", task: "parsing Form 4 insider filings", pulling: "Pulling Form 4 insider filings from SEC EDGAR" },
  { id: "congress", name: "Congressional Trading Analyst", reads: "Congress trades", icon: "🏛️", task: "checking STOCK Act disclosures", comingSoon: true, pulling: "Checking STOCK Act disclosures" },
  { id: "news", name: "News & Sentiment Analyst", reads: "News", icon: "📰", task: "scanning three weeks of headlines", pulling: "Pulling the last 3 weeks of news" },
  { id: "filings", name: "SEC Filings Analyst", reads: "SEC filings", icon: "📑", task: "reading risk factors and 8-Ks", pulling: "Pulling 10-Q, 10-K and 8-K filings from SEC EDGAR" },
  { id: "institutions", name: "Institutional Ownership Analyst", reads: "Institutional holdings", icon: "🏦", task: "looking at big-money positioning", comingSoon: true, pulling: "Checking 13F holdings" },
  { id: "options", name: "Options Market Analyst", reads: "Options market", icon: "⚡", task: "measuring implied volatility and skew", pulling: "Pulling the options chain from Cboe" },
  { id: "economy", name: "Macro Economist", reads: "Economy", icon: "🌐", task: "reviewing rates, inflation and jobs", pulling: "Pulling rates, inflation and jobs data from FRED" },
  { id: "related", name: "Cross-Market Analyst", reads: "Related markets", icon: "🔗", task: "comparing against sector and indices", pulling: "Pulling sector, peer and index prices" },
] as const;

export const ANALYST_BY_ID: Record<string, (typeof ANALYSTS)[number]> = Object.fromEntries(ANALYSTS.map((a) => [a.id, a]));

// Analysts whose data source isn't connected yet. If a run does return data for one, it shows normally.
export function isComingSoon(id: string): boolean {
  const a = ANALYST_BY_ID[id];
  return !!a && "comingSoon" in a && a.comingSoon === true;
}

export const NO_DATA_TEXT = "No data available for this stock right now.";
