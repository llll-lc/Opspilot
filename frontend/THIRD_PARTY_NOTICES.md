# Third-party notices

## Agent Chat UI component baseline

- Upstream: [`langchain-ai/agent-chat-ui`](https://github.com/langchain-ai/agent-chat-ui)
- Fixed source revision: `325517352ca3672c8bc0745c4143b2301dd74997`
- Retrieved: 2026-09-04
- License: MIT, Copyright (c) 2025 Brace Sproul
- Copied/adapted files: `src/components/baseline/avatar.tsx`,
  `src/components/baseline/button.tsx`, `src/components/baseline/card.tsx`,
  `src/lib/utils.ts`, and the Tailwind token structure in `src/app/globals.css`.

The upstream project supplies visual primitives and interaction dependencies only.
OpsPilot does not copy the upstream LangGraph API passthrough route, providers,
thread runtime, API-key handling, or authentication model. The complete MIT text
is preserved in [`LICENSE.agent-chat-ui`](LICENSE.agent-chat-ui).
