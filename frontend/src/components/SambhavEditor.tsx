import { useEffect, useState } from "react";
import type {
  SambhavDomain,
  SambhavMember,
  SambhavStatus,
} from "../types/sambhav";
import { memberApi } from "../services/api";
import { sambhavApi } from "../services/sambhavApi";
const statuses: SambhavStatus[] = ["Not started", "In progress", "Completed"];
export function SambhavEditor({
  domain,
  onSaved,
  onReload,
}: {
  domain: SambhavDomain;
  onSaved: (domain: SambhavDomain) => void;
  onReload: () => void;
}) {
  const [editing, setEditing] = useState(false),
    [draft, setDraft] = useState(domain);
  const [members, setMembers] = useState<SambhavMember[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!editing) return;
    let active = true;
    setLoading(true);
    void (async () => {
      try {
        const values: SambhavMember[] = [];
        for (let page = 1; ; page++) {
          const result = await memberApi.list({ page, pageSize: 100 });
          values.push(
            ...result.items.map((item) => ({
              name: item.name,
              email: item.email,
            })),
          );
          if (page * result.pageSize >= result.total) break;
          if (!result.items.length)
            throw new Error("Unable to load all members.");
        }
        if (active) setMembers(values);
      } catch {
        if (active)
          setError(
            "Unable to load the member directory. Close and reopen the editor to retry.",
          );
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [editing]);
  if (!editing)
    return (
      <div className="sambhav-edit-actions">
        <button
          onClick={() => {
            setDraft(structuredClone(domain));
            setError("");
            setNotice("");
            setEditing(true);
          }}
        >
          Edit domain and ideas
        </button>
        {notice && <p role="status">{notice}</p>}
      </div>
    );
  const updateIdea = (index: number, patch: object) =>
    setDraft((value) => ({
      ...value,
      ideas: value.ideas.map((idea, i) =>
        i === index ? { ...idea, ...patch } : idea,
      ) as SambhavDomain["ideas"],
    }));
  return (
    <form
      className="member-section sambhav-editor"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
          onSaved(await sambhavApi.save(draft));
          setEditing(false);
          setNotice("Domain and idea information saved.");
        } catch (e) {
          setError(
            e instanceof Error
              ? e.message
              : "Unable to save. Please try again.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>Edit {domain.title}</h2>
      <p>
        Changes to the domain heading and other information are shared with
        approved JSO users.
      </p>
      {loading && <p role="status">Loading member choices…</p>}
      <fieldset disabled={busy || loading}>
        <label>
          Domain heading
          <input
            required
            maxLength={200}
            value={draft.title}
            onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          />
        </label>
        <label>
          Domain description
          <textarea
            maxLength={5000}
            value={draft.description || ""}
            onChange={(e) =>
              setDraft({ ...draft, description: e.target.value })
            }
          />
        </label>
        <label>
          Domain status
          <select
            value={draft.status}
            onChange={(e) =>
              setDraft({ ...draft, status: e.target.value as SambhavStatus })
            }
          >
            {statuses.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        {draft.ideas.map((idea, index) => (
          <fieldset key={idea.id}>
            <legend>Idea slot {index + 1}</legend>
            {(
              [
                ["title", "Idea title"],
                ["summary", "Short summary"],
                ["description", "Detailed description"],
                ["vision", "Vision"],
              ] as const
            ).map(([field, label]) => (
              <label key={field}>
                {label}
                <textarea
                  required={field === "title"}
                  maxLength={field === "title" ? 200 : 5000}
                  value={idea[field]}
                  onChange={(e) =>
                    updateIdea(index, { [field]: e.target.value })
                  }
                />
              </label>
            ))}
            <label>
              Idea status
              <select
                value={idea.status}
                onChange={(e) => updateIdea(index, { status: e.target.value })}
              >
                {statuses.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </label>
            {(["lead", "coLead"] as const).map((role) => (
              <label key={role}>
                {role === "lead" ? "Lead member" : "Co-lead member"}
                <select
                  value={idea[role]?.email || ""}
                  onChange={(e) =>
                    updateIdea(index, {
                      [role]:
                        members.find((m) => m.email === e.target.value) || null,
                    })
                  }
                >
                  <option value="">Not assigned</option>
                  {idea[role] &&
                    !members.some((m) => m.email === idea[role]?.email) && (
                      <option value={idea[role]?.email}>
                        {idea[role]?.name} (not active)
                      </option>
                    )}
                  {members.map((m) => (
                    <option key={m.email} value={m.email}>
                      {m.name} — {m.email}
                    </option>
                  ))}
                </select>
              </label>
            ))}
            <label>
              Interested members
              <select
                multiple
                size={5}
                value={idea.interestedMembers.map((m) => m.email)}
                onChange={(e) =>
                  updateIdea(index, {
                    interestedMembers: Array.from(e.target.selectedOptions).map(
                      (o) => members.find((m) => m.email === o.value)!,
                    ),
                  })
                }
              >
                {members.map((m) => (
                  <option key={m.email} value={m.email}>
                    {m.name} — {m.email}
                  </option>
                ))}
              </select>
            </label>
            <p className="muted small">
              Use Ctrl/Cmd to select multiple members, or use your phone’s
              selection controls.
            </p>
          </fieldset>
        ))}
        <button type="submit" className="primary">
          {busy ? "Saving…" : "Save domain and ideas"}
        </button>{" "}
        <button type="button" onClick={() => setEditing(false)}>
          Cancel
        </button>
      </fieldset>
      {error && (
        <div role="alert">
          <p>{error}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Discard unsaved edits and reload the latest domain?",
                )
              ) {
                setEditing(false);
                onReload();
              }
            }}
          >
            Reload latest domain
          </button>
        </div>
      )}
    </form>
  );
}
