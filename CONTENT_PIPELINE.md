# Adaptive lesson content pipeline

The backend selects explanation depth from existing chapter results, then reads an adapted lesson from PostgreSQL. Default depth serves the original lesson unchanged. Missing, outdated or invalid adapted content falls back to that original lesson. Student requests never call a model provider.

## Automatic explanation depth

Reuse existing first-answer evidence, at most the five most recent distinct answers per concept. Repeated fixed questions and exhausted-bank revision do not inflate evidence. Require at least ten counted answers and at least one answer for every chapter concept; otherwise use Default. Below 60% correct selects Beginner, 60% to below 80% selects Default, and 80% or above selects Advanced. This is a transparent chapter-level heuristic, not the future five-signal aptitude engine. Resetting results resets this selection. Education level and assessment selection remain unchanged.

Only the chapter source and concept revision cards go to the provider. User identity, answers, scores, assessment questions and answer keys are excluded. Both depth variants are shared across students and can be prepared ahead of time.

## Provider configuration

Configure these variables only in the backend/operator environment. Never use VITE-prefixed keys or commit credentials.

```dotenv
CONTENT_PROVIDER=openai-compatible
CONTENT_API_BASE_URL=https://integrate.api.nvidia.com/v1
CONTENT_API_KEY=<your NIM key>
CONTENT_MODEL=<exact model ID from your NIM account>
CONTENT_OUTPUT_MODE=json_object
CONTENT_PIPELINE_ENABLED=false
```

| Provider | CONTENT_PROVIDER | CONTENT_API_BASE_URL |
| --- | --- | --- |
| NVIDIA NIM | openai-compatible | https://integrate.api.nvidia.com/v1 |
| OpenRouter | openai-compatible | https://openrouter.ai/api/v1 |
| OpenAI | openai | https://api.openai.com/v1 |
| Anthropic | anthropic | https://api.anthropic.com/v1 |

Switch provider URL, protocol, model and key together. No DB migration or frontend change is required. Pick an explicit model ID; free access, quotas and model availability are provider-controlled. No automatic paid fallback or provider switching occurs. The OpenAI protocol uses max_completion_tokens; NIM/OpenRouter use max_tokens. Both use Chat Completions. Anthropic uses Messages and structured JSON output.

For compatible endpoints, json_object requests JSON mode, json_schema requests strict structured output, and text omits response_format for models without JSON-mode support. Every mode includes the schema in the instructions and undergoes the same local Pydantic validation. Select a mode supported by the chosen model. A refusal, truncation, malformed JSON or unsupported API parameter fails the job; it is never published as a usable lesson. Text mode still requires a JSON object, without code fences. No tools or model-executed code are enabled.

## Migration and rollout

1. On an isolated database branch, run `python -m scripts.generate_content --migrate-only` using DATABASE_URL_UNPOOLED set to the schema owner's direct (non-pooler) connection. This applies migrations/003_content_pipeline.sql without a provider key or call. Verify the content table, partial unique index and admin SELECT grant. The migration is additive and repeatable.
2. Set DATABASE_URL_UNPOOLED in the operator environment to that direct connection; DATABASE_URL remains the normal runtime connection. Existing API settings, including JWT_SECRET, are still required by the app's settings loader.
3. Inspect source without calling the provider: `python -m scripts.generate_content --chapter all --tier both --dry-run`.
4. Generate one sample: `python -m scripts.generate_content --chapter ch-01 --tier beginner --max-generations 1`. Inspect stored content for mathematical correctness. Schema validation does not establish correctness or teacher review.
5. After validation, repeat the migration against the app database and pre-generate there. `python -m scripts.generate_content --chapter all --tier both --max-generations 28` covers all 14 chapters and both adapted depths. Existing matching generations are reused. The default limit is one call; a failed job stops the run. Each call has a 6000-token output cap, 10-second connection timeout and 90-second read timeout. These are bounded requests, not a currency budget.
6. Deploy the backend with CONTENT_PIPELINE_ENABLED=true only after migration. Deploy the frontend. The disabled default does not query the new table, making an early deployment safe. The HTTP-serving environment does not need a provider key: only the publisher does.

`--migrate` can apply schema 003 before generation, using the owner connection. `--dry-run` cannot perform migration or recovery writes. The command holds a session advisory lock on its direct connection to serialize publishers. Pending jobs are committed before provider calls. After a publisher crash, rerun with `--recover-pending` only after diagnosing the failure; the exclusive lock ensures no other publisher is active. An uncertain provider timeout can have consumed tokens even though it recorded a failure, so there is no automatic retry.

## Persistence and cache identity

Each generation has a UUID, source snapshot and hash, prompt version, provider/endpoint/model/output mode, status, timestamps, provider-reported usage, raw text and validated content. Numeric cost data are stored if returned in usage; absent costs are unknown, not zero. Failed generations remain for diagnosis; an explicit retry receives a new UUID. Credentials and raw provider errors are not stored.

The cache key includes source hash, depth, prompt version, provider endpoint/protocol, model and output mode. A partial unique index prevents two pending/ready generations for the same key. Changing source or prompt version invalidates serving old content. For each source/depth, the reader serves the newest ready generation across providers, so previously prepared content remains usable after changing operator credentials. Bump PROMPT_VERSION when changing prompts or schema. No Redis or background queue is needed for 28 shared variants.

`GET /learning/courses/{course}/chapters/{chapter}` derives depth server-side and returns contentVariant alongside the original lesson. `GET /learning/content/{generation_id}` retrieves a ready version after authentication; outdated source returns 410. Neither exposes raw provider responses, source snapshots or usage metadata. Content is plain text rendered through React, never injected as HTML. Generated lessons display their unreviewed status, section links, worked examples, self-check prompts, takeaways and a rough reading-time estimate. verified defaults to false and must only be updated after actual review; no review dashboard is included.

## Verification and current deployment state

Run `python -m unittest discover -s tests`. Offline tests use disposable SQLite plus mocked HTTP provider responses. They cover source redaction, persistence before generation, cache reuse/invalidation, pending deduplication, failures/refusals/truncation, provider request contracts, result-derived depth, cross-user isolation, reset and disabled-rollout behavior. These do not replace a real PostgreSQL migration test or live model-quality check.

Verification completed: 56 backend tests and 5 frontend tests passed, along with TypeScript, ESLint and the production build. Local HTTP checks exercised authentication, different depths for two students, cache reuse, UUID retrieval and fallbacks. Browser checks confirmed automatic Beginner selection, section navigation, reload persistence, missing-variant fallback and Default for a chapter without evidence. These checks used SQLite and fixture-generated content, not a live provider or Neon.

Implementation defaults disabled. As of 24 September 2026, live NIM generation and Neon migration still require working operator credentials. The Neon connector is rejecting project-scoped calls and the previous isolated-branch credentials no longer authenticate. No mock-generated lesson has been published to the app database.

Provider references: [NVIDIA LLM API](https://docs.api.nvidia.com/nim/re/reference/llm-apis), [OpenRouter Chat Completions](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request), [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
