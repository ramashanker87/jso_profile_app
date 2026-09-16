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
vi.mock("../src/services/jobsApi", () => ({
  jobsApi: { list: vi.fn(), create: vi.fn(), remove: vi.fn() },
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
  expect(jobsApi.create).toHaveBeenCalledWith(job.url, "");
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
