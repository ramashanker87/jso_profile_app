import { useEffect, useState } from "react";
import { Header } from "../components/Header";
import { ErrorState, LoadingState } from "../components/States";
import { jobsApi, type JobOpening } from "../services/jobsApi";

export function Jobs() {
  const [jobs, setJobs] = useState<JobOpening[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmId, setConfirmId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadError("");
    jobsApi
      .list()
      .then((data) => {
        if (active) setJobs(data.items);
      })
      .catch((e) => {
        if (active)
          setLoadError(e instanceof Error ? e.message : "Unable to load jobs.");
      });
    return () => {
      active = false;
    };
  }, [revision]);

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
    setSaving(true);
    try {
      const job = await jobsApi.create(link, title.trim());
      setJobs((items) => [
        job,
        ...(items || []).filter((item) => item.id !== job.id),
      ]);
      setUrl("");
      setTitle("");
      setNotice("Job opening added.");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to add the job opening.",
      );
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
              Share job openings with the community. Open a link to read the
              full job description.
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
                disabled={saving}
              />
              <label htmlFor="job-title">Job title / company (optional)</label>
              <input
                id="job-title"
                maxLength={200}
                placeholder="e.g. Software Engineer at Example"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={saving}
              />
              <button
                className="primary"
                disabled={saving || deleting !== null}
              >
                {saving ? "Adding…" : "Add job"}
              </button>
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
                        disabled={saving || deleting !== null}
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
                        <p>Remove “{job.title}” from the community job list?</p>
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
