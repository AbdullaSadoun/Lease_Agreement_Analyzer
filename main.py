# main.py
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import re
from enum import Enum
import asyncio
import httpx
from docx import Document
from pdfminer.high_level import extract_text
import io
import json
from law_processor import NovaScotiaLawProcessor  

# Constants for Llama/Ollama
OLLAMA_API_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama2:7b"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class RuleCheckResult(BaseModel):
    rule: str
    passed: bool
    details: str

class LLMAnalysisResult(BaseModel):
    # fairness_score: float
    # potential_issues: List[str]
    # recommendations: List[str]
    fairness_score: float
    potential_issues: List[str]
    recommendations: List[str]
    law_violations: Optional[List[str]] = []

class LeaseAnalysisResult(BaseModel):
    rule_based_results: List[RuleCheckResult]
    llm_results: LLMAnalysisResult
    risk_level: RiskLevel
    requires_manual_review: bool
    summary: str

class LlamaClient:
    def __init__(self):
        self.url = "http://localhost:11434/api/generate"
        self.model = "llama2:7b"  # Updated to use the 7B model
        self.client = httpx.AsyncClient(timeout=600.0)
        
    async def _call_llama(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 10,
                        "temperature": 0.1
                    }
                }
            )
            response.raise_for_status() # Raise an exception for 4xx/5xx errors
            return response.json()["response"]
            
    async def analyze(self, text: str, law_context: str = "") -> LLMAnalysisResult:
        prompt = f"""You are a legal expert specialized in Nova Scotia lease agreement analysis. Analyze this lease agreement according to Nova Scotia law.:

    LEASE TEXT:
    {text}

    APPLICABLE LAW:
    {law_context}

    Format response as JSON:
    {{
        "fairness_score": <number>,
        "potential_issues": [<list of strings>],
        "recommendations": [<list of strings>],
        "law_violations": [<list of strings>]
    }}

    Ensure your response is ONLY the JSON object, with no additional text."""

        try:
            response = await self._call_llama(prompt)
            result = json.loads(response)
            return LLMAnalysisResult(
                fairness_score=result["fairness_score"],
                potential_issues=result["potential_issues"],
                recommendations=result["recommendations"]
            )
        except Exception as e:
            raise HTTPException(500, f"LLM analysis failed: {str(e)}")

class RuleEngine:
    def __init__(self):
        with open("nova_scotia_law.txt", "r") as f:
            self.law_processor = NovaScotiaLawProcessor(f.read())
            
        # Define the rule functions first
        self.rules = {
            'security_deposit': self._check_security_deposit,
            'rent_terms': self._check_rent_terms,
            'notice_period': self._check_notice_period,
            'maintenance': self._check_maintenance,
            'utilities': self._check_utilities,
            'subletting': self._check_subletting,
            'termination': self._check_termination
        }

        # Store law requirements separately instead of mixing them with rule functions
        self.law_requirements = self.law_processor.key_requirements

    async def _check_security_deposit(self, text: str) -> RuleCheckResult:
        has_deposit = bool(re.search(r'security deposit|damage deposit', text, re.I))
        deposit_limit = bool(re.search(r'deposit.{1,50}(equal|equivalent|not exceed).{1,20}(one|1|two|2).{1,20}month', text, re.I))
        
        # Check against law requirements
        law_requirements_met = True
        details = []
        for req in self.law_requirements.get('security_deposit', []):
            if not self._check_requirement(text, req):
                law_requirements_met = False
                details.append(f"Failed requirement: {req}")
                
        return RuleCheckResult(
            rule="Security Deposit",
            passed=has_deposit and deposit_limit and law_requirements_met,
            details="\n".join(details) if details else "Checks deposit terms and maximum allowed amount"
        )

    async def _check_rent_terms(self, text: str) -> RuleCheckResult:
        has_terms = bool(re.search(r'rent.*payment|payment.*rent', text, re.I))
        return RuleCheckResult(
            rule="Rent Terms",
            passed=has_terms,
            details="Validates rent payment terms"
    )

    async def _check_notice_period(self, text: str) -> RuleCheckResult:
        has_notice = bool(re.search(r'notice period|termination notice', text, re.I))
        return RuleCheckResult(
            rule="Notice Period",
            passed=has_notice,
            details="Verifies notice period requirements"
        )

    async def _check_maintenance(self, text: str) -> RuleCheckResult:
        has_maintenance = bool(re.search(r'maintenance|repairs|upkeep', text, re.I))
        return RuleCheckResult(
            rule="Maintenance",
            passed=has_maintenance,
            details="Checks maintenance responsibilities"
        )

    async def _check_utilities(self, text: str) -> RuleCheckResult:
        has_utilities = bool(re.search(r'utilities|water|electricity|gas', text, re.I))
        return RuleCheckResult(
            rule="Utilities",
            passed=has_utilities,
            details="Checks utility responsibilities"
        )

    async def _check_subletting(self, text: str) -> RuleCheckResult:
        has_subletting = bool(re.search(r'sublet|sublease|assign', text, re.I))
        return RuleCheckResult(
            rule="Subletting",
            passed=has_subletting,
            details="Checks subletting terms"
        )

    async def _check_termination(self, text: str) -> RuleCheckResult:
        has_termination = bool(re.search(r'termination|end.*lease|break.*lease', text, re.I))
        return RuleCheckResult(
            rule="Termination",
            passed=has_termination,
            details="Validates termination conditions"
        )

    async def analyze(self, text: str) -> List[RuleCheckResult]:
        # Create tasks only for the rule functions
        tasks = [rule(text) for rule in self.rules.values()]
        return await asyncio.gather(*tasks)

class LeaseAnalyzer:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.llm_analyzer = LlamaClient()

        with open("nova_scotia_law.txt", "r") as f:
            law_text = f.read()
        self.law_processor = NovaScotiaLawProcessor(law_text)

    def _calculate_risk_level(
        self, 
        rule_results: List[RuleCheckResult], 
        llm_results: LLMAnalysisResult
    ) -> RiskLevel:
        failed_rules = sum(1 for r in rule_results if not r.passed)
        fairness_score = llm_results.fairness_score

        if failed_rules > 2 or fairness_score < 60:
            return RiskLevel.HIGH
        elif failed_rules > 0 or fairness_score < 80:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _generate_summary(
        self,
        rule_results: List[RuleCheckResult],
        llm_results: LLMAnalysisResult,
        risk_level: RiskLevel
    ) -> str:
        failed_rules = [r.rule for r in rule_results if not r.passed]
        summary_parts = []

        if risk_level == RiskLevel.HIGH:
            summary_parts.append("High-risk issues detected in the lease agreement.")
        elif risk_level == RiskLevel.MEDIUM:
            summary_parts.append("Some concerns identified in the lease agreement.")
        else:
            summary_parts.append("Lease agreement appears generally compliant.")

        if failed_rules:
            summary_parts.append(f"Failed checks: {', '.join(failed_rules)}.")
            summary_parts.append("Please review these sections carefully.")

        if llm_results.potential_issues:
            summary_parts.append(f"Key issue: {llm_results.potential_issues[0]}")

        return " ".join(summary_parts)

    async def analyze(self, text: str) -> LeaseAnalysisResult:
        # Get law context first
        law_sections = self.law_processor.get_relevant_law_sections(text)
        formatted_law = self.law_processor.format_for_llm(law_sections)
        
        # Run parallel analysis with context
        rule_results, llm_results, law_results = await asyncio.gather(
            self.rule_engine.analyze(text),
            self.llm_analyzer.analyze(text, formatted_law),
            self.law_processor.analyze_lease_compliance(text)
        )
        
        risk_level = self._calculate_risk_level(rule_results, llm_results)
        
        return LeaseAnalysisResult(
            rule_based_results=rule_results,
            llm_results=llm_results,
            risk_level=risk_level,
            requires_manual_review=risk_level == RiskLevel.HIGH,
            summary=self._generate_summary(rule_results, llm_results, risk_level)
        )

async def extract_text_from_file(file: UploadFile) -> str:
    content = await file.read()
    
    if file.filename.endswith('.txt'):
        return content.decode('utf-8')
    
    elif file.filename.endswith('.docx'):
        doc = Document(io.BytesIO(content))
        return '\n'.join(paragraph.text for paragraph in doc.paragraphs)
    
    elif file.filename.endswith('.pdf'):
        return extract_text(io.BytesIO(content))
    
    else:
        raise HTTPException(400, "Unsupported file format")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
analyzer = LeaseAnalyzer()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze")
async def analyze_lease(file: UploadFile = File(...)):
    if not file.filename.endswith(('.txt', '.doc', '.docx', '.pdf')):
        raise HTTPException(400, "Unsupported file format")

    text = await extract_text_from_file(file)

    # Debug print
    print("\n" + "="*50)
    print(f"📄 DEBUG: Extracted text from {file.filename}")
    print("="*50)
    print(text)
    print("="*50 + "\n")

    return await analyzer.analyze(text)

if __name__ == "__main__":
    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)


    