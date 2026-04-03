# Async Document Processing Workflow System

This project is a full-stack application that enables users to upload documents, process them asynchronously in the background, track progress in real-time, review/edit extracted data, and export finalized results.

## Tech Stack

- **Frontend**: React, TypeScript, Vite, TanStack Query, React Router, Axios, Clerk, shadcn/ui, Tailwind CSS
- **Backend**: FastAPI, Python, Prisma, Celery, Redis, pytest
- **Database**: PostgreSQL
- **Infrastructure**: Docker, Docker Compose

## Getting Started

1.  Clone the repository.
2.  Create a `.env` file in the root directory and populate it with the required environment variables. You can use the `.env.example` file as a template.
3.  Make sure you have Docker and Docker Compose installed and running.
4.  Run `docker-compose up -d --build` to start all the services.
5.  Generate the Prisma client: `docker-compose exec backend prisma generate`
6.  Run the initial database migration: `docker-compose exec backend prisma db push`
7.  The frontend will be available at `http://localhost:5173` and the backend at `http://localhost:8000`.
# Document-Text-Extractor
