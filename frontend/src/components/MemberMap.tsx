import { useState } from "react";
import world from "../data/world-map.json";
const bands = [
  { label: "0", color: "#e3e9e5" },
  { label: "1", color: "#d1e6c7" },
  { label: "2–5", color: "#9fc993" },
  { label: "6–15", color: "#62a36d" },
  { label: "16–30", color: "#34754c" },
  { label: "31+", color: "#164c32" },
];
function color(count: number) {
  return bands[
    count === 0
      ? 0
      : count === 1
        ? 1
        : count <= 5
          ? 2
          : count <= 15
            ? 3
            : count <= 30
              ? 4
              : 5
  ].color;
}
export default function MemberMap({
  counts,
  total,
  selected,
  onSelect,
}: {
  counts: { country: string; count: number }[];
  total: number;
  selected: string;
  onSelect: (country: string) => void;
}) {
  const [hovered, setHovered] = useState("");
  const values = new Map(counts.map((item) => [item.country, item.count]));
  const names = new Set(world.map((item) => item.name));
  const unmapped = counts.filter((item) => !names.has(item.country));
  const shown = hovered || selected;
  return (
    <section className="member-map" aria-label="Member distribution map">
      <div className="map-heading">
        <div>
          <h2>Our community around the world</h2>
          <p>
            {total} members across{" "}
            {counts.filter((item) => names.has(item.country)).length} mapped
            countries. Select a country to see its members below.
          </p>
        </div>
        {selected && (
          <button onClick={() => onSelect("")}>Show all countries</button>
        )}
      </div>
      <div className="map-layout">
        <div>
          <svg
            viewBox="0 0 900 370"
            className="world-map"
            aria-label="World map shaded by member count"
          >
            <rect width="900" height="370" fill="#f1f7f8" />
            {[62.5, 137.5, 212.5, 287.5].map((y) => (
              <path
                key={y}
                d={`M0,${y}H900`}
                stroke="#dce9ec"
                strokeWidth="0.6"
              />
            ))}
            {world.map((item) => {
              const count = values.get(item.name) || 0;
              return (
                <path
                  key={item.name}
                  d={item.path}
                  fill={color(count)}
                  fillRule="evenodd"
                  stroke={selected === item.name ? "#d68a19" : "#ffffff"}
                  strokeWidth={selected === item.name ? 1.6 : 0.45}
                  className={count ? "map-country populated" : "map-country"}
                  role={count ? "button" : undefined}
                  tabIndex={count ? 0 : undefined}
                  aria-label={`${item.name}: ${count} ${count === 1 ? "member" : "members"}`}
                  aria-pressed={count ? selected === item.name : undefined}
                  onMouseEnter={() => setHovered(item.name)}
                  onMouseLeave={() => setHovered("")}
                  onFocus={() => setHovered(item.name)}
                  onBlur={() => setHovered("")}
                  onClick={() => {
                    if (count) onSelect(item.name);
                  }}
                  onKeyDown={(event) => {
                    if (count && ["Enter", " "].includes(event.key)) {
                      event.preventDefault();
                      onSelect(item.name);
                    }
                  }}
                >
                  <title>
                    {item.name}: {count} {count === 1 ? "member" : "members"}
                  </title>
                </path>
              );
            })}
            {world
              .filter((item) => values.has(item.name))
              .map((item) => (
                <circle
                  key={item.name}
                  cx={item.x}
                  cy={item.y}
                  r="3.5"
                  fill={color(values.get(item.name) || 0)}
                  stroke="#163e2a"
                  strokeWidth="0.8"
                  className="map-point"
                  onClick={() => onSelect(item.name)}
                  onMouseEnter={() => setHovered(item.name)}
                  onMouseLeave={() => setHovered("")}
                >
                  <title>
                    {item.name}: {values.get(item.name)} members
                  </title>
                </circle>
              ))}
          </svg>
          <p className="map-readout" aria-live="polite">
            {shown
              ? `${shown}: ${values.get(shown) || 0} members`
              : "Darker countries have more members."}
          </p>
          <div className="map-legend" aria-label="Members per country">
            {bands.map((band) => (
              <span key={band.label}>
                <i style={{ background: band.color }} />
                {band.label}
              </span>
            ))}
          </div>
          <p className="muted small">
            Country-level locations, using country names and clear country names
            in addresses. Members with multiple countries count in each.
            Boundaries:{" "}
            <a
              href="https://www.naturalearthdata.com/about/"
              target="_blank"
              rel="noreferrer"
            >
              Natural Earth
            </a>
            .
          </p>
        </div>
        <aside className="map-countries" aria-label="Member counts by country">
          <h3>Members by country</h3>
          {counts.length ? (
            counts.map((item) => (
              <button
                key={item.country}
                aria-pressed={selected === item.country}
                onClick={() => onSelect(item.country)}
              >
                <span>
                  {item.country}
                  {!names.has(item.country) && <small>Not mapped</small>}
                </span>
                <strong>{item.count}</strong>
              </button>
            ))
          ) : (
            <p>No members match this search.</p>
          )}
        </aside>
      </div>
      {unmapped.length > 0 && (
        <p className="notice">
          Country entries not mapped: {unmapped.reduce((sum, item) => sum + item.count, 0)}.
          Select them in the country list to review their members.
        </p>
      )}
    </section>
  );
}
