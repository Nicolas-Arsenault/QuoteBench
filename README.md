# QuoteBench

QuoteBench is a local LLM-powered semiconductor quoting system. A customer
describes their application, quantity, budget, delivery window, and requested
discount in plain language. The service finds eligible catalog products,
selects the best match, applies deterministic pricing rules, and returns either
a completed quote or a provisional quote requiring human approval.

The project runs locally with FastAPI, LangGraph, Qwen through Ollama, and a
PostgreSQL product catalog. No external AI API key is required. A minimalist
browser console is included for adding products, viewing the catalog, and
testing quote requests.

## System overview

```mermaid
flowchart LR
    UI[Browser console or API client] --> API[FastAPI]
    API --> Catalog[(PostgreSQL catalog)]
    API --> Graph[LangGraph workflow]
    Graph --> Qwen[Qwen via Ollama]
    Graph --> Catalog
    Graph --> Pricing[Pricing policies]
    Pricing --> Result[Final or provisional quote]
```

- **FastAPI** exposes the UI, catalog endpoints, health check, and quote API.
- **LangGraph** coordinates requirement extraction, retrieval, product
  selection, pricing, and approval routing using a typed shared state.
- **Qwen** extracts structured requirements and chooses from catalog candidates.
- **PostgreSQL** stores product data and ranks candidates using full-text search,
  quantity constraints, and delivery constraints.
- **Pricing policies** calculate volume discounts and require manager review
  when the applied discount exceeds 10%.

## Quote graph

```mermaid
flowchart TD
    Start([Customer message]) --> Extract[Extract requirements with Qwen]
    Extract --> Valid{Valid request?}
    Valid -->|No| Invalid([Return validation errors])
    Valid -->|Yes| Search[Find eligible catalog products]
    Search --> Found{Candidates found?}
    Found -->|No| None([Return no candidates])
    Found -->|Yes| Select[Select best SKU with Qwen]
    Select --> Price[Calculate price and discount]
    Price --> Review{Discount above 10%?}
    Review -->|Yes| Provisional([HTTP 202: human review])
    Review -->|No| Complete([HTTP 200: completed quote])
```

Each node adds fields to a `FinalState` object. The deterministic validation,
catalog constraints, pricing, and approval policy remain outside the model so
the LLM cannot invent a product or override business rules.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Open the browser test console |
| `GET` | `/health` | Check API health |
| `GET` | `/products` | List catalog products |
| `POST` | `/products` | Add a catalog product |
| `POST` | `/quote` | Generate a quote from a customer message |

Interactive API documentation is available at `/docs` while the server is
running.

## Run locally

Requirements: Docker, [uv](https://docs.astral.sh/uv/), and
[Ollama](https://ollama.com/).

```bash
cp .env.example .env
docker compose up -d
ollama pull qwen3:4b
uv sync
uv run fastapi dev app/main.py
```

Ensure Ollama is running, then open <http://127.0.0.1:8000>.

Run the automated tests with:

```bash
uv run pytest
```

See [the architecture documentation](docs/architecture.md) for additional
implementation details.


https://github.com/user-attachments/assets/84207700-d9d0-4cd5-a0e4-f4cbdb1d037f



See [the architecture documentation](docs/architecture.md) for workflow,
component, comparison, storage, and testing details.
