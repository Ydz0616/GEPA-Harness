---
license: mit
task_categories:
- question-answering
language:
- en
tags:
- SWE
- QA
- Benchmark
size_categories:
- n<1K
---

# SWE-QA-Pro Bench (A Repository-level QA Benchmark Built from Diverse Long-tail Repositories)

[**💻 GitHub**](https://github.com/TIGER-AI-Lab/SWE-QA-Pro) | [**📖 Paper**](https://arxiv.org/abs/2603.16124) | [**🤗 SWE-QA-Pro**](https://hf.co/collections/TIGER-Lab/swe-qa-pro)


## 📢 News

- **🚀 [2026-5-19] The evaluation code is released on [GitHub](https://github.com/TIGER-AI-Lab/SWE-QA-Pro).**
- **🔥 [2026-3-23] SWE-QA-Pro Bench is publicly released! The model and code will be released soon.**

---

## Introduction
SWE-QA-Pro Bench is a **repository-level question answering dataset** designed to evaluate whether models can perform grounded, agentic reasoning over real-world codebases.

Unlike prior benchmarks that focus on popular repositories or short code snippets, SWE-QA-Pro emphasizes:

- **Long-tail repositories** with diverse structures and domains
- **Repository-grounded questions** that require navigating multiple files
- **Agentic reasoning**, where models must explore code rather than rely on memorized knowledge

To construct this dataset, we adopt a data-driven pipeline:

![benchmark_main_figure](https://cdn-uploads.huggingface.co/production/uploads/670d7aed372cb8fadbd270bb/Dc1zsEFlXfIsRJbZezghC.png)

- Collect large-scale GitHub issues and organize them into **48 semantic clusters** covering diverse software engineering tasks
- Synthesize QA pairs grounded in executable repositories
- Apply a difficulty calibration step to remove questions solvable without repository interaction

The final dataset contains **260 high-quality QA pairs from 26 repositories (10 per repository)**, where solving tasks typically requires multi-step reasoning and codebase exploration.


---

## Dataset Format

- **File type**: `jsonl`
- **Fields**:
  - `repo`: Repository name
  - `commit_id`: Commit hash specifying the exact code version
  - `cluster`: Semantic task cluster (one of 48 categories)
  - `qa_type`: Question type, one of what/where/why/how
  - `question`: The input question
  - `answer`: The reference answer grounded in the repository

---

## Evaluation Protocol
SWE-QA-Pro is designed to evaluate agentic repository-level QA, distinguishing between knowledge recall and true code understanding.

### Evaluation Settings
- Direct Answering (No Tools)
    The model answers without accessing the repository
- Agentic QA (With Tools)
    The model interacts with the repository (e.g., search, file reading)

### Evaluation Method
Answers are evaluated using an LLM-as-a-Judge framework, where each response is scored on correctness, completeness, relevance, clarity, and reasoning quality, with scores averaged across multiple runs and reported on a 5–50 scale.

---

## Citation

```bibtex
@article{cai2026sweqapro,
      title={SWE-QA-Pro: A Representative Benchmark and Scalable Training Recipe for Repository-Level Code Understanding}, 
      author={Songcheng Cai and Zhiheng Lyu and Yuansheng Ni and Xiangchao Chen and Baichuan Zhou and Shenzhe Zhu and Yi Lu and Haozhe Wang and Chi Ruan and Benjamin Schneider and Weixu Zhang and Xiang Li and Andy Zheng and Yuyu Zhang and Ping Nie and Wenhu Chen},
      journal={arXiv preprint arXiv:2603.16124},
      year={2026},
}