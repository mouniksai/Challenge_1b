import json
import os
import time
from pathlib import Path
from typing import List, Dict
import re
from datetime import datetime
from llama_cpp import Llama
import fitz


class DocumentAnalyzer:
    def __init__(self, model_path: str = "models/gemma-3-1b-it-UD-Q5_K_XL.gguf"):
        """Initialize with optimized model settings for CPU-only processing"""
        try:
            # Optimized settings for CPU-only, fast processing
            self.llm = Llama(
                model_path=model_path,
                n_ctx=2048,        # Reduced context for speed
                n_batch=512,       # Smaller batch size
                n_threads=4,       # CPU threads
                verbose=False      # Reduce output noise
            )
        except Exception as e:
            # Fallback to mock LLM for graceful degradation
            self.llm = None
    
    def load_input_config(self, input_file: str) -> Dict:
        """Load the input configuration JSON file"""
        with open(input_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    
    def extract_pdf_sections(self, pdf_path: str) -> List[Dict]:
        """Extract sections from PDF without requiring JSON outline"""
        sections = []
        try:
            doc = fitz.open(pdf_path)
            document_name = os.path.basename(pdf_path)
            
            # Get table of contents if available
            toc = doc.get_toc()
            
            if toc:
                # Use TOC to extract sections
                for i, (level, title, page_num) in enumerate(toc):
                    if level <= 2:  # Only include main sections and subsections
                        start_page = page_num - 1
                        # Find end page from next TOC entry
                        end_page = len(doc) - 1
                        for j in range(i + 1, len(toc)):
                            if toc[j][0] <= level:
                                end_page = toc[j][2] - 1
                                break
                        
                        content = ""
                        for page_idx in range(start_page, min(end_page + 1, len(doc))):
                            content += doc[page_idx].get_text() + "\n"
                        
                        if content.strip():
                            sections.append({
                                'document': document_name,
                                'page_number': page_num,
                                'section_title': title.strip(),
                                'content': self.clean_text(content)[:2000]  # Limit content length
                            })
            else:
                # No TOC - extract page by page with generic titles
                for page_num in range(len(doc)):
                    content = doc[page_num].get_text()
                    if content.strip():
                        # Try to find a title from the first few lines
                        lines = content.split('\n')
                        title = "Page Content"
                        for line in lines[:5]:
                            line = line.strip()
                            if len(line) > 10 and len(line) < 100:
                                title = line
                                break
                        
                        sections.append({
                            'document': document_name,
                            'page_number': page_num + 1,
                            'section_title': title,
                            'content': self.clean_text(content)[:2000]
                        })
            
            doc.close()
            
        except Exception as e:
            # Return minimal section if extraction fails
            document_name = os.path.basename(pdf_path)
            sections.append({
                'document': document_name,
                'page_number': 1,
                'section_title': f"Content from {document_name}",
                'content': f"Unable to extract detailed content from {document_name}"
            })
        
        return sections
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        return re.sub(r'\s+', ' ', text).strip()
    
    def get_domain_keywords(self, persona: str, job: str) -> set:
        """Use LLM to generate domain-specific keywords for any persona/job"""
        if not self.llm:
            # Fallback to generic keywords if no LLM
            return {'relevant', 'important', 'useful', 'key', 'essential', 'main', 'primary'}
        
        try:
            # Generate keywords for the specific domain
            prompt = f"List 10 keywords relevant for {persona} doing {job}. Format: word1, word2, word3..."
            
            response = self.llm(
                prompt,
                max_tokens=60,  # Limited for speed
                temperature=0.3,
                stop=["\n"]
            )
            
            keywords_text = response['choices'][0]['text'].strip()
            # Parse keywords from response
            keywords = set()
            for word in keywords_text.replace(',', ' ').split():
                clean_word = word.strip().lower().strip('.,!?;:"')
                if len(clean_word) > 2:  # Only meaningful words
                    keywords.add(clean_word)
            
            return keywords if keywords else {'relevant', 'important', 'useful'}
            
        except Exception as e:
            # Fallback keywords if LLM fails
            return {'relevant', 'important', 'useful', 'key', 'essential'}
    
    def fast_keyword_score(self, section: Dict, persona_keywords: set, job_keywords: set, domain_keywords: set = None) -> int:
        """Fast keyword-based relevance scoring with dynamic domain keywords"""
        content = section['content'].lower()
        title = section['section_title'].lower()
        
        # Score based on keyword matches
        persona_matches = sum(1 for word in persona_keywords if word in content or word in title)
        job_matches = sum(1 for word in job_keywords if word in content or word in title)
        
        # Dynamic domain-specific keyword matching
        domain_matches = 0
        if domain_keywords:
            domain_matches = sum(1 for word in domain_keywords if word in content or word in title)
        
        # Calculate weighted score
        raw_score = (persona_matches * 2) + (job_matches * 3) + domain_matches
        
        # Scale to 1-10 range
        return min(10, max(1, raw_score + 3))
    
    def llm_analyze_section(self, section: Dict, persona: str, job: str) -> str:
        """Use LLM to analyze section relevance (constraint-aware)"""
        if not self.llm:
            return f"Keyword analysis: {section['section_title']} appears relevant for {persona} planning {job}"
        
        try:
            # Very short prompt to stay within constraints
            prompt = f"For {persona} doing '{job}', rate relevance of: {section['section_title'][:100]}. Brief analysis:"
            
            response = self.llm(
                prompt,
                max_tokens=50,  # Very limited to stay fast
                temperature=0.3,
                stop=[".", "\n"]
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            return f"Analysis: {section['section_title']} relevant for {job}"
    
    def llm_refine_content(self, content: str, persona: str, job: str) -> str:
        """Use LLM to refine content for specific persona/job"""
        if not self.llm:
            return content[:400].replace('\n', ' > ')  # Fallback to truncated content with > replacement
        
        try:
            # Minimal prompt for content refinement
            prompt = f"For {persona} planning {job}, key points from: {content[:300]}. Summary:"
            
            response = self.llm(
                prompt,
                max_tokens=80,  # Limited for speed
                temperature=0.3,
                stop=["\n\n"]
            )
            
            refined = response['choices'][0]['text'].strip()
            refined_text = refined if refined else content[:400]
            # Replace newlines with > for better readability
            return refined_text.replace('\n', ' > ')
            
        except Exception as e:
            return content[:400].replace('\n', ' > ')
    
    def process_from_config(self, input_config_file: str, pdfs_folder: str) -> Dict:
        """Process PDFs based on input configuration file"""
        start_time = time.time()
        
        # Load input configuration
        config = self.load_input_config(input_config_file)
        
        # Get persona and job from config
        persona = config['persona']['role']
        job_to_be_done = config['job_to_be_done']['task']
        
        # Find PDF files based on config documents
        pdf_files = []
        for doc in config['documents']:
            pdf_path = os.path.join(pdfs_folder, doc['filename'])
            if os.path.exists(pdf_path):
                pdf_files.append(pdf_path)
        
        # Extract sections from all PDFs
        all_sections = []
        for pdf_path in pdf_files:
            sections = self.extract_pdf_sections(pdf_path)
            all_sections.extend(sections)
        
        # Prepare keywords for fast scoring
        persona_keywords = set(persona.lower().split())
        job_keywords = set(job_to_be_done.lower().split())
        
        # Generate domain-specific keywords using LLM
        domain_keywords = self.get_domain_keywords(persona, job_to_be_done)
        
        # Fast keyword-based scoring + LLM analysis for top candidates
        scored_sections = []
        for section in all_sections:
            score = self.fast_keyword_score(section, persona_keywords, job_keywords, domain_keywords)
            scored_sections.append({**section, 'relevance_score': score})
        
        # Sort and get top candidates for LLM analysis
        scored_sections.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_candidates = scored_sections[:10]  # Analyze top 10 with LLM
        
        # Use LLM to analyze top candidates (constraint-aware)
        llm_analyzed_sections = []
        for section in top_candidates:
            analysis = self.llm_analyze_section(section, persona, job_to_be_done)
            section['llm_analysis'] = analysis
            llm_analyzed_sections.append(section)
        
        # Select final top 5 sections
        top_sections = llm_analyzed_sections[:5]
        
        # Create subsection analysis with LLM refinement
        subsections = []
        for section in top_sections:
            if section['relevance_score'] >= 6:  # Only high-scoring sections
                # Extract first substantial paragraph
                content_lines = section['content'].split('\n')
                substantial_content = ""
                for line in content_lines:
                    line = line.strip()
                    if len(line) > 100:  # Substantial content
                        substantial_content = line
                        break
                
                if not substantial_content and len(section['content']) > 100:
                    substantial_content = section['content'][:500]
                
                if substantial_content:
                    # Use LLM to refine content for the specific persona/job
                    refined_text = self.llm_refine_content(substantial_content, persona, job_to_be_done)
                    
                    subsections.append({
                        'document': section['document'],
                        'refined_text': refined_text[:800],  # Limit length
                        'page_number': section['page_number']
                    })
        
        # Ensure we have exactly 5 subsections to match output format
        while len(subsections) < 5 and len(llm_analyzed_sections) > len(subsections):
            # Add more subsections from remaining analyzed sections
            for section in llm_analyzed_sections[len(subsections):]:
                if len(subsections) >= 5:
                    break
                content = section['content'][:400] if len(section['content']) > 50 else section['content']
                if content.strip():
                    # Try to refine with LLM if available, and replace newlines
                    refined_text = self.llm_refine_content(content, persona, job_to_be_done)
                    
                    subsections.append({
                        'document': section['document'],
                        'refined_text': refined_text,
                        'page_number': section['page_number']
                    })
        
        # Build result in the exact format required
        result = {
            'metadata': {
                'input_documents': [doc['filename'] for doc in config['documents']],
                'persona': persona,
                'job_to_be_done': job_to_be_done,
                'processing_timestamp': datetime.now().isoformat()
            },
            'extracted_sections': [
                {
                    'document': section['document'],
                    'section_title': section['section_title'],
                    'importance_rank': i + 1,
                    'page_number': section['page_number']
                }
                for i, section in enumerate(top_sections)
            ],
            'subsection_analysis': subsections[:5]  # Limit to 5 to match format
        }
        
        processing_time = time.time() - start_time
        print(f"Processing completed in {processing_time:.2f} seconds")
        
        return result


def main():
    """Main function for optimized document processing"""
    analyzer = DocumentAnalyzer()
    
    # Configuration
    input_config_file = "1binput.json"
    pdfs_folder = "PDFs"
    output_dir = "output"
    
    start_time = time.time()
    
    # Process documents
    result = analyzer.process_from_config(input_config_file, pdfs_folder)
    
    # Save output
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "analysis_output.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    total_time = time.time() - start_time
    print(f"Total processing time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()
