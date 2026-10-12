import { useCreateMeeting } from "@/features/meetings/useCreateMeeting";
import { FormEvent, useState } from "react";

export function CreateMeetingForm({ clientId } : {clientId: string }) {

    const { mutate, isPending, error } = useCreateMeeting(clientId);
    const [ title, setTitle ] = useState("");
    const [ transcript, setTranscript ] = useState("");

    function handleSubmit(event: FormEvent<HTMLFormElement>): void {
        event.preventDefault();
        mutate({client_id: clientId, title: title, occurred_at: new Date().toISOString(), transcript: transcript, }, 
        { onSuccess: () => { setTitle(""); setTranscript(""); } });
    }

    return (
        <form onSubmit={handleSubmit} className="stack">
            <div>
                <div className="row">
                    <label htmlFor="title">Meeting Title</label>
                    <input id="title"
                        type="text"
                        placeholder="e.g. Q3 portfolio review"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}/>
                </div>
                <div className="row">
                    <label htmlFor="transcript">Meeting Transcript</label>                    
                    <textarea id="transcript"
                        placeholder="Lorem ipsum..."
                        value={transcript}
                        onChange={(e) => setTranscript(e.target.value)}/>
                </div>
                <button type="submit" disabled={isPending || !title.trim()}>
                    {isPending ? "Adding..." : "Add meeting"}
                </button>
            </div>
            {error && <p className="error">{error.message}</p>}
        </form>
    );
}