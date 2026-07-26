import type { BatchResultEvent } from "./types";

export async function submitBatch(
  items: { upc12: string; ean5: string | null }[],
  onEvent: (event: BatchResultEvent) => void,
): Promise<void> {
  const response = await fetch("/lookup/batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Batch request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
      if (!dataLine) continue;
      onEvent(JSON.parse(dataLine.slice("data: ".length)) as BatchResultEvent);
    }
  }
}
