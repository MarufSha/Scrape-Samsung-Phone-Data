Samsung Phone Query & Comparison System

A backend-focused intelligent system that collects Samsung smartphone data from GSMArena, stores it in a structured PostgreSQL database, and provides APIs and an AI-powered chatbot for querying, comparison, and analysis.

--------------------------------------------------

PROJECT OVERVIEW

This system combines:

- Web scraping (GSMArena)
- Relational database design (PostgreSQL)
- REST API development (FastAPI)
- AI-based response generation (Hugging Face - gpt-oss-20b)

It allows users to:

- Search for Samsung phones
- Compare two phones
- Retrieve full specifications
- Get structured reviews
- Ask natural language questions via chatbot

--------------------------------------------------

KEY FEATURES

1. Data Collection
- Scrapes real phone specifications from GSMArena
- Extracts:
  - Display, resolution, protection
  - Chipset, GPU, OS
  - Camera specs (rear + selfie + video)
  - Battery, weight, build, colors
  - Release date and pricing
- Supports variant-level data:
  - Storage (ROM)
  - RAM
  - Price per variant

2. Database Design
- PostgreSQL with two main tables:
  - phones
  - phone_variants
- phone_variants stores:
  - storage
  - RAM
  - price (per variant)

3. Smart Query System
- Deterministic backend logic (no AI guessing)
- Supports ranking queries:
  - Best display
  - Highest resolution
  - Latest phone
  - Cheapest / most expensive
  - Best camera / most cameras
  - Highest RAM / storage

4. AI Chatbot (RAG-style)
- Uses Hugging Face inference (gpt-oss-20b)
- AI explains results but does NOT calculate them
- Supports:
  - Spec queries
  - Comparison queries
  - Ranking queries
  - Variant-specific price queries

--------------------------------------------------

API ENDPOINTS

Base URL: http://127.0.0.1:8000

GET  /                  → Health check
GET  /phone-names       → List all phone names
GET  /phones            → Get all phones
GET  /phones/search     → Search phones by name
GET  /phones/{id}       → Get phone by ID
GET  /phones/{id}/variants → Get RAM/Storage variants
GET  /phones/{id}/review   → Generate review

GET  /phones/compare        → Compare two phones
GET  /agents/review/{id}    → Agent-based review
GET  /agents/compare        → Agent-based comparison

POST /chat → AI chatbot endpoint

--------------------------------------------------

PROJECT STRUCTURE

samsung-phone-query-system/

api/
  main.py
  chatbot.py
  review_generator.py

agents/
  coordinator_agent.py

database/
  db.py
  models.py

scraper/
  scrape_gsmarena.py

.env
requirements.txt

--------------------------------------------------

SETUP INSTRUCTIONS

1. Clone project

git clone <repo-url>
cd samsung-phone-query-system

--------------------------------------------------

2. Create virtual environment

python -m venv .venv
.\.venv\Scripts\Activate

--------------------------------------------------

3. Install dependencies

pip install -r requirements.txt

--------------------------------------------------

4. Setup PostgreSQL

Create database:

CREATE DATABASE samsung_db;

Update .env file:

DATABASE_URL=postgresql://username:PASSWORD@localhost:5432/samsung_db
HF_TOKEN=your_huggingface_token
HF_MODEL=openai/gpt-oss-20b:fireworks-ai

--------------------------------------------------

5. Create tables

Run Python shell:

python

Then:

from database.db import Base, engine
Base.metadata.create_all(bind=engine)

python init_db.py
--------------------------------------------------

6. Run scraper

python scraper/scrape_gsmarena.py

--------------------------------------------------

7. Start backend server

uvicorn api.main:app --reload

Open API docs:

http://127.0.0.1:8000/docs

--------------------------------------------------

EXAMPLE CHAT REQUESTS

POST /chat

{
  "question": "What are the camera specs of the Samsung Galaxy S23?"
}

{
  "question": "Which Samsung phone has the best battery life?"
}

{
  "question": "How does the Galaxy S23 compare to the S22 in terms of performance?"
}

--------------------------------------------------
