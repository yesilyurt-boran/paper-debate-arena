# libs
import os
import json
from openai import OpenAI
from llama_index.core import VectorStoreIndex
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
import faiss
from pypdf import PdfReader
import networkx as nx
from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv
import re
import pycountry
import networkx as nx
from datetime import datetime
import uuid
from llama_index.core import StorageContext, load_index_from_storage
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import tempfile

#### Load the API key
load_dotenv()
apikey=os.getenv("OPENAI_API_KEY")
client=OpenAI(api_key=apikey)

#### Structuring data tmeplates
section_names = ['introduction', 'conclusion', 'discussion', 'results','summary','acknowledgment','acknowledgement']
compound_titles = [
        f"{a} and {b}" for a in section_names for b in section_names if a != b
    ] + [
        f"{a} & {b}" for a in section_names for b in section_names if a != b
    ]
country_names = {country.name.lower() for country in pycountry.countries}

country_names.update([
    'usa', 'uk', 'england', 'scotland', 'wales', 'russia', 
    'south korea', 'north korea', 'iran', 'taiwan', 'cambridge', 'oxford', 'boston', 'berkeley', 'paris',
    'beijing', 'tokyo', 'zurich', 'geneva', 'heidelberg'
])

#### - Processing the Papers - 
def is_affiliation(line):
    line_lower = line.lower()
    for country in country_names:
        word=r'\b'+re.escape(country)+r'\b'
        if re.search(word,line_lower):
            return True
    return False

def section_splitter(paper):
    doc= PdfReader(paper)

    page_map=[]
    lines = []

    for page_num,page in enumerate(doc.pages):
        text=page.extract_text()
        page_lines=text.split("\n")
        for line in page_lines:
            page_map.append(page_num + 1)
            lines.append(line)


    clean_lines=[]
    for line in lines:
        stripped=line.strip()
        if not stripped:
            continue
        real_words=re.findall(r'[a-zA-Z.]{2,}',stripped)
        total_chars=len(stripped)
        if total_chars>0 and len(real_words)>=1:
            line=re.sub(r'[^\x00-\x7F]{2,}', ' ', line)
            line = re.sub(r'\b[a-zA-Z]?\d*[_^{}]+\d*[a-zA-Z]?\b', ' ', line)
            line = re.sub(r'/uni[0-9a-fA-F]+', '', line)
            line = re.sub(r'\\uni[0-9a-fA-F]+', '', line)
            line= re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '', line)
            line = re.sub(r'[\ue000-\uf8ff]', '', line)
            line = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', line)
            line = re.sub(r' {2,}', ' ', line)
            line = re.sub(r'\n{3,}', '\n\n', line)
            clean_lines.append(line)

    refs=[]
    ref_index=[]
    i=0
    for line in clean_lines:
        for title in section_names:
            if title in line.lower() and len(line)<26:
                refs.append(line)
                ref_index.append(i)
        for title in compound_titles:
            if title in line.lower() and len(line)<45:
                refs.append(line)
                ref_index.append(i)
        i+=1
   
    if len(refs)>0:
        info_txt=''
        abs_txt=''
        body_txt=''
        conclusion_txt=''

        is_info=[]
        for n, line in enumerate(clean_lines[:ref_index[0]]):
            if is_affiliation(line):
                is_info.append(n)

        for line in clean_lines[:max(is_info)]:
            info_txt+=' '+line
        for line in clean_lines[max(is_info)+1:ref_index[0]]:
            abs_txt+=' '+line
        for line in clean_lines[ref_index[0]+1:ref_index[1]]:
            body_txt+=' '+line
        for line in clean_lines[ref_index[1]+1:ref_index[2]]:
            conclusion_txt+=' '+line

        return {'info':{'text':info_txt,'pages':(page_map[0], page_map[max(is_info)-1]) },'abs': {'text':abs_txt, 'pages':(page_map[max(is_info)], page_map[ref_index[0]-1])},'body': {'text':body_txt, 'pages':(page_map[ref_index[0]+1],page_map[ref_index[1]])},'conclusion':{'text':conclusion_txt,'pages':(page_map[ref_index[1]+1],page_map[ref_index[2]])}}
    else:
        print('Sections are not detected!')

def indexer(sections:dict,paper_id:str,chunk_size=256) -> VectorStoreIndex:
    documents=[]

    for section_name, section_info in sections.items():
        if not section_info['text'].strip():
            continue
        documents.append(Document(
            text=section_info['text'],
            metadata={
                "paper_id": paper_id,
                "section": section_name,
                "page_start":section_info['pages'][0],
                "page_end":section_info['pages'][1]
            }
        ))
    
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=30)
    
    index = VectorStoreIndex.from_documents(
        documents,
        transformations=[splitter]
    )
    
    return index

def query_results(paper,qstn,chunk_size=256,list_results=3):

    if 'info' in paper.keys():
        del paper['info']   

    index=indexer(paper,chunk_size)

    query_engine = index.as_query_engine(similarity_top_k=list_results)
    results = query_engine.query(qstn)

    return results


#### - Conflict Detection - 

def concept_extract(sections:dict):
    prompt=f"""
    Given the following academic paper sections, extract 5-10 key concepts,
    claims, or topics that are central to the paper's argument.
    Return as JSON with exactly this structure: {{"concepts": ["concept1", "concept2", ...]}}

    INFO: {sections['abs']['text']}
    CONCLUSION: {sections['conc']['text']}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)

def concept_overlap(concept1,concept2):

    prompt = f"""
    Given these two lists of concepts from different papers,
    return a JSON list of concepts that both papers likely address.
    Be specific — prefer precise claims over broad topics.

    Paper A concepts: {concept1}
    Paper B concepts: {concept2}
    Return as JSON with exactly this structure: {{"common_concepts": ["concept1", "concept2", ...]}}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)

def deduplicate(shared_concepts: list) -> list:
    prompt = f"""
    Given this list of concepts extracted from two academic papers,
    remove any concepts that are redundant, overlapping, or that are 
    sub-topics of another concept in the list.
    Keep the most specific version when concepts overlap.
    Return as JSON with exactly this structure: {{"concepts": [...]}}
    
    Concepts: {shared_concepts}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)['concepts']

def query_same_concepts(concepts,paper1,paper2):
    pairs=[]

    for concept in concepts:
       results_a=query_results(paper1,concept,128)
       results_b=query_results(paper2,concept,128)

       pairs.append({
            'concept': concept,
            'paper_a': {
                'text': [n.text for n in results_a.source_nodes],
                'sections': [n.metadata['section'] for n in results_a.source_nodes]
            },
            'paper_b': {
                'text': [n.text for n in results_b.source_nodes],
                'sections': [n.metadata['section'] for n in results_b.source_nodes]
            }
        })
    
    return pairs

def detect_conflict(pair:dict):
    prompt = f"""
    Compare these passages from two different papers on the concept: {pair['concept']}

    Paper A: {pair['paper_a']['text']}
    Paper B: {pair['paper_b']['text']}

    Determine:
    1. Is there a genuine conflict, agreement, or qualification?
    2. If conflict, classify it: empirical | assumption | definitional | methodological
    3. Summarize the conflict in one sentence
    4. Explain in one sentence why you classified it that way

    Return as JSON with keys: conflict_exists (bool), type, summary, type_reasoning
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )

    result = json.loads(response.choices[0].message.content)
    result['concept'] = pair['concept']
    result['evidence'] = pair

    return result

def run_conflict_detection(paper1,section1,paper2,section2):

    concepts1=concept_extract(section1)['concepts']
    concepts2=concept_extract(section2)['concepts']

    concept_match=deduplicate(concept_overlap(concepts1,concepts2)['common_concepts'])

    comparison=query_same_concepts(concept_match,paper1,paper2)

    conflicts = []
    for pair in comparison:
        result = detect_conflict(pair)
        if result['conflict_exists']:
            conflicts.append(result)

    return conflicts

#### - Argument Map & Cross-Examination - ####

def create_graph():
    return nx.DiGraph()  

def add_conflict_to_map(G: nx.DiGraph, conflict: dict, paper_a_id: str, paper_b_id: str):

    #: conflict id
    conflict_id = f"conflict_{len(G.nodes)}_{conflict['concept'].replace(' ', '_').lower()}"

    node_a_id = f"{paper_a_id}_{conflict_id}"
    G.add_node(node_a_id,
        type="claim",
        paper_id=paper_a_id,
        concept=conflict['concept'],
        text=conflict['evidence']['paper_a']['text'],
        sections=conflict['evidence']['paper_a']['sections'],
    )
    
    node_b_id = f"{paper_b_id}_{conflict_id}"
    G.add_node(node_b_id,
        type="claim",
        paper_id=paper_b_id,
        concept=conflict['concept'],
        text=conflict['evidence']['paper_b']['text'],
        sections=conflict['evidence']['paper_b']['sections'],
    )
    
    G.add_edge(paper_a_id, node_a_id, type="owns")
    G.add_edge(paper_b_id, node_b_id, type="owns")
    
    #: conflict edge 
    G.add_edge(node_a_id, node_b_id,
        type="conflict",
        conflict_type=conflict['type'],         # empirical | assumption | definitional | methodological
        summary=conflict['summary'],
        type_reasoning=conflict['type_reasoning'],
        interrogations=[],                       # cross-examination history
        created_at=datetime.now().isoformat()
    )
    
    return conflict_id



def argument_map(conflicts:list,paper_a_id: str, paper_b_id: str):
    G = create_graph()

    G.add_node(paper_a_id,type='paper')
    G.add_node(paper_b_id,type='paper')

    for conflict in conflicts:
        add_conflict_to_map(G,conflict,paper_a_id,paper_b_id)
    return G
##
def steelman(G: nx.DiGraph, node_a_id: str, node_b_id: str, steelmaned_paper: str, index_a, index_b, client):
    edge_data = G.edges[node_a_id, node_b_id]
    node_data = G.nodes[node_a_id] if steelmaned_paper == "paper_a" else G.nodes[node_b_id]
    
    index = index_a if steelmaned_paper == "paper_a" else index_b
    

    claim_text = node_data['text'][0][:400]
    query = f"""
    Regarding {node_data['concept']}:
    The claim is: {edge_data['summary']}
    Specifically: {claim_text}
    Find evidence that supports.
    """
    
    query_engine = index.as_query_engine(similarity_top_k=6)
    results = query_engine.query(query)
    
   
    sources = []
    for node in results.source_nodes:
        sources.append({
            "paper_id": steelmaned_paper,
            "section": node.metadata['section'],
            "page_start": node.metadata['page_start'],
            "page_end": node.metadata['page_end'],
            "text": node.text,
            "score": node.score
        })
    

    chunks_text = "\n\n".join([
        f"[{s['section']}, pp.{s['page_start']}-{s['page_end']}]\n{s['text']}" 
        for s in sources
    ])
    
    prompt = f"""
    You are analyzing a claim from an academic paper.
    
    CLAIM BEING STEELMANED: {edge_data['summary']}
    
    RETRIEVED PASSAGES FROM {steelmaned_paper}:
    {chunks_text}
    
    From the retrieved passage, 
    Make the strongest possible case that {steelmaned_paper}'s position is CORRECT.
    Argue in favor of it, not just describe it.
    Do not invent anything not present in the retrieved text.
    Do not use phrases that imply external corroboration unless it appears in the text.

    Return as JSON with exactly this structure:
    {{
        "Argument": "maximum 3 sentence steelman argument"
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Build final output
    output = {
        "tool": "STEELMAN",
        "concept": node_data['concept'],
        "steelmaned_paper": steelmaned_paper,
        "response": result,
        "sources": sources,
        "timestamp": datetime.now().isoformat()
    }

    # Append to edge interrogation history
    G.edges[node_a_id, node_b_id]['interrogations'].append(output)
    
    return output

##

def steelman_light(G: nx.DiGraph, node_a_id: str, node_b_id: str, steelmaned_paper: str, index_a, index_b, client):
    edge_data = G.edges[node_a_id, node_b_id]
    node_data = G.nodes[node_a_id] if steelmaned_paper == "paper_a" else G.nodes[node_b_id]
    
    index = index_a if steelmaned_paper == "paper_a" else index_b
    

    claim_text = node_data['text'][0][:400]
    query = f"""
    Regarding {node_data['concept']}:
    The claim is: {edge_data['summary']}
    Specifically: {claim_text}
    Find evidence that supports.
    """
    
    query_engine = index.as_query_engine(similarity_top_k=6)
    results = query_engine.query(query)
    
   
    sources = []
    for node in results.source_nodes:
        sources.append({
            "paper_id": steelmaned_paper,
            "section": node.metadata['section'],
            "page_start": node.metadata['page_start'],
            "page_end": node.metadata['page_end'],
            "text": node.text,
            "score": node.score
        })
    

    chunks_text = "\n\n".join([
        f"[{s['section']}, pp.{s['page_start']}-{s['page_end']}]\n{s['text']}" 
        for s in sources
    ])
    
    prompt = f"""
    You are analyzing a claim from an academic paper.
    
    CLAIM BEING STEELMANED: {edge_data['summary']}
    
    RETRIEVED PASSAGES FROM {steelmaned_paper}:
    {chunks_text}
    
    From the retrieved passage, 
    Make the strongest possible case that {steelmaned_paper}'s position is CORRECT.
    Argue in favor of it, not just describe it.
    Do not invent anything not present in the retrieved text.
    Do not use phrases that imply external corroboration unless it appears in the text.

    Return as JSON with exactly this structure:
    {{
        "Argument": "maximum 3 sentence steelman argument"
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Build final output
    output = {
        "tool": "STEELMAN",
        "concept": node_data['concept'],
        "steelmaned_paper": steelmaned_paper,
        "response": result,
        "sources": sources,
        "timestamp": datetime.now().isoformat()
    }
    
    return output

##

def challenge(G: nx.DiGraph, node_a_id: str, node_b_id: str, challenged_paper: str, index_a, index_b, client):
    
    edge_data = G.edges[node_a_id, node_b_id]
    node_data = G.nodes[node_a_id] if challenged_paper == "paper_a" else G.nodes[node_b_id]
    
    index = index_a if challenged_paper == "paper_a" else index_b
    
    claim = steelman_light(G, node_a_id, node_b_id, challenged_paper , index_a, index_b, client)
    claim_text = claim['response']['Argument']

    query = f"""
    Regarding {node_data['concept']}:
    The claim is: {claim_text}
    Find evidence that supports or contradicts this claim.
    """
    
    query_engine = index.as_query_engine(similarity_top_k=6)
    results = query_engine.query(query)
    
   
    sources = []
    for node in results.source_nodes:
        sources.append({
            "paper_id": challenged_paper,
            "section": node.metadata['section'],
            "page_start": node.metadata['page_start'],
            "page_end": node.metadata['page_end'],
            "text": node.text,
            "score": node.score
        })
    
    # LLM verdict over retrieved chunks
    chunks_text = "\n\n".join([
        f"[{s['section']}, pp.{s['page_start']}-{s['page_end']}]\n{s['text']}" 
        for s in sources
    ])
    
    prompt = f"""
    You are analyzing a claim from an academic paper.
    
    CLAIM BEING CHALLENGED: {claim_text}
    
    RETRIEVED PASSAGES FROM {challenged_paper}:
    {chunks_text}
    
    For each passage:
    1. State whether it supports, contradicts, or is neutral to the claim
    2. Explain why in one sentence
    3. Text snippet must be compatible with the verdict
    
    Then give an overall verdict: does the evidence hold up under scrutiny?
    
    Return as JSON with exactly this structure:
    {{
        "passage_verdicts": [
            {{"text_snippet": "...", "verdict": "supports|contradicts|neutral", "reasoning": "..."}}
        ],
        "overall_verdict": "holds|weakened|refuted",
        "overall_reasoning": "one paragraph summary"
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Build final output
    output = {
        "tool": "CHALLENGE",
        "concept": node_data['concept'],
        "challenged_paper": challenged_paper,
        "response": result,
        "sources": sources,
        "timestamp": datetime.now().isoformat()
    }
    
    # Append to edge interrogation history
    G.edges[node_a_id, node_b_id]['interrogations'].append(output)
    
    return output

##

def answer_for(G: nx.DiGraph, node_a_id: str, node_b_id: str, responding_paper: str, index_a, index_b, client):
    edge_data = G.edges[node_a_id, node_b_id]

    if responding_paper == "paper_a":
        node_data = G.nodes[node_b_id] # info of questioned paper
        questioned_paper='paper_b' 
        questioned_index=index_b
        index = index_a
    else:
        node_data = G.nodes[node_a_id] # info of questioned paper
        questioned_paper='paper_a'
        questioned_index=index_a 
        index = index_b 

    claim = steelman_light(G, node_a_id, node_b_id, questioned_paper , index_a, index_b, client)
    claim_text = claim['response']['Argument']

    query = f"""
    Regarding {node_data['concept']}:
    The claim of {questioned_paper} is in {claim_text}
    Find evidence that answers to the claim.
    """
    
    query_engine = index.as_query_engine(similarity_top_k=6)
    results = query_engine.query(query)
    
    sources = []
    for node in results.source_nodes:
        sources.append({
            "paper_id": responding_paper,
            "section": node.metadata['section'],
            "page_start": node.metadata['page_start'],
            "page_end": node.metadata['page_end'],
            "text": node.text,
            "score": node.score
        })
    
    chunks_text = "\n\n".join([
        f"[{s['section']}, pp.{s['page_start']}-{s['page_end']}]\n{s['text']}" 
        for s in sources
    ])
    

    prompt = f"""
        You are analyzing an academic debate.

        {responding_paper} must directly respond to this specific claim from {questioned_paper}:
        claim: {claim_text}

        {responding_paper} cannot restate its own position — it must specifically address 
        why the objection is wrong, incomplete, or misleading.

        RETRIEVED PASSAGES FROM RESPONDING PAPER {responding_paper}:
        {chunks_text}

        Use only evidence from the retrieved passages.
        Give credit to specific methods, techniques used to justify claims.

        Return as JSON:
        {{
            "Answer": "maximum 3 sentence direct rebuttal that specifically addresses the objection"
        }}
        """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(response.choices[0].message.content)
    
    # Build final output
    output = {
        "tool": "ANSWER_FOR",
        "concept": node_data['concept'],
        "responding paper": responding_paper,
        "questioned paper": questioned_paper,
        "response": result,
        "Claim of the Questioned": claim_text,
        "sources": sources,
        "timestamp": datetime.now().isoformat()
    }

    # Append to edge interrogation history
    G.edges[node_a_id, node_b_id]['interrogations'].append(output)
    
    return output
#### - Map Export - ####
def export_map(G: nx.DiGraph, paper_a_id: str, paper_b_id: str):
    return {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "papers": {
            "paper_a": paper_a_id,
            "paper_b": paper_b_id
        },
        "nodes": [
            {"id": n, **G.nodes[n]} 
            for n in G.nodes
        ],
        "edges": [
            {"source": u, "target": v, **G.edges[u, v]} 
            for u, v in G.edges
        ]
    }
#### - Session Export/Import - ####

def create_session_id():
    return str(uuid.uuid4())

def get_session_dir(session_id: str):
    return f"./exports/{session_id}"

def save_session(session_id: str, index_a, index_b, G: nx.DiGraph, 
                 paper_a_id: str, paper_b_id: str,
                 paper_a_filename: str, paper_b_filename: str,
                 sections_a: dict, sections_b: dict):
    
    session_dir = get_session_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Save FAISS indexes
    index_a.storage_context.persist(persist_dir=f"{session_dir}/index_a")
    index_b.storage_context.persist(persist_dir=f"{session_dir}/index_b")
    
    # Save NetworkX graph
    graph_data = export_map(G, paper_a_id, paper_b_id)
    with open(f"{session_dir}/graph.json", 'w') as f:
        json.dump(graph_data, f, indent=2)
    
    # Save metadata
    metadata = {
        "session_id": session_id,
        "paper_a": {
            "id": paper_a_id,
            "filename": paper_a_filename,
            "sections": {
                section: {
                    "page_start": data['pages'][0],
                    "page_end": data['pages'][1]
                }
                for section, data in sections_a.items()
            }
        },
        "paper_b": {
            "id": paper_b_id,
            "filename": paper_b_filename,
            "sections": {
                section: {
                    "page_start": data['pages'][0],
                    "page_end": data['pages'][1]
                }
                for section, data in sections_b.items()
            }
        }
    }
    with open(f"{session_dir}/metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Session saved: {session_dir}")
    return session_dir

def load_session(session_id: str):
    session_dir = get_session_dir(session_id)
    
    if not os.path.exists(session_dir):
        raise ValueError(f"Session {session_id} not found")
    
    # Load FAISS indexes
    storage_context_a = StorageContext.from_defaults(
        persist_dir=f"{session_dir}/index_a"
    )
    index_a = load_index_from_storage(storage_context_a)
    
    storage_context_b = StorageContext.from_defaults(
        persist_dir=f"{session_dir}/index_b"
    )
    index_b = load_index_from_storage(storage_context_b)
    
    # Load graph
    with open(f"{session_dir}/graph.json", 'r') as f:
        graph_data = json.load(f)
    G = load_graph(graph_data)
    
    # Load metadata
    with open(f"{session_dir}/metadata.json", 'r') as f:
        metadata = json.load(f)
    
    return index_a, index_b, G, metadata

def load_graph(graph_data: dict) -> nx.DiGraph:
    G = nx.DiGraph()
    
    for node in graph_data['nodes']:
        node_id = node.pop('id')
        G.add_node(node_id, **node)
    
    for edge in graph_data['edges']:
        source = edge.pop('source')
        target = edge.pop('target')
        G.add_edge(source, target, **edge)
    
    return G

#### - Full Pipeline - ####

def run_full_pipeline(pdf_a_path: str, pdf_b_path: str, 
                      paper_a_filename: str, paper_b_filename: str):
    
    session_id = create_session_id()
    paper_a_id = "paper_a"
    paper_b_id = "paper_b"
    
    # Ingestion
    sections_a = section_splitter(pdf_a_path)
    sections_b = section_splitter(pdf_b_path)
    sections_a_simp={}
    sections_b_simp={}

    sections_a_simp['abs']=sections_a['abs']
    sections_a_simp['conc']=sections_a['conclusion']
    sections_b_simp['abs']=sections_b['abs']
    sections_b_simp['conc']=sections_b['conclusion']


    # Build indexes
    index_a = indexer(sections_a, 128)
    index_b = indexer(sections_b, 128)
    
    # Conflict detection
    conflicts = run_conflict_detection(sections_a,sections_a_simp,sections_b, sections_b_simp)
    
    # Build argument map
    G= argument_map(conflicts, paper_a_id, paper_b_id)
    
    # Save everything
    save_session(
        session_id,
        index_a,
        index_b,
        G,
        paper_a_id,
        paper_b_id,
        paper_a_filename,
        paper_b_filename,
        sections_a,
        sections_b
    )
    
    return session_id, G, conflicts

#### - Frontend <--> Backend: FastAPI - ####

app = FastAPI()

# Allow React frontend to talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_methods=["*"],
    allow_headers=["*"],
)

# Interact with nodes
class ToolRequest(BaseModel):
    session_id: str
    node_a_id: str
    node_b_id: str
    tool: str        # "CHALLENGE" | "STEELMAN" | "ANSWER_FOR"
    paper: str       # "paper_a" | "paper_b"

class ReviewRequest(BaseModel):
    graph: dict


@app.post("/upload")
async def upload_papers(
    paper_a: UploadFile = File(...),
    paper_b: UploadFile = File(...)
):
    try:
        # Save uploaded files to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_a:
            tmp_a.write(await paper_a.read())
            path_a = tmp_a.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_b:
            tmp_b.write(await paper_b.read())
            path_b = tmp_b.name

        # Run full pipeline
        session_id, G, conflict_nodes = run_full_pipeline(
            pdf_a_path=path_a,
            pdf_b_path=path_b,
            paper_a_filename=paper_a.filename,
            paper_b_filename=paper_b.filename
        )

        # Cleanup temp files
        os.remove(path_a)
        os.remove(path_b)

        return {
            "session_id": session_id,
            "graph": export_map(G, "paper_a", "paper_b"),
            "conflict_nodes": conflict_nodes
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query")
async def run_tool(req: ToolRequest):
    try:
        # Load session from disk
        index_a, index_b, G, metadata = load_session(req.session_id)

        # Route to correct tool
        if req.tool == "CHALLENGE":
            result = challenge(G, req.node_a_id, req.node_b_id, 
                             req.paper, index_a, index_b, client)

        elif req.tool == "STEELMAN":
            result = steelman(G, req.node_a_id, req.node_b_id, 
                            req.paper, index_a, index_b, client)

        elif req.tool == "ANSWER_FOR":
            result = answer_for(G, req.node_a_id, req.node_b_id, 
                              req.paper, index_a, index_b, client)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {req.tool}")

        # Save updated graph with new interrogation history
        session_dir = get_session_dir(req.session_id)
        with open(f"{session_dir}/graph.json", 'w') as f:
            json.dump(export_map(G, "paper_a", "paper_b"), f, indent=2)

        return {
            "result": result,
            "graph": export_map(G, "paper_a", "paper_b")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/review")
async def review_map(file: UploadFile = File(...)):
    try:
        content = await file.read()
        graph_data = json.loads(content)

        # Validate minimum required fields
        if not all(k in graph_data for k in ["nodes", "edges", "papers"]):
            raise HTTPException(status_code=400, detail="Invalid map file")

        return graph_data

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/metadata")
async def review_map(file: UploadFile = File(...)):
    try:
        content = await file.read()
        metadata = json.loads(content)

        return metadata

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))