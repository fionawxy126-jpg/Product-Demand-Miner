---
name: generate-docs
description: Analyze codebase and generate project documentation following adit spec
---
Analyze the current codebase and generate project documentation following the adit document specification.

## Context

This project uses adit for AI-assisted planning. The planning pipeline needs structured project documents as context. Your job is to analyze the codebase and fill in document templates.

## Steps

1. Check what document templates exist in the `.adit/docs/` directory. If none exist, list what's missing and suggest the user run `adit docs scaffold <type>` first.
2. For each template file in `.adit/docs/`:
   a. Read the template to understand which sections need content.
   b. Analyze the relevant parts of the codebase:
      - `package.json` — dependencies, scripts, project metadata
      - Directory structure (`src/`, `app/`, `lib/`, etc.) — modules and organization
      - `prisma/schema.prisma` or ORM configs — data models
      - API route files — endpoints
      - Config files — tech stack, conventions
      - Test files — testing patterns
   c. Fill in each section with specific, accurate content derived from the codebase.
   d. Remove the HTML comment placeholders (<!-- ... -->) and replace with real content.
3. Run `adit docs validate` to check the quality scores.
4. If any documents score below 60%, improve the content and re-validate.

## Rules

- Be specific: reference actual file paths, function names, dependencies, and patterns.
- Do NOT invent content — only document what actually exists in the codebase.
- Keep each section concise but informative (2-5 sentences minimum per section).
- Preserve the H2 heading structure exactly — do not rename or remove required sections.
- All analysis happens locally. No code leaves this machine.
