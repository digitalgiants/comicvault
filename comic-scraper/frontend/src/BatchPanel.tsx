import { useState } from "react";
import type { StagedItem } from "./types";

interface Props {
  items: StagedItem[];
  maxItems: number;
  submitting: boolean;
  error: string | null;
  onAddPasted: (codes: { upc12: string; ean5: string | null }[]) => void;
  onRemove: (id: string) => void;
  onEdit: (id: string, upc12: string, ean5: string | null) => void;
  onSubmit: () => void;
}

function parseLines(text: string): { upc12: string; ean5: string | null }[] {
  return text
    .split("\n")
    .map((line) => line.replace(/\D/g, ""))
    .filter((digits) => digits.length === 12 || digits.length === 17)
    .map((digits) =>
      digits.length === 17
        ? { upc12: digits.slice(0, 12), ean5: digits.slice(12) }
        : { upc12: digits, ean5: null },
    );
}

export function BatchPanel({
  items,
  maxItems,
  submitting,
  error,
  onAddPasted,
  onRemove,
  onEdit,
  onSubmit,
}: Props) {
  const [pasteText, setPasteText] = useState("");
  const atLimit = items.length >= maxItems;

  function handlePasteSubmit(e: React.FormEvent) {
    e.preventDefault();
    onAddPasted(parseLines(pasteText));
    setPasteText("");
  }

  return (
    <div className="batch-panel">
      <p className="batch-notice">
        Batches are limited to {maxItems} items — Metron currently only supports 20 requests/minute,
        so large or uncached batches take a bit to fully process.
      </p>

      <form className="batch-paste" onSubmit={handlePasteSubmit}>
        <textarea
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          placeholder="Paste UPCs, one per line (12 or 17 digits each)"
          rows={4}
        />
        <button type="submit" disabled={!pasteText.trim() || atLimit}>
          Add to batch
        </button>
      </form>

      {atLimit && (
        <p className="batch-notice batch-notice-warning">
          Batch is full ({maxItems} items) — submit or remove some before adding more.
        </p>
      )}

      {items.length > 0 && (
        <ul className="staged-list">
          {items.map((item) => (
            <li key={item.id} className="staged-item">
              <input
                value={item.upc12}
                onChange={(e) => onEdit(item.id, e.target.value.replace(/\D/g, ""), item.ean5)}
                inputMode="numeric"
                pattern="\d*"
                className="staged-upc"
                aria-label="UPC"
              />
              <input
                value={item.ean5 ?? ""}
                onChange={(e) => onEdit(item.id, item.upc12, e.target.value.replace(/\D/g, "") || null)}
                placeholder="EAN-5"
                inputMode="numeric"
                pattern="\d*"
                className="staged-ean5"
                aria-label="EAN-5"
              />
              <button
                type="button"
                onClick={() => onRemove(item.id)}
                aria-label="Remove from batch"
                className="staged-remove"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="error">{error}</p>}

      <button
        type="button"
        className="batch-submit"
        onClick={onSubmit}
        disabled={items.length === 0 || submitting}
      >
        {submitting ? "Submitting…" : `Look up ${items.length} item${items.length === 1 ? "" : "s"}`}
      </button>
    </div>
  );
}
