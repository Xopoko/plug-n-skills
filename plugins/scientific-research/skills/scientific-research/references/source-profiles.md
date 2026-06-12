# Source Profiles

Use this file when selecting or debugging scholarly sources. Prefer official docs and live source behavior over stale memory.

## OpenAlex

- Official docs: https://developers.openalex.org/
- API intro: https://developers.openalex.org/api-reference/introduction
- Primary endpoint: `https://api.openalex.org/works`
- Strengths: broad cross-domain metadata, DOI normalization, open-access metadata, citation/entity graph.
- Auth: support `OPENALEX_API_KEY` if configured. Since February 2026 OpenAlex requires a key for production scale; anonymous calls work only for small demo use. Documented exhaustion signals are `403` (rate) and `429` (daily limit); a `409` is undocumented but observed in the wild — treat it defensively as `auth_required` and continue with fallbacks.
- Pagination: use `per_page <= 100`, prefer cursor paging for large pulls, and keep quick searches bounded.
- Policy: identify via `api_key`; current docs no longer document `mailto`/User-Agent identification. Track usage through `X-RateLimit-*` headers and the `/rate-limit` endpoint.
- Diagnostics: record HTTP status, body excerpt, `Retry-After`, and `X-RateLimit-*` headers when available. A failed OpenAlex query should not block Crossref, Semantic Scholar, or Europe PMC fallbacks.

## arXiv

- API manual: https://info.arxiv.org/help/api/user-manual.html
- API terms: https://info.arxiv.org/help/api/tou.html
- API access: https://info.arxiv.org/help/api/index.html
- Bulk/OAI-PMH: https://info.arxiv.org/help/oa/index.html and https://info.arxiv.org/help/bulk_data.html
- Search endpoint: `https://export.arxiv.org/api/query`
- Strengths: arXiv preprints and versioned metadata.
- Policy: keep requests small, cache same-query results, wait at least 3 seconds between sequential API requests, and do not retry-loop 429/503/transport failures. For bulk metadata, use OAI-PMH or bulk access.

## Crossref

- REST tips: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/
- Access/auth: https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- Rate-limit update: https://www.crossref.org/blog/announcing-changes-to-rest-api-rate-limits/
- Endpoint: `https://api.crossref.org/works`
- Strengths: DOI metadata, publisher metadata, references where available.
- Policy: include `mailto` when a real contact is available. Keep list queries paced because public list requests are more constrained than single-record lookups; use cursor pagination for large pulls.

## Europe PMC

- REST API: https://europepmc.org/RestfulWebService
- Developer resources: https://europepmc.org/developers
- Endpoint: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- Strengths: biomedical/life-science records, open-access full text metadata, PMCID/PMID linkage.
- Policy: use `resultType=core` for richer metadata; download only open-access files exposed by metadata.

## Semantic Scholar

- Product page: https://www.semanticscholar.org/product/api
- API docs: https://api.semanticscholar.org/api-docs/
- Endpoint: `https://api.semanticscholar.org/graph/v1/paper/search`
- Strengths: citation/reference metadata, paper relevance search, author summaries.
- Auth: use `SEMANTIC_SCHOLAR_API_KEY` if configured; anonymous access is shared and can throttle.

## NCBI E-utilities

- Intro and policy: https://www.ncbi.nlm.nih.gov/books/NBK25497/
- Parameter reference: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- Strengths: PubMed/PMC biomedical metadata.
- Policy: include `tool` and `email` when available; use `NCBI_API_KEY` if configured for higher limits.

## CORE

- API overview: https://core.ac.uk/services/api
- API docs: https://core.ac.uk/documentation/api
- Strengths: open-access repository aggregation.
- Auth: the API itself allows limited keyless access (100 tokens/day, max 10/min); a free registered key raises that to 1,000/day. The bundled fetcher chooses to require `CORE_API_KEY` (Bearer) and fails as `auth_required` without it, routing to fallbacks.

## DBLP

- Search API: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
- Strengths: authoritative computer-science bibliography (venues, years, DOIs); excellent for CS/ML topics.
- Auth: none. Keep queries paced (~1s interval — a self-imposed default; official docs cap result size, not request rate).

## DOAJ

- Search API: https://doaj.org/api/docs
- Strengths: open-access journal articles with direct full-text links; everything indexed is OA by definition.
- Auth: none. Keep queries paced (~1s interval).

## OpenCitations

- Meta API: https://api.opencitations.net/meta/v1 (canonical; the old opencitations.net/meta/api/v1 URL redirects here)
- Official limit: 180 requests/minute per IP; use dumps for large-scale retrieval. The API also accepts issn/isbn/omid ids; the bundled fetcher restricts queries to DOIs.
- Strengths: open bibliographic and citation metadata keyed by DOI.
- Query contract: the bundled fetcher accepts only DOI queries (`10.xxxx/...`); non-DOI queries fail fast as `query_error`. `OPENCITATIONS_ACCESS_TOKEN` optional.
- Policy: use for citation graph enrichment and DOI verification, not as the only discovery source.

## Source Routing Rules

- If a source returns 401/403, mark it `auth_required` and continue.
- For OpenAlex specifically, treat 403 and 429 as cooldown/rate-limit unless the response clearly says credentials are invalid; treat an undocumented 409 defensively as `auth_required`/quota-key state.
- If a source returns 429/503 or times out, mark it `cooldown` and continue with fallbacks.
- Retry at most once after a backoff for transient network errors in interactive work.
- Record blocked sources in `query_log.jsonl` or a source status sidecar.
- Never make the final answer depend on a source that failed silently.
