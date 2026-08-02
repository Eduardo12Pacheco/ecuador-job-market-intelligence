# Ecuador Job Market Intelligence

> A Python-first, end-to-end data product for understanding the skills, roles, and technology demand in Ecuador's data, AI, and software job market.

## Project status

**Repository bootstrap / project definition.** Implementation has not started yet. This README is the initial project contract and will be updated as the system becomes real.

## Problem

Students and early-career professionals often have to search through scattered job postings to understand which skills employers actually request. The information is difficult to compare because postings use inconsistent job titles, duplicate technologies, different seniority labels, and mixed location or remote-work terminology.

This project will turn permitted public job-posting data into an explorable, reproducible, and evidence-based view of the Ecuadorian and Ecuador-relevant remote job market.

## Product goal

Build a small production-style data platform that answers questions such as:

- Which technical skills are most requested in data and AI roles?
- How does demand differ between data science, AI engineering, data engineering, and full-stack roles?
- Which tools appear together in the same job postings?
- How do seniority, location, and remote-work requirements affect the observed demand?
- How has the market changed over time?

The product must show the evidence behind its conclusions. Every record should retain its source, collection time, and transformation history.

## Intended users

- Students choosing what to learn next.
- Early-career candidates preparing a portfolio or CV.
- Career advisors and university communities.
- Recruiters or hiring managers exploring local technology demand.

## What the system will do

1. **Collect** job-posting data from public and permitted sources.
2. **Preserve** raw source responses with collection timestamps and source metadata.
3. **Normalize** titles, locations, seniority, work mode, and technology names.
4. **Extract** skills from descriptions using a transparent taxonomy and measurable NLP methods.
5. **Model** an analytical dataset for roles, skills, companies, locations, and observations over time.
6. **Analyze** demand, co-occurrence, trends, and differences between role families.
7. **Expose** results through an API and an interactive web demo.
8. **Report** data freshness, source health, quality checks, assumptions, and limitations.

## Demo vision

The final demo should be understandable in under one minute and should show more than a happy-path chart:

- A landing dashboard with current role volume, top skills, role families, locations, and remote-work distribution.
- A skill explorer showing demand trends and related technologies.
- A role comparison view for Data Scientist, AI/ML Engineer, Data Engineer, and Full-Stack AI Engineer positions.
- A searchable job view with the original source link and extracted evidence.
- A data-quality page showing the latest successful ingestion, source status, duplicate rate, and known limitations.
- An empty-result or source-outage state that explains what happened instead of silently failing.

The project will have a public deployment when the data-source and hosting constraints are understood. Until then, a reproducible local demo and a short recorded walkthrough will be required.

## Scope

### Minimum viable product

- One or more public, permitted data sources.
- A reproducible ingestion command using saved fixtures for offline development.
- Raw and cleaned data layers.
- Normalized job titles, locations, seniority, and work mode.
- A versioned technology-skill taxonomy.
- Core descriptive analysis and visualizations.
- An interactive Streamlit demo.
- Automated tests for parsing, normalization, deduplication, and data validation.
- A README that documents the data lineage, metrics, limitations, and setup.

### Version 2

- FastAPI service for the analytical dataset.
- PostgreSQL storage for application-facing data.
- Semantic search using sentence embeddings and a vector index, only after a keyword-search baseline exists.
- Scheduled ingestion and freshness monitoring.
- A small labeled evaluation set for skill extraction and search relevance.
- Dockerized local deployment and CI checks.

### Explicitly out of scope

- Scraping LinkedIn or any website in violation of its terms, robots policy, or access controls.
- Collecting personal contact information or candidate profiles.
- Claiming to represent the entire Ecuadorian labor market.
- Presenting correlation as causation.
- Building an opaque LLM-only extraction pipeline without a baseline or evaluation.
- Adding cloud infrastructure before the local pipeline is reproducible.

## Proposed technical stack

| Layer | Initial choice | Purpose |
| --- | --- | --- |
| Language | Python | Core implementation and analysis |
| Environment | `uv` | Reproducible dependency and environment management |
| Quality | Ruff, pytest, Pandera | Formatting/linting, tests, and data contracts |
| Ingestion | Python source adapters, `httpx`, permitted parsers | Collect data without coupling the domain to one source |
| Raw storage | JSON and Parquet fixtures | Preserve source evidence and enable offline development |
| Analytics | pandas and DuckDB | Cleaning, SQL analysis, and local analytical queries |
| NLP baseline | Normalization rules, taxonomy matching, scikit-learn | Transparent and measurable skill extraction |
| NLP extension | sentence-transformers | Semantic matching and search after the baseline |
| API | FastAPI and Pydantic | Typed service boundary for the application |
| Demo | Streamlit for the MVP | Fast, readable, interactive public demonstration |
| Application storage | PostgreSQL, later | Durable records and search-ready data |
| Delivery | Docker and GitHub Actions, later | Reproducible execution and automated checks |

Technology choices are staged deliberately. The project will not start with a large framework stack or an LLM. First we will make the data pipeline, baseline extraction, and evaluation trustworthy.

## Skills demonstrated

### Data science

- Problem framing and metric definition.
- Exploratory data analysis and visualization.
- Grouped comparisons and time-based trend analysis.
- Bias, missingness, sampling limitations, and uncertainty.
- Evidence-based conclusions instead of technology-counting alone.

### Data engineering

- Source adapters and resilient ingestion.
- Raw, cleaned, and analytical data layers.
- Schema design and data contracts.
- Deduplication, idempotency, freshness, and failure handling.
- SQL analytics with DuckDB and PostgreSQL.

### AI and NLP

- Taxonomy design and entity normalization.
- A transparent keyword/rule baseline.
- Embeddings and semantic search as a measured extension.
- Labeled evaluation data, error analysis, and abstention when evidence is weak.

### Software and full stack

- Typed Python modules and service boundaries.
- FastAPI endpoints and validation with Pydantic.
- Interactive user experience through Streamlit.
- Tests, documentation, configuration, logging, and reproducible execution.
- CI and deployment readiness.

### Professional communication

- Clear problem statement and stakeholder value.
- Architecture and data-lineage diagrams.
- Metrics, trade-offs, limitations, and failure analysis.
- A short demo video and a LinkedIn post focused on the result rather than the tool list.

## Evaluation plan

The project will report measurable evidence, including:

- Ingestion success rate and source freshness.
- Duplicate detection results on a reviewed sample.
- Field completeness for title, source, location, and publication time.
- Skill-extraction precision and recall on a small manually labeled evaluation set.
- Search relevance against representative candidate questions.
- Dashboard or API response time for the demo workload.
- Reproducibility from a clean environment using fixtures.
- At least one intentionally induced failure and the system's response.

A strong result is not necessarily a large number of collected postings. A strong result is a trustworthy, explainable system whose limitations are visible.

## Data and ethics principles

- Use only public or explicitly permitted sources.
- Respect terms of service, robots policies, rate limits, and attribution requirements.
- Store source URLs and collection timestamps.
- Avoid personal data and unnecessary identifiers.
- Keep a fixture dataset so the project remains runnable if a source changes or disappears.
- Document source coverage and known sampling bias.
- Never present the dashboard as an official labor-market statistic.

## Planned repository structure

```text
.
├── README.md
├── pyproject.toml
├── src/
│   └── job_market_intelligence/
│       ├── ingestion/
│       ├── normalization/
│       ├── extraction/
│       ├── analytics/
│       └── config.py
├── tests/
├── data/
│   └── sample/
├── notebooks/
├── app/
├── docs/
└── .github/
    └── workflows/
```

Large raw datasets, credentials, and local runtime state must not be committed.

## Roadmap

- [ ] Audit candidate data sources and their usage constraints.
- [ ] Define the canonical domain schema and skill taxonomy.
- [ ] Create source fixtures and the first ingestion adapter.
- [ ] Implement raw storage, normalization, and deduplication.
- [ ] Build the first analytical dataset and baseline visualizations.
- [ ] Add data-quality checks and failure-path tests.
- [ ] Build the Streamlit MVP.
- [ ] Add the skill-extraction evaluation set.
- [ ] Add FastAPI and PostgreSQL only when the MVP justifies them.
- [ ] Add semantic search only after measuring the keyword baseline.
- [ ] Deploy the demo or publish a recorded walkthrough.
- [ ] Write the final technical case study and LinkedIn publication.

## Definition of done

The project is ready for portfolio publication when:

- A new contributor can run it from documented instructions.
- The demo answers a clear user question with traceable evidence.
- The data pipeline can handle duplicates, missing fields, and a source failure.
- Baselines and evaluation results are reported honestly.
- Tests and CI pass on the reviewed revision.
- The README explains the architecture, trade-offs, limitations, and next steps.
- A recruiter can understand the problem, result, and demo link in under two minutes.

## License

To be decided after the data-source and dependency licenses are audited.
