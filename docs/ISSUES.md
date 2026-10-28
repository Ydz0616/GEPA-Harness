# GEPA × HL — Issue Log

## Issue 1: Traces are not used in optimization

**Summary**
- Judge context (one call per run, DeepSeek-flash, temp 0, no tools):
  - Scoring rubric: 5 dimensions × 1–10 (same text as the official SWE-QA-Pro `judge_prompt.txt`)
  - Question
  - Reference answer (full gold answer)
  - Candidate answer (`<finish>` block, or the whole final reply)
  - Output: JSON with 5 scores, no rationale
- Reflector context (one call per iteration, DeepSeek-flash, no tools, ~8.7k–20k tokens):
  - GEPA default meta-prompt ("…include niche domain facts in the instruction…")
  - Current instruction (full text)
  - 3 train examples, each with:
    - `question`: the example id only (bug: the question text is lost from this field)
    - `Generated Outputs`: the full agent reply
    - `Feedback`: repo@commit, question, gold answer, agent answer (second copy), 5 judge scores, then `Execution trace: status; turns; tool_calls; cost; latency` (the tool-name list is empty)
    - `score`, `trace_id` (the reflector cannot open it)
- Neither sees the trace: no tool calls or arguments, no files read, no tool results. Full traces sit in Langfuse unused. The only process signal is counts, plus whatever the agent says it did.

**Direction**
- Add a compact trace digest to ASI: tool sequence, files read, and wasted turns (as GEPA gskill does).
- Or let an agentic reflector read the traces itself (upstream `gepa/oa/proposers/claude_code_agent.py`).
- Also fix the `question` field bug and the empty tool-name list, and drop the duplicate answer.

**Result**
- TBD (not yet tested).
