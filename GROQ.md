# Groq configuration

Groq can use the existing OpenAI-compatible adapter. The scoped GPT-OSS integration uses `max_completion_tokens`, explicit reasoning effort and `include_reasoning=false`. Internal reasoning is excluded from stored/served answers; this does not disable the model's reasoning or remove its token cost. Unsupported provider options are rejected before an API call.

Use a Groq key in the backend environment only. No frontend key or Groq SDK is needed.

```dotenv
CONTENT_PROVIDER=openai-compatible
CONTENT_API_BASE_URL=https://api.groq.com/openai/v1
CONTENT_MODEL=openai/gpt-oss-120b
CONTENT_API_KEY=<backend secret>
CONTENT_OUTPUT_MODE=json_schema
CONTENT_STREAM=false
CONTENT_MAX_TOKENS=4096
CONTENT_READ_TIMEOUT=90
CONTENT_TEMPERATURE=0.2
CONTENT_REASONING_EFFORT=medium
TUTOR_REASONING_EFFORT=medium
TUTOR_MAX_TOKENS=2048
TUTOR_READ_TIMEOUT=45
TUTOR_TEMPERATURE=0.2
```

Remove `CONTENT_ENABLE_THINKING` and `TUTOR_ENABLE_THINKING`, including explicit `false` values: these options belong to NIM. Remove the old `CONTENT_TOP_P` override so only temperature controls sampling. Restart the backend after environment changes.

Reasoning effort accepts `low`, `medium` or `high` for Groq's `openai/gpt-oss-20b` and `openai/gpt-oss-120b`. When unset, those models use an explicit medium effort. Unset Groq effort overrides when switching to a different provider or unsupported model. No automatic provider fallback or retry was added.

Groq JSON Schema output requires non-streaming requests. The adapter rejects `CONTENT_OUTPUT_MODE=json_schema` with `CONTENT_STREAM=true`; JSON Object mode remains available. Application schema and curriculum checks still run after generation, and shared lessons require mathematical review before publication. Structured output guarantees shape, not mathematical truth.

Keep activation flags unchanged while testing. `CONTENT_PIPELINE_ENABLED` controls retrieval of reviewed DB lessons, not provider calls. The operator publishes new lesson variants separately. `TUTOR_ENABLED` independently controls live tutor calls; test harnesses can enable it only in their own process without changing `.env`.

## Limits and verification

As checked on 3 October 2026, the published GPT-OSS 120B free limits are 30 requests/minute, 1,000/day, 8,000 tokens/minute and 200,000 tokens/day. Account limits are authoritative. Prompt and output token budgets both matter: a 131K model context window does not imply that a free account can send that much. Long chapter references or rapid calls can return 429. A paid plan can increase limits but does not guarantee availability.

Sources: [models](https://console.groq.com/docs/models), [limits](https://console.groq.com/docs/rate-limits), [GPT-OSS reasoning](https://console.groq.com/docs/reasoning#reasoning-effort), [structured outputs](https://console.groq.com/docs/structured-outputs).

The initial live probe connected successfully but exposed a wrong polynomial solution, one formatting rejection and a rate limit. Subsequent paced checks use the real backend adapter and public chapter source, without student data or DB publication. Passing a small smoke suite does not prove all mathematical answers correct or production rollout complete.

The final tutor prompt distinguishes a supplied zero from an explicitly repeated zero and requires checking signed coefficients, expansion and substitution. Final four-case checks returned correct signed-coefficient arithmetic, the explicitly repeated-root solution and an off-topic redirect (0.94–1.95 seconds); the missing-information case was rejected by the formatting guard. A separate targeted repeat of that case returned the correct infinite family in 1.42 seconds. This is three of four successful answers in that final batch, with a successful repeat; it is not evidence of 100% tutor reliability.

The live Polynomials lesson completed with strict schema output in 5.48 seconds. Its shape was valid, but the mathematical guard rejected a non-monic-scaling claim that omitted the exception for multiplier 1. The draft was not published. The existing 28 reviewed DB variants remain unchanged and independent of this provider test.

A separate Real Numbers Beginner lesson completed in 5.11 seconds and passed the application schema and curriculum guards. This proves the configured lesson-generation path can complete successfully; the output remains a local draft and still requires review before any publication.
Manual inspection found overbroad takeaway wording about expressions containing an irrational square root, an unqualified HCF/LCM product statement and periodic-event alignment. Those claims need correction/conditions before approval. Automated guard success is not mathematical approval.

Backend regression suite: 102 tests passed, including Groq payload scoping, supported reasoning settings, incompatible schema/stream rejection and ignored reasoning deltas. No production deployment, feature activation, automatic failover, DB migration or curriculum publication was performed during configuration.

## Local tutor readiness — 3 October 2026

The remaining formatting rejection was reproduced and captured: the model returned a correct polynomial family with `r\in\mathbb{R}`. The normalizer did not support number-set notation, and a Unicode word boundary prevented matching `\in` directly before `ℝ`. The normalizer now converts a bounded set of number-set symbols, membership/quantifier commands, spacing and boxed results into plain Unicode text. ASCII command boundaries prevent partial matching of unknown commands. Parentheses preserve boxed/fraction precedence; unsupported commands and HTML still fail closed. No renderer, dependency or additional provider request was added.

The updated offline suite passes all 106 tests. A paced live batch covered Real Numbers, Polynomials, Quadratic Equations, Arithmetic Progressions, Triangles, Trigonometry, Statistics and Probability at Beginner, Default and Advanced depths. All eight final answers were checked against the stated problems and were mathematically correct. Before the fix, seven were served and the polynomial-family answer failed the formatting guard. Replaying that exact captured answer through the fixed normalizer passed without changing its conditions. This batch was not rerun wholesale after the fix and is not a guarantee of correctness for arbitrary questions.

A subsequent real Groq request through FastAPI returned the correct HCF(48,18)=6 in 1.31 seconds. All 14 API/persistence checks passed: authentication, no-store headers, provider-metadata redaction, persisted turn/history/events, idempotent retry without a second inference, saved-note persistence/idempotency and user ownership. Storage for this HTTP check was disposable SQLite, with separate sessions per request. Neon was checked read-only: Flyway version 7 and the required runtime table permissions are present. No live student records were changed by these checks.

Only the local backend `.env` is activated:

```dotenv
ENGAGEMENT_ENABLED=true
TUTOR_ENABLED=true
CONTENT_PIPELINE_ENABLED=false
```

Restart the local backend to load these flags. Engagement is required for chapter-tutor routes and also enables the existing enrollment, reading-progress and assessment-readiness flow. After signing in, enroll/select Maths, open a Class 10 chapter and use **Ask about this chapter**; completed answers can be saved to Notes. Existing subject preferences and coursework remain in Neon.

Production flags and Cloud Run deployment remain deferred. Shared lesson variants are still read from reviewed database content when their retrieval flag is enabled; this change adds no automatic lesson generation on a cache miss. Provider quota/availability and mathematical uncertainty remain possible; existing request limits, failure states and student review/flag controls remain in place.
