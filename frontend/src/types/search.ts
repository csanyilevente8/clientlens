export interface SearchSource {
  meeting_id: string;
  client_id: string;
  excerpt: string;
  score: number;
}
export interface SearchResponse {
  answer: string;
  sources: SearchSource[];
}