import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../src/auth/AuthProvider";
import { App } from "../src/App";
import { api, memberApi } from "../src/services/api";
import {
  registerEmail,
  verifySignup,
  resendSignup,
  currentUser,
  login,
  loginWithGoogle,
  hasAppAccess,
  onAuthChange,
} from "../src/auth/client";
import type { Profile, ProfilePage } from "../src/types/profile";
import samples from "../src/services/sampleProfiles.json";

vi.mock("../src/auth/client", () => ({
  registerEmail: vi.fn(),
  verifySignup: vi.fn(),
  resendSignup: vi.fn(),
  mockMode: true,
  googleLoginEnabled: true,
  loginWithGoogle: vi.fn(),
  hasAppAccess: vi.fn().mockResolvedValue(true),
  onAuthChange: vi.fn(() => () => {}),
  currentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  challenge: vi.fn(),
}));
vi.mock("../src/services/api", () => ({
  memberApi: {
    update: vi.fn(),
    list: vi.fn(),
    get: vi.fn(),
    sync: vi.fn(),
    syncStatus: vi.fn().mockResolvedValue(null),
  },
  api: {
    list: vi.fn(),
    get: vi.fn(),
    document: vi.fn(),
    sync: vi.fn(),
    syncStatus: vi.fn(),
  },
}));
const profiles = samples as Profile[];
const result: ProfilePage = {
  items: profiles,
  total: 3,
  totalProfiles: 3,
  page: 1,
  pageSize: 25,
  themes: ["Education", "Employment", "Healthcare"],
  lastSyncedAt: profiles[0].lastSyncedAt,
};
function show(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.mocked(hasAppAccess).mockResolvedValue(true);
  vi.mocked(currentUser).mockResolvedValue("admin@example.com");
  vi.mocked(api.list).mockResolvedValue(result);
  vi.mocked(api.get).mockResolvedValue(profiles[0]);
  vi.mocked(api.document).mockResolvedValue({
    url: "https://private.example/preview.pdf",
    expiresIn: 900,
    fileName: "profile.pdf",
  });
  vi.mocked(api.syncStatus).mockResolvedValue(null);
});

describe("Profile Library", () => {
  it("syncs Members independently of Profiles", async () => {
    vi.mocked(memberApi.list).mockResolvedValue({ ...result, items: [] });
    vi.mocked(memberApi.sync).mockResolvedValue({
      jobId: "member-job",
      status: "COMPLETED",
      processed: 29,
      created: 29,
      deleted: 2,
      updated: 0,
      unchanged: 0,
      failed: 0,
      error: null,
      updatedAt: new Date().toISOString(),
    });
    const profileCalls = vi.mocked(api.sync).mock.calls.length;
    show("/members");
    await userEvent.click(
      await screen.findByRole("button", { name: "Sync Now" }),
    );
    expect(memberApi.sync).toHaveBeenCalled();
    expect(vi.mocked(api.sync).mock.calls).toHaveLength(profileCalls);
    expect(
      await screen.findByText(/Sync completed · 29 processed/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Sync completed · 29 processed/)).toHaveTextContent(
      "2 removed",
    );
  });
  it("opens a dedicated Google signup view and returns to login", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    show("/login");
    await userEvent.click(
      await screen.findByRole("link", { name: "Create an account" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Create your JSO account" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(
      screen.getByText(/An administrator will approve/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Sign up", exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await userEvent.click(
      screen.getAllByRole("link", { name: "Log in", exact: true })[0],
    );
    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
  });
  it("starts Google signup from its direct URL", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    vi.mocked(loginWithGoogle).mockResolvedValue();
    show("/signup");
    await userEvent.click(
      await screen.findByRole("button", { name: "Sign up with Google" }),
    );
    expect(loginWithGoogle).toHaveBeenCalled();
  });
  it("starts Google signup from the login page", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    vi.mocked(loginWithGoogle).mockResolvedValue();
    show("/login");
    await userEvent.click(
      await screen.findByRole("button", { name: "Continue with Google" }),
    );
    expect(loginWithGoogle).toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "Connecting to Google…" }),
    ).toBeDisabled();
  });
  it("allows retry when Google redirect fails", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    vi.mocked(loginWithGoogle).mockRejectedValue(new Error("redirect failed"));
    show("/login");
    await userEvent.click(
      await screen.findByRole("button", { name: "Continue with Google" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to start Google sign-in",
    );
    expect(
      screen.getByRole("button", { name: "Continue with Google" }),
    ).toBeEnabled();
  });
  it("keeps users without approval out of the directory", async () => {
    vi.mocked(hasAppAccess).mockResolvedValue(false);
    const calls = vi.mocked(api.list).mock.calls.length;
    show("/members");
    expect(
      await screen.findByRole("heading", { name: "Awaiting approval" }),
    ).toBeInTheDocument();
    expect(vi.mocked(api.list).mock.calls).toHaveLength(calls);
  });
  it("shows a Google callback error", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    show("/login");
    await screen.findByLabelText("Email");
    const callback = vi.mocked(onAuthChange).mock.calls.at(-1)![0];
    await act(async () => {
      callback(true);
    });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Google sign-in was not completed",
    );
  });
  it("finishes Google sign-in after the redirect event", async () => {
    vi.mocked(currentUser).mockResolvedValue(null);
    show("/login");
    await screen.findByLabelText("Email");
    vi.mocked(currentUser).mockResolvedValue("google-user@example.com");
    const callback = vi.mocked(onAuthChange).mock.calls.at(-1)![0];
    await act(async () => {
      callback(false);
    });
    expect(await screen.findByText("3 submissions")).toBeInTheDocument();
  });
  it("shows login and signs in", async () => {
    vi.mocked(currentUser)
      .mockResolvedValueOnce(null)
      .mockResolvedValue("admin@example.com");
    vi.mocked(login).mockResolvedValue(null);
    show("/login");
    await userEvent.type(
      await screen.findByLabelText("Email"),
      "admin@example.com",
    );
    await userEvent.type(screen.getByLabelText("Password"), "demo-password");
    await userEvent.click(
      screen.getByRole("button", { name: "Login", exact: true }),
    );
    expect(await screen.findByText("3 submissions")).toBeInTheDocument();
  });
  it("lists the three sample profiles", async () => {
    show();
    expect(await screen.findByText("Amit Kumar")).toBeInTheDocument();
    expect(screen.getByText("Ajay Kumar Suman")).toBeInTheDocument();
    expect(screen.getByText("Salauddin Ahmad")).toBeInTheDocument();
  });
  it("searches profiles", async () => {
    show();
    await screen.findByText("3 submissions");
    await userEvent.type(screen.getByRole("searchbox"), "amit");
    await waitFor(() =>
      expect(api.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "amit", page: 1 }),
      ),
    );
  });
  it("filters by dynamically returned theme", async () => {
    show();
    await screen.findByText("3 submissions");
    await userEvent.selectOptions(screen.getByLabelText("Theme"), "Healthcare");
    await waitFor(() =>
      expect(api.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ theme: "Healthcare" }),
      ),
    );
  });
  it("keeps the submitted total when a filter has no matches", async () => {
    vi.mocked(api.list).mockResolvedValue({
      ...result,
      items: [],
      total: 0,
      totalProfiles: 124,
    });
    show("/?theme=Unknown");
    await screen.findByRole("heading", { name: "No submissions found" });
    expect(
      screen.getByRole("region", { name: "Total submissions" }),
    ).toHaveTextContent("124");
    expect(screen.getByText("0 submissions")).toBeInTheDocument();
  });
  it("renders profile detail", async () => {
    show("/profiles/" + profiles[0].profileId);
    expect(
      await screen.findByRole("heading", { name: "Amit Kumar" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open LinkedIn/ })).toHaveAttribute(
      "rel",
      "noopener noreferrer",
    );
    expect(screen.getByText("amit-kumar.pdf")).toBeInTheDocument();
  });
  it("shows structured member details, membership ID and photo", async () => {
    vi.mocked(api.get).mockResolvedValue({
      ...profiles[0],
      photoUrl: "https://private.example/photo",
      member: {
        membershipId: "JSO-001",
        status: "active",
        education: "Masters in Education",
        skills: "Teaching",
        country: "Sweden",
        roleTitle: "Coordinator",
      },
    });
    show("/profiles/" + profiles[0].profileId);
    expect(await screen.findByText("JSO-001")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Background & expertise" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Masters in Education")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: profiles[0].name })).toHaveAttribute(
      "src",
      "https://private.example/photo",
    );
  });
  it("navigates to Members and opens member details", async () => {
    const member = {
      ...profiles[0],
      profileId: "member+test@example.org",
      email: "member+test@example.org",
      name: "Member Example",
      photoUrl: "https://private.example/member.jpg",
      theme: "Member interest",
      pdf: null,
      member: {
        membershipId: "JSO-199",
        status: "active",
        education: "Member education",
        sourceUniqueId: "source-199",
      },
    };
    vi.mocked(memberApi.list).mockResolvedValue({
      ...result,
      items: [member],
      total: 1,
      totalProfiles: 199,
    });
    vi.mocked(memberApi.get).mockResolvedValue(member);
    show();
    await userEvent.click(
      await screen.findByRole("link", { name: "Members", exact: true }),
    );
    expect(await screen.findByText("1 Members")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Total active members" }),
    ).toHaveTextContent("Active members1");
    expect(
      screen.getByRole("button", { name: "Sync Now" }),
    ).toBeInTheDocument();
    expect(screen.getByText("source-199")).toBeInTheDocument();
    expect(screen.queryByText("JSO-199")).not.toBeInTheDocument();
    expect(screen.queryByText("Member interest")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Member Example" })).toHaveAttribute(
      "src",
      "https://private.example/member.jpg",
    );
    await userEvent.click(screen.getByRole("link", { name: "View Member" }));
    expect(await screen.findByText("Member education")).toBeInTheDocument();
    expect(memberApi.get).toHaveBeenCalledWith("member+test@example.org");
    expect(screen.getAllByText("source-199").length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("heading", { name: "Document" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Back to Members/ }),
    ).toHaveAttribute("href", "/members");
  });
  it.each([
    ["Chapter", "Stockholm"],
    ["Country", "Sweden"],
    ["Region", "Europe"],
  ])(
    "updates the member total when filtering by %s and clearing it",
    async (label, value) => {
      const directory = {
        ...result,
        total: 199,
        totalProfiles: 199,
        chapters: ["Stockholm"],
        countries: ["Sweden"],
        regions: ["Europe"],
      };
      vi.mocked(memberApi.list).mockResolvedValue(directory);
      show("/members");
      const count = await screen.findByRole("region", {
        name: "Total active members",
      });
      await waitFor(() => expect(count).toHaveTextContent("199"));
      vi.mocked(memberApi.list).mockResolvedValue({
        ...directory,
        items: [],
        total: 0,
      });
      await userEvent.selectOptions(screen.getByLabelText(label), value);
      await waitFor(() => expect(count).toHaveTextContent("Active members0"));
      expect(count).toHaveTextContent("Matching your filters");
      vi.mocked(memberApi.list).mockResolvedValue(directory);
      await userEvent.selectOptions(screen.getByLabelText(label), "");
      await waitFor(() => expect(count).toHaveTextContent("199"));
      expect(count).toHaveTextContent("In the member directory");
    },
  );
  it("filters members by country and resets pagination while preserving search", async () => {
    vi.mocked(memberApi.list).mockResolvedValue({
      ...result,
      countries: ["Sweden", "United States"],
    });
    show("/members?search=member&page=2");
    await screen.findByRole("option", { name: "Sweden" });
    await userEvent.selectOptions(screen.getByLabelText("Country"), "Sweden");
    await waitFor(() =>
      expect(memberApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({
          search: "member",
          country: "Sweden",
          page: 1,
        }),
      ),
    );
    await userEvent.selectOptions(screen.getByLabelText("Country"), "");
    await waitFor(() =>
      expect(memberApi.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ country: "", page: 1 }),
      ),
    );
  });
  it("automatically embeds the selected profile PDF", async () => {
    show("/profiles/" + profiles[0].profileId);
    expect(
      await screen.findByTitle("PDF preview for " + profiles[0].name),
    ).toHaveAttribute("src", "https://private.example/preview.pdf");
    expect(api.document).toHaveBeenCalledWith(profiles[0].profileId, false);
  });
  it("lets the user retry a failed PDF preview", async () => {
    vi.mocked(api.document).mockRejectedValueOnce(
      new Error("Preview unavailable"),
    );
    show("/profiles/" + profiles[0].profileId);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Preview unavailable",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Reload preview" }),
    );
    expect(
      await screen.findByTitle("PDF preview for " + profiles[0].name),
    ).toBeInTheDocument();
  });
  it("downloads through a temporary document URL", async () => {
    const tab = { opener: null, location: { href: "" }, close: vi.fn() };
    vi.spyOn(window, "open").mockReturnValue(tab as unknown as Window);
    vi.mocked(api.document).mockResolvedValue({
      url: "https://private.example/signed",
      expiresIn: 900,
      fileName: "amit.pdf",
    });
    show("/profiles/" + profiles[0].profileId);
    await userEvent.click(
      await screen.findByRole("button", { name: "Download PDF" }),
    );
    await waitFor(() =>
      expect(tab.location.href).toBe("https://private.example/signed"),
    );
    expect(api.document).toHaveBeenCalledWith(profiles[0].profileId, true);
  });
  it("starts sync and displays the completed summary", async () => {
    vi.mocked(api.sync).mockResolvedValue({
      jobId: "job",
      status: "COMPLETED",
      processed: 3,
      created: 1,
      updated: 1,
      unchanged: 1,
      failed: 0,
      error: null,
      updatedAt: new Date().toISOString(),
    });
    show();
    await userEvent.click(
      await screen.findByRole("button", { name: "Sync Now" }),
    );
    expect(
      await screen.findByText(/Sync completed · 3 processed/),
    ).toBeInTheDocument();
  });
  it("shows a loading state", async () => {
    vi.mocked(api.list).mockReturnValue(new Promise(() => {}));
    show();
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Loading profiles",
    );
  });
  it("shows a friendly loading error", async () => {
    vi.mocked(api.list).mockRejectedValue(
      new Error("Unable to load profiles."),
    );
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load profiles.",
    );
  });
  it("shows an empty state", async () => {
    vi.mocked(api.list).mockResolvedValue({ ...result, items: [], total: 0 });
    show();
    expect(
      await screen.findByRole("heading", { name: "No submissions found" }),
    ).toBeInTheDocument();
  });
  it("shows missing document clearly", async () => {
    vi.mocked(api.get).mockResolvedValue({ ...profiles[0], pdf: null });
    show("/profiles/" + profiles[0].profileId);
    expect(
      await screen.findByText("No profile document available."),
    ).toBeInTheDocument();
  });
});

it("allows the owner to edit and save member information", async () => {
  const profile = {
    ...profiles[0],
    email: "admin@example.com",
    name: "Original Owner",
  };
  vi.mocked(memberApi.get).mockResolvedValue(profile);
  vi.mocked(memberApi.update).mockResolvedValue({
    ...profile,
    name: "Updated Owner",
  });
  show("/members/" + encodeURIComponent(profile.email));
  await userEvent.click(
    await screen.findByRole("button", { name: "Edit my information" }),
  );
  await userEvent.clear(screen.getByLabelText("Full Name"));
  await userEvent.type(screen.getByLabelText("Full Name"), "Updated Owner");
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(
    await screen.findByRole("heading", { name: "Updated Owner" }),
  ).toBeInTheDocument();
  expect(memberApi.update).toHaveBeenCalledWith(
    profile.email,
    expect.objectContaining({ "Full Name": "Updated Owner" }),
  );
});
it("does not offer editing on another member's information", async () => {
  vi.mocked(memberApi.get).mockResolvedValue({
    ...profiles[0],
    email: "other@yahoo.com",
  });
  show("/members/other%40yahoo.com");
  await screen.findByRole("heading", { name: profiles[0].name });
  expect(
    screen.queryByRole("button", { name: "Edit my information" }),
  ).not.toBeInTheDocument();
});

it("signs up with email, resends and verifies before administrator approval", async () => {
  vi.mocked(currentUser).mockResolvedValue(null);
  vi.mocked(registerEmail).mockResolvedValue(false);
  vi.mocked(verifySignup).mockResolvedValue();
  vi.mocked(resendSignup).mockResolvedValue();
  show("/signup");
  await userEvent.type(
    await screen.findByLabelText("Email"),
    "member@yahoo.com",
  );
  await userEvent.type(screen.getByLabelText("Password"), "ExamplePass123!");
  await userEvent.type(
    screen.getByLabelText("Confirm password"),
    "ExamplePass123!",
  );
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  expect(registerEmail).toHaveBeenCalledWith(
    "member@yahoo.com",
    "ExamplePass123!",
  );
  await userEvent.click(
    await screen.findByRole("button", { name: "Resend code" }),
  );
  expect(resendSignup).toHaveBeenCalledWith("member@yahoo.com");
  await userEvent.type(screen.getByLabelText("Verification code"), "123456");
  await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
  expect(
    await screen.findByText(/Your account is ready for administrator approval/),
  ).toBeInTheDocument();
  expect(verifySignup).toHaveBeenCalledWith("member@yahoo.com", "123456");
});
it("keeps invalid verification codes retryable", async () => {
  vi.mocked(currentUser).mockResolvedValue(null);
  vi.mocked(verifySignup).mockRejectedValue(
    new Error("Invalid verification code"),
  );
  show("/signup");
  await userEvent.click(
    await screen.findByRole("button", {
      name: "Already have a verification code?",
    }),
  );
  await userEvent.type(screen.getByLabelText("Email"), "member@yahoo.com");
  await userEvent.type(screen.getByLabelText("Verification code"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Verify email" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid verification code",
  );
  expect(screen.getByRole("button", { name: "Verify email" })).toBeEnabled();
});

it("opens the Members map beside its heading and filters by clicking a country", async () => {
  vi.mocked(memberApi.list).mockResolvedValue({
    ...result,
    totalProfiles: 40,
    mapTotal: 40,
    countries: ["Canada", "Sweden"],
    countryCounts: [
      { country: "Sweden", count: 31 },
      { country: "Canada", count: 9 },
    ],
  });
  show("/members");
  await userEvent.click(
    await screen.findByRole("button", { name: "Map", exact: true }),
  );
  expect(
    await screen.findByRole("region", { name: "Member distribution map" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/40 members across 2 mapped countries/),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Sweden: 31 members" }),
  );
  await waitFor(() =>
    expect(memberApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ country: "Sweden", page: 1 }),
    ),
  );
  expect(
    await screen.findByRole("button", { name: "Show all countries" }),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "List", exact: true }),
  );
  expect(
    screen.queryByRole("region", { name: "Member distribution map" }),
  ).not.toBeInTheDocument();
});
it("shows unmapped members and permits keyboard country selection", async () => {
  vi.mocked(memberApi.list).mockResolvedValue({
    ...result,
    countryCounts: [
      { country: "Canada", count: 2 },
      { country: "Not specified", count: 1 },
    ],
    mapTotal: 3,
  });
  show("/members?view=map");
  const canada = await screen.findByRole("button", {
    name: "Canada: 2 members",
  });
  expect(screen.getByText(/Country entries not mapped: 1/)).toBeInTheDocument();
  act(() => canada.focus());
  await userEvent.keyboard("{Enter}");
  await waitFor(() =>
    expect(memberApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ country: "Canada" }),
    ),
  );
});

it("shows Idea Incubation and opens Sambhav next to Members", async () => {
  show();
  expect(
    await screen.findByRole("heading", { name: "Idea Incubation" }),
  ).toBeInTheDocument();
  const nav = screen.getByRole("navigation", { name: "Main navigation" });
  expect(
    Array.from(nav.querySelectorAll("a")).map((link) => link.textContent),
  ).toEqual(["Idea Incubation", "Members", "Sambhav", "Jobs"]);
  await userEvent.click(screen.getByRole("link", { name: "Sambhav" }));
  expect(
    await screen.findByRole("heading", { name: "Sambhav" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sambhav" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});
