import { apiPost } from "@/api/client";
import { Client } from "@/types/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function useCreateClient() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (name: string) => apiPost<Client>("/api/v1/clients", { name }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["clients"] });
        },
    });
}