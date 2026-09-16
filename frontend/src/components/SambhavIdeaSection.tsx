import { Link } from "react-router-dom";
import type {
  SambhavDomain,
  SambhavIdea,
  SambhavMember,
} from "../types/sambhav";
import { ideaPath } from "../programs/sambhav";
import { SambhavDocuments, SambhavUploader } from "./SambhavAttachments";
import { formatDate } from "./ProfileCard";
function Member({ member }: { member: SambhavMember | null }) {
  return member ? (
    <Link
      to={`/members/${encodeURIComponent(member.email.trim().toLowerCase())}`}
    >
      {member.name}
    </Link>
  ) : (
    <>Not assigned</>
  );
}
export function SambhavIdeaSection({
  domain,
  idea,
  standalone = false,
  onSaved,
}: {
  domain: SambhavDomain;
  idea: SambhavIdea;
  standalone?: boolean;
  onSaved?: (domain: SambhavDomain) => void;
}) {
  const titleId = `idea-${idea.id}`;
  return (
    <section className="member-section sambhav-idea" aria-labelledby={titleId}>
      <div className="card-top">
        {standalone ? (
          <h1 id={titleId}>{idea.title}</h1>
        ) : (
          <h2 id={titleId}>
            <Link to={ideaPath(domain, idea)}>{idea.title}</Link>
          </h2>
        )}
        <span className="member-status">{idea.status}</span>
      </div>
      <dl>
        <div>
          <dt>Short summary</dt>
          <dd>{idea.summary || "Not provided"}</dd>
        </div>
        <div>
          <dt>Detailed description</dt>
          <dd>{idea.description || "Not provided"}</dd>
        </div>
        <div>
          <dt>Vision</dt>
          <dd>{idea.vision || "Not provided"}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{idea.status}</dd>
        </div>
        <div>
          <dt>Lead member</dt>
          <dd>
            <Member member={idea.lead} />
          </dd>
        </div>
        <div>
          <dt>Co-lead member</dt>
          <dd>
            <Member member={idea.coLead} />
          </dd>
        </div>
        <div>
          <dt>Interested members</dt>
          <dd>
            {idea.interestedMembers.length ? (
              <ul>
                {idea.interestedMembers.map((member) => (
                  <li key={member.email}>
                    <Member member={member} />
                  </li>
                ))}
              </ul>
            ) : (
              "No interested members yet"
            )}
          </dd>
        </div>
        <div>
          <dt>Vision documents</dt>
          <dd>
            <SambhavDocuments
              documents={idea.visionDocuments}
              domain={domain.slug}
              idea={idea.id}
            />
          </dd>
        </div>
        <div>
          <dt>Project documents</dt>
          <dd>
            <SambhavDocuments
              documents={idea.projectDocuments}
              domain={domain.slug}
              idea={idea.id}
            />
          </dd>
        </div>
        <div>
          <dt>Member profile documents</dt>
          <dd>
            <SambhavDocuments
              documents={idea.memberProfileDocuments || []}
              domain={domain.slug}
              idea={idea.id}
            />
          </dd>
        </div>
        <div>
          <dt>Other documents</dt>
          <dd>
            <SambhavDocuments
              documents={idea.otherDocuments || []}
              domain={domain.slug}
              idea={idea.id}
            />
          </dd>
        </div>
        <div>
          <dt>Last updated date</dt>
          <dd>
            {idea.updatedAt
              ? formatDate(idea.updatedAt, true)
              : "Not yet updated"}
          </dd>
        </div>
      </dl>
      {onSaved && (
        <SambhavUploader domain={domain} idea={idea} onSaved={onSaved} />
      )}
    </section>
  );
}
