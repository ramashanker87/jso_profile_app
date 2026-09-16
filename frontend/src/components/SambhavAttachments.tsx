import { useState } from "react";
import { sambhavApi } from "../services/sambhavApi";
import type {
  SambhavDocument,
  SambhavDomain,
  SambhavIdea,
} from "../types/sambhav";
export function SambhavDocuments({
  documents,
  domain,
  idea,
}: {
  documents: SambhavDocument[];
  domain: string;
  idea: string;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState("");
  return (
    <>
      {documents.length ? (
        <ul>
          {documents.map((doc) => (
            <li key={doc.id}>
              <button
                type="button"
                disabled={!!busy}
                onClick={async () => {
                  setBusy(doc.id);
                  setError("");
                  try {
                    const link = await sambhavApi.document(
                      domain,
                      idea,
                      doc.id,
                    );
                    window.location.assign(link.url);
                  } catch (e) {
                    setError(
                      e instanceof Error
                        ? e.message
                        : "Unable to download document.",
                    );
                  } finally {
                    setBusy("");
                  }
                }}
              >
                {busy === doc.id ? "Preparing download…" : doc.title}
              </button>
              {doc.size && (
                <small> · {(doc.size / 1024 / 1024).toFixed(2)} MB</small>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <>No documents yet</>
      )}
      {error && <p role="alert">{error}</p>}
    </>
  );
}
export function SambhavUploader({
  domain,
  idea,
  onSaved,
}: {
  domain: SambhavDomain;
  idea: SambhavIdea;
  onSaved: (domain: SambhavDomain) => void;
}) {
  const [category, setCategory] = useState("project"),
    [files, setFiles] = useState<File[]>([]),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  const [inputKey, setInputKey] = useState(0);
  return (
    <form
      className="sambhav-uploader"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        setMessage("");
        let uploaded = 0;
        try {
          for (const file of files) {
            setMessage(
              `Uploading ${uploaded + 1} of ${files.length}: ${file.name}`,
            );
            onSaved(
              await sambhavApi.upload(domain.slug, idea.id, category, file),
            );
            uploaded++;
          }
          setMessage(
            `${uploaded} PDF attachment${uploaded === 1 ? "" : "s"} saved.`,
          );
          setFiles([]);
          setInputKey((value) => value + 1);
        } catch (e) {
          setFiles(files.slice(uploaded));
          setError(
            `${uploaded} saved. ${e instanceof Error ? e.message : "Upload failed."} Retry the remaining files.`,
          );
          setMessage("");
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3>Attach PDF files</h3>
      <p className="muted small">
        Multiple PDFs, up to 20 MB each and 30 attachments per idea. Files are
        private to approved JSO users.
      </p>
      <fieldset disabled={busy}>
        <label>
          Attachment category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="vision">Vision documents</option>
            <option value="project">Project details</option>
            <option value="member-profile">Member profiles</option>
            <option value="other">Other documents</option>
          </select>
        </label>
        <label>
          PDF files
          <input
            key={inputKey}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            onChange={(e) => {
              setFiles(Array.from(e.target.files || []));
              setError("");
            }}
          />
        </label>
        <button type="submit" disabled={!files.length}>
          {busy ? "Uploading…" : "Upload PDFs"}
        </button>
      </fieldset>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
