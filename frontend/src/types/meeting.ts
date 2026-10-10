export type MeetingStatus = "CREATED" | "PROCESSING" | "COMPLETED" | "FAILED";
// (confirm the exact enum values against the backend — see note below)

export interface Meeting {
  id: string;
  tenant_id: string;
  client_id: string;
  title: string;
  occurred_at: string;
  status: MeetingStatus;
  created_at: string;
  updated_at: string;
}
