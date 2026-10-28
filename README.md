# NEX

NEX is a full-stack AI software engineering platform that helps developers understand, modify, test, review, and ship code through intelligent automation.

## Architecture

NEX is built with a modular architecture:

- Django for the core backend and application data.
- FastAPI for the AI agent runtime.
- LangGraph for agent orchestration.
- React for the web interface.
- Python for the CLI.
- PostgreSQL and pgvector for application data and code intelligence.
- Redis for caching and asynchronous tasks.
- Docker for isolated and reproducible environments.

## Development

The project is currently in the foundation stage.

The development environment will be fully containerized and designed for production deployment from the beginning.

## Project Structure

```text
apps/             Backend services
cli/              NEX command-line interface
frontend/         React web application
packages/         Shared project code
infrastructure/   Docker and deployment configuration
scripts/           Development and automation scripts
tests/             Cross-service tests
