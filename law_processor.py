# law_processor.py
from typing import Dict, List, Optional
from pydantic import BaseModel
import re

class LawSubsection(BaseModel):
    id: str
    content: str
    requirements: List[str]

class LawSection(BaseModel):
    title: str
    content: str
    subsections: List[LawSubsection]
    requirements: List[str]

class ComplianceResult(BaseModel):
    compliant: bool
    violations: List[str]
    warnings: List[str]
    recommendations: List[str]

class NovaScotiaLawProcessor:
    def __init__(self, law_text: str):
        self.law_text = law_text
        self.sections = self._parse_sections()
        self.key_requirements = self._extract_requirements()

    def _parse_sections(self) -> List[LawSection]:
        sections = []
        current_section = None
        current_subsection = None

        for line in self.law_text.split('\n'):
            if line.strip().startswith('Section'):
                if current_section:
                    sections.append(current_section)
                current_section = LawSection(
                    title=line.strip(),
                    content='',
                    subsections=[],
                    requirements=[]
                )
            elif line.strip().startswith('(') and current_section:
                if current_subsection:
                    current_section.subsections.append(current_subsection)
                current_subsection = LawSubsection(
                    id=line.strip().split(')')[0] + ')',
                    content=line.strip(),
                    requirements=[]
                )
            elif current_subsection and line.strip():
                current_subsection.content += '\n' + line.strip()
                # Extract requirements from line
                if 'shall' in line or 'must' in line or 'required' in line:
                    current_subsection.requirements.append(line.strip())
            elif current_section and line.strip():
                current_section.content += '\n' + line.strip()

        if current_subsection:
            current_section.subsections.append(current_subsection)
        if current_section:
            sections.append(current_section)

        return sections

    def _extract_requirements(self) -> Dict[str, List[str]]:
        requirements = {
            'security_deposit': [],
            'rent': [],
            'termination': [],
            'maintenance': [],
            'utilities': [],
            'subletting': [],
            'notices': []
        }

        for section in self.sections:
            for subsection in section.subsections:
                for req in subsection.requirements:
                    if 'security deposit' in req.lower():
                        requirements['security_deposit'].append(req)
                    elif 'rent' in req.lower():
                        requirements['rent'].append(req)
                    elif 'termination' in req.lower() or 'notice to quit' in req.lower():
                        requirements['termination'].append(req)
                    elif 'maintenance' in req.lower() or 'repair' in req.lower():
                        requirements['maintenance'].append(req)
                    elif 'utility' in req.lower() or 'utilities' in req.lower():
                        requirements['utilities'].append(req)
                    elif 'sublet' in req.lower() or 'assign' in req.lower():
                        requirements['subletting'].append(req)
                    elif 'notice' in req.lower():
                        requirements['notices'].append(req)

        return requirements

    def get_section_by_title(self, title: str) -> Optional[LawSection]:
        for section in self.sections:
            if title.lower() in section.title.lower():
                return section
        return None

    async def analyze_lease_compliance(self, lease_text: str) -> ComplianceResult:
        compliance_results = {
            'compliant': True,
            'violations': [],
            'warnings': [],
            'recommendations': []
        }

        # Check security deposit requirements
        if 'security deposit' in lease_text.lower():
            for req in self.key_requirements['security_deposit']:
                if not self._check_requirement(lease_text, req):
                    compliance_results['violations'].append(
                        f"Security Deposit Violation: {req}"
                    )

        # Add checks for other requirements...
        
        return ComplianceResult(**compliance_results)

    def _check_requirement(self, lease_text: str, requirement: str) -> bool:
        # Extract the key terms from requirement
        key_terms = re.findall(r'\b\w+\b', requirement.lower())
        key_terms = [term for term in key_terms if len(term) > 3]
        
        # Check if key terms are present in lease text
        lease_text_lower = lease_text.lower()
        return all(term in lease_text_lower for term in key_terms)

    def get_relevant_law_sections(self, lease_text: str) -> List[LawSection]:
        relevant_sections = []
        
        # Add sections based on lease content
        if 'security deposit' in lease_text.lower():
            security_section = self.get_section_by_title('Security Deposit')
            if security_section:
                relevant_sections.append(security_section)
                
        # Add more section checks...
        
        return relevant_sections

    def format_for_llm(self, sections: List[LawSection]) -> str:
        formatted = "NOVA SCOTIA RESIDENTIAL TENANCIES ACT REQUIREMENTS:\n\n"
        
        for section in sections:
            formatted += f"Section: {section.title}\n"
            formatted += f"Content: {section.content}\n"
            if section.requirements:
                formatted += "Requirements:\n"
                for req in section.requirements:
                    formatted += f"- {req}\n"
            formatted += "\n"
            
        return formatted