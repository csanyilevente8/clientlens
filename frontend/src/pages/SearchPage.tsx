import { useSearch } from "@/features/search/useSearch";
import { useState } from "react";

export function SearchPage() {

    const [query, setQuery] = useState("");
    const { mutate, data, isPending, error } = useSearch();
    
    function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!query.trim()) return;
        mutate(query);
    }
    
    return (
    <div>
      <h2>Search</h2>

      {/* --- the query form --- */}
      <form onSubmit={handleSubmit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about a client's history..."
        />
        <button type="submit" disabled={isPending || !query.trim()}>
          {isPending ? "Searching..." : "Search"}
        </button>
      </form>

      {/* --- error state --- */}
      {error && <p style={{ color: "red" }}>{error.message}</p>}

      {/* --- results (only after a successful search) --- */}
      {data && (
        <div>
          {/* the RAG answer */}
          <section>
            <h3>Answer</h3>
            <p>{data.answer}</p>
          </section>

          {/* the sources it was grounded in */}
          <section>
            <h3>Sources</h3>
            <ul>
              {data.sources.map((s) => (
                <li key={s.meeting_id}>
                  {s.excerpt} <small>(meeting {s.meeting_id})</small>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>    
    )
}