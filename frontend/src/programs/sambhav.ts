import type { SambhavDomain, SambhavIdea } from "../types/sambhav";
const structure = [
  ["01", "FinTech & Financial Inclusion", "fintech-financial-inclusion", 6],
  [
    "02",
    "AI-Driven Skills Mapping & Entrepreneurship",
    "ai-skills-mapping-entrepreneurship",
    7,
  ],
  [
    "03",
    "Primary, Middle & School Education",
    "primary-middle-school-education",
    8,
  ],
  [
    "04",
    "Higher Education, STEM & Research",
    "higher-education-stem-research",
    9,
  ],
  [
    "05",
    "Content Creation, Media & Public Outreach",
    "content-media-public-outreach",
    10,
  ],
  [
    "06",
    "Community Policy, Governance & Social Research",
    "community-policy-governance-social-research",
    11,
  ],
  ["07", "Healthcare & Public Health", "healthcare-public-health", 12],
  [
    "08",
    "Agriculture, Environment & Sustainability",
    "agriculture-environment-sustainability",
    13,
  ],
  [
    "09",
    "Engineering, Industrial & Vocational Skill Development",
    "engineering-industrial-vocational-skills",
    14,
  ],
] as const;
function emptyIdea(code: string, slot: number): SambhavIdea {
  return {
    id: `${code}-${String(slot).padStart(2, "0")}`,
    title: `Idea ${slot}`,
    summary: "",
    description: "",
    vision: "",
    status: "Not started",
    lead: null,
    coLead: null,
    interestedMembers: [],
    visionDocuments: [],
    projectDocuments: [],
    updatedAt: null,
  };
}
export const sambhav = {
  title: "Sambhav",
  slug: "sambhav",
  numberOfDomains: 9,
  ideasPerDomain: 3,
  totalIdeaSlots: 27,
  domains: structure.map(
    ([code, title, slug, sourcePageReference]): SambhavDomain => ({
      code,
      title,
      slug,
      sourcePageReference,
      status: "Not started",
      ideas: [emptyIdea(code, 1), emptyIdea(code, 2), emptyIdea(code, 3)],
    }),
  ),
};
export function domainPath(domain: SambhavDomain) {
  return `/sambhav/domains/${domain.slug}`;
}
export function ideaPath(domain: SambhavDomain, idea: SambhavIdea) {
  return `${domainPath(domain)}/ideas/${idea.id}`;
}
export function participantCount(domain: SambhavDomain) {
  return new Set(
    domain.ideas
      .flatMap((idea) => [idea.lead, idea.coLead, ...idea.interestedMembers])
      .filter((member) => member !== null)
      .map((member) => member.email.trim().toLowerCase()),
  ).size;
}
