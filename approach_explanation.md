# Methodology – Persona-Based Document Intelligence

Our solution for Challenge 1B focuses on adaptive, fast, and persona-aware document parsing under strict runtime and resource constraints.

## 1. Problem Understanding

Given a persona and job-to-be-done, the system must analyze a set of PDF documents and return the top 5 most relevant sections, along with brief refined sub-sections. Constraints include:

* No internet access at runtime
* Efficient execution (within minutes)
* Lightweight, open-source LLMs

## 2. Model Selection

We use gemma-3-1b-it-Q5\_K\_M in GGUF format, which is:

* Open-source and license compliant
* Quantized to 851 MB
* Compatible with CPU inference via llama.cpp

This enables reproducibility and ensures sub-second inference per prompt even without GPU access.

## 3. Pipeline Overview

Our solution consists of 5 key phases:

1. Input Parsing:

   * Load 1binput.json to identify the persona, job-to-be-done, and input files

2. PDF Section Extraction:

   * If a table of contents is present, we extract sections/subsections using TOC structure
   * If not, we fall back to page-wise extraction with title heuristics

3. Fast Relevance Scoring:

   * Using keyword overlap between section content, persona, and task
   * Dynamically generated domain-specific keywords via the LLM (if available)

4. Lightweight LLM Analysis:

   * Top 10 sections are analyzed using small-context prompts (max 50 tokens)
   * We summarize relevance to persona-task without exceeding constraints

5. Subsection Refinement:

   * Top 5 sections are selected
   * A concise paragraph from each is summarized/refined using the LLM
   * Output includes document name, page number, and refined text

## 4. Design Considerations

* The entire pipeline is containerized via Docker for reproducibility.
* The LLM component gracefully degrades to keyword scoring if LLM is unavailable.
* The code is modular, allowing reuse or adaptation for other tasks like summarization, clustering, or content routing.

## 5. Output

The final output strictly adheres to Adobe’s challenge schema, ensuring seamless integration with the judging pipeline.

This hybrid of keyword-engineered heuristics and lightweight LLM guidance strikes a balance between accuracy, interpretability, and performance.

Let me know if you'd like this zipped or if you want a final challenge1b\_output.json example too.
