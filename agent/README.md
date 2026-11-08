# agent

The agent lives in `backend/agent.py`, not here (it runs inside the backend). This folder is empty
apart from this note.

- Nemotron 3.5 Lightning (`NEMOTRON_AGENT_MODEL`) over build.nvidia.com's OpenAI-compatible API,
  OpenRouter (`OPENROUTER_MODEL`) as fallback. Thinking off.
- Tools: `find_item`, `where_is`, `item_history`, `look_at_snapshot` (Super VL). See
  `docs/interfaces.md` section 4.
- Carer alerts are not an agent tool: Spacetime decides when (`check_alerts`) and the backend's
  sender loop texts them (`backend/alerts.py`). See section 5.
- Try it without the device: `POST /ask_text` with `{"question": "where's my wallet?"}`.
