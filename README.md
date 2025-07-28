# Document Analyzer Docker Container

## Overview
This is a containerized document analysis application that processes PDF files using AI-powered analysis. The container includes a streamlined Python application with CPU-optimized LLM capabilities for intelligent document processing.

## Container Features
- **Multi-stage Docker build** for optimized image size
- **CPU-only processing** with OpenMP optimization
- **Security hardening** with non-root user execution
- **874MB Gemma-3-1B model** for intelligent analysis
- **Universal keyword generation** for any domain/persona
- **Health checks** for container monitoring
- **Auto PDF discovery** from input JSON configuration

## Usage

### 1. Build the Container
```bash
docker build -t document-analyzer .
```

### 2. Run Analysis
```bash
docker run --rm --name analyzer document-analyzer
```

### 3. Extract Output (Optional)
```bash
docker run --rm --name analyzer -v "${PWD}:/host" document-analyzer bash -c "python main.py && cp /app/output/analysis_output.json /host/results.json"
```

## Input Format
The container expects a `1binput.json` file with the following structure:
```json
{
  "challenge_info": {
    "challenge_id": "round_1b_003",
    "test_case_name": "create_manageable_forms",
    "description": "Creating manageable forms"
  },
  "persona": {
    "role": "HR professional",
    "job_to_be_done": "Create and manage fillable forms for onboarding and compliance."
  },
  "documents": [
    {
      "filename": "document.pdf",
      "title": "Document Title"
    }
  ]
}
```

## Output Format
The container generates `analysis_output.json` with:
- **Metadata**: Input documents, persona, job description, timestamp
- **Extracted Sections**: Key sections with importance ranking
- **Subsection Analysis**: Detailed analysis with relevance scores and refined text

## Performance
- **Processing Time**: ~0.8 seconds for 15 PDF documents
- **Model Size**: 874MB (under 1GB constraint)
- **CPU Threads**: Optimized for 4 threads
- **Memory Usage**: Minimal with efficient resource management

## Technical Specifications
- **Base Image**: Python 3.11-slim
- **LLM Engine**: llama-cpp-python with Gemma-3-1B
- **PDF Processing**: PyMuPDF (fitz)
- **Security**: Non-root user (app:app)
- **Environment**: CPU-only with OpenMP support

## Health Check
The container includes automatic health checks to verify:
- LLM dependencies are properly loaded
- PDF processing capabilities are functional

## Files in Container
- `/app/main.py` - Main analysis application
- `/app/1binput.json` - Input configuration
- `/app/PDFs/` - Source PDF documents
- `/app/models/` - LLM model file
- `/app/output/` - Generated analysis results

## Container Optimization
- Multi-stage build reduces final image size
- Runtime dependencies separated from build tools
- CPU-specific environment variables for optimal performance
- Proper file ownership and permissions for security
