# issue-prioritiser
A tool that analyzes GitHub issues and ranks them by priority and contributor-friendliness using NLP and metadata.

## Tech stack

- Backend: Python (FastAPI)
- Frontend: React
- Database: PostgreSQL (SQLite for local development)
- Others: Docker (for deployment, later)

## Planned features

- Connect a GitHub repository and fetch open issues.
- Score issues by priority and contributor-friendliness.
- Dashboard to filter and sort issues by score.
- Explanations for why each issue received its score.

## Scoring Metrics

Issues are scored on two dimensions: **Priority** and **Friendliness**. Both scores are out of 10.

### Priority Score (0-10)
Reflects the urgency and importance of an issue.

- **10 (Critical):** Blocks all core user functionality (e.g., login, checkout), causes data corruption/loss, exposes severe security vulnerabilities, or takes down production services. *Immediate, all-hands-on-deck required.*
- **8-9 (High):** Impacts a large percentage of users or a critical business flow (e.g., broken search, major UI component failing). Significant degradation in system performance or reliability. Directly affects revenue or critical user workflows.
- **5-7 (Medium):** Affects a moderate number of users or a non-critical feature. Includes important enhancements that improve efficiency or user experience, or minor bugs with workarounds. (e.g., UI glitch in a rarely used page, adding a small filter option).
- **2-4 (Low):** Cosmetic issues (e.g., misaligned elements, wrong color), typos, minor UI/UX suggestions, or small, non-disruptive performance improvements. Has little to no impact on core functionality. (e.g., changing button border-radius, updating a tooltip text).
- **0-1 (Trivial/Backlog):** Purely speculative ideas, very minor aesthetic tweaks, or issues explicitly marked as "won't fix" or "future consideration." No immediate action needed.

### Friendliness Score (0-10)
Reflects how approachable and suitable an issue is for new contributors.

- **10 (Perfect First Issue):** Clearly defined task with detailed steps (e.g., "Change button color from blue to green in `src/components/Button.js`"), explicitly labeled "good first issue" or "easy-fix". Requires modifying 1-2 files. Setup instructions are comprehensive and easy to follow.
- **8-9 (Good for Beginners):** Task involves a single, isolated component or module. Clear problem description and expected outcome. May require slight debugging or understanding of local project conventions. Max 3-5 files involved. Requires basic familiarity with the project's tech stack.
- **5-7 (Intermediate):** Requires understanding of interconnected components or a specific feature area. Problem might require some investigation to reproduce. Involves moderate logic changes or additions. Good for someone familiar with the tech stack but new to the codebase. (e.g., adding a new field to an existing form, implementing a simple API integration).
- **2-4 (Challenging):** Involves multiple modules, significant logic changes, or refactoring existing code. Requires debugging complex interactions or understanding architectural patterns. Might affect several parts of the system. Requires solid experience with the tech stack and some codebase familiarity.
- **0-1 (Expert Level):** Highly complex, touches core architecture, potential for widespread impact, requires expert domain knowledge. Often involves performance optimization, security fixes, or major feature overhauls. (e.g., database schema changes, refactoring core authentication logic).

## Getting started

Project setup is in progress.

Planned structure:

- `backend/` – FastAPI API for fetching and scoring issues.
- `frontend/` – React dashboard for viewing issues.

Once the initial structure is ready, this section will include install and run commands.