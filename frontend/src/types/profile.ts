export interface Profile {
  member?: Record<string, string> | null;
  photoUrl?: string | null;
  profileId: string;
  submissionId: string;
  name: string;
  email: string;
  linkedinUrl: string;
  support: string[];
  supportRaw: string;
  theme: string;
  submissionDate: string;
  lastSyncedAt: string;
  createdAt: string;
  updatedAt: string;
  source: string;
  syncStatus: "SUCCESS" | "PARTIAL" | "FAILED";
  syncError: string | null;
  pdf: { fileName: string; contentType: string; size: number } | null;
}
export interface ProfilePage {
  items: Profile[];
  page: number;
  pageSize: number;
  total: number;
  totalProfiles: number;
  themes: string[];
  chapters?: string[];
  regions?: string[];
  countries?: string[];
  countryCounts?: { country: string; count: number }[];
  mapTotal?: number;
  lastSyncedAt: string | null;
}
export interface ListQuery {
  chapter?: string;
  region?: string;
  country?: string;
  search?: string;
  theme?: string;
  page?: number;
  pageSize?: number;
}
export interface DocumentLink {
  url: string;
  expiresIn: number;
  fileName: string;
}
export interface SyncJob {
  jobId: string;
  status: "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED";
  processed: number;
  created: number;
  updated: number;
  unchanged: number;
  failed: number;
  deleted?: number;
  error: string | null;
  updatedAt: string;
}
export interface Api {
  list(query: ListQuery): Promise<ProfilePage>;
  get(id: string): Promise<Profile>;
  document(id: string, download: boolean): Promise<DocumentLink>;
  sync(): Promise<SyncJob>;
  syncStatus(id?: string): Promise<SyncJob | null>;
}
