import { useState } from "react";
import type { Profile } from "../types/profile";
import { memberApi } from "../services/api";
const fields = [
  ["Full Name", "name"],
  ["Phone", "phone"],
  ["Chapter", "chapter"],
  ["Country", "country"],
  ["Region", "region"],
  ["City/Place", "city"],
  ["Address", "address"],
  ["Educational Background", "education"],
  ["Professional Experience", "experience"],
  ["Areas of Interest", "interests"],
  ["Skills/Expertise", "skills"],
  ["Motivation", "motivation"],
  ["Support Type", "supportRaw"],
  ["Comments", "comments"],
];
export function MemberEditor({
  profile,
  onSave,
}: {
  profile: Profile;
  onSave: (profile: Profile) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  if (!editing)
    return (
      <div className="member-edit">
        <button
          onClick={() => {
            setValues(
              Object.fromEntries(
                fields.map(([label, key]) => [
                  label,
                  key === "name"
                    ? profile.name
                    : key === "supportRaw"
                      ? profile.supportRaw
                      : profile.member?.[key] || "",
                ]),
              ),
            );
            setError("");
            setSaved(false);
            setEditing(true);
          }}
        >
          Edit my information
        </button>
        {saved && <p role="status">Your information has been saved.</p>}
      </div>
    );
  return (
    <form
      className="member-section member-edit"
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");
        try {
          onSave(await memberApi.update(profile.email, values));
          setEditing(false);
          setSaved(true);
        } catch (e) {
          setError(
            e instanceof Error ? e.message : "Unable to save your information.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <h2>Edit my information</h2>
      <p>Your updates will be kept when members are synced again.</p>
      <details>
        <summary>Region definitions</summary>
        <p>
          North America, South America, Europe, Africa and Oceania cover their
          respective countries and territories. Oceania includes Australia, New
          Zealand and Fiji.
        </p>
        <p>
          Asia excludes India and the Middle East countries. Middle East
          includes Iraq, Iran, Saudi Arabia, Kuwait, Oman, Bahrain, Lebanon,
          Yemen, Syria, Jordan, Qatar and UAE.
        </p>
        <p>
          Leave the region unassigned if your country is not covered by these
          definitions.
        </p>
      </details>
      <fieldset disabled={busy}>
        {fields.map(([label]) => (
          <label key={label}>
            {label}
            {label === "Region" ? (
              <select
                value={values[label] || ""}
                onChange={(event) =>
                  setValues({ ...values, [label]: event.target.value })
                }
              >
                <option value="">Not assigned</option>
                {[
                  "North America",
                  "South America",
                  "Europe",
                  "Africa",
                  "Asia",
                  "Middle East",
                  "Oceania",
                ].map((region) => (
                  <option key={region}>{region}</option>
                ))}
              </select>
            ) : (
              <textarea
                required={label === "Full Name"}
                maxLength={4000}
                value={values[label] || ""}
                onChange={(event) =>
                  setValues({ ...values, [label]: event.target.value })
                }
              />
            )}
          </label>
        ))}
        <button type="submit">{busy ? "Saving…" : "Save changes"}</button>{" "}
        <button type="button" onClick={() => setEditing(false)}>
          Cancel
        </button>
      </fieldset>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
