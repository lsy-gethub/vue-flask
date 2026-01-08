# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a graduation project (毕业设计) - a power distribution network simulation system with AI-based dispatch. It simulates transformer networks, users, and switches, with AI agents (Coze) for power allocation optimization.

## Tech Stack

**Backend:**
- Python Flask (single-file backend: `app.py`)
- Coze AI SDK for intelligent agent integration
- CORS enabled for frontend-backend communication

**Frontend:**
- Vue 3 (Composition API with `<script setup>`)
- Vite build tool
- Pinia for state management
- Element Plus UI component library
- ECharts for data visualization
- Vue Router for navigation

## Commands

### Frontend Development
```sh
cd front-end
pnpm install          # Install dependencies
pnpm dev             # Start dev server (Vite, hot-reload)
pnpm build           # Production build (outputs to front-end/dist)
pnpm preview         # Preview production build
```

### Backend Development
```sh
python app.py        # Start Flask server (port 5000)
```

### Full Stack Setup
1. Build frontend: `cd front-end && pnpm build`
2. Run backend: `python app.py`
3. Access app at `http://127.0.0.1:5000`

## Architecture

### Backend (`app.py`)
Single-file Flask application with:
- **Core Classes:**
  - `TransformerCalculator` - Local transformer loss calculation (replaces AI calls for performance)
  - `Transformer` - Transformer device with power/loss attributes
  - `User` - Power consumer with load profiles (6 time slices)
  - `Switch` - Power distribution switch with configuration
  - `Wire` - Connection between components

- **Dispatch System:**
  - Time-slice simulation (6 time points: 0:00, 4:00, 8:00, 12:00, 16:00, 20:00)
  - AI-powered switch dispatch via Coze agents
  - Blackboard pattern for sharing state between dispatch steps
  - Planning suggestions system for network optimization

- **Key API Endpoints:**
  - `POST /api/nodes` - Create transformer/user/switch
  - `POST /api/wires` - Create connections
  - `POST /api/dispatch/init` - Initialize dispatch
  - `POST /api/dispatch/switch/:id` - Dispatch single switch
  - `POST /api/dispatch/continue` - Advance time slice
  - `POST /api/dispatch/finalize` - Finalize and get results
  - `GET/POST /api/planning-suggestions` - Get AI planning advice

### Frontend (`front-end/src/`)
```
front-end/src/
├── main.js              # App entry - imports Vue, Pinia, Element Plus
├── App.vue              # Root component
├── router/index.js      # Vue Router config (4 routes)
├── assets/base.css      # Global styles with CSS variables
├── components/
│   └── Loading.vue      # Loading component
└── views/
    ├── WelcomeView.vue  # Welcome page
    ├── MainView.vue     # Main canvas - drag-drop, wiring, AI dispatch
    └── NotFound.vue     # 404 page
```

### MainView.vue Architecture
- **Canvas System:** Drag-drop components, pan/zoom support
- **Linking System:** Connect components to form power network topology
- **Parameter Editor:** Contextual panel for editing component properties
- **Simulation Engine:** Multi-time-slice power flow simulation
- **Visualization:** ECharts charts for transformer power, line losses

## Key Patterns

### Node Types
- `transformer` - Power transformer (200kVA or 630kVA capacity)
- `user` - Power consumer (residential/commercial/industrial with load profiles)
- `switch` - Distribution switch with config dict `{transformerId: enabled}`

### Time-Slice Simulation
- 6 time slices representing 24-hour cycle
- Each user has a load profile array `[P0, P4, P8, P12, P16, P20]`
- Dispatch runs per time slice, updating user demand dynamically

### Blackboard Pattern
Global state (`blackboard`) shared across dispatch steps:
- `ai_results` - AI agent responses for transformers/users/switches
- `dispatch_state` - Intermediate dispatch calculations
- `planning_suggestions` - AI-generated network optimization advice

## Environment Variables
- `COZE_API_TOKEN` - Coze API authentication token
- `COZE_BOT_ID_*` - Bot IDs for dispatch/switch/planning agents
- `COZE_USER_ID` - User identifier for Coze API calls

## Development Notes
- Frontend serves static files from `front-end/dist` via Flask in production
- Transformer loss calculation uses local formulas (no AI call needed):
  - Load factor β = S_current / S_rated
  - Load loss P_k = β² × P_kn (rated load loss)
  - Total loss = No-load loss + Load loss
- Power factor fixed at 0.8 for calculations
- Network topology: Transformer → Switch → User
