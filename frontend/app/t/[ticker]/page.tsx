import Council from "@/components/Council";

export default async function TickerPage({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params;
  return <Council ticker={decodeURIComponent(ticker).toUpperCase()} />;
}
