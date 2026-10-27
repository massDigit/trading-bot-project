# AI Project Template

Universal AI-native development structure for:
- Antigravity
- Claude Code
- Gemini CLI
- other `AGENTS.md`-compatible coding agents

## 📌 Overview
This repository provides a standardized **AI-Native Development Operating System** enabling optimal collaboration between human developers and AI coding agents.

## 🗂️ Documentation & Memory Structure

- **`AGENTS.md`** : Master entry point, documentation routing, decision rules, and non-negotiable agent contracts.
- **`docs/`** : Domain documentation (architecture, stack, business rules, API, database).
- **`.ai/`** : Active project memory:
  - `CONTEXT.md` → Project identity & vision
  - `STATE.md` → Current snapshot & active focus
  - `TASKS.md` → Backlog & active tasks
  - `RULES.md` → Non-negotiable engineering rules
  - `DECISIONS.md` → Approved Architectural Decision Records (ADRs)
  - `ASSUMPTIONS.md` → Unconfirmed assumptions awaiting user validation
- **`.agents/skills/`** : Automated workflows & agent procedures (including `project-bootstrap`).
- **`VERSION`** / **`CHANGELOG.md`** : Current version ([SemVer](https://semver.org/)) and release history ([Keep a Changelog](https://keepachangelog.com/)).

## 🚀 Getting Started

### 1. Bootstrap a New Project
Create the project from the template **without its Git history** (otherwise your new project would still point to the template repository):

```bash
# Option A (recommended): new GitHub repository from the template
gh repo create my-new-project --template massDigit/ai-project-template --private --clone
cd my-new-project

# Option B: local copy without history (--mode=git is required for a private template)
npx degit --mode=git git@github.com:massDigit/ai-project-template.git my-new-project
cd my-new-project
git init
```

> A repository created from the template copies the files only: branch protection and merge settings are **not** inherited. The `project-bootstrap` skill configures them (Step 6).

Then use the `project-bootstrap` skill with your high-level project description.

Ask your AI assistant:
> "Bootstrap this project: [Describe your project vision, target audience, and key requirements]"

The `project-bootstrap` procedure will systematically generate all initial documentation (`docs/` and `.ai/`) before any code is written.

### 2. Daily Workflow
```bash
# Check current project snapshot
cat .ai/STATE.md

# Run validation suite
npm test
```
