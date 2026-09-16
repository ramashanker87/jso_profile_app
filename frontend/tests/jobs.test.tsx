import { beforeEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../src/auth/AuthProvider";
import { App } from "../src/App";
import { jobsApi } from "../src/services/jobsApi";
vi.mock("../src/auth/client", () => ({
  mockMode: true,
  googleLoginEnabled: false,
  currentUser: vi.fn().mockResolvedValue("member@example.org"),
  hasAppAccess: vi.fn().mockResolvedValue(true),
  onAuthChange: vi.fn(() => () => {}),
  logout: vi.fn(),
}));
vi.mock("../src/services/jobsApi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/services/jobsApi")>()),
  jobsApi: {
    list: vi.fn(),
    create: vi.fn(),
    remove: vi.fn(),
    upload: vi.fn(),
    download: vi.fn(),
  },
}));
const job = {
  id: "job-one",
  url: "https://example.org/careers/123",
  title: "Engineer",
  createdAt: "2026-09-16T10:00:00Z",
};
function show() {
  return render(
    <MemoryRouter initialEntries={["/jobs"]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(jobsApi.list).mockResolvedValue({ items: [] });
  vi.mocked(jobsApi.create).mockResolvedValue(job);
  vi.mocked(jobsApi.remove).mockResolvedValue(undefined);
});
it("adds a pasted link, opens the original description, and persists on reload", async () => {
  const user = userEvent.setup();
  const view = show();
  expect(await screen.findByText("No job openings yet")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Jobs", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await user.type(screen.getByLabelText("Job-opening link"), job.url);
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(jobsApi.create).toHaveBeenCalledWith(job.url, "", "");
  const link = await screen.findByRole("link", {
    name: /View job description/,
  });
  expect(link).toHaveAttribute("href", job.url);
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
  expect(
    screen.getByRole("region", { name: "Job openings count" }),
  ).toHaveTextContent("1");
  expect(screen.getByLabelText("Job-opening link")).toHaveValue("");
  view.unmount();
  vi.mocked(jobsApi.list).mockResolvedValue({ items: [job] });
  show();
  expect(
    await screen.findByRole("link", { name: "Engineer" }),
  ).toBeInTheDocument();
});
it("requires confirmation, supports cancel, and removes a closed listing", async () => {
  vi.mocked(jobsApi.list).mockResolvedValue({ items: [job] });
  const user = userEvent.setup();
  show();
  await user.click(
    await screen.findByRole("button", { name: "Delete closed job" }),
  );
  expect(jobsApi.remove).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(
    screen.queryByRole("button", { name: "Confirm delete" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Delete closed job" }));
  await user.click(screen.getByRole("button", { name: "Confirm delete" }));
  expect(await screen.findByText("No job openings yet")).toBeInTheDocument();
  expect(jobsApi.remove).toHaveBeenCalledWith(job.id);
  expect(
    screen.getByRole("region", { name: "Job openings count" }),
  ).toHaveTextContent("0");
});
it("retains the job when deletion fails and permits retry", async () => {
  vi.mocked(jobsApi.list).mockResolvedValue({ items: [job] });
  vi.mocked(jobsApi.remove).mockRejectedValueOnce(
    new Error("Unable to delete."),
  );
  const user = userEvent.setup();
  show();
  await user.click(
    await screen.findByRole("button", { name: "Delete closed job" }),
  );
  await user.click(screen.getByRole("button", { name: "Confirm delete" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to delete.",
  );
  expect(screen.getByRole("link", { name: "Engineer" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Confirm delete" }));
  expect(await screen.findByText("No job openings yet")).toBeInTheDocument();
});
it("preserves input after duplicate errors and rejects unsafe URL schemes", async () => {
  vi.mocked(jobsApi.create).mockRejectedValueOnce(
    new Error("This job-opening link has already been added."),
  );
  const user = userEvent.setup();
  show();
  const input = await screen.findByLabelText("Job-opening link");
  await user.type(input, job.url);
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "already been added",
  );
  expect(input).toHaveValue(job.url);
  await user.clear(input);
  await user.type(input, "javascript:alert(1)");
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "valid http:// or https://",
  );
  expect(jobsApi.create).toHaveBeenCalledTimes(1);
});
it("retries a failed list request", async () => {
  vi.mocked(jobsApi.list).mockRejectedValueOnce(
    new Error("Unable to load jobs."),
  );
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to load jobs.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("No job openings yet")).toBeInTheDocument();
});

it("saves descriptions and both attachment categories, then downloads a file", async () => {
  const user = userEvent.setup();
  const candidate = new File(["pdf"], "candidate.pdf", {
    type: "application/pdf",
  });
  const profile = new File(["pdf"], "role.pdf", { type: "application/pdf" });
  const first = {
    ...job,
    description: "Remote role",
    attachments: [
      {
        id: "candidate",
        category: "candidate-profile" as const,
        fileName: candidate.name,
        size: 3,
      },
    ],
  };
  const complete = {
    ...first,
    attachments: [
      ...first.attachments,
      {
        id: "role",
        category: "job-profile" as const,
        fileName: profile.name,
        size: 3,
      },
    ],
  };
  vi.mocked(jobsApi.upload)
    .mockResolvedValueOnce(first)
    .mockResolvedValueOnce(complete);
  vi.mocked(jobsApi.download).mockResolvedValue(undefined);
  show();
  await user.type(await screen.findByLabelText("Job-opening link"), job.url);
  await user.type(
    screen.getByLabelText("Short description (optional)"),
    "Remote role",
  );
  await user.upload(screen.getByLabelText("Candidate profiles"), candidate);
  await user.upload(screen.getByLabelText("Job profiles"), profile);
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(
    await screen.findByText("Job opening added with attachments."),
  ).toBeInTheDocument();
  expect(jobsApi.create).toHaveBeenCalledWith(job.url, "", "Remote role");
  expect(jobsApi.upload).toHaveBeenNthCalledWith(
    1,
    job.id,
    "candidate-profile",
    candidate,
  );
  expect(jobsApi.upload).toHaveBeenNthCalledWith(
    2,
    job.id,
    "job-profile",
    profile,
  );
  expect(screen.getByText("Remote role")).toBeInTheDocument();
  expect(screen.getByLabelText("Short description (optional)")).toHaveValue("");
  await user.click(
    screen.getByRole("button", { name: "Download candidate.pdf" }),
  );
  expect(jobsApi.download).toHaveBeenCalledWith(job.id, "candidate");
});

it("retries only remaining attachments without creating another job", async () => {
  const user = userEvent.setup();
  const first = new File(["pdf"], "first.pdf", { type: "application/pdf" });
  const second = new File(["pdf"], "second.pdf", { type: "application/pdf" });
  const saved = {
    ...job,
    attachments: [
      {
        id: "first",
        category: "job-profile" as const,
        fileName: "first.pdf",
        size: 3,
      },
    ],
  };
  vi.mocked(jobsApi.upload)
    .mockResolvedValueOnce(saved)
    .mockRejectedValueOnce(new Error("Network error."))
    .mockResolvedValueOnce({
      ...saved,
      attachments: [
        ...saved.attachments,
        { ...saved.attachments[0], id: "second", fileName: "second.pdf" },
      ],
    });
  show();
  await user.type(await screen.findByLabelText("Job-opening link"), job.url);
  await user.upload(screen.getByLabelText("Job profiles"), [first, second]);
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Job saved.");
  expect(
    screen.getByRole("button", { name: "Download first.pdf" }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry attachments" }));
  expect(
    await screen.findByText("Job opening added with attachments."),
  ).toBeInTheDocument();
  expect(jobsApi.create).toHaveBeenCalledTimes(1);
  expect(jobsApi.upload).toHaveBeenCalledTimes(3);
  expect(jobsApi.upload).toHaveBeenLastCalledWith(
    job.id,
    "job-profile",
    second,
  );
});

it("keeps a saved job when the user skips a failed attachment", async () => {
  const user = userEvent.setup();
  vi.mocked(jobsApi.upload).mockRejectedValueOnce(new Error("Invalid PDF."));
  show();
  await user.type(await screen.findByLabelText("Job-opening link"), job.url);
  await user.upload(
    screen.getByLabelText("Candidate profiles"),
    new File(["pdf"], "bad.pdf", { type: "application/pdf" }),
  );
  await user.click(screen.getByRole("button", { name: "Add job" }));
  await user.click(
    await screen.findByRole("button", {
      name: "Keep job without remaining attachments",
    }),
  );
  expect(screen.getByRole("link", { name: "Engineer" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add job" })).toBeEnabled();
  expect(screen.getByLabelText("Job-opening link")).toHaveValue("");
  expect(jobsApi.remove).not.toHaveBeenCalled();
});

it("rejects too many attachments before creating the job", async () => {
  const user = userEvent.setup();
  show();
  await user.type(await screen.findByLabelText("Job-opening link"), job.url);
  await user.upload(
    screen.getByLabelText("Job profiles"),
    Array.from(
      { length: 11 },
      (_, i) => new File(["pdf"], `${i}.pdf`, { type: "application/pdf" }),
    ),
  );
  await user.click(screen.getByRole("button", { name: "Add job" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("10 attachments");
  expect(jobsApi.create).not.toHaveBeenCalled();
});

it("shows a download error and disables uploads when local storage is unavailable", async () => {
  vi.mocked(jobsApi.list).mockResolvedValue({
    items: [
      {
        ...job,
        attachments: [
          {
            id: "doc",
            category: "job-profile",
            fileName: "job.pdf",
            size: 100,
          },
        ],
      },
    ],
    uploadsEnabled: false,
  });
  vi.mocked(jobsApi.download).mockRejectedValueOnce(
    new Error("Download unavailable."),
  );
  show();
  await userEvent.click(
    await screen.findByRole("button", { name: "Download job.pdf" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Download unavailable.",
  );
  expect(screen.getByLabelText("Job profiles")).toBeDisabled();
});
