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
        <form onSubmit={handleSubmit}>
            <label htmlFor="name">Client Name</label>
            <input id="name" 
                type="text" 
                value={name} 
                onChange={(e) => setName(e.target.value)}/>

            <button type="submit" disabled={isPending || !name.trim()}>
                {isPending ? "Adding..." : "Add client"}
            </button>

            {error && <p style={{ color: "red" }}>{error.message}</p>}
        </form>
    )
}