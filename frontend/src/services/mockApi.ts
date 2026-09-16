import sampleProfiles from "./sampleProfiles.json";
import type { Api, Profile, SyncJob } from "../types/profile";
const wait = () => new Promise((resolve) => setTimeout(resolve, 200));
const profiles = sampleProfiles as Profile[];
let job: SyncJob | null = null;
export const mockApi: Api = {
  async list({ search = "", theme = "", page = 1, pageSize = 25 }) {
    await wait();
    const query = search.toLowerCase();
    const items = profiles.filter(
      (p) =>
        (!theme || p.theme === theme) &&
        [p.name, p.email, p.linkedinUrl, p.theme, p.supportRaw]
          .join(" ")
          .toLowerCase()
          .includes(query),
    );
    return {
      items: items.slice((page - 1) * pageSize, page * pageSize),
      page,
      pageSize,
      total: items.length,
      totalProfiles: profiles.length,
      themes: [...new Set(profiles.map((p) => p.theme))].sort(),
      lastSyncedAt: job?.updatedAt || profiles[0].lastSyncedAt,
    };
  },
  async get(id) {
    await wait();
    const p = profiles.find((p) => p.profileId === id);
    if (!p) throw new Error("Profile not found.");
    return p;
  },
  async document(id) {
    await wait();
    const p = profiles.find((p) => p.profileId === id);
    if (!p?.pdf) throw new Error("PDF is not available.");
    return {
      url: "/sample-profile.pdf",
      expiresIn: 900,
      fileName: p.pdf.fileName,
    };
  },
  async sync() {
    await wait();
    job = {
      jobId: "mock-sync",
      status: "RUNNING",
      processed: 0,
      created: 0,
      updated: 0,
      unchanged: 0,
      failed: 0,
      error: null,
      updatedAt: new Date().toISOString(),
    };
    return { ...job };
  },
  async syncStatus() {
    await wait();
    if (job)
      job = {
        ...job,
        status: "COMPLETED",
        processed: 3,
        unchanged: 3,
        updatedAt: new Date().toISOString(),
      };
    return job ? { ...job } : null;
  },
};
