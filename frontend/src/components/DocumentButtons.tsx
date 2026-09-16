import { useState } from "react";
import { api } from "../services/api";
export function DocumentButtons({
  id,
  view = true,
}: {
  id: string;
  view?: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function open(download: boolean) {
    const tab = window.open("about:blank", "_blank");
    if (tab) tab.opener = null;
    setBusy(true);
    setError("");
    try {
      const result = await api.document(id, download);
      if (tab) tab.location.href = result.url;
      else throw new Error("Allow pop-ups to open the PDF, then try again.");
    } catch (e) {
      tab?.close();
      setError(e instanceof Error ? e.message : "PDF is not available.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="actions">
        {view && (
          <button disabled={busy} onClick={() => open(false)}>
            View PDF
          </button>
        )}
        <button disabled={busy} onClick={() => open(true)}>
          Download PDF
        </button>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </div>
  );
}
