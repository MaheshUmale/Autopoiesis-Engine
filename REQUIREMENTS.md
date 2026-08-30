# Technical Requirements Specification: Autopoiesis-Engine

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

## 3. Skill Registry Architecture (3-Tier)

* **Level 1 (Core):** Universal, domain-agnostic skills (e.g., standard parsers, generic file handlers) under `registry/level_1_core/`.
* **Level 2 (Variants):** Domain-specific implementations (e.g., specific broker REST API callers) under `registry/level_2_variants/`.
* **Level 3 (Templates):** Parameterized macro workflow graphs referencing Level 1 and Level 2 skills under `registry/level_3_templates/`.

## 4. Micro-Skill Structural Requirements

* **Schema Definition:** Every skill requires a strict metadata schema defining its unique identifier, namespace, scope level, text description, required input properties, and expected output structure.
* **AST Deduplication:** Prior to registry insertion, a skill's Abstract Syntax Tree (AST) must be cryptographically hashed.
* **Hashing Rules:** The AST generation must strip all docstrings, comments, function names, and variable identifiers.
* **Duplicate Handling:** Skills with identical AST hashes in the same namespace are rejected.
* **Domain Exception:** Variations with identical logic but domain-specific structural nodes (e.g., distinct API endpoint constants) are permitted under designated namespaces.

## 5. Execution Pipeline & Intent Resolution

* **Namespace Isolation:** Execution queries the vector database filtered strictly by active namespaces defined in the project configuration file.
* **Look-Ahead Parsing:** The engine parses incoming execution intents (`project.yaml`) to map required steps before invoking workers (`autopoiesis.core.intent`).
* **Synthesis Trigger:** If the vector similarity match for a required step falls below a 0.85 threshold, the engine asynchronously synthesizes the missing micro-skill.
* **Template Extraction:** Successfully executed multi-step sequences are abstracted into dynamically parameterized composite templates and saved to the Level 3 Registry.

## 6. Distributed Execution & State Payload Thresholds

* **Deterministic Orchestration:** Directed Acyclic Graphs (DAGs) execute deterministically via Temporal.io workflows.
* **Inline Payload ($< 100 \text{ KB}$):** Inter-node payloads under 100 Kilobytes serialize as inline JSON within the Temporal state.
* **File Pointer Payload ($\ge 100 \text{ KB}$):** Payloads 100 Kilobytes or larger write to disk as `.parquet` files within the `.autopoiesis/staging/` directory. Downstream nodes receive a lightweight JSON pointer and automatically re-hydrate the data into memory.

## 7. Sandbox Verification & Dynamic Timeout

* **Dynamic Timeout Scaling:** Sandbox verification timeout duration strictly follows payload size scaling:

$$\text{Timeout}_{\text{total}} = 5.0\text{ seconds} + \left( \frac{\text{Payload Size in Bytes}}{1,048,576} \times 2.0\text{ seconds} \right)$$

* **Isolation:** Unverified skills execute in isolated sandbox environments with mock inputs prior to runtime promotion.

## 8. Diagnostic Self-Healing Matrix

* **Schema Validation Failure:** Flag upstream node generating the payload. Do not mutate current skill logic.
* **OOM / Timeout:** Refactor skill code for data chunking/streaming logic.
* **Network Errors (429/500):** Wrap existing execution logic in exponential backoff decorators.
* **Logic/Syntax Exception:** Send stack trace to the repair loop for code patching.
* **Retry Bound:** Cap self-healing logic repair attempts at a strict maximum of 3 retries.
* **Terminal Failure:** Upon exceeding 3 retries, halt execution and emit an `isError: true` payload compliant with the MCP specification.

## 9. Cross-Platform Abstraction (`PlatformAdapter`)

* **Shell Enforcement:** Hardcoded Unix strings (e.g., `/bin/bash`) are strictly prohibited.
* **Routing:** `PlatformAdapter` routes commands to `pwsh` (PowerShell with non-interactive flags) on `win32` systems and standard shells on Unix/macOS.
* **Path Sanitization:** All system paths are sanitized to OS-native path objects before execution.

## 10. Process Multiplexing (`AgentWindowManager`)

* **Windows Native (`win32`):** Terminal splitting spawns native Windows Terminal split panes using the `wt.exe split-pane` command.
* **Unix/macOS:** Terminal splitting uses `libtmux`.
* **Graceful Degradation:** If `wt.exe` or `tmux` binaries are unavailable, the system defaults to standard single-terminal background logging without generating process exceptions.
* **CLI Binding:** Multiplexing operates via standard daemon background processes without requiring custom GUI command-line flags.

## 11. Interface & Integration Standards

* **Protocol:** All valid skills expose endpoints via the standard Model Context Protocol (MCP).
* **Transports:** The daemon supports both standard input/output (`stdio`) for IDEs and HTTP Server-Sent Events (`SSE` via `/sse` and `/messages`) for remote/background tasks.
* **Auto-Configuration:** The CLI initialization command automatically detects local developer environments (Claude Desktop, Cursor, VS Code, Kilocode) and writes/merges the required local MCP server configuration pointers.
