import { apiPost } from "@/api/client";
import { SearchResponse } from "@/types/search";
import { useMutation } from "@tanstack/react-query";

export function useSearch() {
    return useMutation({
        mutationFn: (query: string) => 
            apiPost<SearchResponse>("/api/v1/search", { query }),
    });
};