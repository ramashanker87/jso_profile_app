import { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { ErrorState, LoadingState } from "../components/States";
import { mockMode } from "../auth/client";
import {
  jobsApi,
  validateJobFiles,
  type JobOpening,
  type JobFile,
  type JobAttachmentCategory,
} from "../services/jobsApi";

export function Jobs() {
  const [jobs, setJobs] = useState<JobOpening[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<JobFile[]>([]);
  const [inputKey, setInputKey] = useState(0);
  const [pendingJob, setPendingJob] = useState<JobOpening | null>(null);
  const [uploadsEnabled, setUploadsEnabled] = useState(true);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadError("");
    jobsApi
      .list()
      .then((data) => {
        if (active) {
          setJobs(data.items);
          setUploadsEnabled(data.uploadsEnabled !== false);
        }
      })
      .catch((e) => {
        if (active)
          setLoadError(e instanceof Error ? e.message : "Unable to load jobs.");
      });
    return () => {
      active = false;
    };
  }, [revision]);

  function updateJob(job: JobOpening) {
    setJobs((items) => [
      job,
      ...(items || []).filter((item) => item.id !== job.id),
    ]);
  }

  function resetForm() {
    setUrl("");
    setTitle("");
    setDescription("");
    setFiles([]);
    setPendingJob(null);
    setInputKey((key) => key + 1);
  }

  function selectFiles(
    category: JobAttachmentCategory,
    selected: FileList | null,
  ) {
    setFiles((items) => [
      ...items.filter((item) => item.category !== category),
      ...Array.from(selected || []).map((file) => ({ file, category })),
    ]);
    setError("");
  }

  async function download(job: JobOpening, documentId: string) {
    setDownloading(documentId);
    setError("");
    try {
      await jobsApi.download(job.id, documentId);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to download attachment.",
      );
    } finally {
      setDownloading(null);
    }
  }

  async function add(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    const link = url.trim();
    try {
      const parsed = new URL(link);
      if (
        !["http:", "https:"].includes(parsed.protocol) ||
        parsed.username ||
        parsed.password ||
        /[\s\\]/.test(link)
      )
        throw new Error();
    } catch {
      setError(
        "Enter a valid http:// or https:// job-opening link without login credentials.",
      );
      return;
    }
    try {
      validateJobFiles(files);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Choose valid PDF files.");
      return;
    }
    setSaving(true);
    let saved = pendingJob;
    let uploaded = 0;
    try {
      if (!saved) {
        saved = await jobsApi.create(link, title.trim(), description.trim());
        setPendingJob(saved);
        updateJob(saved);
      }
      for (const { file, category } of files) {
        setNotice(`Uploading ${uploaded + 1} of ${files.length}: ${file.name}`);
        saved = await jobsApi.upload(saved.id, category, file);
        setPendingJob(saved);
        updateJob(saved);
        uploaded++;
      }
      resetForm();
      setNotice(
        "Job opening added" + (files.length ? " with attachments." : "."),
      );
    } catch (e) {
      setNotice("");
      if (saved) {
        setFiles(files.slice(uploaded));
        setError(
          `Job saved. ${e instanceof Error ? e.message : "Upload failed."} Retry the remaining attachments or keep the job without them.`,
        );
      } else {
        setError(
          e instanceof Error ? e.message : "Unable to add the job opening.",
        );
      }
    } finally {
      setSaving(false);
    }
  }

  async function remove(job: JobOpening) {
    setError("");
    setNotice("");
    setDeleting(job.id);
    try {
      await jobsApi.remove(job.id);
      setJobs((items) => items?.filter((item) => item.id !== job.id) || []);
      setConfirmId(null);
      setNotice("Closed job removed.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to delete the job opening.",
      );
    } finally {
      setDeleting(null);
    }
  }

  return (
    <>
      <Header />
      <main>
        <div className="page-title">
          <div>
            <span className="eyebrow">YOUR COMMUNITY</span>
            <h1>Jobs</h1>
            <p className="muted">
              Share job openings, a short description, and candidate or job
              profiles with the community.
            </p>
          </div>
          <section className="submission-count" aria-label="Job openings count">
            <span>Job openings</span>
            <strong>{jobs ? jobs.length.toLocaleString() : "…"}</strong>
            <small>Shared by the community</small>
          </section>
        </div>
        {loadError ? (
          <>
            <ErrorState message={loadError} />
            <button onClick={() => setRevision((n) => n + 1)}>Retry</button>
          </>
        ) : jobs === null ? (
          <LoadingState label="jobs" />
        ) : (
          <>
            <form className="profile-card job-form" onSubmit={add}>
              <h2>Share a job opening</h2>
              <label htmlFor="job-url">Job-opening link</label>
              <input
                id="job-url"
                type="url"
                required
                maxLength={4000}
                placeholder="https://company.com/careers/job"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={saving || pendingJob !== null}
              />
              <label htmlFor="job-title">Job title / company (optional)</label>
              <input
                id="job-title"
                maxLength={200}
                placeholder="e.g. Software Engineer at Example"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={saving || pendingJob !== null}
              />
              <label htmlFor="job-description">
                Short description (optional)
              </label>
              <textarea
                id="job-description"
                rows={3}
                maxLength={2000}
                placeholder="Add a brief summary, requirements, or candidate details"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={saving || pendingJob !== null}
              />
              <p className="muted small">
                {description.length}/2,000 characters
              </p>
              <fieldset
                className="job-files"
                disabled={saving || pendingJob !== null || !uploadsEnabled}
              >
                <legend>Attachments (optional)</legend>
                <p className="muted small" id="job-file-help">
                  PDF files, up to 20 MB each and 10 files per job. Visible to
                  all approved JSO users.
                  {mockMode &&
                    " Demo attachments are temporary and disappear on reload."}
                  {!uploadsEnabled &&
                    " File uploads are unavailable in the local API."}
                </p>
                <label htmlFor="job-candidate-files">Candidate profiles</label>
                <input
                  key={`candidate-${inputKey}`}
                  id="job-candidate-files"
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  aria-describedby="job-file-help"
                  onChange={(e) =>
                    selectFiles("candidate-profile", e.target.files)
                  }
                />
                <label htmlFor="job-profile-files">Job profiles</label>
                <input
                  key={`job-${inputKey}`}
                  id="job-profile-files"
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  aria-describedby="job-file-help"
                  onChange={(e) => selectFiles("job-profile", e.target.files)}
                />
              </fieldset>
              {files.length > 0 && (
                <ul className="job-selected-files" aria-label="Files to upload">
                  {files.map(({ file, category }, index) => (
                    <li key={`${category}-${index}`}>
                      {file.name} (
                      {category === "candidate-profile"
                        ? "Candidate profile"
                        : "Job profile"}
                      )
                      <button
                        type="button"
                        disabled={saving}
                        aria-label={`Remove ${file.name}`}
                        onClick={() =>
                          setFiles((items) =>
                            items.filter((_, i) => i !== index),
                          )
                        }
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {pendingJob && (
                <p role="status">
                  The job is saved. {files.length} attachment(s) remaining.
                </p>
              )}
              <button
                className="primary"
                disabled={saving || deleting !== null}
              >
                {saving
                  ? "Saving…"
                  : pendingJob
                    ? "Retry attachments"
                    : "Add job"}
              </button>
              {pendingJob && (
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    resetForm();
                    setError("");
                    setNotice("Job kept with its saved attachments.");
                  }}
                >
                  Keep job without remaining attachments
                </button>
              )}
            </form>
            {error && <ErrorState message={error} />}
            {notice && <p role="status">{notice}</p>}
            {jobs.length === 0 ? (
              <section className="empty">
                <h2>No job openings yet</h2>
                <p>Paste a job-opening link above to share it.</p>
              </section>
            ) : (
              <div className="job-list">
                {jobs.map((job) => (
                  <article
                    className="profile-card job-card"
                    key={job.id}
                    aria-label={job.title}
                  >
                    <h2>
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {job.title}
                      </a>
                    </h2>
                    <p className="job-url">{job.url}</p>
                    {job.description && (
                      <p className="job-description">{job.description}</p>
                    )}
                    {!!job.attachments?.length && (
                      <section
                        className="job-attachments"
                        aria-label="Job attachments"
                      >
                        <h3>Attachments</h3>
                        <ul>
                          {job.attachments.map((attachment) => (
                            <li key={attachment.id}>
                              <span>
                                {attachment.category === "candidate-profile"
                                  ? "Candidate profile"
                                  : "Job profile"}
                              </span>
                              <button
                                disabled={downloading !== null}
                                onClick={() => download(job, attachment.id)}
                              >
                                {downloading === attachment.id
                                  ? "Preparing download…"
                                  : `Download ${attachment.fileName}`}
                              </button>
                              <small>
                                {(attachment.size / 1024 / 1024).toFixed(2)} MB
                              </small>
                            </li>
                          ))}
                        </ul>
                      </section>
                    )}
                    <p className="muted">
                      Shared {new Date(job.createdAt).toLocaleDateString()}
                    </p>
                    <div className="job-actions">
                      <a
                        className="button primary"
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View job description ↗
                      </a>
                      <button
                        disabled={
                          saving || deleting !== null || pendingJob !== null
                        }
                        onClick={() => {
                          setConfirmId(job.id);
                          setError("");
                        }}
                      >
                        Delete closed job
                      </button>
                    </div>
                    {confirmId === job.id && (
                      <div
                        className="job-delete-confirm"
                        role="group"
                        aria-label="Confirm job deletion"
                      >
                        <p>
                          Remove “{job.title}” and its attachments from the
                          community job list?
                        </p>
                        <div className="job-actions">
                          <button
                            disabled={deleting !== null}
                            onClick={() => remove(job)}
                          >
                            {deleting === job.id
                              ? "Deleting…"
                              : "Confirm delete"}
                          </button>
                          <button
                            disabled={deleting !== null}
                            onClick={() => setConfirmId(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
