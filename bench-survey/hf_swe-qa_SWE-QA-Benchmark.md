---
license: apache-2.0
task_categories:
- question-answering
- text-generation
language:
- en
tags:
- software-engineering
- code-qa
- swe-bench
size_categories:
- 1K<n<10K
configs:
- config_name: default
  data_files:
  - split: default
    path: default.jsonl
  - split: astropy
    path: astropy.jsonl
  - split: conan
    path: conan.jsonl
  - split: django
    path: django.jsonl
  - split: flask
    path: flask.jsonl
  - split: matplotlib
    path: matplotlib.jsonl
  - split: pylint
    path: pylint.jsonl
  - split: pytest
    path: pytest.jsonl
  - split: reflex
    path: reflex.jsonl
  - split: requests
    path: requests.jsonl
  - split: scikit_learn
    path: scikit-learn.jsonl
  - split: sphinx
    path: sphinx.jsonl
  - split: sqlfluff
    path: sqlfluff.jsonl
  - split: streamlink
    path: streamlink.jsonl
  - split: sympy
    path: sympy.jsonl
  - split: xarray
    path: xarray.jsonl
---

# SWE-QA Benchmark

A comprehensive benchmark dataset for Software Engineering Question Answering, containing 720 questions across 15 popular Python repositories.

## Dataset Summary

- **Total Questions**: 720
- **Repositories**: 15
- **Format**: JSONL (JSON Lines)
- **Fields**: `question`, `answer`

## Repository Coverage

Each repository contains 48 questions:
- astropy
- conan
- django
- flask
- matplotlib
- pylint
- pytest
- reflex
- requests
- scikit-learn
- sphinx
- sqlfluff
- streamlink
- sympy
- xarray

## Usage

### Load all data (default split)
```python
from datasets import load_dataset

dataset = load_dataset("swe-qa/SWE-QA-Benchmark", split="default")
# 720 questions
```

### Load data by repository
```python
from datasets import load_dataset

# Load Flask questions
flask_dataset = load_dataset("swe-qa/SWE-QA-Benchmark", split="flask")
# 48 questions

# Load Django questions
django_dataset = load_dataset("swe-qa/SWE-QA-Benchmark", split="django")
# 48 questions
```

### Load all splits
```python
from datasets import load_dataset

dataset_dict = load_dataset("swe-qa/SWE-QA-Benchmark")
# Contains all splits: default, flask, django, pytest, etc.
```

## Data Structure

Each record contains:
- `question`: The question about the codebase
- `answer`: The detailed answer explaining the code behavior

## Citation

If you use this dataset, please cite:

```bibtex
@inproceedings{peng2026swe,
  title={Swe-qa: Can language models answer repository-level code questions?},
  author={Peng, Weihan and Shi, Yuling and Wang, Yuhang and Zhang, Xinyun and Shen, Beijun and Gu, Xiaodong},
  booktitle={Findings of the Association for Computational Linguistics: ACL 2026},
  pages={8230--8245},
  year={2026}
}
```