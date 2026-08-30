# Autopoiesis-Engine

**Self-Evolving, Multi-Tenant Agent Execution Framework**

`Autopoiesis-Engine` is an autonomous AI agent execution engine built on top of the **Model Context Protocol (MCP)**, **Temporal.io Distributed Harness**, and **OpenTelemetry**. It enables autonomous coding agents (Cursor, Claude 3.5 Sonnet, Windsurf, Devika, Kilocode) to synthesize, test, cache, self-heal, and orchestrate micro-skills into composite workflow Directed Acyclic Graphs (DAGs) using a biological paradigm (**DNA $\rightarrow$ RNA $\rightarrow$ Protein Synthesis**).

---

## Key Features

- **Autopoietic Tool Synthesis:** Eliminates hardcoded agent tools by dynamically synthesizing missing micro-skills on-demand.
- **3-Tier Registry Architecture:**
  - `Level 1 Core`: Universal primitive micro-skills.
  - `Level 2 Variants`: Domain-specific skill implementations.
  - `Level 3 Templates`: Parameterized macro workflow composite DAGs.
- **Normalized AST Deduplication:** Structural code fingerprints strip comments, docstrings, and parameter identifiers to prevent duplicate logic.
- **Isolated Sandbox Execution:** Subprocess sandboxing with dynamic timeout scaling ($\text{Timeout} = 5.0 + (\text{Payload}_{\text{MB}} \times 2.0)$).
- **Inter-Node State Thresholding:** 100 KB boundary rule separating inline Temporal activity state from Parquet file pointers to prevent payload limit breaches.
- **Temporal.io Harness & Self-Healing:** Deterministic DAG execution with a diagnostic decision tree loop capped at 3 hotfix attempts.
- **Multi-IDE MCP Support:** Exposes active skills via Model Context Protocol over `stdio` and `HTTP/SSE` for Claude Desktop, Cursor, VS Code, and Kilocode.

---

## Quick Start

```bash
# 1. Install via pip / uv
pip install -e .

# 2. Initialize project workspace & IDE configurations
autopoiesis init

# 3. Start local MCP daemon
autopoiesis serve --mode stdio
```

---

## Documentation

- **[Installation Guide](INSTALLATION.md):** Detailed guide on environment prerequisites and distribution setup.
- **[Setup Guide](SETUP_GUIDE.md):** Configuration instructions for IDEs (Cursor, Claude Desktop, VS Code, Kilocode).
- **[User Manual](USER_MANUAL.md):** Complete guide on CLI commands, MCP tool usage, DAG workflows, and Registry management.
- **[Technical Specification](REQUIREMENTS.md):** Complete architectural requirements document.
