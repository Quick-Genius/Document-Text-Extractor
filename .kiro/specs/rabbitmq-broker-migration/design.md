# Design Document: RabbitMQ Broker Migration

## Overview

This design specifies the migration of the document processing system's Celery task queue from Redis to RabbitMQ as the message broker. The migration addresses reliability concerns by leveraging RabbitMQ's superior message durability, persistence guarantees, and task acknowledgment mechanisms. Redis will be retained for its current roles: storing Celery task results (result backend) and managing WebSocket pub/sub for real-time progress updates.

### Goals

1. Replace Redis with RabbitMQ as the Celery message broker
2. Maintain Redis for result backend and WebSocket pub/sub functionality
3. Enable message persistence to survive broker restarts
4. Implement reliable task acknowledgment and requeuing
5. Preserve all existing task definitions and behavior
6. Maintain or improve system performance and throughput

### Non-Goals

1. Migrating the result backend from Redis to another system
2. Changing task serialization formats or task signatures
3. Modifying WebSocket pub/sub implementation
4. Implementing custom message routing beyond Celery defaults
5. Building a custom message broker abstraction layer

## Architecture

### System Components

```mermaid
graph TB
    subgraph "Application Layer"
        API[FastAPI Application]
        WS[WebSocket Manager]
    end
    
    subgraph "Task Queue Layer"
        CELERY[Celery App]
        WORKER[Celery Workers]
    end
    
    subgraph "Message Infrastructure"
        RMQ[RabbitMQ Broker<br/>Port 5672 AMQP<br/>Port 15672 Management]
        REDIS[Redis<br/>Result Backend<br/>WebSocket Pub/Sub]
    end
    
    subgraph "Storage Layer"
        DB[(PostgreSQL<br/>Database)]
        S3[S3 Storage]
    end
    
    API -->|Enqueue Tasks| CELERY
    CELERY -->|Send Messages| RMQ
    RMQ -->|Deliver Tasks| WORKER
    WORKER -->|Store Results| REDIS
    WORKER -->|Publish Progress| REDIS
    REDIS -->|Subscribe| WS
    WS -->|Real-time Updates| API
    WORKER -->|Update Status| DB
    WORKER -->|Read/Write Files| S3
    
    style RMQ fill:#ff9999
    style REDIS fill:#99ccff
```

### Message Flow

