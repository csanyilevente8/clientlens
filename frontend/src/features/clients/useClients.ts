import { apiGet } from "@/api/client";
import { Client } from "@/types/client";
import { useQuery } from "@tanstack/react-query";

export function useClients() {
    return useQuery({
        queryKey: ["clients"],
        queryFn: () => apiGet<Client[]>("/api/v1/clients"),
    })
}