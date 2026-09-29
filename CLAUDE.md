# Stock Council

Multi-agent stock analysis: 12 isolated specialist agents → bull/bear → challenger → judge.
See `docs/ARCHITECTURE.md` for the design.

- Backend: `backend/` (FastAPI, Python 3.11). Check with `ruff check . && ruff format --check . && pytest -q`.
- Frontend: `frontend/` (Next.js 15, Tailwind 4). Check with `npm run lint && npm run build`.
- The isolation rule is the core invariant: a specialist's prompt may contain only its own `DataPacket`.
  Keep `tests/test_pipeline.py::test_specialists_only_see_their_own_packet` passing.
- New data segment = new module in `backend/app/data/` exposing `SEGMENT` + `fetch`, registered in
  `registry.py`, with a matching `Specialist` in `agents/specialists.py` and entry in `frontend/lib/analysts.ts`.
- `frontend/lib/types.ts` mirrors `backend/app/schemas.py`; change them together.
- All Claude calls go through `backend/app/agents/llm.py`.
- Website state: `frontend/lib/council.ts` folds the SSE event stream into page state (live runs and saved
  history both replay events through it). Saved reports live in the browser (`lib/history.ts`, localStorage).
- New agent output fields must be optional in `frontend/lib/types.ts` so older saved runs still render.
