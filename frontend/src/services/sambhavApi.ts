import { mockMode } from "../auth/client";
import { request } from "./api";
import { sambhav } from "../programs/sambhav";
import type { SambhavDomain } from "../types/sambhav";
export const sambhavApi = {
  list: (): Promise<{ domains: SambhavDomain[]; canEdit: boolean }> =>
    mockMode
      ? Promise.resolve({
          domains: structuredClone(sambhav.domains),
          canEdit: true,
        })
      : request("/sambhav"),
  save: (domain: SambhavDomain): Promise<SambhavDomain> => {
    const data = {
      version: domain.version || 0,
      title: domain.title,
      description: domain.description || "",
      status: domain.status,
      ideas: domain.ideas.map((idea) => ({
        id: idea.id,
        title: idea.title,
        summary: idea.summary,
        description: idea.description,
        vision: idea.vision,
        status: idea.status,
        lead: idea.lead?.email || null,
        coLead: idea.coLead?.email || null,
        interestedMembers: idea.interestedMembers.map((member) => member.email),
      })),
    };
    if (mockMode)
      return Promise.resolve({ ...domain, version: (domain.version || 0) + 1 });
    return request(
      "/sambhav/domain?" + new URLSearchParams({ domain: domain.slug }),
      "POST",
      data,
    );
  },
  upload: async (
    domain: string,
    ideaId: string,
    category: string,
    file: File,
  ): Promise<SambhavDomain> => {
    if (mockMode) throw new Error("PDF uploads are unavailable in demo mode.");
    if (
      !file.name.toLowerCase().endsWith(".pdf") ||
      file.size < 1 ||
      file.size > 20 * 1024 * 1024
    )
      throw new Error("Choose a PDF up to 20 MB.");
    const query = new URLSearchParams({ domain });
    const ticket = await request<{
      uploadId: string;
      url: string;
      fields: Record<string, string>;
    }>("/sambhav/upload?" + query, "POST", {
      ideaId,
      category,
      fileName: file.name,
      size: file.size,
    });
    const form = new FormData();
    Object.entries(ticket.fields).forEach(([key, value]) =>
      form.append(key, value),
    );
    form.append("file", file);
    const result = await fetch(ticket.url, { method: "POST", body: form });
    if (!result.ok) throw new Error("File upload failed. Please try again.");
    return request("/sambhav/upload/complete?" + query, "POST", {
      uploadId: ticket.uploadId,
    });
  },
  document: (
    domain: string,
    idea: string,
    document: string,
  ): Promise<{ url: string }> =>
    request(
      "/sambhav/document?" + new URLSearchParams({ domain, idea, document }),
    ),
};
