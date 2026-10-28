---
license: apache-2.0
task_categories:
- question-answering
language:
- en
tags:
- code
- programming
- software-engineering
size_categories:
- 1K<n<10K
---

# Deep Code Bench Dataset

This dataset contains question-answer pairs with code context for evaluating deep code understanding.

## Dataset Structure

Each example contains:
- `question`: The question about the code
- `answer`: The expected answer
- `facts`: List of factual statements supporting the answer
- `metadata`: Additional information about difficulty, scope, etc.
- `id`: Unique identifier

## Usage

```python
from datasets import load_dataset

dataset = load_dataset("Qodo/deep_code_bench")
```
