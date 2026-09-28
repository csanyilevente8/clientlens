import { useClients } from "@/features/clients/useClients";

export function ClientsPage() {
    const {data, isLoading, error } = useClients();
    if (isLoading) return <p>Loading...</p>
    if (error) return <p>Error: {error.message}</p>
    return (
        <ul>
            {data?.map((c) => <li key={c.id}>{c.name}</li>)}
        </ul>
    )
}