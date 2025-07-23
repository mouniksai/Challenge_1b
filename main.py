"""
Simplified Persona-Driven Document Intelligence
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict
import re
from llama_cpp import Llama
import fitz  # PyMuPDF


class DocumentAnalyzer:
    def __init__(self, model_path: str = "models/gemma-3-1b-it-UD-Q5_K_XL.gguf"):
        print("Loading model...")
        self.llm = Llama(model_path=model_path, n_ctx=2048, verbose=False)
        print("Model loaded!")
    
    def load_outlines(self, input_dir: str) -> Dict[str, Dict]:
        """Load JSON outline files"""
        outlines = {}
        for json_file in Path(input_dir).glob("*.json"):
            pdf_name = json_file.stem + ".pdf"
            with open(json_file, 'r', encoding='utf-8') as f:
                outlines[pdf_name] = json.load(f)
        print(f"Loaded {len(outlines)} outlines")
        return outlines
    
    def extract_content(self, pdf_path: str, section_info: Dict, next_section: Dict = None) -> str:
        """Extract text from PDF section"""
        try:
            doc = fitz.open(pdf_path)
            start_page = section_info['page'] - 1
            end_page = next_section['page'] - 1 if next_section else len(doc)
            
            content = ""
            for page_num in range(start_page, min(end_page + 1, len(doc))):
                content += doc[page_num].get_text() + "\n"
            
            doc.close()
            return self.clean_text(content)[:1500]  # Limit length
            
        except Exception as e:
            print(f"Error extracting from {pdf_path}: {e}")
            return f"Content from: {section_info['text']}"
    
    def clean_text(self, text: str) -> str:
        """Clean text"""
        return re.sub(r'\s+', ' ', text).strip()
    
    def extract_all_sections(self, pdf_files: List[str], outlines: Dict[str, Dict]) -> List[Dict]:
        """Extract all sections from PDFs"""
        sections = []
        for pdf_file in pdf_files:
            pdf_name = os.path.basename(pdf_file)
            if pdf_name not in outlines:
                continue
            
            outline = outlines[pdf_name]['outline']
            for i, section in enumerate(outline):
                next_section = outline[i + 1] if i + 1 < len(outline) else None
                content = self.extract_content(pdf_file, section, next_section)
                
                sections.append({
                    'document': pdf_name,
                    'page_number': section['page'],
                    'section_title': section['text'],
                    'level': section['level'],
                    'content': content
                })
        return sections
    
    def fast_score_all_sections(self, sections: List[Dict], persona: str, job: str) -> List[Dict]:
        """Ultra-fast scoring using only 1 LLM call for ALL sections"""
        print("Fast scoring all sections...")
        
        # Create one mega-prompt for ALL sections at once
        all_titles = []
        for i, section in enumerate(sections):
            all_titles.append(f"{i+1}. {section['section_title']}")
        
        mega_prompt = f"""Rate ALL sections for {persona} doing {job}. 
Sections: {' | '.join(all_titles[:20])}  

Rate each 1-10: 1:score 2:score 3:score etc."""

        try:
            response = self.llm(mega_prompt, max_tokens=100, temperature=0.1)
            scores = self.parse_mega_scores(response['choices'][0]['text'], len(sections))
        except:
            # Fallback: keyword-based scoring (instant)
            scores = self.keyword_score_all(sections, persona, job)
        
        # Apply scores
        for i, section in enumerate(sections):
            section['relevance_score'] = scores[i] if i < len(scores) else 5
            
        return sections
    
    def keyword_score_all(self, sections: List[Dict], persona: str, job: str) -> List[int]:
        """Instant keyword-based scoring as fallback"""
        persona_words = set(persona.lower().split())
        job_words = set(job.lower().split())
        target_words = persona_words | job_words
        
        scores = []
        for section in sections:
            title_words = set(section['section_title'].lower().split())
            content_words = set(section['content'][:200].lower().split())
            
            title_matches = len(target_words & title_words) * 3
            content_matches = len(target_words & content_words)
            level_bonus = {'H1': 2, 'H2': 1, 'H3': 0}.get(section.get('level', 'H3'), 0)
            
            score = min(10, max(1, 4 + title_matches + content_matches + level_bonus))
            scores.append(score)
            
        return scores
    
    def parse_mega_scores(self, response_text: str, num_sections: int) -> List[int]:
        """Parse mega scoring response"""
        scores = []
        for i in range(1, min(num_sections + 1, 21)):  # Max 20 sections
            pattern = f"{i}:\\s*(\\d+)"
            match = re.search(pattern, response_text)
            if match:
                scores.append(max(1, min(10, int(match.group(1)))))
            else:
                scores.append(5)
        
        # Fill remaining with default scores
        while len(scores) < num_sections:
            scores.append(5)
            
        return scores
    
    def infer_persona_job(self, outlines: Dict, sections: List[Dict]) -> tuple:
        """Infer persona and job using LLM"""
        doc_titles = [outline.get('title', 'Unknown') for outline in outlines.values()]
        section_titles = [s['section_title'] for s in sections[:8]]
        sample_content = " ".join([s['content'][:150] for s in sections[:3]])
        
        prompt = f"""Analyze these documents and determine the PERSONA and JOB:

Documents: {', '.join(doc_titles)}
Sections: {', '.join(section_titles)}
Sample: {sample_content[:500]}

Determine:
PERSONA: [professional role, e.g., "PhD Researcher", "Business Analyst"]
JOB: [specific task, e.g., "Literature review", "Market analysis"]"""

        try:
            response = self.llm(prompt, max_tokens=100, temperature=0.3)
            text = response['choices'][0]['text'].strip()
            
            persona_match = re.search(r'PERSONA:\s*(.+)', text, re.IGNORECASE)
            job_match = re.search(r'JOB:\s*(.+)', text, re.IGNORECASE)
            
            persona = persona_match.group(1).strip() if persona_match else "Researcher"
            job = job_match.group(1).strip() if job_match else "Document analysis"
            
            return persona, job
            
        except Exception as e:
            print(f"Error inferring: {e}")
            return "Researcher", "Document analysis"
    
    def fast_keyword_score(self, section: Dict, persona_keywords: set, job_keywords: set) -> int:
        """Ultra-fast keyword-based scoring"""
        title = section['section_title'].lower()
        content = section['content'][:500].lower()  # Only check first 500 chars
        
        # Weight different parts
        title_matches = sum(1 for word in persona_keywords | job_keywords if word in title) * 3
        content_matches = sum(1 for word in persona_keywords | job_keywords if word in content)
        
        # Level importance
        level_boost = {'H1': 2, 'H2': 1, 'H3': 0}.get(section.get('level', 'H3'), 0)
        
        # Quick scoring
        raw_score = title_matches + content_matches + level_boost
        return min(10, max(1, raw_score + 3))  # Scale to 1-10
    
    def ultra_fast_process(self, input_dir: str) -> Dict:
        """Ultra-fast processing - target under 15 seconds"""
        start_time = time.time()
        
        # Load outlines and find PDFs (fast)
        outlines = self.load_outlines(input_dir)
        pdf_files = [os.path.join(input_dir, f) for f in outlines.keys() if os.path.exists(os.path.join(input_dir, f))]
        
        print(f"Processing {len(pdf_files)} PDFs")
        
        # Extract sections (moderate speed)
        sections = self.extract_all_sections(pdf_files, outlines)
        print(f"Extracted {len(sections)} sections")
        
        # ONLY 1 LLM CALL for persona/job inference
        persona, job = self.infer_persona_job(outlines, sections[:3])  # Only use first 3 sections
        print(f"Persona: {persona}")
        print(f"Job: {job}")
        
        # Prepare keywords for fast scoring
        persona_keywords = set(persona.lower().split())
        job_keywords = set(job.lower().split())
        
        # ULTRA FAST: Keyword-based scoring (no LLM calls!)
        print("Fast keyword scoring...")
        scored_sections = []
        for section in sections:
            score = self.fast_keyword_score(section, persona_keywords, job_keywords)
            scored_sections.append({**section, 'relevance_score': score})
        
        # Quick sort and select
        scored_sections.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_sections = scored_sections[:10]
        
        # ONLY 1 MORE LLM CALL for final refinement of top 3 sections
        if len(top_sections) >= 3:
            top_3_content = "\n".join([f"{i+1}. {s['section_title']}: {s['content'][:200]}" 
                                     for i, s in enumerate(top_sections[:3])])
            
            refinement_prompt = f"For {persona} doing {job}, rank these 3 sections by importance (1=most important):\n{top_3_content}\nRanking: 1:[section_num] 2:[section_num] 3:[section_num]"
            
            try:
                response = self.llm(refinement_prompt, max_tokens=20, temperature=0)
                # Parse and reorder top 3 if needed
                ranking_text = response['choices'][0]['text']
                # Simple reordering logic here...
            except:
                pass  # Keep original order if refinement fails
        
        # Super fast subsection creation
        subsections = []
        for section in top_sections[:3]:  # Only top 3
            if section['relevance_score'] >= 7:
                first_para = section['content'].split('\n')[0][:250]
                if len(first_para) > 50:
                    subsections.append({
                        'document': section['document'],
                        'page_number': section['page_number'],
                        'refined_text': first_para,
                        'importance_rank': section['relevance_score']
                    })
        
        # Build result
        result = {
            'metadata': {
                'input_documents': [os.path.basename(f) for f in pdf_files],
                'persona': persona,
                'job_to_be_done': job,
                'processing_timestamp': int(time.time()),
                'total_sections_analyzed': len(sections),
                'processing_time_seconds': round(time.time() - start_time, 2)
            },
            'extracted_sections': [
                {
                    'document': s['document'],
                    'page_number': s['page_number'],
                    'section_title': s['section_title'],
                    'importance_rank': i + 1
                }
                for i, s in enumerate(top_sections)
            ],
            'subsection_analysis': subsections
        }
        
        return result
    
    def parse_batch_scores(self, response_text: str, num_sections: int) -> List[int]:
        """Parse batch scoring response"""
        scores = []
        for i in range(1, num_sections + 1):
            pattern = f"SECTION{i}:\\s*(\\d+)"
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                scores.append(max(1, min(10, int(match.group(1)))))
            else:
                scores.append(5)  # Default score
        return scores


def main():
    """Main function"""
    analyzer = DocumentAnalyzer()
    
    input_dir = "input"
    output_dir = "output"
    
    print("Starting ULTRA-FAST document analysis...")
    result = analyzer.ultra_fast_process(input_dir)  # Use the ultra-fast method
    
    # Save output
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "analysis_output.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n🚀 ULTRA-FAST Processing complete!")
    print(f"Output: {output_file}")
    print(f"Persona: {result['metadata']['persona']}")
    print(f"Job: {result['metadata']['job_to_be_done']}")
    print(f"Time: {result['metadata']['processing_time_seconds']}s")
    print(f"Sections: {len(result['extracted_sections'])}")


if __name__ == "__main__":
    main()