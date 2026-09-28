export interface Client {
  id: string;
  tenant_id: string;
  name: string;
  created_at: string;   // ISO datetime comes over the wire as string
  updated_at: string;
}