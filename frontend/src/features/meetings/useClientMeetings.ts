import { apiGet } from "@/api/client"
import { Meeting } from "@/types/meeting"
import { useQuery } from "@tanstack/react-query"

export function useClientMeetings(clientId: string) {
    return useQuery({
        queryKey: ["meetings", clientId],
        queryFn: () => apiGet<Meeting[]>(`/api/v1/meetings?client_id=${clientId}`),
        refetchInterval: (query) => {
            const meetings = query.state.data;
            const anyPending = meetings?.some(
                (m) => m.status === "CREATED" || m.status === "PROCESSING"
            );
            return anyPending ? 2000 : false;
        }
    });
};