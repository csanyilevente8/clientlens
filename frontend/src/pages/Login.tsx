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
        <div className="auth-wrap">
            <form className="card auth-card stack" onSubmit={handleSubmit}>
                <h2>Sign in to ClientLens</h2>

                <div>
                    <label htmlFor="slug">Tenant</label>
                    <input id="slug" value={slug} placeholder="acme" onChange={(e) => setSlug(e.target.value)} />
                </div>

                <div>
                    <label htmlFor="email">Email</label>
                    <input id="email" value={email} type="email" placeholder="you@example.com" onChange={(e) => setEmail(e.target.value)} />
                </div>

                <div>
                    <label htmlFor="password">Password</label>
                    <input id="password" value={password} type="password" placeholder="••••••••" onChange={(e) => setPassword(e.target.value)} />
                </div>

                {error && <p className="error">{error}</p>}

                <button type="submit">Log In</button>
            </form>
        </div>
    )
}