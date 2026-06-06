# Debate Arena
### A particle collider for research papers

Most multi-document AI tools treat disagreement as a problem to summarise away. Debate Arena treats it like a particle collider, the collision between two papers is where the interesting physics happens. The system's job is not to resolve conflict but to make it legible.

---

## What it does

Debate Arena ingests two research papers, detects where they disagree, classifies the nature of each disagreement, and lets you interrogate the conflict through a structured cross-examination interface. Every claim the system makes is grounded in a specific retrieved passage from the original papers, with section and page references attached.

The result is an argument map, a persistent graph structure where nodes are claims and edges are conflicts. The map can be exported as a JSON file and reopened in Review mode, making it a shareable research artifact rather than a disposable chat session.

---

## Conflict taxonomy

The system classifies every detected conflict into one of four types:

**Empirical**, both papers accept the same framework but report different results. Points toward methodology, sample size, or measurement differences.

**Assumption**, the papers reach different conclusions because they start from different premises, often unstated ones.

**Definitional**, the papers use the same term to mean different things, or different terms to mean the same thing. The most insidious type because it can make genuine agreement look like disagreement.

**Methodological**, the papers disagree about how to study the question, not just what the answer is.

---

## Cross-examination tools

Once a conflict node is selected, three tools are available for each paper:

**STEELMAN**, constructs the strongest possible case for one side, grounded entirely in retrieved passages. No invention, every sentence is traceable to a specific page and section.

**CHALLENGE**, runs STEELMAN on the challenged paper first to get its strongest position, then retrieves fresh passages and returns a verdict on whether that position holds up under scrutiny. Each passage is labeled as supporting, contradicting, or neutral, with an overall verdict of holds, weakened, or refuted.

**ANSWER FOR**, forces one paper to directly respond to the other's strongest argument. Uses STEELMAN output as the claim to ensure the response engages with the best version of the opposing case rather than a strawman.

---

## Technical architecture

**Ingestion pipeline**

Each uploaded PDF is extracted with PyPDF and passed through a cleaning stage that removes equations, LaTeX artifacts, figure captions, Unicode garbage, and email addresses. The cleaned text is split into four labeled sections, info (title, authors, affiliations), abstract, body (introduction through results), and conclusion. Section boundaries are detected using hard anchor matching against a list of known section names and compound titles (e.g. results and discussion). Affiliation lines are identified using pycountry for country name detection with whole-word boundary matching to avoid substring false positives.

Each section becomes a LlamaIndex Document with metadata carrying paper ID, section label, and page range. LlamaIndex splits these into chunks using SentenceSplitter at 256 tokens with 30-token overlap, and indexes them into a per-paper FAISS vector store using OpenAI text-embedding-3-small embeddings. Source identity is preserved throughout, every retrieved chunk knows which paper and section it came from.

**Conflict detection**

Key concepts are extracted from the abstract and conclusion of each paper using GPT-4o. The two concept lists are compared to find shared topics, deduplicated to remove overlapping or redundant terms, and used as shared query targets against both indexes. The info section is excluded from concept extraction to avoid author metadata polluting the concept lists. For each shared concept, retrieved passage pairs are compared by GPT-4o to detect incompatibilities and classify their type. Detected conflicts become nodes and edges in a NetworkX directed graph.

**Cross-examination tools**

All three tools follow the same pattern, fresh retrieval against the relevant paper index using a query constructed from the conflict context, reasoning over retrieved chunks with GPT-4o, structured JSON response with sources attached including section label, page range, and similarity score.

CHALLENGE uses a light STEELMAN call internally to get the strongest version of the challenged claim before querying for supporting and contradicting evidence. ANSWER FOR similarly runs a light STEELMAN on the questioned paper first to get a sharp, argued claim for the responding paper to rebut, rather than using a raw retrieved chunk which tends to surface introductory background text instead of the paper's core argument.

**Persistence**

Sessions are saved to disk after the ingestion pipeline completes under an exports directory keyed by UUID session ID. Each session stores the two FAISS indexes via LlamaIndex's storage context persistence, the argument map as graph.json, and paper metadata including filenames and section page ranges as metadata.json. Sessions are loaded on demand for cross-examination tool calls. After each tool call the graph is resaved with the updated interrogation history appended to the relevant conflict edge.
Moreover, you can share your sessions with other users by just sharing your session folder. They will be able to see your cross-examination history and can perform their own investigations!

**API endpoints**

`POST /upload`, accepts two PDF files, runs the full pipeline, returns session ID and argument map graph.

`POST /query`, accepts session ID, node IDs, tool name, and paper target, loads the session, runs the tool, resaves the graph, returns the tool result and updated graph.

`POST /review`, accepts a JSON map file, validates it contains nodes, edges, and papers fields, returns the parsed graph for Review mode rendering.

`POST /metadata`, accepts a JSON metadata file and returns it parsed.

**Stack**

Backend: Python 3, FastAPI, LlamaIndex, FAISS, NetworkX, OpenAI API (GPT-4o and text-embedding-3-small), PyPDF, pycountry.

Frontend: React 19, Vite 8, React Flow 11, Axios, Tailwind CSS 4

---

## Demo

Two papers on competing interpretations of DESI DR2 dark energy evidence, followed by a Review mode demonstration on a condensed matter physics paper pair covering valley polarization in MoSe2/CrSBr heterostructures.
[![Debate Arena Demo](https://img.youtube.com/vi/eo8o9LTj3Bo/0.jpg)](https://www.youtube.com/watch?v=eo8o9LTj3Bo)
---

## Setup

**Backend**

```bash
git clone https://github.com/yourusername/debate-arena
cd debate-arena
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file:
```
OPENAI_API_KEY=your_key_here
```

Start the server:
```bash
python -m uvicorn main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Limitations and known issues

Section detection works reliably on standard academic paper formats but can misidentify boundaries on heavily formatted or two-column papers. The splitter requires at least three detectable section headers and returns None on papers with no standard structure. Equation removal is heuristic and occasionally leaves fragments. Page numbers are approximate on papers with figure-only pages, which PyPDF skips during extraction. Pipeline runtime is approximately 50 seconds per paper pair on a standard machine, dominated by OpenAI embedding API calls during index construction. Sessions are loaded from disk on every tool call, which adds latency on slower storage.

---

## Future directions

- Multi-paper collision graphs, extending beyond two papers to map a full literature landscape where a binary disagreement often turns into a more complex network when a third paper partially resolves or reframes it.

- Export formats, a rendered PDF or structured report of the full argument map with interrogation history, suitable for inclusion in a literature review.

- User-directed querying, a free-form chat mode against individual paper indexes for cases where the user wants to explore a specific claim not surfaced by automated conflict detection.
