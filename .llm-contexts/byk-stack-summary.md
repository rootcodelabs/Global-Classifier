# Bürokratt Project Overview

## Goal and Vision

Bürokratt is an initiative by the Estonian Ministry of Economic Affairs and Communications (MKM), with technical implementation managed by the Information System Authority (RIA).
The core vision is to create a seamless, unified, and user-friendly channel for citizens and businesses to access Estonia's approximately 3,000 public e-services (and potentially private sector services).
It aims to function as an interoperable network of public and private sector AI solutions, acting as a virtual assistant accessible via text and voice, 24/7.
The goal is to make interacting with the state radically easier, moving beyond simple chatbots to a system that understands user needs and proactively offers bundled services, potentially based on life events.

## Development and Architecture (Based on Codebase & ADRs)

- **Open Development:** Bürokratt follows an open development model, with all code, planning, and project management happening publicly on GitHub. This facilitates collaboration with numerous development partners.
- **Modular Architecture:** The system is designed to be highly modular, with functionalities developed as independent, replaceable services communicating via APIs (ARCH-001).
- **DSL-Based Development:** A key principle is Domain-Specific Language (DSL)-based development. Instead of traditional programming languages for many tasks, developers work with YAML (e.g., for Ruuter configurations), SQL files (for Resql), and Handlebars (for DataMapper) to define service logic and data transformations.

### Key Components:

- **Ruuter:** Acts as the central router and reverse proxy, handling service requests (POST, GET, etc.), conditional logic, and templated services. Mock services are often built first using Ruuter's capabilities.
- **Resql:** Manages all PostgreSQL database interactions. Each query resides in a separate .sql file, exposed as a REST endpoint. ADRs emphasize strict standards for SQL: no UPDATE/DELETE, standardized formatting, no SELECT *, no cross-table joins (enforcing denormalization), query parameterization, and security declarations.
- **DataMapper (DMapper):** Uses Handlebars templates to restructure JSON outputs.
- **TIM (TARA Integration Module):** Facilitates TARA-based authentication and JWT management.
- **CVI:** A fork of a front-end component library for reusable React GUI elements.
- **PostgreSQL:** The relational database used. Schema management uses Liquibase with specific rules (SQL-only definitions tracked via XML, UUIDs for all objects, use of ENUMs and TEXT, mandatory indexing, defined schemas instead of public).
- **Liquibase:** Used for database schema version control.
- **OpenSearch:** Increasingly used, particularly for its Query DSL capabilities. Storage ADRs indicate OpenSearch is a reference for document-oriented storage for metadata/structured text, separate from blob storage (like S3) for raw files.
- **Rasa:** Used for chatbot functionalities like rules and stories, though intent recognition might be replaced.
- **Centops:** It's the central orchestrator for the entire BYK stack
- **DMR:** Stands for distributed message rooms, a message orchestration system which can recieve messages from one Buerokratt chatbot and pass it to another