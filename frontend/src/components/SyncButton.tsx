import { useEffect, useState } from "react";
import { api, memberApi } from "../services/api";
import type { SyncJob } from "../types/profile";
import { formatDate } from "./ProfileCard";
export function SyncButton({
  onComplete,
  members = false,
}: {
  onComplete(): void;
  members?: boolean;
}) {
  const client = members ? memberApi : api;
  const [job, setJob] = useState<SyncJob | null>(null),
    [error, setError] = useState(""),
    [starting, setStarting] = useState(false);
  const running = job?.status === "QUEUED" || job?.status === "RUNNING";
  useEffect(() => {
    let active = true;
    client
      .syncStatus()
      .then((value) => {
        if (active) setJob(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [client]);
  useEffect(() => {
    if (!running || !job) return;
    let active = true;
    const timer = setTimeout(() => {
      client
        .syncStatus(job.jobId)
        .then((value) => {
          if (!active) return;
          setJob(value);
          if (value?.status === "COMPLETED" || value?.status === "FAILED")
            onComplete();
        })
        .catch(() => {
          if (active) {
            setError("Unable to check sync status. Refresh to reconnect.");
            setJob(null);
          }
        });
    }, 2000);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [job, running, onComplete, client]);
  async function start() {
    setStarting(true);
    setError("");
    try {
      setJob(await client.sync());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Synchronization failed.");
      const latest = await client.syncStatus().catch(() => null);
      setJob(latest);
    } finally {
      setStarting(false);
    }
  }
  return (
    <section className="sync-panel">
      <button
        className="primary"
        disabled={!!running || starting}
        onClick={start}
      >
        {running || starting ? "Syncing…" : "Sync Now"}
      </button>
      {job && (
        <p role="status">
          {job.status === "COMPLETED"
            ? `Sync completed · ${job.processed} processed · ${job.created} new · ${job.updated} updated · ${job.failed} failed${members ? ` · ${job.deleted || 0} removed` : ""}`
            : job.status === "FAILED"
              ? job.error || "Synchronization failed."
              : `${job.processed} processed so far`}
          {job.status === "COMPLETED" && (
            <span className="muted">
              {" "}
              · Last synced: {formatDate(job.updatedAt, true)}
            </span>
          )}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
