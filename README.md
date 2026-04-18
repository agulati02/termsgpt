# TermsGPT

---

## Executive Summary

Every time someone signs up for a digital service, they are asked to agree to Terms & Conditions that can run to dozens of pages of dense legal text. Most users click "I Agree" without reading a word — and in doing so, they may unknowingly consent to the sale of their personal data, waive their right to sue, or surrender ownership of their content.

TermsGPT addresses this problem directly. It is a browser extension that sits in the background and, the moment a user lands on a Terms & Conditions or Privacy Policy page, automatically reads the document, identifies the clauses that carry the most risk, and presents a plain-English summary in a clean side panel — no copy-pasting, no separate tools, no legal expertise required.

For each document, TermsGPT produces a structured risk report covering six critical areas: data sharing practices, arbitration requirements, auto-renewal terms, intellectual property rights, dispute jurisdiction, and data deletion rights. Each finding is rated by severity and linked directly to the relevant section of the original document so users can read the exact language themselves.

Beyond the automatic scan, users can ask natural language questions about any part of the agreement and receive grounded, citation-backed answers drawn from the actual text. TermsGPT turns opaque legal contracts into a transparent, navigable resource — putting users back in control of what they agree to.

---

## Documentation

The following documents provide a complete reference for understanding, setting up, and extending TermsGPT.

| Document | Description |
|----------|-------------|
| [Project Description](docs/DESCRIPTION.md) | Problem statement, proposed solution, and project scope |
| [Technical Details](docs/TECHNICAL.md) | Technology stack, directory structure, extension architecture, and backend pipeline |
| [Usage Guidelines](docs/USAGE.md) | Pre-requisites, local setup instructions, and troubleshooting |
| [Future Scope](docs/FUTURE.md) | Planned improvements: API key UI, vector database integration, and containerization |
