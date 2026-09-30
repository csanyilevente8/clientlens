import { useClients } from "@/features/clients/useClients";
import { CreateClientForm } from "./CreateClientForm";

export function ClientsPage() {
    const {data, isLoading, error } = useClients();
    if (isLoading) return <p>Loading...</p>
    if (error) return <p>Error: {error.message}</p>
    return (
        <div>
            <div>
                <CreateClientForm/>
            </div>
            <div>
                <ul>
                    {data?.map((c) => <li key={c.id}>{c.name}</li>)}
                </ul>
            </div>
        </div>
    )
}