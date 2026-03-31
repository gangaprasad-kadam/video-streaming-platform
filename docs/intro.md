# Distributed Video Streaming Platform

## Project Summary & High-Level Design

---

## 📌 Project Summary

A scalable distributed video streaming platform (similar to YouTube/Netflix) built using microservices and event-driven architecture. It supports video upload, processing, streaming, and real-time user interaction.

---

## 🎯 Objective

To demonstrate how large-scale systems handle heavy traffic, asynchronous processing, and real-time features efficiently.

---

## 🚀 Core Features

- Video Upload & Processing
- Adaptive Video Streaming
- Trending System
- Scalable Microservices Architecture
- AI-Powered Video Summarization
- **🔥 Viewer Behavior Heatmap Engine** *(unique feature — see [unique-feature.md](./unique-feature.md))*

---

## 🏗️ High-Level Architecture

### 1. Frontend (React.js)

Handles UI for uploading, streaming, and user interaction.

### 2. API Gateway (NGINX)

Acts as a load balancer and routes requests to backend services.

### 3. Backend Microservices

- **User Service**: Authentication and profiles
- **Video Service**: Metadata and upload handling
- **Streaming Service**: Video delivery
- **Recommendation Service**: Suggests content
- **Summarization Service**: Generates video summaries and key moments

### 4. Event-Driven Processing (Kafka)

Handles asynchronous video processing such as:

- Encoding
- Compression
- Thumbnail generation
- Summarization

### 5. Databases

- **SQL (PostgreSQL/MySQL)**: Structured data
- **NoSQL (MongoDB)**: Logs and flexible data

### 6. Caching Layer (Redis)

Used for:

- Sessions
- Trending videos
- Summaries
- Fast data retrieval

---

## 🔄 End-to-End Flow

### 1. Upload Flow

User uploads video → Metadata stored → Event sent to Kafka → Processing services handle video → Summarization service generates summary → Stored in DB and cache

### 2. Streaming Flow

User requests video → Cache checked → Video chunks served → Adaptive streaming applied

### 3. Trending Flow

User interactions → Kafka events → Processed → Stored in Redis

### 4. Summarization Flow

Video uploaded → Audio extracted → Speech-to-text → NLP summarization → Key timestamps generated → Stored and served via API

---

## 🧠 Key Design Principles

- Microservices Architecture
- Event-Driven Systems
- Caching Strategies
- Load Balancing
- Scalability & Fault Tolerance

---

## 📂 Phase Documentation

Each phase has detailed documentation in [`docs/phases/`](./phases/README.md):

| Phase | Document |
|---|---|
| 1 — Infrastructure | [phase-1-infrastructure.md](./phases/phase-1-infrastructure.md) |
| 2 — User Service | [phase-2-user-service.md](./phases/phase-2-user-service.md) |
| 3 — Video Service | [phase-3-video-service.md](./phases/phase-3-video-service.md) |
| 4 — Processing Pipeline | [phase-4-processing-pipeline.md](./phases/phase-4-processing-pipeline.md) |
| 5 — Streaming Service | [phase-5-streaming-service.md](./phases/phase-5-streaming-service.md) |
| 6 — AI Summarization | [phase-6-ai-summarization.md](./phases/phase-6-ai-summarization.md) |
| 7 — Trending & Recommendations | [phase-7-trending-recommendations.md](./phases/phase-7-trending-recommendations.md) |
| 8 — 🔥 Heatmap Engine (unique) | [phase-8-heatmap-engine.md](./phases/phase-8-heatmap-engine.md) |
| 9 — Frontend | [phase-9-frontend.md](./phases/phase-9-frontend.md) |
| 10 — Integration & Docs | [phase-10-integration.md](./phases/phase-10-integration.md) |

---

## ✅ Conclusion

This project demonstrates how modern distributed systems are designed to handle scalability, performance, real-time interaction, and intelligent content processing using AI.
