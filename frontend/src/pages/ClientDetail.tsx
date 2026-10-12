import { useClient } from "@/features/clients/useClient";
import { useClientMeetings } from "@/features/meetings/useClientMeetings";
import { useParams, Link } from "react-router-dom"
import { CreateMeetingForm } from "./CreateMeetingForm";

const badgeClass: Record<string, string> = {
    CREATED: "badge badge--created",
    PROCESSING: "badge badge--processing",
    COMPLETED: "badge badge--completed",
    FAILED: "badge badge--failed",
};

export function ClientDetail() {

    const { id } = useParams();
    const { data: client, isLoading, error } = useClient(id!);
    const { data: meetings } = useClientMeetings(id!);

    if (isLoading) return <p className="muted">Loading...</p>;
    if (error) return <p className="error">Error: {error.message}</p>;
    if (!client) return null;

    return (
        <div>
            <p><Link to="/clients">← Clients</Link></p>
            <h2>{client.name}</h2>

            <div className="card">
                <h3>New meeting</h3>
                <CreateMeetingForm clientId={client.id} />
            </div>
            
            <div className="card">
                <h3>Meetings</h3>
                {meetings && meetings.length > 0 ? (
                    <ul className="list">
                        {meetings.map((m) => (
                            <li className="list__item" key={m.id}>
                                <span>{m.title}</span>
                                <span className={badgeClass[m.status] ?? "badge"}>{m.status}</span>
                            </li>
                        ))}
                    </ul>
                ) : (
                    <p className="muted">No meetings for this client yet.</p>
                )}
            </div>
        </div>
    );
}