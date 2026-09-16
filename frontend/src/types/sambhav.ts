export type SambhavStatus = "Not started" | "In progress" | "Completed";
// References point to the existing email-keyed member directory.
export interface SambhavMember {
  email: string;
  name: string;
}
export interface SambhavDocument {
  id: string;
  title: string;
  url?: string;
  fileName?: string;
  size?: number;
  uploadedAt?: string;
}
export interface SambhavIdea {
  id: string;
  title: string;
  summary: string;
  description: string;
  vision: string;
  status: SambhavStatus;
  lead: SambhavMember | null;
  coLead: SambhavMember | null;
  interestedMembers: SambhavMember[];
  visionDocuments: SambhavDocument[];
  projectDocuments: SambhavDocument[];
  memberProfileDocuments?: SambhavDocument[];
  otherDocuments?: SambhavDocument[];
  updatedAt: string | null;
}
export interface SambhavDomain {
  version?: number;
  updatedAt?: string | null;
  code: string;
  title: string;
  slug: string;
  sourcePageReference: number;
  description?: string;
  status: SambhavStatus;
  ideas: [SambhavIdea, SambhavIdea, SambhavIdea];
}
