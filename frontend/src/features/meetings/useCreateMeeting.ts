import { apiPost } from "@/api/client";
import { MeetingCreate } from "@/types/createMeeting";
import { Meeting } from "@/types/meeting";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useCreateMeeting(clientId: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (meeting: MeetingCreate) => apiPost<Meeting>("/api/v1/meetings", meeting),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["meetings", clientId] });
        },
    });
}