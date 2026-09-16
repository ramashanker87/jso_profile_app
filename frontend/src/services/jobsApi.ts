import { mockMode } from "../auth/client";
import { request } from "./api";

export type JobOpening = {
  id: string;
  url: string;
  title: string;
  createdAt: string;
};

let demoJobs: JobOpening[] = [];

export const jobsApi = {
  list: (): Promise<{ items: JobOpening[] }> =>
    mockMode
      ? Promise.resolve({ items: [...demoJobs] })
      : request("/job-openings"),
  create: async (url: string, title: string): Promise<JobOpening> => {
    if (!mockMode) return request("/job-openings", "POST", { url, title });
    const normalized = new URL(url).href;
    if (demoJobs.some((job) => job.url === normalized))
      throw new Error("This job-opening link has already been added.");
    const job = {
      id: crypto.randomUUID(),
      url: normalized,
      title: title.trim() || new URL(url).hostname,
      createdAt: new Date().toISOString(),
    };
    demoJobs = [job, ...demoJobs];
    return job;
  },
  remove: async (id: string): Promise<void> => {
    if (mockMode) {
      demoJobs = demoJobs.filter((job) => job.id !== id);
      return;
    }
    await request("/job-openings/" + encodeURIComponent(id), "DELETE");
  },
};
