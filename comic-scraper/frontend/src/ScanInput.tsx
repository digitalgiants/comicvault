import { useRef, useState } from "react";

// Hardware scanners send no terminator key, so a brief pause + valid digit count
// (12 or 17) is what distinguishes a finished scan from in-progress manual typing.
const SETTLE_DELAY_MS = 150;

interface Props {
  onSubmit: (upc12: string, ean5: string | null) => void;
  disabled?: boolean;
}

function parseCode(raw: string): { upc12: string; ean5: string | null } | null {
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 12) return { upc12: digits, ean5: null };
  if (digits.length === 17) return { upc12: digits.slice(0, 12), ean5: digits.slice(12) };
  return null;
}

export function ScanInput({ onSubmit, disabled }: Props) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<number | undefined>(undefined);

  function submitIfValid(raw: string) {
    const parsed = parseCode(raw);
    if (!parsed) return;
    onSubmit(parsed.upc12, parsed.ean5);
    setValue("");
    inputRef.current?.focus();
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const next = e.target.value;
    setValue(next);
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => submitIfValid(next), SETTLE_DELAY_MS);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    window.clearTimeout(timerRef.current);
    submitIfValid(value);
  }

  return (
    <form className="scan-input" onSubmit={handleSubmit}>
      <input
        ref={inputRef}
        value={value}
        onChange={handleChange}
        placeholder="Scan barcode, or type 12-digit UPC (or 17-digit UPC+EAN5)"
        inputMode="numeric"
        pattern="\d*"
        disabled={disabled}
        autoFocus
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        Look Up
      </button>
    </form>
  );
}
