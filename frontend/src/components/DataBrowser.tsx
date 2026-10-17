import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { describe, listData } from "../api/endpoints";
import type { Collection, DataList } from "../api/types";

const COLLECTIONS: Collection[] = ["users", "user-permissions"];
const PAGE_SIZES = [5, 10, 25];

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function DataBrowser() {
  const [collection, setCollection] = useState<Collection>("users");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [result, setResult] = useState<DataList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [schema, setSchema] = useState<unknown>(null);
  const [showSchema, setShowSchema] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listData(collection, page, pageSize)
      .then((res) => !cancelled && setResult(res))
      .catch((e) => {
        if (cancelled) return;
        setResult(null);
        setError(e instanceof ApiError ? e.display : "Something went wrong");
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [collection, page, pageSize]);

  async function toggleSchema() {
    if (showSchema) return setShowSchema(false);
    try {
      setSchema(await describe(collection));
      setShowSchema(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.display : "Something went wrong");
    }
  }

  const rows = result?.data ?? [];
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  // The API's total_page is not reliable for Postgres lists (it counts only the current page),
  // so "full page" is the only dependable sign that another page may exist.
  const hasNext = rows.length === pageSize;

  return (
    <section className="card" aria-labelledby="data-title">
      <h2 id="data-title">Data browser</h2>

      <div className="toolbar">
        <label>
          Collection
          <select
            value={collection}
            onChange={(e) => {
              setCollection(e.target.value as Collection);
              setPage(1);
              setShowSchema(false);
            }}
          >
            {COLLECTIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Rows per page
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
          >
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={toggleSchema}>
          {showSchema ? "Hide schema" : "Show schema"}
        </button>
      </div>

      {error && (
        <p className="banner error" role="alert">
          {error}
        </p>
      )}
      {loading && <p aria-live="polite">Loading…</p>}

      {!loading && !error && rows.length === 0 && <p>No rows on this page.</p>}
      {rows.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => (
                    <td key={c}>{cell(row[c])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <button type="button" disabled={page === 1 || loading} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span>Page {page}</span>
        <button type="button" disabled={!hasNext || loading} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>

      {showSchema && (
        <pre className="schema" aria-label="Schema">
          {JSON.stringify(schema, null, 2)}
        </pre>
      )}
    </section>
  );
}
