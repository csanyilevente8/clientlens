import { useClients } from "@/features/clients/useClients";
import { CreateClientForm } from "./CreateClientForm";
import { Link } from "react-router-dom";

export function ClientsPage() {
    const {data, isLoading, error } = useClients();
    if (isLoading) return <p className="muted">Loading...</p>
    if (error) return <p className="error">Error: {error.message}</p>
    return (
        <div>
            <h2>Clients</h2>
            <div className="card">
                <CreateClientForm/>
            </div>
            <div className="card">
                {data && data.length > 0 ? (
                    <ul className="list">
                        {data.map((c) => (
                            <li className="list__item" key={c.id}>
                                <Link to={`/clients/${c.id}`}>{c.name}</Link>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="muted">No clients yet. Add one above.</p>
                )}
            </div>
        </div>
    )
}