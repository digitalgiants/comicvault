export interface CreditInfo {
  creator: string;
  roles: string[];
}

export interface LookupResult {
  series_name: string;
  series_volume: number | null;
  publisher_name: string | null;
  issue_number: string;
  cover_date: string;
  store_date: string | null;
  variant_name: string | null;
  cover_artists: string[];
  writers: string[];
  pencillers: string[];
  inkers: string[];
  credits: CreditInfo[];
  matched_on: "base_upc" | "variant_upc";
  source: "cache" | "metron";
  metron_id: number | null;
  cv_id: number | null;
  gcd_id: number | null;
  image: string | null;
  cover_hash: string | null;
}

interface LookupAttemptBase {
  id: string;
  upc12: string;
  ean5: string | null;
  timestamp: string;
}

export type LookupAttempt =
  | (LookupAttemptBase & { status: "pending" })
  | (LookupAttemptBase & { status: "success"; result: LookupResult })
  | (LookupAttemptBase & { status: "not_found" })
  | (LookupAttemptBase & { status: "error"; message: string });

export interface StagedItem {
  id: string;
  upc12: string;
  ean5: string | null;
}

export interface BatchResultEvent {
  index: number;
  upc12: string;
  ean5: string | null;
  status: "success" | "not_found" | "error";
  result?: LookupResult;
  message?: string;
}
