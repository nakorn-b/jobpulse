# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-24

First tagged release. JobPulse is now an installable package that serves job
search and RAG chat over a REST API, backed by a daily Prefect ingestion flow.

### Added

- `POST /search` endpoint that returns the jobs most relevant to a query, without generating an answer.
- `POST /chat` endpoint that returns a generated answer together with the matched job list (`{response, job_list}`).
- `GET /health` endpoint for health checks.
- Daily Prefect flow (`daily_job_scraper`) that scrapes RemoteOK and loads new jobs into Postgres and Qdrant.
- Postgres storage service for job data.
- Job `category` field in the database schema, set by a classifier in the RemoteOK adapter.
- Gemma embedding model for Qdrant.
- RAG fusion retrieval, with retrieval methods pluggable through a strategy pattern.
- Job URLs in RAG results.
- Data seeding script (`scripts/seed_db.py`) and seed JSON for deployment databases.
- Dockerfile and `docker-compose.yaml` for running the API and its services.
- Ruff lint workflow in GitHub Actions.

### Changed

- Restructured the codebase into an installable `src/app` package (`ingestion`, `storage`, `ml`, `rag`, `api`, `flows`) built with `uv_build`.
- Replaced local SQLite and Chroma storage with Postgres for job data and Qdrant for vector search.
- Switched the chat LLM from `meta-llama/Llama-3.1-8B-Instruct` to `Qwen/Qwen3-0.6B`.
- RemoteOK scraper now mirrors the full set of job fields.

### Removed

- Airflow DAGs and services, replaced by Prefect.
- BigQuery and GCS storage.
- Streamlit demo UI.
- Early `/query` endpoint, replaced by `/search` and `/chat`.

### Fixed

- Truncated job descriptions before embedding to avoid Hugging Face API bad-request errors.
- Inconsistent syncing of job data between the relational and vector databases.

[unreleased]: https://github.com/Nemo-netidol/jobpulse/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Nemo-netidol/jobpulse/releases/tag/v1.0.0
