# Distributed Price Comparison Platform

A microservice-based price comparison system designed to aggregate and compare
product prices across multiple platforms.

## Architecture Overview

The system follows a distributed microservice architecture:

- Frontend Service: User interface for viewing price comparisons
- API Gateway: Aggregates and normalizes price data
- Scraper Services: Independently fetch prices from different sources

All services are containerized using Docker and orchestrated using Kubernetes.
CI/CD is implemented using GitHub Actions.

## Tech Stack
- Git & GitHub (Version Control, CI/CD)
- Docker (Containerization)
- Kubernetes (Orchestration)
