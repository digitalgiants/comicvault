import type { LookupResult } from "./types";

export async function lookupUpc(
  upc12: string,
  ean5: string | null,
): Promise<LookupResult | null> {
  const query = ean5 ? `?ean5=${encodeURIComponent(ean5)}` : "";
  const response = await fetch(`/lookup/${encodeURIComponent(upc12)}${query}`);

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Lookup failed with status ${response.status}`);
  }
  return response.json();
}
