import { afterEach, describe, it, expect, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../src/auth/AuthProvider";
import { App } from "../src/App";
import { memberApi } from "../src/services/api";
import { sambhavApi } from "../src/services/sambhavApi";
import { sambhav, participantCount } from "../src/programs/sambhav";
vi.mock("../src/auth/client", () => ({
  mockMode: true,
  googleLoginEnabled: false,
  currentUser: vi.fn().mockResolvedValue("member@example.org"),
  hasAppAccess: vi.fn().mockResolvedValue(true),
  onAuthChange: vi.fn(() => () => {}),
  logout: vi.fn(),
}));
const expected = [
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
];
function show(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}
describe("Sambhav program requirements", () => {
  it("preserves the exact domain order, metadata and 27 stable idea slots", () => {
    expect(sambhav.title).toBe("Sambhav");
    expect(sambhav.slug).toBe("sambhav");
    expect(
      sambhav.domains.map((d) => [
        d.code,
        d.title,
        d.slug,
        d.sourcePageReference,
      ]),
    ).toEqual(expected);
    expect(sambhav.domains.every((d) => d.ideas.length === 3)).toBe(true);
    expect(
      new Set(sambhav.domains.flatMap((d) => d.ideas.map((i) => i.id))).size,
    ).toBe(27);
  });
  it("renders nine ordered domain cards with three idea links each", async () => {
    show("/sambhav");
    const cards = await screen.findAllByRole("article");
    expect(cards).toHaveLength(9);
    cards.forEach((card, index) => {
      expect(within(card).getByRole("heading", { level: 2 })).toHaveTextContent(
        String(expected[index][1]),
      );
      expect(within(card).getAllByRole("listitem")).toHaveLength(3);
      expect(
        within(card).getByText("0 participating members"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/Source page/)).not.toBeInTheDocument();
  });
  it("opens a domain and an idea with every required field", async () => {
    show("/sambhav");
    await userEvent.click(
      await screen.findByRole("link", {
        name: "Explore FinTech & Financial Inclusion",
      }),
    );
    const sections = screen.getAllByRole("region", { name: /^Idea [123]$/ });
    expect(sections).toHaveLength(3);
    for (const section of sections)
      for (const field of [
        "Short summary",
        "Detailed description",
        "Vision",
        "Status",
        "Lead member",
        "Co-lead member",
        "Interested members",
        "Vision documents",
        "Project documents",
        "Last updated date",
      ]) {
        expect(
          within(section).getByText(field, { exact: true, selector: "dt" }),
        ).toBeInTheDocument();
      }
    await userEvent.click(
      screen.getByRole("link", { name: "Idea 2", exact: true }),
    );
    expect(
      screen.getByRole("heading", { level: 1, name: "Idea 2" }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("region", { name: /^Idea/ })).toHaveLength(1);
    expect(screen.getByText("Not yet updated")).toBeInTheDocument();
  });
  it("supports direct idea links and rejects ideas from another domain", async () => {
    show("/sambhav/domains/healthcare-public-health/ideas/01-01");
    expect(
      await screen.findByRole("heading", { name: "Idea not found" }),
    ).toBeInTheDocument();
  });
  it("renders a direct idea URL", async () => {
    show("/sambhav/domains/healthcare-public-health/ideas/07-03");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Idea 3" }),
    ).toBeInTheDocument();
  });
  it("counts a member once across roles and ideas", () => {
    const domain = structuredClone(sambhav.domains[0]);
    domain.ideas[0].lead = { name: "One", email: "ONE@example.org" };
    domain.ideas[1].coLead = { name: "One", email: "one@example.org" };
    domain.ideas[2].interestedMembers = [
      { name: "Two", email: "two@example.org" },
    ];
    expect(participantCount(domain)).toBe(2);
  });
});

afterEach(() => vi.restoreAllMocks());
it("edits a domain and saves idea content with existing member assignments", async () => {
  vi.spyOn(memberApi, "list").mockResolvedValue({
    items: [{ name: "Existing Member", email: "member@example.org" } as any],
    total: 1,
    totalProfiles: 1,
    page: 1,
    pageSize: 100,
    themes: [],
    lastSyncedAt: null,
  });
  const save = vi
    .spyOn(sambhavApi, "save")
    .mockImplementation(async (domain) => ({ ...domain, version: 1 }));
  show("/sambhav/domains/fintech-financial-inclusion");
  await userEvent.click(
    await screen.findByRole("button", { name: "Edit domain and ideas" }),
  );
  await waitFor(() =>
    expect(screen.getByLabelText("Domain description")).toBeEnabled(),
  );
  await userEvent.type(
    screen.getByLabelText("Domain description"),
    "Financial inclusion program",
  );
  await userEvent.clear(screen.getByLabelText("Domain heading"));
  await userEvent.type(
    screen.getByLabelText("Domain heading"),
    "Community development",
  );
  const titles = screen.getAllByLabelText("Idea title");
  await userEvent.clear(titles[0]);
  await userEvent.type(titles[0], "Community finance");
  await userEvent.selectOptions(
    screen.getAllByLabelText("Lead member")[0],
    "member@example.org",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save domain and ideas" }),
  );
  expect(
    await screen.findByText("Domain and idea information saved."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Community finance" }),
  ).toBeInTheDocument();
  expect(save).toHaveBeenCalledWith(
    expect.objectContaining({
      title: "Community development",
      description: "Financial inclusion program",
    }),
  );
  expect(
    screen.getByRole("heading", { name: "Community development" }),
  ).toBeInTheDocument();
  expect(save.mock.calls[0][0].ideas[0].lead?.email).toBe("member@example.org");
});
it("attaches multiple member-profile PDFs to the selected idea", async () => {
  const upload = vi
    .spyOn(sambhavApi, "upload")
    .mockImplementation(async () => structuredClone(sambhav.domains[0]));
  show("/sambhav/domains/fintech-financial-inclusion/ideas/01-01");
  const input = await screen.findByLabelText("PDF files");
  await userEvent.selectOptions(
    screen.getByLabelText("Attachment category"),
    "member-profile",
  );
  const files = [
    new File(["%PDF-1.4"], "one.pdf", { type: "application/pdf" }),
    new File(["%PDF-1.4"], "two.pdf", { type: "application/pdf" }),
  ];
  await userEvent.upload(input, files);
  await userEvent.click(screen.getByRole("button", { name: "Upload PDFs" }));
  expect(
    await screen.findByText("2 PDF attachments saved."),
  ).toBeInTheDocument();
  expect(upload).toHaveBeenCalledTimes(2);
  expect(upload).toHaveBeenLastCalledWith(
    "fintech-financial-inclusion",
    "01-01",
    "member-profile",
    files[1],
  );
});
