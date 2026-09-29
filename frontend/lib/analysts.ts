export const ANALYSTS = [
  { id: "price", name: "Technical Analyst", reads: "Price charts", icon: "📈", task: "reading two years of price action" },
  { id: "financials", name: "Fundamental Analyst", reads: "Financial statements", icon: "💰", task: "working through the latest 10-Q" },
  { id: "analysts", name: "Sell-Side Tracker", reads: "Analyst ratings", icon: "🎯", task: "tallying Wall Street ratings" },
  { id: "earnings", name: "Earnings Analyst", reads: "Earnings & estimates", icon: "📊", task: "comparing results to expectations" },
  { id: "insiders", name: "Insider Activity Analyst", reads: "Insider trades", icon: "🕵️", task: "parsing Form 4 insider filings" },
  { id: "congress", name: "Congressional Trading Analyst", reads: "Congress trades", icon: "🏛️", task: "checking STOCK Act disclosures" },
  { id: "news", name: "News & Sentiment Analyst", reads: "News", icon: "📰", task: "scanning three weeks of headlines" },
  { id: "filings", name: "SEC Filings Analyst", reads: "SEC filings", icon: "📑", task: "reading risk factors and 8-Ks" },
  { id: "institutions", name: "Institutional Ownership Analyst", reads: "Institutional holdings", icon: "🏦", task: "looking at big-money positioning" },
  { id: "options", name: "Options Market Analyst", reads: "Options market", icon: "⚡", task: "measuring implied volatility and skew" },
  { id: "economy", name: "Macro Economist", reads: "Economy", icon: "🌐", task: "reviewing rates, inflation and jobs" },
  { id: "related", name: "Cross-Market Analyst", reads: "Related markets", icon: "🔗", task: "comparing against sector and indices" },
] as const;

export const ANALYST_BY_ID: Record<string, (typeof ANALYSTS)[number]> = Object.fromEntries(ANALYSTS.map((a) => [a.id, a]));
