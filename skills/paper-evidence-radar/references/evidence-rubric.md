# Evidence rubric and report contract

Read this file when ranking candidates or writing the final radar.

## Four evidence dimensions

Score in words, not fake precision.

1. **Recency**: first submission and latest revision; whether the field moves fast enough for age to matter.
2. **Relevance**: direct match to the user's failure mode, not broad topical similarity.
3. **Maturity**: official code, weights/data, license, reproducibility, hardware and model-access requirements.
4. **Decision value**: whether the finding changes an implementation, architecture, experiment, or benchmark choice.

## Triage lanes

### Actionable now

The user can integrate or test it within the stated horizon. Include:

- mechanism;
- exact landing point;
- prerequisites and cost;
- smallest validating experiment;
- stop condition.

### Architecture lesson

The implementation is unavailable or unsuitable, but the failure mechanism or design principle should alter a decision. State what not to copy and what principle transfers.

### Evaluation benchmark

The work provides a runnable or adaptable test. State inputs, metrics, license, integration effort, and what a passing result would mean.

## Report template

```markdown
# [Question] research radar - YYYY-MM-DD

Search window: [...]  Queries: [...]  Candidates screened: N  Retained: N

## Decision summary
[One paragraph and the 1-2 next actions]

## Actionable now
### [Paper title]
- Evidence: [paper] [project] [code]
- Dates and maturity:
- Mechanism:
- User consequence:
- Smallest test:
- Boundary:

## Architecture lessons
[Same evidence-first shape]

## Evaluation benchmarks
[Same evidence-first shape]

## Delta from previous run
[New, changed, obsolete, or “first run”]
```
