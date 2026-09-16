import { accessToken, mockMode } from "../auth/client";
import type {
  Api,
  ListQuery,
  Profile,
  ProfilePage,
  SyncJob,
} from "../types/profile";
export async function request<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  let token: string;
  try {
    token = await accessToken();
  } catch {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Your session has expired. Please login again.");
  }
  const result = await fetch(
    import.meta.env.VITE_API_BASE_URL.replace(/\/$/, "") + path,
    {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(data ? { "Content-Type": "application/json" } : {}),
      },
      body: data ? JSON.stringify(data) : undefined,
    },
  );
  if (result.status === 401) {
    window.dispatchEvent(new Event("session-expired"));
    throw new Error("Your session has expired. Please login again.");
  }
  const body = await result.json();
  if (!result.ok)
    throw new Error(
      body.error ||
        (result.status === 403
          ? "Your account is not authorized to access profiles."
          : "Unable to complete this request."),
    );
  return body;
}
const realApi: Api = {
  list: (query: ListQuery) =>
    request(
      "/profiles?" +
        new URLSearchParams(
          Object.entries(query).map(([k, v]) => [k, String(v)]),
        ),
    ),
  get: (id) => request("/profiles/" + encodeURIComponent(id)),
  document: (id, download) =>
    request(
      `/profiles/${encodeURIComponent(id)}/document?disposition=${download ? "attachment" : "inline"}`,
    ),
  sync: () => request("/sync", "POST"),
  syncStatus: (id) =>
    request("/sync" + (id ? "/" + encodeURIComponent(id) : "")),
};
export const api: Api = mockMode
  ? (await import("./mockApi")).mockApi
  : realApi;

export const memberApi = {
  update: (email: string, fields: Record<string, string>): Promise<Profile> =>
    request(
      "/members/detail?" + new URLSearchParams({ email }),
      "POST",
      fields,
    ),
  sync: (): Promise<SyncJob> =>
    mockMode
      ? Promise.reject(new Error("Member sync is unavailable in demo mode."))
      : request("/members/sync", "POST"),
  syncStatus: (id?: string): Promise<SyncJob | null> =>
    mockMode
      ? Promise.resolve(null)
      : request("/members/sync" + (id ? "/" + encodeURIComponent(id) : "")),
  list: (query: ListQuery): Promise<ProfilePage> =>
    mockMode
      ? Promise.resolve({
          items: [],
          page: query.page || 1,
          pageSize: 25,
          total: 0,
          totalProfiles: 0,
          themes: [],
          lastSyncedAt: null,
        })
      : request(
          "/members?" +
            new URLSearchParams(
              Object.entries(query).map(([key, value]) => [key, String(value)]),
            ),
        ),
  get: (email: string): Promise<Profile> =>
    mockMode
      ? Promise.reject(new Error("Member not found in demo mode."))
      : request("/members/detail?" + new URLSearchParams({ email })),
};
