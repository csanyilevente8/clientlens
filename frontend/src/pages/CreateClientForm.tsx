import { useCreateClient } from "@/features/clients/useCreateClient";
import { FormEvent, useState } from "react";

export function CreateClientForm() {
  const [name, setName] = useState("");
    const {mutate, isPending, error} = useCreateClient();

    function handleSubmit(event: FormEvent<HTMLFormElement>): void {
        event.preventDefault();
        mutate(name, { onSuccess: () => setName("") });
    }

    return (
        <form onSubmit={handleSubmit} className="stack">
            <div>
                <label htmlFor="name">Client name</label>
                <div className="row">
                    <input id="name"
                        type="text"
                        placeholder="e.g. Jane Smith"
                        value={name}
                        onChange={(e) => setName(e.target.value)}/>
                    <button type="submit" disabled={isPending || !name.trim()}>
                        {isPending ? "Adding..." : "Add client"}
                    </button>
                </div>
            </div>

            {error && <p className="error">{error.message}</p>}
        </form>
    )
}