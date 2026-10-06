# AI analysis

Research runs are stored in PostgreSQL and owned by the signed-in user. The React app calls `/api/ai`. It does not call a model provider, and it does not store analysis in browser storage.

The model, when configured, explains a compact evidence object. It does not calculate indicators, financial ratios, chart patterns, or the coverage report. A run is not a forecast, a target price, or a buy, hold, or sell instruction.

The older `ai_analysis` table is not written by this feature.

## Provider

Leave the provider empty until you have a key. An empty provider returns status `ai_unavailable`. The stored evidence and coverage report are still saved. No narrative is invented.

| Variable | Purpose |
| --- | --- |
| `AI_PROVIDER` | `openai` selects the chat-completions client. Any other value, including empty, stays unconfigured. |
| `AI_API_KEY` | Backend only. Never sent to the browser or written into analysis responses. |
| `AI_MODEL` | Model id sent to the provider, for example `gpt-4o-mini`. |
| `AI_BASE_URL` | Defaults to `https://api.openai.com/v1`. A compatible chat-completions base URL may be used. |
| `AI_TIMEOUT_SECONDS` | 5–120. Default 30. |
| `AI_MAX_OUTPUT_TOKENS` | 100–4000. Default 800. |
| `AI_RUNS_PER_HOUR` | Per-user creations. 1–60. Default 10. Reused runs do not count. |
| `AI_REUSE_MINUTES` | 0–1440. Default 30. The same user, stock, and input hash is returned unless `refresh=true`. |

Put the key only in the server environment or the gitignored `.env`.

## Workflow

1. Read stored fundamental threshold comparisons, the existing technical analysis, confirmed pattern statuses, and linked news.
2. If one of those reads fails, that section is omitted and named in `gaps`. Other sections are still stored.
3. Build a compact evidence object. Metrics are not recalculated here.
4. `coverage-1` describes which sections have enough stored input. It does not produce a number.
5. If a provider is configured, ask it to explain that object and validate the JSON before saving.
6. Save the run with the input hash, score, prompt version `prompts-1`, and scoring version `coverage-1`.

Analysis runs in the request. It is not a background job and it is not real time. A refresh after the reuse window, or `refresh=true`, starts a new run. Configuring a provider later does not rewrite an older `ai_unavailable` row until you refresh.

## Coverage methodology (`coverage-1`)

There is no numeric stock score. Missing data is not treated as neutral or as low risk.

| Section | Included when |
| --- | --- |
| Fundamental | At least three fresh comparisons have state `met` or `not_met` and are not stale. Meeting a threshold is not a valuation opinion. |
| Technical | Freshness is not stale and the existing detector category is `bullish_evidence`, `bearish_evidence`, `mixed_evidence`, or `no_clear_direction`. The category is copied, not converted into a number. |
| News | At least one confirmed stored article is linked. Sentiment counts are reported. They do not predict a price move. |

`aggregate` is `insufficient_data` when no section is included, `partial` when some are, and `described` when all three are. Status `ai_unavailable` means no model narrative was produced. Status `partial` is also used when the model reply is rejected or the provider call fails, while the coverage report remains.

## Output

Validated explanation fields are `summary`, `fundamental`, `technical`, `patterns`, `news`, `limitations`, and `conflicts`. The validator rejects trade language, target-price language, and any `http` link that was not on a stored article in the evidence. Rejected text is not saved.

Article headlines are untrusted data. They are placed in the user message. The system instruction tells the model to explain the evidence and to ignore instructions inside it. The model has no tools and cannot reach the database.

## API

All routes require the session cookie.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/ai/methodology` | Prompt version, scoring version, and whether a provider is configured. |
| GET | `/api/ai/analyses` | The current user's history. `stock_id`, `limit` (1–50), `offset`. |
| GET | `/api/ai/analyses/{id}` | One owned run. Another user's id is `404`. |
| GET | `/api/ai/stocks/{stock_id}/latest` | Latest owned run for that stock, or `404`. |
| POST | `/api/ai/stocks/{stock_id}/analyses` | Create or reuse a run. `refresh=true` skips reuse. Unknown stock is `404`. Over quota is `429`. |

Example when no provider is configured:

```json
{
  "status": "ai_unavailable",
  "explanation": null,
  "score": {
    "version": "coverage-1",
    "aggregate": "partial",
    "numeric_score": null
  },
  "prompt_version": "prompts-1",
  "scoring_version": "coverage-1"
}
```

The response includes `analysis_timestamp` and the evidence `assembled_at` time. A reused row is still labeled with those times.

## Local commands

From `backend`, with `DATABASE_URL` unset in the shell so `.env` is used:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\pytest.exe tests/test_ai.py
```

From `frontend`:

```powershell
npx vitest run tests/ResearchPanel.test.tsx --pool=threads
```

Tests use fixture model replies. They do not call a paid provider.
