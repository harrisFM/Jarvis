# Jarvis

Research and build plan for a state-of-the-art personal AI assistant ("Jarvis") for the home, as of September 2026.

- **Start here:** [`docs/JARVIS-PLAN.md`](docs/JARVIS-PLAN.md) — executive summary, requirements, architecture, component decisions, hardware tiers, latency and cost budgets, security model, phased roadmap.
- **Research notes with sources:** [`docs/research/`](docs/research/) — six notes covering the DIY landscape, the speech stack, LLMs/agents/memory, hardware, orchestration and Home Assistant, and UX/vision/privacy/operations.

The plan recommends a streaming voice cascade (XMOS satellites → Pipecat → local STT/TTS on a 128 GB unified-memory GPU box → tiered LLMs with Claude Sonnet 5 / Opus 5 and a local Qwen3.6 fallback → Home Assistant and MCP tools), with an explicit permission harness and self-hosted memory. Facts the research could not verify against a primary source are marked "(uncertain)" in the documents.
