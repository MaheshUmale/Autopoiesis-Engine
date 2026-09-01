---
name: git-advanced-workflow
description: Comprehensive operating procedures for Git actions, repo context ingestion, MCP live connections, browser-based editing, and conventional commits.
version: 1.1.0
compatibility:
  git: ">=2.25.0"
metadata:
  author: MAHESH
  license: Apache-2.0
  version: 0.5.0
---

# Git Workflow & Context Exploration Skill Guide

You are an expert software engineering agent. Follow this structured process for repository manipulation, codebase comprehension, and atomic commits. Use the integrated web-ecosystem protocols below to maximize context window utilization and eliminate code hallucinations.

## 1. Context Ingestion & Mapping Ecosystem
When exploring a repository, troubleshooting an issue, or providing architecture breakdowns, utilize the following specific Git web overlays instead of blindly traversing file trees.

### High-Priority Daily Workflows
* **Live AI Knowledge (MCP Integration)**: Connect through `gitmcp.io` to spin up a Model Context Protocol server. This gives you a live, accurate window into the real code to stop hallucinating nonexistent module functions or imports.
* **Flattening for Prompts**: Use `gitingest.com` to condense the repository structure into a clean, text-based payload optimized for context injection.
* **Instant Web-IDE**: Navigate to `github.dev` (or press `.` on any GitHub landing page) to boot a zero-setup, native web-based VS Code environment.

### Repo Auditing & Analysis Architecture
* **Visual Blueprints**: Navigate to `gitdiagram.com` to analyze an auto-generated, clickable architectural flowchart of the entire system layout.
* **Knowledge Retrieval Engine**: Query documentation using `deepwiki.com` for auto-generated wikis containing exact citation tracking.
* **Repository Health Dashboard**: Review `github.gg` to check the centralized repository control panel, retrieve AI-copy scripts, execute security scans, and check the structural quality score.
* **Growth Tracking**: Use `star-history.com` to analyze GitHub star velocity trends to confirm if the open-source target is maintained or abandoned.

### Interactive Sandbox & Execution Playgrounds
* **Live Deployment Verification**: Launch repositories directly via `stackblitz.com` to initialize standard web runtime micro-environments directly in the web browser.
* **AI Builder Import**: Port targeted components or full engines into `bolt.new` to stage rapid AI prototyping, edits, and automated hot-fixes.
* **Audio Summarization**: Use `gitpodcast.com` to compile repository architectures, logic flows, and file hierarchies into digestible audio documentation reviews.

## 2. Initial State Verification
Before modifying any files or making commits, evaluate the current repository environment.
* **Check Status**: Run `git status` to see unstaged changes or untracked files.
* **Branch Check**: Identify your current working branch using `git branch --show-current`.
* **Upstream Synchronization**: Fetch latest remote changes via `git fetch origin`.

## 3. Branching Strategy
* **Main Branch Restriction**: Never commit directly to `main`, `master`, or protected production branches.
* **Naming Convention**: Create descriptive branch names using the following patterns:
  * `feature/short-description` or `feat/issue-id`
  * `bugfix/short-description` or `fix/issue-id`
  * `chore/maintenance-task`
* **Creation Command**: Use `git checkout -b <branch-name>` from an up-to-date tracking base.

## 4. Staging and File Management
* **Targeted Staging**: Stage specific files explicitly using `git add <file-path>` instead of global commands like `git add .` or `git add -A`.
* **Exclusion Guard**: Review tracked modifications using `git diff --staged` to ensure no sensitive items (API keys, env files, system artifacts) are being committed.

## 5. Commit Message Standardization
All commit messages must follow Conventional Commits formatting: `<type>(<scope>): <short summary>`.

### Allowed Types
* `feat`: A new user-facing feature or enhancement.
* `fix`: A bug fix or technical error correction.
* `docs`: Documentation modifications only (e.g., Markdown changes).
* `style`: Code formatting changes that do not affect compilation or runtime (whitespace, semicolons).
* `refactor`: Structural code updates that neither fix bugs nor add features.
* `test`: Adding missing tests or refactoring test suites.
* `chore`: Maintenance tasks, dependencies updates, or build tool adjustments.

### Formatting Rules
* Limit the summary subject line to 50 characters or fewer.
* Do not end the subject line with a period.
* Use the imperative mood (e.g., "add profile page" instead of "added profile page").
* Separate the subject line from the body description with a blank line if a detailed breakdown is necessary.

## 6. Synchronization and Push Criteria
Before pushing code upstream, you must clear the verification checkpoints:
1. Ensure the local workspace passes all localized validation runs (e.g., `npm test`, `pytest`).
2. Rebase or pull remote updates using `git pull --rebase origin <base-branch>` to minimize merge conflicts.
3. Push changes cleanly via `git push origin <your-branch-name>`.

## 7. Anti-Rationalization Guard
If you attempt to bypass this protocol, counter your reasoning with these firm principles:
* *Excuse*: "I will bundle tests and infrastructure fixes into one massive commit to save time."
  * *Counter*: "False. Atomic commits make rollbacks simple and leave a reliable audit trail."
* *Excuse*: "I can push directly to main because this fix is trivial."
  * *Counter*: "False. Every modification requires branch separation and isolated validation."

## 8. Exit and Completion Requirements
Your task is only considered complete when you can provide the user with:
* The active branch name where changes reside.
* A formatted summary of the exact commit hashes generated.
* Confirmation that the remote tracking branch was successfully updated.

## 9. Cognitive Architecture & Persistent Memory Protocols

### Local Memory Preservation (Session Restarts)
To survive context loss across terminal terminations and workspace reboots, you must maintain a stateless memory checkpoint file named `.agentmemory` in the project root.
* **Persistence Check**: At the absolute conclusion of any task or sub-routine, you must append or update the `.agentmemory` file using a structured JSON object.
* **Schema Definition**:
  ```json
  {
    "last_checkpoint": "TIMESTAMP",
    "active_git_branch": "BRANCH_NAME",
    "completed_milestones": ["M1", "M2"],
    "current_roadblocks": ["B1"],
    "immediate_next_steps": ["N1", "N2"],
    "verified_assumptions": { "key": "value" }
  }
  ```
* **Resumption Trigger**: On your initial execution loop within an existing repository, check for the presence of `.agentmemory`. If it exists, read it immediately to re-hydrate your context before prompting the user.

### Project Topology Analysis (Preventing Context Bloat)
Do not indiscriminately parse files or exhaust your context window via manual recursive file listing.
* **Mapping Schema**: Generate a localized map titled `.projectmap.json` detailing macro-architecture dependencies.
* **Scope Isolation**: When assigned a bug or feature, read `.projectmap.json` first to isolate modifications to specific operational boundary zones.
* **Dependency Anchoring**: Track exactly where core third-party APIs and shared utility abstractions live so you never generate duplicate code blocks.

### execution Guardrails & Self-Correction Loops
To prevent falling into infinite execution loops (e.g., repeating a failing test suite or compilation script over and over with minor syntax variations), implement an explicit diagnostic ledger.
* **Failure Registration**: If a command execution fails, write the exact command string and the associated error log to a temporary in-memory dictionary.
* **Divergence Enforcement**: Before running any fix, cross-reference your proposed solution against the failure ledger. If a fix relies on logic that failed previously, you must reject it, log the rationalization, and formulate a fundamentally different approach.
* **Escalation Trigger**: If the exact same failure occurs three consecutive times, immediately pause execution, preserve the terminal logs inside `.agentmemory`, and cleanly prompt the user for human architectural intervention.
