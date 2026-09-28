import { apiPost } from "@/api/client";
import { setToken } from "@/auth/token";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

export function Login() {
    const [slug, setSlug] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [error, setError] = useState("")
    const navigate = useNavigate();

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        try {
            const res = await apiPost<{ access_token: string }>("/api/v1/auth/login", {
                tenant_slug: slug, email, password,
            });
            setToken(res.access_token);
            navigate("/clients");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Login failed");
        }
    }

    return(
    <form onSubmit={handleSubmit}>
        <label htmlFor="slug">Tenant</label>
        <input id="slug" value={slug} placeholder="Tenant" onChange={(e) => setSlug(e.target.value)} />
        
        <label htmlFor="email">Tenant</label>
        <input id="email" value={email} type="email" placeholder="Email" onChange={(e) => setEmail(e.target.value)} />
        
        <label htmlFor="password">Tenant</label>        
        <input id="password" value={password} type="password" placeholder="Password" onChange={(e) => setPassword(e.target.value)} />

        {error && <p style={{ color: "red" }}>{error}</p>}

        <button type="submit">Log In</button>
    </form>
    )
}