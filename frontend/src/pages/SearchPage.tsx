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
      <form className="card" onSubmit={handleSubmit}>
        <div className="row">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about a client's history..."
          />
          <button type="submit" disabled={isPending || !query.trim()}>
            {isPending ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {/* --- error state --- */}
      {error && <p className="error">{error.message}</p>}

      {/* --- results (only after a successful search) --- */}
      {data && (
        <>
          <div className="card">
            <h3>Answer</h3>
            <p>{data.answer}</p>
          </div>

          <div className="card">
            <h3>Sources</h3>
            {data.sources.length > 0 ? (
              data.sources.map((s, i) => (
                <div className="source" key={`${s.meeting_id}-${i}`}>
                  <p className="source__excerpt">{s.excerpt}</p>
                  <p className="source__meta">meeting {s.meeting_id} · score {s.score.toFixed(3)}</p>
                </div>
              ))
            ) : (
              <p className="muted">No sources found.</p>
            )}
          </div>
        </>
      )}
    </div>
    )
}