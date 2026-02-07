# Ekonomi Dashboard (Monorepo)

Struktur:
- `frontend/` Next.js-app
- `backend/` FastAPI-tjänst
- `config/` instrument-konfiguration (YAML/JSON)
- `docker-compose.yml` lokal orkestrering

Nästa steg:
1. Skapa frontend (Next.js App Router + Tailwind)
2. Skapa backend (FastAPI + provider-lager + cache)
3. Fyll `config/instruments.example.yaml`
4. Lägg till `docker-compose.yml`

Test:
- Samlad: `./scripts/test-all.sh`
- Backend: `cd backend && .venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt && .venv/bin/python -m pytest`
- Frontend: `cd frontend && npm install && npm run test`
