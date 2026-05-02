export type Severity = "low" | "med" | "high";

export type Company = {
  ticker: string;
  name: string;
  market: "KOSPI" | "KOSDAQ";
  sector: string | null;
  price: number | null;
  change: number | null;
};

export type Disclosure = {
  rcept_no: string;
  ticker: string;
  title: string;
  date: string;
  summary: string | null;
  severity: Severity | null;
  reason?: string | null;
  raw_url?: string | null;
};

export type Quote = {
  ticker: string;
  price: number | null;
  change_percent: number | null;
  series: { d: string; c: number }[];
  cached: boolean;
  age_sec: number;
  stale?: boolean;
};

export type DDMemo = {
  memo_id: string;
  version_id: string;
  version: number;
  bull: string;
  bear: string;
  thesis: string;
  sources?: {
    disclosures?: { rcept_no: string; dart_url: string }[];
    news?: { url: string }[];
  };
  generated_by?: string | null;
  created_at?: string | null;
};
