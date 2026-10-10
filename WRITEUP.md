# Support Ticket Triage Agent: Write-up

## 1. Architecture decisions and why

- **The LLM decides, code enforces.** The model reads the whole thread, calls tools and proposes urgency, intents, action and a draft. Deterministic guardrails then enforce policy that must not depend on the model: money disputes, Enterprise outages, security, promises, language, grounding. Guardrails can only *raise* action or urgency, never lower them.
- **Tool registry.** Each tool is a Pydantic args model plus a handler. Its strict schema is generated from that model; failures return to the LLM as structured errors. A new tool is one file plus one line.
- **Pydantic contract.** The model fills a strict schema and gets one repair attempt. Audit fields (tools used, overrides, cost) are set only by code.
- **LLM behind an interface, prompt as a file, no framework.** A scripted `FakeLLM` lets the whole pipeline run offline. The loop stays short and debuggable.

## 2. What could go wrong and how I handle it

- **Hallucinated answers.** The draft may only cite retrieved KB ids, and unretrieved ids are removed. An uncited auto-reply is downgraded.
- **Wrong escalation.** Hard rules cover money, outages and security, and low confidence escalates. The eval treats missed escalations as the headline metric.
- **Tool or LLM outage.** Timeouts, backoff retries and an iteration cap. Any failure ends in escalate-to-human with a holding reply and a logged reason, never silently.
- **Prompt injection.** Ticket text is delimited and escaped, and treated as data. A rule escalates and discards the draft.
- **Language mix.** The language is detected from the ticket, not taken from the model. A wrong-language draft is replaced.
- **Status page vs reality.** The status tool returns the public page and the internal feed together, so a conflict is visible (T-1002).
- **Drift, cost, PII.** Model is set by environment variable; tokens, cost and latency are recorded per ticket; identifiers are stripped before the LLM and masked in logs.

## 3. How I'd evaluate it in production

1. **CI regression.** Run the labelled set, growing with real tickets, on every prompt or model change. Block on escalation recall; track urgency/action accuracy and escalation precision.
2. **Shadow mode.** The agent triages live tickets while humans act. Measure agreement.
3. **Human-in-the-loop.** Agents approve drafts; track the override rate per field and per guardrail.
4. **Gradual auto-respond.** Only for low-risk, high-agreement intents, behind a percentage rollout. A/B test prompts.
5. **Live metrics.** Missed escalations, override rate, reopen rate, time to first response, CSAT, cost and latency per ticket.
6. **Monitoring.** Weekly sampled reviews; alerts on shifts in the urgency/action mix, guardrail fire rate and fallback rate.
7. **Feedback loop.** Every human correction becomes an eval case.
