import { useClient } from "@/features/clients/useClient";
import { useClientMeetings } from "@/features/meetings/useClientMeetings";
import { useParams } from "react-router-dom"

export function ClientDetail() {

    const { id } = useParams();
    const { data: client, isLoading, error } = useClient(id!);
    const { data: meetings } = useClientMeetings(id!);

    if (isLoading) return <p>Loading...</p>;
    if (error) return <p>Error: {error.message}</p>;
    if (!client) return null;

  return (
        <div>
        <h2>{client.name}</h2>
        <h3>Meetings</h3>
        <ul>
            {meetings?.map((m) => (
                <li key={m.id}>{m.title} — {m.status}</li>
            ))}
        </ul>
        </div>
    );
}