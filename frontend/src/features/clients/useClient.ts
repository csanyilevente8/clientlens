import { apiGet } from "@/api/client";
import { Client } from "@/types/client";
import { useQuery } from "@tanstack/react-query";

export function useClient(id: string) {
    return useQuery({
        queryKey: ["client", id],
        queryFn: () => apiGet<Client>(`/api/v1/clients/${id}`),
    });
}