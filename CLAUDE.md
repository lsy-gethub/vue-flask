# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repository is a full-stack power network simulation app:

- `app.py` is the single Flask backend. It stores the entire network topology and dispatch state in in-memory global dictionaries, exposes all JSON APIs, calls Coze agents, and serves the built frontend from `front-end/dist`.
- `front-end/` is a Vue 3 + Vite single-page app. The main application logic lives almost entirely in `front-end/src/views/MainView.vue`.
- The frontend talks directly to the backend at `http://127.0.0.1:5000` via `fetch`; there is no Vite proxy configured.

## Common commands

### Frontend (`front-end/`)

```bash
cd front-end
pnpm install
pnpm dev
pnpm build
pnpm preview
```

Notes:
- `front-end/package.json` only defines `dev`, `build`, and `preview` scripts.
- There is no configured frontend test or lint script in `front-end/package.json`.
- There is no single-test command configured because no test runner is currently set up.
- Vite requires Node `^20.19.0 || >=22.12.0`.

### Backend (repo root)

```bash
python app.py
```

Notes:
- The Flask app runs on `0.0.0.0:5000` with `debug=True`.
- `app.py` expects the frontend build output at `front-end/dist`; if that directory is missing, it prints a warning and still starts.
- The backend imports `flask`, `flask_cors`, and `cozepy`. There is no `requirements.txt` or `pyproject.toml` in the repo, so dependency installation must be inferred from imports.

### Full app workflow

For local development, run these in separate terminals:

```bash
cd front-end && pnpm dev
python app.py
```

For backend-served frontend output:

```bash
cd front-end && pnpm build
python app.py
```

## Architecture

### Backend state model

`app.py` is stateful and keeps the whole simulation in module-level globals instead of a database:

- `transformers`, `users`, `switches`, `wires`: core topology objects
- `next_node_id`, `next_wire_id`: in-memory ID counters
- `blackboard`: shared AI/dispatch/planning state
- `current_time_slice`: current index into the 6-point daily load profile

This means:
- state resets when the Flask process restarts
- most frontend actions must stay synchronized with backend-created IDs
- debugging often requires inspecting both frontend local state and backend globals

### Backend domain model

Core classes in `app.py`:

- `Transformer`: stores rated capacity, current power, losses, and derived max active power
- `User`: stores user type plus a 6-point `load_profile`
- `Switch`: stores transformer enablement in `config`
- `Wire`: stores graph connections between components
- `TransformerCalculator`: local deterministic loss calculator used instead of AI for transformer loss computation

Important domain detail:
- transformer nameplate capacity is treated as kVA, while active power is derived with fixed power factor `0.8`
- time slices are fixed to 6 labels: `0:00`, `4:00`, `8:00`, `12:00`, `16:00`, `20:00`

### Dispatch pipeline

The dispatch flow in `app.py` is multi-step and should be preserved when changing simulation behavior:

1. `init_dispatch()` or `init_dispatch_continue()` initializes the current time slice and remaining demand/capacity.
2. `dispatch_switch(sid, is_continue=False)` dispatches one switch at a time.
3. `get_switch_ai_params()` sends structured JSON topology data to the Coze switch agent.
4. `_sanitize_switch_plan()` clamps AI output to actual adjacency, remaining demand, and remaining transformer capacity.
5. `finalize_dispatch()` recomputes transformer output/loss locally and returns the final snapshot.

The frontend uses the stepwise API (`/api/dispatch/init`, `/api/dispatch/switch/<id>`, `/api/dispatch/finalize`) rather than relying only on the older `/api/ai-dispatch` endpoint.

### Planning/advice system

Planning suggestions are a separate backend flow from dispatch:

- `build_network_topology()` summarizes the current network
- `get_planning_advice_from_ai()` calls the Coze planning agent
- `analyze_network_redundancy()` adds local heuristic suggestions
- `/api/apply-suggestion` mutates topology directly by creating/deleting wires or adding components

When changing planning behavior, check both the Coze-driven path and the local redundancy-analysis fallback logic.

### Frontend structure

Important frontend entry points:

- `front-end/src/main.js`: creates the Vue app, installs Pinia, router, and Element Plus
- `front-end/src/router/index.js`: routes `/home` to `WelcomeView.vue`, `/main` to `MainView.vue`, and uses history mode
- `front-end/src/App.vue`: owns the route transition/loading overlay logic and wraps routed pages in `<keep-alive>`
- `front-end/src/components/Loading.vue`: fullscreen loading overlay used for route transitions
- `front-end/src/views/WelcomeView.vue`: animated landing page
- `front-end/src/views/MainView.vue`: main editor/simulator UI

### Frontend design constraints

`front-end/src/views/MainView.vue` is the central file for almost all product behavior. It contains:

- drag/drop canvas state
- node and wire creation/editing
- context menus
- backend synchronization via `fetch`
- AI dispatch orchestration
- simulation engine state machine
- planning suggestion UI
- ECharts visualization logic
- import/export/reset flows

Before refactoring `MainView.vue`, check whether a change touches both local canvas state and backend persistence/stateful APIs.

### Frontend/backend synchronization

The frontend keeps its own local node/line objects and also stores backend IDs (`backendId`) returned by Flask APIs. Many operations are mirrored:

- create node locally and on backend
- create wire locally and on backend
- update/delete node or wire locally and on backend
- run simulation against backend state, then hydrate local UI from AI results

Be careful not to update only one side.

## API surface

Major backend routes defined in `app.py`:

- topology CRUD: `/api/nodes`, `/api/nodes/<id>`, `/api/wires`, `/api/wires/<id>`
- dispatch: `/api/dispatch/init`, `/api/dispatch/continue`, `/api/dispatch/switch/<id>`, `/api/dispatch/finalize`, `/api/ai-dispatch`
- AI/planning state: `/api/blackboard`, `/api/blackboard/<kind>/<id>`, `/api/planning-suggestions`, `/api/network-analysis`
- automation/mutations: `/api/apply-suggestion`, `/api/reset-all`
- metadata: `/api/user-types`, `/api/users/<id>`

If frontend API calls need to change, update both `MainView.vue` and the Flask route handlers in `app.py`.

## Coze integration

`app.py` initializes Coze from environment variables, with hardcoded fallbacks currently present in code:

- `COZE_API_TOKEN`
- `COZE_BOT_ID_100KW`
- `COZE_BOT_ID_500KW`
- `COZE_BOT_ID_SWITCH`
- `COZE_BOT_ID_ADVICE`
- `COZE_USER_ID`

The active Coze usage in this codebase is primarily for:
- switch-level dispatch plans
- planning suggestions

Transformer loss calculation is handled locally by `TransformerCalculator` instead of AI.

## Existing docs/config sources

- `front-end/README.md` is the default Vite/Vue template README and only contributes the standard `pnpm install`, `pnpm dev`, and `pnpm build` workflow.
- No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` were found in this repository.
