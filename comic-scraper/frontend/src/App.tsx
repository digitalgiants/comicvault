import { useCallback, useState } from "react";
import "./App.css";
import { lookupUpc } from "./api";
import { BarcodeScanner } from "./BarcodeScanner";
import { BatchPanel } from "./BatchPanel";
import { submitBatch } from "./batchApi";
import { ScanInput } from "./ScanInput";
import type { LookupAttempt, StagedItem } from "./types";

const MAX_BATCH_SIZE = 20;

export default function App() {
  const [attempts, setAttempts] = useState<LookupAttempt[]>([]);
  const [batchMode, setBatchMode] = useState(false);
  const [stagedItems, setStagedItems] = useState<StagedItem[]>([]);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);

  const runLookup = useCallback(async (upc12: string, ean5: string | null) => {
    const id = crypto.randomUUID();
    const timestamp = new Date().toISOString();
    setAttempts((prev) => [{ id, upc12, ean5, timestamp, status: "pending" }, ...prev]);

    try {
      const result = await lookupUpc(upc12, ean5);
      setAttempts((prev) =>
        prev.map((a) => {
          if (a.id !== id) return a;
          return result
            ? { ...a, status: "success" as const, result }
            : { ...a, status: "not_found" as const };
        }),
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setAttempts((prev) =>
        prev.map((a) => (a.id === id ? { ...a, status: "error" as const, message } : a)),
      );
    }
  }, []);

  const addStagedItem = useCallback((upc12: string, ean5: string | null) => {
    setStagedItems((prev) => (prev.length >= MAX_BATCH_SIZE ? prev : [...prev, { id: crypto.randomUUID(), upc12, ean5 }]));
  }, []);

  function handleDetected(upc12: string, ean5: string | null) {
    if (batchMode) {
      addStagedItem(upc12, ean5);
    } else {
      void runLookup(upc12, ean5);
    }
  }

  async function submitStagedBatch() {
    if (stagedItems.length === 0) return;
    setBatchSubmitting(true);
    setBatchError(null);

    const idsInOrder = stagedItems.map(() => crypto.randomUUID());
    const timestamp = new Date().toISOString();
    setAttempts((prev) => [
      ...stagedItems.map((item, i) => ({
        id: idsInOrder[i],
        upc12: item.upc12,
        ean5: item.ean5,
        timestamp,
        status: "pending" as const,
      })),
      ...prev,
    ]);

    const items = stagedItems.map(({ upc12, ean5 }) => ({ upc12, ean5 }));
    setStagedItems([]);

    try {
      await submitBatch(items, (event) => {
        const id = idsInOrder[event.index];
        setAttempts((prev) =>
          prev.map((a) => {
            if (a.id !== id) return a;
            if (event.status === "success" && event.result) {
              return { ...a, status: "success" as const, result: event.result };
            }
            if (event.status === "not_found") {
              return { ...a, status: "not_found" as const };
            }
            return { ...a, status: "error" as const, message: event.message ?? "Unknown error" };
          }),
        );
      });
    } catch (err) {
      setBatchError(err instanceof Error ? err.message : "Batch request failed");
    } finally {
      setBatchSubmitting(false);
    }
  }

  return (
    <div className="app">
      <h1>Comic UPC Lookup</h1>

      <label className="mode-toggle">
        <input
          type="checkbox"
          checked={batchMode}
          onChange={(e) => setBatchMode(e.target.checked)}
        />
        Batch mode
      </label>

      <BarcodeScanner onDetected={handleDetected} />

      <ScanInput onSubmit={handleDetected} />

      {batchMode && (
        <BatchPanel
          items={stagedItems}
          maxItems={MAX_BATCH_SIZE}
          submitting={batchSubmitting}
          error={batchError}
          onAddPasted={(codes) => codes.forEach(({ upc12, ean5 }) => addStagedItem(upc12, ean5))}
          onRemove={(id) => setStagedItems((prev) => prev.filter((i) => i.id !== id))}
          onEdit={(id, upc12, ean5) =>
            setStagedItems((prev) => prev.map((i) => (i.id === id ? { ...i, upc12, ean5 } : i)))
          }
          onSubmit={() => void submitStagedBatch()}
        />
      )}

      <ul className="results">
        {attempts.map((a) => (
          <li key={a.id} className={`result result-${a.status}`}>
            <div className="result-code">
              {a.upc12}
              {a.ean5 ? ` + ${a.ean5}` : ""}
            </div>
            {a.status === "pending" && <div className="result-body">Looking up…</div>}
            {a.status === "not_found" && <div className="result-body">No issue found</div>}
            {a.status === "error" && <div className="result-body">Error: {a.message}</div>}
            {a.status === "success" && (
              <div className="result-body">
                <div className="result-content">
                  {a.result.image && (
                    <img
                      className="result-thumb"
                      src={a.result.image}
                      alt={`${a.result.series_name} #${a.result.issue_number} cover`}
                    />
                  )}
                  <div className="result-details">
                    <strong>
                      {a.result.series_name} #{a.result.issue_number}
                    </strong>
                    {a.result.variant_name && <span> ({a.result.variant_name})</span>}
                    <div>
                      {[a.result.publisher_name, a.result.series_volume ? `Vol. ${a.result.series_volume}` : null]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                    <div>
                      {a.result.cover_date}
                      {a.result.store_date ? ` (on sale ${a.result.store_date})` : ""}
                    </div>
                    {a.result.writers.length > 0 && <div>Writer: {a.result.writers.join(", ")}</div>}
                    {a.result.pencillers.length > 0 && (
                      <div>Pencils: {a.result.pencillers.join(", ")}</div>
                    )}
                    {a.result.inkers.length > 0 && <div>Inks: {a.result.inkers.join(", ")}</div>}
                    {a.result.cover_artists.length > 0 && (
                      <div>Cover: {a.result.cover_artists.join(", ")}</div>
                    )}
                    <div className="badge">
                      {a.result.matched_on} · {a.result.source}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
