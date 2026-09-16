import { Link } from "react-router-dom";
import type { Profile } from "../types/profile";
import { DocumentButtons } from "./DocumentButtons";
export function formatDate(value: string | null, time = false) {
  return value
    ? Number.isNaN(Date.parse(value))
      ? value
      : new Date(value).toLocaleString("en-GB", {
          dateStyle: "medium",
          ...(time ? { timeStyle: "short" as const } : {}),
        })
    : "Not yet";
}
export function ProfileCard({
  profile,
  members = false,
}: {
  profile: Profile;
  members?: boolean;
}) {
  const path =
    (members ? "/members/" : "/profiles/") +
    encodeURIComponent(profile.profileId);
  return (
    <article className="profile-card">
      {members && (
        <div className="member-avatar member-card-avatar">
          {profile.photoUrl && (
            <img
              src={profile.photoUrl}
              alt={profile.name}
              onError={(event) => {
                event.currentTarget.hidden = true;
              }}
            />
          )}
          <span aria-hidden="true">
            {profile.name
              .split(" ")
              .map((part) => part[0])
              .slice(0, 2)
              .join("")}
          </span>
        </div>
      )}
      <div className="card-top">
        <h2>
          <Link to={path}>{profile.name}</Link>
        </h2>
        {!members && <span className="theme">{profile.theme}</span>}
      </div>
      {profile.member && (
        <div className="membership-badge">
          <span>Membership ID</span>
          <strong>
            {(members
              ? profile.member.sourceUniqueId
              : profile.member.membershipId) || "Not assigned"}
          </strong>
          <span className="member-status">{profile.member.status}</span>
        </div>
      )}
      <p className="muted">{profile.email}</p>
      {members && profile.member?.phone && (
        <p className="member-contact">
          <span>Phone: </span>
          {/^[+()\d\s.-]+$/.test(profile.member.phone) ? (
            <a href={"tel:" + profile.member.phone.replace(/[^+\d]/g, "")}>
              {profile.member.phone}
            </a>
          ) : (
            profile.member.phone
          )}
        </p>
      )}
      {profile.member && (
        <p className="muted small">
          {[profile.member.city, profile.member.country]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}
      {members && (
        <dl className="member-affiliation">
          {[
            ["Chapter", profile.member?.chapter],
            ["Country", profile.member?.country],
            ["Region", profile.member?.region],
          ].map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value || "Not assigned"}</dd>
            </div>
          ))}
        </dl>
      )}
      {(profile.supportRaw || !members) && (
        <p>{profile.supportRaw || "No support preference supplied."}</p>
      )}
      <p className="muted small">
        Submitted:{" "}
        {members
          ? profile.member?.submittedOn || "Not provided"
          : formatDate(profile.submissionDate)}
      </p>
      {profile.syncStatus !== "SUCCESS" && (
        <p className="notice document-warning">{profile.syncError}</p>
      )}
      <div className="actions">
        <Link className="button primary" to={path}>
          {members ? "View Member" : "View Profile"}
        </Link>
        {profile.pdf && <DocumentButtons id={profile.profileId} view={false} />}
      </div>
    </article>
  );
}
