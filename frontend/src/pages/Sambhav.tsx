import { useEffect, useState } from "react";
import { sambhavApi } from "../services/sambhavApi";
import type { SambhavDomain } from "../types/sambhav";
import { SambhavEditor } from "../components/SambhavEditor";
import { ErrorState, LoadingState } from "../components/States";
import { Link, useParams } from "react-router-dom";
import { Header } from "../components/Header";
import { SambhavIdeaSection } from "../components/SambhavIdeaSection";
import {
  sambhav,
  domainPath,
  ideaPath,
  participantCount,
} from "../programs/sambhav";

function useProgram() {
  const [domains, setDomains] = useState<SambhavDomain[] | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [canEdit, setCanEdit] = useState(false);
  useEffect(() => {
    let active = true;
    setError("");
    setDomains(null);
    sambhavApi
      .list()
      .then((data) => {
        if (active) {
          setDomains(data.domains);
          setCanEdit(data.canEdit);
        }
      })
      .catch((e) => {
        if (active)
          setError(e instanceof Error ? e.message : "Unable to load Sambhav.");
      });
    return () => {
      active = false;
    };
  }, [revision]);
  return {
    domains,
    error,
    canEdit,
    reload: () => setRevision((v) => v + 1),
    saved: (domain: SambhavDomain) =>
      setDomains(
        (values) =>
          values?.map((d) => (d.slug === domain.slug ? domain : d)) || null,
      ),
  };
}
function Pending({ error, reload }: { error: string; reload: () => void }) {
  return (
    <>
      <Header />
      <main>
        {error ? (
          <>
            <ErrorState message={error} />
            <button onClick={reload}>Retry</button>
          </>
        ) : (
          <LoadingState label="Sambhav" />
        )}
      </main>
    </>
  );
}
export function Sambhav() {
  const { domains, error, reload } = useProgram();
  if (!domains) return <Pending error={error} reload={reload} />;
  return (
    <>
      <Header />
      <main>
        <div className="page-title">
          <div>
            <span className="eyebrow">YOUR COMMUNITY</span>
            <h1>{sambhav.title}</h1>
            <p className="muted">
              Nine domains. Three ideas in each. Explore where you can
              contribute.
            </p>
          </div>
          <section
            className="submission-count"
            aria-label="Sambhav program structure"
          >
            <span>Idea slots</span>
            <strong>{sambhav.totalIdeaSlots}</strong>
            <small>
              {sambhav.numberOfDomains} domains · {sambhav.ideasPerDomain} ideas
              per domain
            </small>
          </section>
        </div>
        <div className="sambhav-domains">
          {domains.map((domain) => (
            <article
              className="profile-card sambhav-domain"
              key={domain.code}
              aria-labelledby={`domain-${domain.code}`}
            >
              <div className="card-top">
                <span className="eyebrow">Domain {domain.code}</span>
                <span className="member-status">{domain.status}</span>
              </div>
              <h2 id={`domain-${domain.code}`}>
                <Link to={domainPath(domain)}>{domain.title}</Link>
              </h2>
              {domain.description && <p>{domain.description}</p>}
              <ol className="sambhav-slots">
                {domain.ideas.map((idea) => (
                  <li key={idea.id}>
                    <Link to={ideaPath(domain, idea)}>{idea.title}</Link>
                    <span>{idea.status}</span>
                  </li>
                ))}
              </ol>
              <p className="muted">
                {participantCount(domain)} participating members
              </p>
              <Link
                className="button"
                to={domainPath(domain)}
                aria-label={`Explore ${domain.title}`}
              >
                Explore domain →
              </Link>
            </article>
          ))}
        </div>
      </main>
    </>
  );
}
export function SambhavDetail() {
  const { domainSlug, ideaId } = useParams();
  const { domains, error, reload, saved, canEdit } = useProgram();
  if (!domains) return <Pending error={error} reload={reload} />;
  const domain = domains.find((item) => item.slug === domainSlug);
  const idea = domain?.ideas.find((item) => item.id === ideaId);
  if (!domain || (ideaId && !idea))
    return (
      <>
        <Header />
        <main>
          <Link to="/sambhav">← Back to Sambhav</Link>
          <h1>{domain ? "Idea not found" : "Domain not found"}</h1>
          <p>Select a domain or idea from Sambhav to continue.</p>
        </main>
      </>
    );
  return (
    <>
      <Header />
      <main>
        <nav className="sambhav-breadcrumb" aria-label="Breadcrumb">
          <Link to="/sambhav">Sambhav</Link>
          <span aria-hidden="true"> / </span>
          {idea ? (
            <>
              <Link to={domainPath(domain)}>{domain.title}</Link>
              <span aria-hidden="true"> / </span>
              <span>{idea.title}</span>
            </>
          ) : (
            <span>{domain.title}</span>
          )}
        </nav>
        {canEdit && (
          <SambhavEditor
            key={domain.slug}
            domain={domain}
            onSaved={saved}
            onReload={reload}
          />
        )}
        {idea ? (
          <>
            <p className="eyebrow">
              Domain {domain.code} · {domain.title}
            </p>
            <SambhavIdeaSection
              domain={domain}
              idea={idea}
              standalone
              onSaved={canEdit ? saved : undefined}
            />
          </>
        ) : (
          <>
            <div className="page-title">
              <div>
                <span className="eyebrow">Domain {domain.code}</span>
                <h1>{domain.title}</h1>
                {domain.description && <p>{domain.description}</p>}
                <p>
                  <span className="member-status">{domain.status}</span> ·{" "}
                  {participantCount(domain)} participating members · 3 idea
                  slots
                </p>
              </div>
            </div>
            <div className="sambhav-ideas">
              {domain.ideas.map((item) => (
                <SambhavIdeaSection
                  key={item.id}
                  domain={domain}
                  idea={item}
                  onSaved={canEdit ? saved : undefined}
                />
              ))}
            </div>
          </>
        )}
      </main>
    </>
  );
}
