# Lyrax Verification Schema

Version: 1.0
Status: Initial specification

## 1. Purpose

This document defines how Lyrax evaluates AI agents.
Every evaluation must preserve raw evidence and produce independently
traceable results.

Lyrax evaluates agents across four independent dimensions.

## 2. Evaluation Dimensions

### 2.1 Capability

Purpose: Measure whether an agent produces the expected output.

Measurements:
- Field-level accuracy.
- Correct fields.
- Missing fields.
- Unexpected fields.
- Incorrect values.

Scoring:
Field Accuracy = Correct Fields / Total Expected Fields * 100

Missing and incorrect fields count as incorrect.
Unexpected fields are reported separately.

Evidence:
- Original input.
- Expected output.
- Actual output.
- Field-level comparison.
- Individual field results.

### 2.2 Reliability

Purpose: Measure consistency across repeated runs.

Measurements:
- Number of successful runs.
- Number of failed runs.
- Consistency percentage.
- Failure classification.

Scoring:
Consistency = Consistent Runs / Total Runs * 100

Failure classifications:
- Random: Failure occurs inconsistently across repeated runs.
- Input-specific: Failure is reproducible for a particular input.

Evidence:
- Input used.
- Every raw output.
- Run timestamps.
- Failure details.
- Classification rationale.

### 2.3 Performance

Purpose: Measure response speed and operational availability.

Measurements:
- Median response time.
- P95 response time.
- Total calls.
- Failed calls.
- Call failure rate.
- Wrong-answer rate, reported separately.

Scoring:
Call Failure Rate = Failed Calls / Total Calls * 100

Wrong Answer Rate = Incorrect Answers / Valid Responses * 100

Response times are measured in milliseconds.

Failed calls must not automatically be classified as wrong answers.

Evidence:
- Individual response times.
- Call status.
- Error messages.
- Raw responses.
- Evaluation timestamps.

### 2.4 Protocol Compliance

Purpose: Verify whether agents correctly implement the protocols
they claim to support.

A2A checks:
- Agent Card retrieval.
- Agent Card validation.
- Task submission.
- Task response validation.

MCP checks:
- Capability negotiation.
- Tool discovery.
- Individual advertised tool calls.
- Tool response validation.

Each check receives its own result:
- PASS
- FAIL
- NOT_RUN

Only protocols explicitly claimed in an agent profile are tested.

Evidence:
- Protocol name and version.
- Request and response.
- Validation results.
- Error details.
- Timestamp.

## 3. Overall Evaluation Results

The four dimensions remain independent.

Lyrax must not hide a failure in one dimension behind a combined score.

Each report contains:
- Agent ID.
- Agent name.
- Evaluation timestamp.
- Capability results.
- Reliability results.
- Performance results.
- Protocol compliance results.
- Raw observations.
- Limitations.

An overall weighted score is not defined in this version.

## 4. Evidence Requirements

Every evaluation result must preserve:
- Original test input.
- Expected output, where applicable.
- Actual agent output.
- Request and response metadata.
- Execution duration.
- Errors and failure details.
- Individual scoring results.

Scores without supporting evidence are insufficient.

## 5. Scoring Rules

- Use deterministic scoring wherever possible.
- Use exact comparisons by default.
- Tolerance rules must be explicitly defined by individual test cases.
- Do not invent expected outputs.
- Do not introduce arbitrary passing thresholds.
- Thresholds remain TBD until explicitly approved.

## 6. LLM-as-Judge

LLM-as-judge is disabled by default.

It may only run when explicitly enabled through a configuration flag.

Its results must be stored separately from deterministic scores, including:
- Judge model.
- Prompt or rubric.
- Raw judgment.
- Timestamp.

## 7. Limitations

- Results represent observed behavior under tested conditions.
- They do not guarantee future agent performance.
- Performance can vary with network conditions and provider availability.
- Protocol compliance does not establish agent reliability.
- Untested capabilities must not be presented as verified.

## 8. Specification Governance

This document is the source of truth for evaluation methodology.

Any change to scoring formulas or thresholds must be reflected here
before implementation changes are made.
