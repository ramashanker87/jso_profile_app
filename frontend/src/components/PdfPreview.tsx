import { useEffect, useState } from "react";
import { api } from "../services/api";

export function PdfPreview({ id, name }: { id: string; name: string }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    let refresh: ReturnType<typeof setTimeout> | undefined;
    setUrl("");
    setError("");
    api
      .document(id, false)
      .then((link) => {
        if (!active) return;
        setUrl(link.url);
        // Renew the private link before it expires while this profile stays open.
        refresh = setTimeout(
          () => setRevision((value) => value + 1),
          Math.max(10, link.expiresIn - 30) * 1000,
        );
      })
      .catch((cause) => {
        if (active)
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to load the PDF preview.",
          );
      });
    return () => {
      active = false;
      clearTimeout(refresh);
    };
  }, [id, revision]);
  return (
    <div className="pdf-preview">
      {error ? (
        <p role="alert" className="error">
          {error}
        </p>
      ) : !url ? (
        <p role="status">Loading PDF preview…</p>
      ) : (
        <iframe
          src={url}
          title={`PDF preview for ${name}`}
          className="pdf-frame"
          onError={() =>
            setError(
              "Unable to display this PDF. Reload the preview or use View PDF to open it separately.",
            )
          }
        />
      )}
      <div className="preview-help">
        <p className="muted small">
          If your browser cannot display the preview, use View PDF or Download
          PDF.
        </p>
        <button onClick={() => setRevision((value) => value + 1)}>
          Reload preview
        </button>
      </div>
    </div>
  );
}
