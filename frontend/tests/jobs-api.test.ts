import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { jobsApi, validateJobFiles } from "../src/services/jobsApi";
import { request } from "../src/services/api";

vi.mock("../src/auth/client", () => ({ mockMode: false }));
vi.mock("../src/services/api", () => ({ request: vi.fn() }));

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

it("retries confirmation without re-uploading bytes when its response is lost", async () => {
  const file = new File(["pdf"], "candidate.pdf", { type: "application/pdf" });
  const transfer = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", transfer);
  vi.mocked(request)
    .mockResolvedValueOnce({
      uploadId: "ticket-one",
      url: "https://bucket.example",
      fields: { key: "pending/file.pdf", policy: "signed" },
    })
    .mockRejectedValueOnce(new Error("Response lost"))
    .mockResolvedValueOnce({ id: "job", attachments: [{ id: "ticket-one" }] });
  await expect(
    jobsApi.upload("job", "candidate-profile", file),
  ).rejects.toThrow("Response lost");
  const result = await jobsApi.upload("job", "candidate-profile", file);
  expect(result.attachments).toHaveLength(1);
  expect(transfer).toHaveBeenCalledTimes(1);
  const options = transfer.mock.calls[0][1];
  expect(options.headers).toBeUndefined(); // Never send the Cognito token to S3.
  expect(options.body.get("key")).toBe("pending/file.pdf");
  expect(options.body.get("file")).toBeInstanceOf(File);
  expect(request).toHaveBeenNthCalledWith(
    2,
    "/job-openings/job/upload/complete",
    "POST",
    { uploadId: "ticket-one" },
  );
  expect(request).toHaveBeenNthCalledWith(
    3,
    "/job-openings/job/upload/complete",
    "POST",
    { uploadId: "ticket-one" },
  );
});

it("does not confirm a failed S3 transfer and obtains a new form on retry", async () => {
  const file = new File(["pdf"], "job.pdf", { type: "application/pdf" });
  const transfer = vi
    .fn()
    .mockResolvedValueOnce({ ok: false })
    .mockResolvedValueOnce({ ok: true });
  vi.stubGlobal("fetch", transfer);
  vi.mocked(request)
    .mockResolvedValueOnce({
      uploadId: "failed",
      url: "https://bucket.example",
      fields: {},
    })
    .mockResolvedValueOnce({
      uploadId: "retry",
      url: "https://bucket.example",
      fields: {},
    })
    .mockResolvedValueOnce({ id: "job", attachments: [] });
  await expect(jobsApi.upload("job", "job-profile", file)).rejects.toThrow(
    "File upload failed",
  );
  expect(request).toHaveBeenCalledTimes(1);
  await jobsApi.upload("job", "job-profile", file);
  expect(request).toHaveBeenLastCalledWith(
    "/job-openings/job/upload/complete",
    "POST",
    { uploadId: "retry" },
  );
});

it("rejects empty, oversized, and unsupported files before network requests", async () => {
  const oversized = new File(["pdf"], "big.pdf", { type: "application/pdf" });
  Object.defineProperty(oversized, "size", { value: 20 * 1024 * 1024 + 1 });
  for (const file of [
    new File([], "empty.pdf"),
    new File(["doc"], "job.docx"),
    oversized,
  ]) {
    expect(() => validateJobFiles([{ file, category: "job-profile" }])).toThrow(
      "Choose PDF files",
    );
    await expect(jobsApi.upload("job", "job-profile", file)).rejects.toThrow(
      "Choose PDF files",
    );
  }
  expect(request).not.toHaveBeenCalled();
});
