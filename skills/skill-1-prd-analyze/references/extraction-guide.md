# PRD Extraction Guide

## PRD Format Detection

PRDs come in many formats. Use these heuristics:

### Markdown PRD (most common)
- Sections with `##` headings
- User stories may be in tables or bullet lists
- NFRs often in a dedicated section near the end
- Look for keywords: "Requirements", "User Stories", "Acceptance Criteria", "Non-Functional"

### Formal PRD (structured)
- Numbered sections (1.0, 2.0, etc.)
- "SHALL" / "MUST" / "SHOULD" language
- Traceability matrix
- Version history table

### Lightweight PRD (startup-style)
- Problem statement
- Solution overview
- Feature list (often just bullets)
- Success metrics
- May lack formal acceptance criteria — you'll need to infer them

## Extraction Tips

### Modules
- Look for "Architecture", "System Components", "Modules"
- If not explicit, infer from user story groupings
- Each logical subsystem = one module

### User Stories
- Standard format: "As a {persona}, I want to {action} so that {goal}"
- May also appear as: "Feature: {name}" with scenarios
- If no formal stories, convert feature descriptions to story format
- Always add acceptance criteria — if not in PRD, derive from context

### NFRs
- Look for: "Performance", "Security", "Scalability", "Reliability"
- Also check: "Constraints", "Quality Attributes", "SLAs"
- Convert vague NFRs to measurable: "fast" → "< 200ms p95"

### Dependencies
- External APIs, SDKs, services mentioned in the PRD
- "Integration with X" phrases
- Infrastructure requirements (databases, message queues)

## Common Pitfalls

1. **Scope creep in extraction**: Only extract what the PRD says, don't add features
2. **Missing personas**: If PRD mentions features without personas, ask who uses them
3. **Ambiguous priorities**: Default to medium; flag for clarification
4. **Cross-cutting concerns**: Auth, logging, monitoring often span all modules — create a dedicated module or tag as cross-cutting
