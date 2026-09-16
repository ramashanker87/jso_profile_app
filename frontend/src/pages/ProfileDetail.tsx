import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, memberApi } from "../services/api";
import type { Profile } from "../types/profile";
import { useAuth } from "../auth/AuthProvider";
import { MemberEditor } from "../components/MemberEditor";
import { Header } from "../components/Header";
import { PdfPreview } from "../components/PdfPreview";
import { DocumentButtons } from "../components/DocumentButtons";
import { formatDate } from "../components/ProfileCard";
import { LoadingState, ErrorState } from "../components/States";
export function ProfileDetail({ members = false }: { members?: boolean }) {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setProfile(null);
    setError("");
    (members ? memberApi : api)
      .get(id)
      .then((value) => {
        if (active) setProfile(value);
      })
      .catch((e) => {
        if (active)
          setError(e instanceof Error ? e.message : "Unable to load profile.");
      });
    return () => {
      active = false;
    };
  }, [id, members]);
  return (
    <>
      <Header />
      <main className="detail">
        <Link to={members ? "/members" : "/"}>
          ← Back to {members ? "Members" : "Idea Incubation"}
        </Link>
        {error ? (
          <ErrorState message={error} />
        ) : !profile ? (
          <LoadingState label={members ? "members" : "submissions"} />
        ) : (
          <>
            <div className="member-hero">
              <div className="member-avatar">
                {profile.photoUrl ? (
                  <img
                    src={profile.photoUrl}
                    alt={profile.name}
                    onError={(event) => {
                      event.currentTarget.hidden = true;
                    }}
                  />
                ) : null}
                <span aria-hidden="true">
                  {profile.name
                    .split(" ")
                    .map((part) => part[0])
                    .slice(0, 2)
                    .join("")}
                </span>
              </div>
              <div>
                <h1>{profile.name}</h1>
                {profile.member && (
                  <div className="membership-badge">
                    <span>Membership ID</span>
                    <strong>
                      {(members
                        ? profile.member.sourceUniqueId
                        : profile.member.membershipId) || "Not assigned"}
                    </strong>
                    <span className="member-status">
                      {profile.member.status}
                    </span>
                  </div>
                )}
              </div>
            </div>
            {!members && <span className="theme">{profile.theme}</span>}
            {!members && (
              <section className="document">
                <h2>Document</h2>
                {profile.pdf ? (
                  <>
                    <p>{profile.pdf.fileName}</p>
                    <DocumentButtons id={profile.profileId} />
                    <PdfPreview
                      key={profile.profileId}
                      id={profile.profileId}
                      name={profile.name}
                    />
                  </>
                ) : (
                  <p>No profile document available.</p>
                )}
              </section>
            )}
            {members &&
              user?.trim().toLowerCase() ===
                profile.email.trim().toLowerCase() && (
                <MemberEditor
                  key={profile.email}
                  profile={profile}
                  onSave={setProfile}
                />
              )}
            <div className="member-sections">
              {[
                {
                  title: "Contact & location",
                  fields: [
                    ["Email", profile.email],
                    ["Phone", profile.member?.phone],
                    ["Chapter", profile.member?.chapter],
                    ["Country", profile.member?.country],
                    ["Region", profile.member?.region],
                    ["City / place", profile.member?.city],
                    ["Address", profile.member?.address],
                  ],
                },
                {
                  title: "Background & expertise",
                  fields: [
                    ["Educational background", profile.member?.education],
                    ["Professional experience", profile.member?.experience],
                    ["Skills / expertise", profile.member?.skills],
                  ],
                },
                {
                  title: "Interests & contribution",
                  fields: [
                    [
                      "Areas of interest",
                      profile.member?.interests || profile.theme,
                    ],
                    ["Motivation", profile.member?.motivation],
                    ["Support type", profile.supportRaw],
                    ["Comments", profile.member?.comments],
                  ],
                },
                {
                  title: "Membership & submission history",
                  fields: [
                    [
                      "Earliest submission",
                      profile.member?.submittedOn ||
                        formatDate(profile.submissionDate, true),
                    ],
                    ["Number of submissions", profile.member?.submissionCount],
                    ["Sources", profile.member?.sources || profile.source],
                    ["Source unique ID", profile.member?.sourceUniqueId],
                    ["File upload", profile.member?.fileUpload],
                    ["Last synced", formatDate(profile.lastSyncedAt, true)],
                  ],
                },
              ]
                .filter(
                  (section) =>
                    profile.member ||
                    [
                      "Contact & location",
                      "Interests & contribution",
                      "Membership & submission history",
                    ].includes(section.title),
                )
                .map((section) => (
                  <section className="member-section" key={section.title}>
                    <h2>{section.title}</h2>
                    <dl>
                      {section.fields
                        .filter(
                          ([label]) =>
                            !members ||
                            !["File upload", "Last synced"].includes(
                              label || "",
                            ),
                        )
                        .map(([label, value]) => (
                          <div key={label}>
                            <dt>{label}</dt>
                            <dd>{value || "Not provided"}</dd>
                          </div>
                        ))}
                    </dl>
                  </section>
                ))}
            </div>
            {/^https?:\/\//i.test(profile.linkedinUrl || "") && (
              <p>
                <a
                  href={profile.linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open LinkedIn ↗
                </a>
              </p>
            )}
            {profile.syncStatus !== "SUCCESS" && (
              <p className="notice document-warning">{profile.syncError}</p>
            )}
          </>
        )}
      </main>
    </>
  );
}
