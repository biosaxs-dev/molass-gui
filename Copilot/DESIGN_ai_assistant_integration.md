# Design: Embedded AI Assistant for molass-gui

**Status**: Paused at discussion stage (2026-09-14). Nothing implemented. Resume by
re-reading this file before writing any code.

**Origin**: User asked about adding "simple AI support in the GUI such that it can
help with the knowledge of the molass codebase", pointing at
[github/copilot-sdk getting-started.md](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md).
Scope, as clarified by the user: help users use molass-gui's *minimal* feature set
(not a general-purpose coding agent) — "another story" from the earlier "GUI stays
simple" wizard-philosophy discussion (see `molass-gui-prototype-status.md` repo
memory, 2026-08-19/20 entries), not in tension with it.

---

## What was investigated

The [GitHub Copilot SDK](https://github.com/github/copilot-sdk) (`github-copilot-sdk`
on PyPI, Python 3.11+) is a JSON-RPC client for the Copilot CLI. Minimal usage really is
~10 lines (`CopilotClient` → `create_session(model=...)` → `session.send_and_wait(prompt)`).
Supports custom `@define_tool`s, a `working_directory` for agentic file access, and
`system_message` customization (append/replace/customize modes) for narrowing scope.

## Architecture sketch (not built)

1. **Async/Tkinter bridge**: SDK is `asyncio`-native; Tkinter is not. Run the client's
   event loop in a background thread, hand results back via `win.after(...)` polling —
   the exact same pattern `rigorous_view.py` already uses for `optimize_rigorously()`,
   so this is not a new idiom for this codebase.
2. **Source of "molass knowledge"** — two options, not mutually exclusive:
   - `working_directory` pointed at a real `molass-library` checkout → Copilot's own
     file/search tools read source on demand (genuinely agentic, but only works for
     developers running from a source checkout, not a plain `pip install molass`
     end user with no source tree present).
   - Curated `system_message` (append mode) distilling
     `molass-library/.github/copilot-instructions.md` — always available, cheaper,
     but static (can't answer "what does this specific error mean" as well).
   - A small custom `@define_tool` exposing *live GUI session state* (current
     decomposition, model, SV) so it can answer session-specific questions, not just
     general ones.
3. **Minimal prototype scope** (if resumed): single "Ask AI…" dialog — text box +
   response pane, one non-streaming `send_and_wait()` call, `working_directory` set
   to molass-library, no streaming/tools/hooks initially.

## Real blocker surfaced: what end users actually need (this is why it's paused)

`pip install` only gets the client library. Actually using it requires:

- **Account & billing**: a GitHub account with an active Copilot license, OR BYOK with
  a separate paid API key (OpenAI/Azure/Anthropic) — a recurring cost decision for the
  end user, not a one-time install like adding `numpy`.
- **Authentication**: first use needs an interactive OAuth device-flow login (browser
  popup) unless the user already has `gh`/`copilot` CLI logged in on that machine, or
  a raw token is supplied (which then becomes molass-gui's responsibility to store
  safely — never logged, never world-readable).
- **Runtime + network**: CLI binary auto-downloaded on first use (tens of MB,
  platform-specific), plus live network egress to the Copilot API (or BYOK endpoint)
  for every query.
- **Audience-specific concern**: SEC-SAXS beamline control computers are frequently on
  locked-down institutional networks (no general internet egress, proxy-only, or fully
  air-gapped), sometimes headless/remote-desktop-only (awkward for OAuth popups), and
  may be subject to data-governance policy against sending code/errors to a
  third-party API. None of this is fixable in code — it's an environment constraint a
  real chunk of molass's actual user base will simply fail on.

**Conclusion reached**: this cannot be bundled into the base `molass-gui` install. If
resumed, it needs to be an explicit opt-in extra (e.g. `pip install "molass-gui[ai]"`)
with its own first-run setup path and graceful hide/detect-and-disable when
unavailable — not something present by default in the wizard flow.

## Open question for next session

Decide the target audience before designing further: developers running molass-gui
from a source checkout with normal internet (all of the above is a non-issue), vs.
genuine end-user beamline scientists (most of the above is a real barrier). The
answer changes what "minimal viable version" even means.
