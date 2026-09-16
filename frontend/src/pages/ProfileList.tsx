import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, memberApi } from "../services/api";
import type { ProfilePage } from "../types/profile";
import { Header } from "../components/Header";
import { ProfileCard, formatDate } from "../components/ProfileCard";
import { SearchBar } from "../components/SearchBar";
import { ThemeFilter } from "../components/ThemeFilter";
import { SyncButton } from "../components/SyncButton";
import { LoadingState, EmptyState, ErrorState } from "../components/States";
const MemberMap = lazy(() => import("../components/MemberMap"));
export function ProfileList({ members = false }: { members?: boolean }) {
  const label = members ? "Members" : "Idea Incubation";
  const [params, setParams] = useSearchParams();
  const mapView = members && params.get("view") === "map";
  const search = params.get("search") || "",
    theme = params.get("theme") || "",
    country = params.get("country") || "",
    chapter = params.get("chapter") || "",
    region = params.get("region") || "",
    page = Math.max(1, Number(params.get("page")) || 1);
  const [data, setData] = useState<ProfilePage | null>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      (members ? memberApi : api)
        .list({
          search,
          ...(members ? { country, chapter, region } : { theme }),
          page,
          pageSize: 25,
        })
        .then((result) => {
          if (active) {
            setData(result);
            setLoading(false);
          }
        })
        .catch((e) => {
          if (active) {
            setError(
              e instanceof Error ? e.message : "Unable to load profiles.",
            );
            setLoading(false);
          }
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [search, theme, country, chapter, region, page, revision, members]);
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    next.set(key, value);
    if (key !== "page") next.set("page", "1");
    setParams(next, { replace: true });
  }
  return (
    <>
      <Header />
      <main>
        <div className="page-title">
          <div>
            <span className="eyebrow">YOUR COMMUNITY</span>
            <div className="member-title-row">
              <h1>{label}</h1>
              {members && (
                <div className="member-view-switch" aria-label="Member view">
                  <button
                    aria-pressed={!mapView}
                    onClick={() => change("view", "list")}
                  >
                    List
                  </button>
                  <button
                    aria-pressed={mapView}
                    onClick={() => change("view", "map")}
                  >
                    Map
                  </button>
                </div>
              )}
            </div>
            <p className="muted">
              {members
                ? "Explore your community and read each member’s details."
                : "Explore submissions in Idea Incubation."}
            </p>
          </div>
          <section
            className="submission-count"
            aria-label={members ? "Total active members" : "Total submissions"}
          >
            <span>{members ? "Active members" : "Submissions"}</span>
            <strong>
              {error
                ? "—"
                : loading
                  ? "…"
                  : data
                    ? (members
                        ? data.total
                        : data.totalProfiles
                      ).toLocaleString()
                    : "…"}
            </strong>
            <small>
              {error
                ? "Count unavailable"
                : members
                  ? search || chapter || country || region
                    ? "Matching your filters"
                    : "In the member directory"
                  : "Synced to this library"}
            </small>
          </section>
        </div>
        <div className="toolbar">
          <SearchBar
            placeholder={
              members ? "Search name, email, membership ID…" : undefined
            }
            value={search}
            onChange={(value) => change("search", value)}
          />
          {members &&
            (
              [
                ["chapter", "Chapter", chapter, data?.chapters || []],
                ["country", "Country", country, data?.countries || []],
                ["region", "Region", region, data?.regions || []],
              ] as const
            ).map(([key, label, selected, options]) => (
              <label key={key}>
                {label}
                <select
                  value={selected}
                  onChange={(event) => change(key, event.target.value)}
                >
                  <option value="">
                    All {key === "country" ? "countries" : key + "s"}
                  </option>
                  {selected && !options.includes(selected) && (
                    <option value={selected}>{selected}</option>
                  )}
                  {options.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          {!members && (
            <ThemeFilter
              value={theme}
              themes={data?.themes || []}
              onChange={(value) => change("theme", value)}
            />
          )}
        </div>
        <SyncButton
          key={members ? "members" : "profiles"}
          members={members}
          onComplete={refresh}
        />
        {mapView && !loading && !error && data && (
          <Suspense fallback={<LoadingState label="map" />}>
            <MemberMap
              counts={data.countryCounts || []}
              total={data.mapTotal ?? data.totalProfiles}
              selected={country}
              onSelect={(value) => change("country", value)}
            />
          </Suspense>
        )}
        {data && (
          <div className="list-meta">
            <strong>
              {data.total} {members ? "Members" : "submissions"}
            </strong>
            <span>Last synced: {formatDate(data.lastSyncedAt, true)}</span>
          </div>
        )}
        {error ? (
          <ErrorState message={error} />
        ) : loading ? (
          <LoadingState label={members ? "members" : "submissions"} />
        ) : !data?.items.length ? (
          members ? (
            <section className="empty">
              <h2>No members found</h2>
              <p>
                Try another search or clear the chapter, country and region
                filters.
              </p>
            </section>
          ) : (
            <EmptyState />
          )
        ) : (
          <div className="profile-list">
            {data.items.map((profile) => (
              <ProfileCard
                key={profile.profileId}
                profile={profile}
                members={members}
              />
            ))}
          </div>
        )}
        {data && data.total > data.pageSize && (
          <nav aria-label="Pagination" className="pagination">
            <button
              disabled={page <= 1 || loading}
              onClick={() => change("page", String(page - 1))}
            >
              Previous
            </button>
            <span>
              Page {page} of {Math.ceil(data.total / data.pageSize)}
            </span>
            <button
              disabled={page * data.pageSize >= data.total || loading}
              onClick={() => change("page", String(page + 1))}
            >
              Next
            </button>
          </nav>
        )}
      </main>
    </>
  );
}
