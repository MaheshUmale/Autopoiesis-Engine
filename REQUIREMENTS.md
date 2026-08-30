# Technical Requirements Specification: Autopoiesis-Engine

**Document Version:** 2.0.0 (Final Consolidated)

## 1. Project Overview & Environment

* **Project Name:** Autopoiesis-Engine
* **Target OS:** Cross-Platform Native (Windows `win32`, Linux, macOS)
* **Packaging Tool:** `hatchling` (PEP 621 compliant)
* **Core Protocols & Frameworks:** Model Context Protocol (MCP), Temporal.io, OpenTelemetry (OTEL)
* **Execution Paradigm:** Biological Tool Synthesis (DNA Primitive Skills $\rightarrow$ RNA Translation $\rightarrow$ Protein Composite DAGs)

## 2. Directory & State Management

* **State Isolation:** All local execution state, metadata, and temporary datasets must reside strictly within a `.autopoiesis/` directory in the project root.
* **Relational Storage:** SQLite database located at `.autopoiesis/autopoiesis.db` for execution history, project parameters, and skill metadata.
* **Vector Index:** Embedded persistent Qdrant database located at `.autopoiesis/qdrant/` for semantic skill similarity searches.
* **Staging Storage:** Temporary disk storage located at `.autopoiesis/staging/` for inter-node dataset caching.

## 3. Pre-Seeded Level 1 OS Core Base Pack

The framework ships with a built-in library of core Python OS operations under `registry/level_1_core/`, populated out-of-the-box:

* **File System Operations:** `global.file.reader`, `global.file.writer`, `global.file.lister`.
* **Process & Shell:** `global.shell.executor`.
* **Data Processing:** `global.parsers.json_parser`, `global.data.parquet_converter`.

## 4. Skill Registry Architecture (3-Tier) & AST Deduplication

* **Level 1 (Core):** Universal, domain-agnostic skills under `registry/level_1_core/`.
* **Level 2 (Variants):** Domain-specific implementations under `registry/level_2_variants/`.
* **Level 3 (Templates):** Parameterized macro workflow graphs under `registry/level_3_templates/`.
* **AST Normalization:** Strips docstrings, comments, function names, parameter identifiers, and variable assignments to compute SHA-256 fingerprints.

## 5. Startup Delta Reconciliation & Look-Ahead Intent Resolution

* **Delta Indexing:** Daemon startup scans disk file timestamps against Qdrant metadata, re-indexes new/modified skills, and purges deleted disk skills.
* **Intent Resolution:** Converts prompt/manifest steps into vector embeddings filtered by `active_namespaces`. Matches $\ge 0.85$ link directly to existing skills; matches $< 0.85$ trigger asynchronous synthesis.

## 6. Distributed Execution & State Payload Thresholds

* **Deterministic Orchestration:** DAGs execute deterministically via Temporal.io workflows.
* **Inline Payload ($< 100 \text{ KB}$):** Payloads under 100 KB serialize as inline JSON within Temporal state.
* **File Pointer Payload ($\ge 100 \text{ KB}$):** Payloads $\ge 100\text{ KB}$ serialize to `.autopoiesis/staging/{execution_id}_{node_id}.parquet`. Downstream nodes automatically re-hydrate file pointers back into memory.

## 7. Sandbox Verification & Dynamic Timeout Scaling

* **Dynamic Timeout Scaling:**
$$\text{Timeout}_{\text{total}} = 5.0\text{ seconds} + \left( \frac{\text{Payload Size in Bytes}}{1,048,576} \times 2.0\text{ seconds} \right)$$

## 8. Diagnostic Self-Healing Matrix

* Diagnostic Decision Tree categorizes errors (Schema, Resource, Network, Logic) and caps logic hotfix retries at **exactly 3 attempts**. Terminal failures emit `isError: true` MCP payloads.

## 9. Cross-Platform Abstraction & Process Multiplexing

* **`PlatformAdapter`:** Routes commands to `pwsh -NoProfile -NonInteractive` on Windows (`win32`) and `/bin/bash` on Unix/macOS.
* **`AgentWindowManager`:** Handles terminal splitting via `wt.exe split-pane` on Windows and `libtmux` on Unix/macOS with graceful fallback logging.

## 10. Model Context Protocol (MCP) Interface & Resources

* **Transports:** Supports standard `stdio` and HTTP/SSE (`/sse`, `/messages`, `/tools`).
* **Resources Endpoints:** Exposes `resource://autopoiesis/registry`, `resource://autopoiesis/state/history`, and `resource://autopoiesis/config`.
