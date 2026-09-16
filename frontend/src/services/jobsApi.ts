import { mockMode } from "../auth/client";
import { request } from "./api";

export type JobAttachmentCategory = "candidate-profile" | "job-profile";
export type JobAttachment = {
  id: string;
  category: JobAttachmentCategory;
  fileName: string;
  size: number;
};
export type JobOpening = {
  id: string;
  url: string;
  title: string;
  description?: string;
  attachments?: JobAttachment[];
  createdAt: string;
};
export type JobFile = { file: File; category: JobAttachmentCategory };
export const MAX_JOB_ATTACHMENTS = 10;
export function validateJobFiles(files: JobFile[]) {
  if (files.length > MAX_JOB_ATTACHMENTS)
    throw new Error("Each job supports up to 10 attachments.");
  for (const { file } of files) {
    if (
      !file.name.toLowerCase().endsWith(".pdf") ||
      file.name.length > 180 ||
      /[/\\\x00-\x1f\x7f]/.test(file.name) ||
      file.size < 1 ||
      file.size > 20 * 1024 * 1024
    )
      throw new Error(
        "Choose PDF files up to 20 MB each, with filenames up to 180 characters.",
      );
  }
}

let demoJobs: JobOpening[] = [];
const demoDocuments = new Map<string, string>();
// Preserve a successful S3 transfer if confirmation fails or its response is lost.
const pendingUploads = new WeakMap<
  File,
  Map<string, { uploadId: string; expires: number }>
>();
const path = (id: string) => "/job-openings/" + encodeURIComponent(id);

export const jobsApi = {
  list: (): Promise<{ items: JobOpening[]; uploadsEnabled?: boolean }> =>
    mockMode
      ? Promise.resolve({
          items: structuredClone(demoJobs),
          uploadsEnabled: true,
        })
      : request("/job-openings"),
  create: async (
    url: string,
    title: string,
    description = "",
  ): Promise<JobOpening> => {
    if (!mockMode)
      return request("/job-openings", "POST", { url, title, description });
    const normalized = new URL(url).href;
    if (demoJobs.some((job) => job.url === normalized))
      throw new Error("This job-opening link has already been added.");
    const job = {
      id: crypto.randomUUID(),
      url: normalized,
      title: title.trim() || new URL(url).hostname,
      description,
      attachments: [],
      createdAt: new Date().toISOString(),
    };
    demoJobs = [job, ...demoJobs];
    return structuredClone(job);
  },
  upload: async (
    id: string,
    category: JobAttachmentCategory,
    file: File,
  ): Promise<JobOpening> => {
    validateJobFiles([{ file, category }]);
    if (mockMode) {
      const job = demoJobs.find((item) => item.id === id);
      if (!job) throw new Error("Job opening not found.");
      if ((job.attachments?.length || 0) >= MAX_JOB_ATTACHMENTS)
        throw new Error("Each job supports up to 10 attachments.");
      const attachment = {
        id: crypto.randomUUID(),
        category,
        fileName: file.name,
        size: file.size,
      };
      demoDocuments.set(attachment.id, URL.createObjectURL(file));
      job.attachments = [...(job.attachments || []), attachment];
      return structuredClone(job);
    }
    const key = `${id}/${category}`;
    const pending = pendingUploads.get(file) || new Map();
    pendingUploads.set(file, pending);
    let ticket = pending.get(key);
    if (!ticket || ticket.expires < Date.now()) {
      const post = await request<{
        uploadId: string;
        url: string;
        fields: Record<string, string>;
      }>(path(id) + "/upload", "POST", {
        category,
        fileName: file.name,
        size: file.size,
      });
      const form = new FormData();
      Object.entries(post.fields).forEach(([name, value]) =>
        form.append(name, value),
      );
      form.append("file", file);
      const response = await fetch(post.url, { method: "POST", body: form });
      if (!response.ok) throw new Error("File upload failed. Please retry.");
      ticket = {
        uploadId: post.uploadId,
        expires: Date.now() + 50 * 60 * 1000,
      };
      pending.set(key, ticket);
    }
    const job = await request<JobOpening>(
      path(id) + "/upload/complete",
      "POST",
      { uploadId: ticket.uploadId },
    );
    pending.delete(key);
    return job;
  },
  download: async (id: string, documentId: string): Promise<void> => {
    const link = mockMode
      ? { url: demoDocuments.get(documentId) }
      : await request<{ url: string }>(
          path(id) + "/attachments/" + encodeURIComponent(documentId),
        );
    if (!link.url) throw new Error("Attachment is no longer available.");
    const anchor = document.createElement("a");
    anchor.href = link.url;
    if (mockMode)
      anchor.download =
        demoJobs
          .find((job) => job.id === id)
          ?.attachments?.find((doc) => doc.id === documentId)?.fileName ||
        "attachment.pdf";
    anchor.rel = "noopener noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  },
  remove: async (id: string): Promise<void> => {
    if (mockMode) {
      for (const attachment of demoJobs.find((job) => job.id === id)
        ?.attachments || []) {
        const url = demoDocuments.get(attachment.id);
        if (url) URL.revokeObjectURL(url);
        demoDocuments.delete(attachment.id);
      }
      demoJobs = demoJobs.filter((job) => job.id !== id);
      return;
    }
    await request(path(id), "DELETE");
  },
};
