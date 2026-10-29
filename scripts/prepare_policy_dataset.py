from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "dataset"
DATASET_DIR.mkdir(exist_ok=True)

POLICIES = [
    {
        "filename": "remote_work_policy.pdf",
        "title": "Remote Work Policy",
        "sections": [
            {
                "heading": "1. Purpose",
                "paragraphs": [
                    "This policy establishes the expectations for hybrid and remote work arrangements across the enterprise. It is designed to support productivity, service continuity, and employee wellbeing while preserving cybersecurity and compliance requirements.",
                    "Employees are expected to maintain the same standard of performance, responsiveness, and professionalism whether working from the office or a remote location. Managers must document work expectations, availability windows, and team collaboration norms for each remote arrangement.",
                ],
            },
            {
                "heading": "2. Eligibility and Scheduling",
                "paragraphs": [
                    "Remote work is available to employees in roles that can be executed effectively away from the office without material operational risk. Employees must receive manager approval before adopting a remote schedule.",
                    "Standard remote arrangements may not exceed three days per week unless approved by the executive sponsor. Employees must remain reachable during core business hours and must log all planned absences in the timekeeping system.",
                ],
            },
            {
                "heading": "3. Security and Equipment",
                "paragraphs": [
                    "Employees working remotely must use company-issued laptops, secure VPN access, and approved collaboration tools. Personal devices may only be used under a policy exception approved by IT and security leadership.",
                    "Confidential data must remain within approved systems, and employees must avoid storing policy or customer information on local personal storage or unapproved file-sharing platforms.",
                ],
            },
        ],
    },
    {
        "filename": "expense_reimbursement_policy.pdf",
        "title": "Expense Reimbursement Policy",
        "sections": [
            {
                "heading": "1. Scope",
                "paragraphs": [
                    "This policy defines allowable business expenses and the expectations for reimbursement requests. It applies to employees, contractors with approved travel authority, and temporary project team members.",
                    "The organization reimburses reasonable and necessary expenses directly related to work duties, client obligations, and approved travel. Expenses must be supported by original receipts and company-approved accounting documentation.",
                ],
            },
            {
                "heading": "2. Approval and Submission",
                "paragraphs": [
                    "All expenses must be submitted within 30 calendar days of the purchase or travel event. Requests without itemized receipts, business purpose descriptions, or manager approval will be returned for correction.",
                    "Travel and lodging expenses must align with approved budgets. The company will not reimburse personal upgrades, alcohol, entertainment, or non-business-related purchases.",
                ],
            },
        ],
    },
    {
        "filename": "information_security_policy.pdf",
        "title": "Information Security Policy",
        "sections": [
            {
                "heading": "1. Security Responsibilities",
                "paragraphs": [
                    "All employees are responsible for protecting enterprise information assets, including customer records, internal strategic plans, and vendor documentation. Security responsibilities are included in role-based training and annual attestations.",
                    "Employees must use strong passwords, multifactor authentication, and only approved applications when handling business information. Any suspected account compromise or data exposure must be reported immediately to the security operations center.",
                ],
            },
            {
                "heading": "2. Acceptable Use",
                "paragraphs": [
                    "Systems and data may be used only for authorized business purposes and in alignment with approved policies. Unauthorized exfiltration, tampering, or access to restricted information is prohibited.",
                    "Users may not bypass security controls, transfer confidential files to unmanaged devices, or install unapproved software. Access rights are assigned based on business need and are periodically reviewed.",
                ],
            },
        ],
    },
    {
        "filename": "data_retention_policy.pdf",
        "title": "Data Retention Policy",
        "sections": [
            {
                "heading": "1. Retention Schedule",
                "paragraphs": [
                    "The company retains records for the period required by legal obligations, operational needs, and audit requirements. Data categories with regulatory retention requirements must not be deleted before the minimum retention window has elapsed.",
                    "Records related to personnel administration, tax reporting, and contracts are retained according to the approved enterprise retention schedule, which is reviewed at least annually by legal and compliance teams.",
                ],
            },
            {
                "heading": "2. Destruction and Disposal",
                "paragraphs": [
                    "When records reach the end of their retention period, they must be securely deleted or destroyed using approved methods. Paper records may be cross-shredded or securely destroyed by an authorized disposal vendor.",
                    "System administrators must document deletion activities and maintain evidence of disposal for regulated records. Discrepancies or exceptions must be escalated to the Records Management Office.",
                ],
            },
        ],
    },
    {
        "filename": "vendor_management_policy.pdf",
        "title": "Third-Party Vendor Management Policy",
        "sections": [
            {
                "heading": "1. Due Diligence",
                "paragraphs": [
                    "All third-party service providers must complete a due diligence review before contract execution. The review includes ownership information, security posture assessments, financial stability, and compliance history.",
                    "Procurement and legal teams must confirm that contracts include data handling obligations, confidentiality protections, and the right to audit. Exceptions require executive approval.",
                ],
            },
            {
                "heading": "2. Ongoing Monitoring",
                "paragraphs": [
                    "Vendor performance, contract compliance, and control effectiveness are reviewed on a periodic basis. Issues that create operational, legal, or security risk must be documented in the vendor risk register.",
                    "The organization may suspend or terminate a vendor relationship if material security violations, regulatory failures, or service degradation occur.",
                ],
            },
        ],
    },
    {
        "filename": "anti_bribery_policy.pdf",
        "title": "Anti-Bribery and Corruption Policy",
        "sections": [
            {
                "heading": "1. Standards of Conduct",
                "paragraphs": [
                    "The company prohibits bribery, corruption, facilitation payments, and improper gifts or hospitality in all business dealings. This policy applies to employees, intermediaries, agents, and contractors acting on behalf of the company.",
                    "Any facilitation or inducement offered to influence a decision, secure a contract, or gain a business advantage is prohibited, regardless of whether the benefit is cash, gifts, travel, or employment opportunities.",
                ],
            },
            {
                "heading": "2. Reporting and Escalation",
                "paragraphs": [
                    "Employees should report suspected violations through the confidential reporting hotline or directly to legal and compliance. Reports will be investigated promptly and handled with appropriate confidentiality.",
                    "Retaliation against a reporting employee is prohibited. Violations may result in disciplinary action, contract termination, and referral to external authorities where required.",
                ],
            },
        ],
    },
    {
        "filename": "leave_policy.pdf",
        "title": "Leave and Time Off Policy",
        "sections": [
            {
                "heading": "1. Types of Leave",
                "paragraphs": [
                    "Employees may be eligible for annual paid leave, sick leave, parental leave, bereavement leave, and other state-specific or local leave programs as required by law. Managers must coordinate staffing plans to maintain continuity of operations.",
                    "Employees should request leave as early as practical and comply with the required notice periods for planned time off. Unscheduled absences should be reported according to the emergency attendance procedures.",
                ],
            },
            {
                "heading": "2. Documentation and Approval",
                "paragraphs": [
                    "Leave requests must be submitted using the designated system and approved by the employee's manager before the absence begins unless circumstances prevent advance approval. Medical documentation may be required for absences beyond a defined threshold.",
                    "Misrepresentation of leave eligibility, falsification of records, or repeated unauthorized absences may result in corrective action, up to and including termination of employment.",
                ],
            },
        ],
    },
    {
        "filename": "incident_response_policy.pdf",
        "title": "Incident Response Policy",
        "sections": [
            {
                "heading": "1. Response Objectives",
                "paragraphs": [
                    "The company maintains a documented incident response capability to mitigate the impact of cybersecurity, service outage, and operational disruption events. Response work is coordinated by the incident commander and supported by technology, legal, and business stakeholders.",
                    "The organization prioritizes containment, preservation of evidence, and restoration of critical services while ensuring timely communication to affected stakeholders and regulators when required.",
                ],
            },
            {
                "heading": "2. Escalation Procedures",
                "paragraphs": [
                    "All suspected security incidents must be reported immediately to the security operations center and line management. High-severity events require notification within one hour to the executive response team.",
                    "Post-incident reviews must document the root cause, business impact, remediation actions, and lessons learned. Corrective actions must be tracked to closure.",
                ],
            },
        ],
    },
    {
        "filename": "business_continuity_policy.pdf",
        "title": "Business Continuity Policy",
        "sections": [
            {
                "heading": "1. Continuity Planning",
                "paragraphs": [
                    "Each business unit must maintain a continuity plan for critical services, key personnel, essential records, and technology dependencies. Plans must identify recovery priorities, delegated decision authority, and alternate operating procedures.",
                    "Plan owners must review their continuity documentation at least annually and whenever a material process, system, or supplier changes. Business unit leaders are accountable for confirming that assigned recovery roles remain current.",
                ],
            },
            {
                "heading": "2. Testing and Recovery",
                "paragraphs": [
                    "Critical service recovery procedures must be exercised at least once each calendar year. Exercises may use a tabletop scenario or a technical recovery test appropriate to the service risk.",
                    "Exercise results, identified gaps, and corrective action owners must be recorded in the continuity register. During a disruption, the incident commander coordinates restoration priorities with business unit leaders.",
                ],
            },
        ],
    },
    {
        "filename": "supplier_assurance_policy.pdf",
        "title": "Supplier Assurance Policy",
        "sections": [
            {
                "heading": "1. Supplier Review",
                "paragraphs": [
                    "Business owners must assess supplier performance against agreed service levels, contractual obligations, and risk controls. Reviews must be documented at least annually for critical suppliers and when a significant service change occurs.",
                    "Material weaknesses must be assigned an accountable owner and a target remediation date. The supplier relationship manager tracks open actions and escalates overdue high-risk issues to procurement leadership.",
                ],
            },
            {
                "heading": "2. Assurance Records",
                "paragraphs": [
                    "Assessment records, service reports, and remediation evidence must be stored in the approved vendor management repository. Access to supplier records is limited to personnel with a business need.",
                    "Before renewal, the business owner must confirm that unresolved findings have an approved treatment plan and that the supplier remains suitable for the service provided.",
                ],
            },
        ],
    },
]


def build_policy_pdf(policy: dict[str, object], output_path: Path) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=18)
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["BodyText"],
        fontSize=12,
        leading=16,
        spaceAfter=8,
        textColor="#1f2937",
        fontName="Helvetica-Bold",
    )
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=10, textColor="#1f2937")
    story = [
        Paragraph(str(policy["title"]), title_style),
        Paragraph("Internal policy document | Confidential", styles["Italic"]),
        Spacer(1, 0.2 * inch),
    ]
    for section in policy["sections"]:
        story.append(Paragraph(str(section["heading"]), heading_style))
        for paragraph in section["paragraphs"]:
            story.append(Paragraph(paragraph, body_style))
        story.append(Spacer(1, 0.08 * inch))
    doc = SimpleDocTemplate(str(output_path), pagesize=letter, title=str(policy["title"]))
    doc.build(story)


def main() -> None:
    for policy in POLICIES:
        output_path = DATASET_DIR / policy["filename"]
        if output_path.exists():
            print(f"Kept existing {output_path.name}")
            continue
        build_policy_pdf(policy, output_path)
        print(f"Generated {output_path.name}")

    questions = [
        {"question": "What is the minimum notice required to request remote work flexibility?", "policy": "Remote Work Policy"},
        {"question": "Which employees are eligible for remote work arrangements?", "policy": "Remote Work Policy"},
        {"question": "What equipment must employees use while working remotely?", "policy": "Remote Work Policy"},
        {"question": "What documentation is required for expense reimbursement requests?", "policy": "Expense Reimbursement Policy"},
        {"question": "Which expenses are not reimbursable under the policy?", "policy": "Expense Reimbursement Policy"},
        {"question": "How quickly must employees report a suspected information security incident?", "policy": "Information Security Policy"},
        {"question": "What types of data are protected under the security policy?", "policy": "Information Security Policy"},
        {"question": "What is the retention principle for regulated records?", "policy": "Data Retention Policy"},
        {"question": "How should records be destroyed at the end of their retention period?", "policy": "Data Retention Policy"},
        {"question": "What due diligence checks are required before engaging a vendor?", "policy": "Third-Party Vendor Management Policy"},
        {"question": "When can a vendor relationship be suspended or terminated?", "policy": "Third-Party Vendor Management Policy"},
        {"question": "What is prohibited under the anti-bribery policy?", "policy": "Anti-Bribery and Corruption Policy"},
        {"question": "How should employees report suspected bribery or corruption?", "policy": "Anti-Bribery and Corruption Policy"},
        {"question": "What are the approved categories of leave under the policy?", "policy": "Leave and Time Off Policy"},
        {"question": "What happens if employees misrepresent leave eligibility?", "policy": "Leave and Time Off Policy"},
        {"question": "Who leads the incident response effort during a major event?", "policy": "Incident Response Policy"},
        {"question": "What must be documented after an incident is resolved?", "policy": "Incident Response Policy"},
    ]

    (DATASET_DIR / "test_questions.json").write_text(json.dumps(questions, indent=2), encoding="utf-8")
    (DATASET_DIR / "README.md").write_text(
        "# Synthetic Enterprise Policy Dataset\n\n"
        "This dataset contains original synthetic policy documents used to test the document ingestion, indexing, and RAG policy Q&A experience.\n\n"
        "Files are generated by `scripts/prepare_policy_dataset.py` and ingested by `scripts/ingest_dataset.py`.\n\n"
        "The dataset includes policy documents covering remote work, reimbursement, information security, data retention, vendor management, anti-bribery, leave, and incident response.\n",
        encoding="utf-8",
    )
    print(f"Wrote dataset metadata to {DATASET_DIR}")


if __name__ == "__main__":
    main()
