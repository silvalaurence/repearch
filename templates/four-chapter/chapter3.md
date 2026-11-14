# CHAPTER III
# DESIGN AND METHODOLOGY

[STUDENT: this is your longest chapter. The parts marked "from the scan" are already written for you in `output/auto_sections.md` - paste them in and check them against your real system. Everything else needs your input.]

## 3.1 Research Design

{{name the design your adviser approved, e.g. descriptive-developmental, and one line on why it fits}}

## 3.2 Method

{{the method used to gather what you needed to build and evaluate the system}}

## 3.3 Flow of the Study

[STUDENT: draw the study as a flowchart: proposal, requirements, design, build, test, evaluation, revision. Mermaid code is fine here.]

## 3.4 Research Environment

{{where the study was conducted - the actual office, school or site - and the dates}}

## 3.5 Respondents

[STUDENT: real people only. Never report respondents who did not answer.]

| Group | Who they are | How many | How you reached them |
|-------|--------------|----------|----------------------|
| {{end users}} | {{role found in the code or intake}} | [STUDENT] | |
| {{IT experts / evaluators}} | {{...}} | [STUDENT] | |

## 3.6 Research Instrument

{{the questionnaire or interview guide you used. Attach the blank copy in the appendices.}}

## 3.7 Research Procedure

[STUDENT: list the real steps in order, with the dates each one happened.]

## 3.8 Data Gathering

{{how responses were collected, in what form, and over what period}}

## 3.9 Treatment of Data

The statistics used to read the results:

| Tool | Used for | Where it comes from |
|------|----------|---------------------|
| Weighted mean | {{which survey results}} | `Survey_Results.xlsx` computes it |
| Likert scale 1-5 | {{rating each item}} | see `survey_iso25010.md` |
| Verbal interpretation | {{the labels beside each mean}} | see the Scale sheet in `Survey_Results.xlsx` |

[STUDENT: confirm your college's interpretation ranges. The default here is 4.21-5.00 Strongly Agree, 3.41-4.20 Agree, 2.61-3.40 Neutral, 1.81-2.60 Disagree, 1.00-1.80 Strongly Disagree.]

## 3.10 Ethical Considerations

[STUDENT: write what you actually did, not what sounds good.]

- Consent: {{informed consent form used, and when respondents signed}}
- Data privacy: {{how personal data in the system is stored, who can see it, whether it is deleted}}
- Only claim protections your code really implements. Check `output/auto_sections.md` for what the scan found - if it did not find password hashing or access control, do not say the system has them.

# Software Engineering Methodology

## 3.11 Planning / Conception-Initiation Phase

**Business Model Canvas** - [STUDENT: fill your college's canvas template. Key partners, activities, resources, value proposition, customer segments, channels, costs, revenue.]

**Program Workflow** - {{the real process the system now handles, step by step}}

**Validation Board (Stages 1 to 3)** - [STUDENT: who validated each stage and on what date. Include the signatures your college requires.]

**Business Roadmap** - [STUDENT: the phases in real order with the dates you actually worked them.]

**Functional Decomposition Diagram** - [STUDENT: break the system into functions, then sub-functions. Start from the module list in `output/auto_sections.md`.]

**Gantt Chart** - [STUDENT: real schedule with real dates. A panel can tell an invented one.]

## 3.12 Analysis-Design Phase

**Use Case Diagrams** - from the scan: paste Mermaid built from the real roles and modules in `output/auto_sections.md`, then check every use case exists in your code.

[STUDENT: add any other applicable UML diagram only if you actually made it - sequence, class, or activity.]

**UI/UX Design** - {{what the screens do and the reasoning behind the layout. Put the screenshots themselves in Chapter 4.}}

**Database Design**

*Entity-Relationship Diagram* - from the scan: use the relations-only figure in `output/diagrams/er.mmd`; every column belongs in the data dictionary, and `output/diagrams/er_detail.mmd` keeps that full version in case a panelist asks for it. A schema with more tables than one page can hold is already split into `er_part1.mmd`, `er_part2.mmd` and so on along its foreign-key lines - caption those as separate figures instead of shrinking one. [STUDENT: verify each relationship against your real schema before you paste it.]

*Data Dictionary* - from the scan: use the data dictionary table in `output/auto_sections.md`, then write the meaning of every column yourself.

**Network Design**

*Network Model* - [STUDENT: how the pieces connect - client, server, database, and where each is hosted.]

*Network Topology* - [STUDENT: draw the real topology of your deployment. If everything runs on one machine, say that.]

## 3.13 Development / Construction / Build Phase

**Technology Stack Diagram** - from the scan: use the architecture diagram in `output/auto_sections.md`, which draws a tier only where the client demonstrably reaches it. If a server folder exists but nothing calls it, keep it out of the figure and say what it is. Caption the figure on the line above it (`**Figure 3.x ...**`) and keep the drawing page-shaped. [STUDENT: correct it if your layers differ from what the packages suggest.]

**Software Specification** - {{operating system, language versions, frameworks and their versions, database engine and version}}

**Hardware Specification** - [STUDENT: the machine the system runs on. These are not in your code - read them off the actual server or computer.]

| Item | Minimum | Used in this project |
|------|---------|----------------------|
| Processor | | {{...}} |
| Memory | | {{...}} |
| Storage | | {{...}} |
| Network | | {{...}} |

**Program Specification** - {{how the program is structured: main modules, what each one does, how they call each other}}

**List of Modules** - from the scan: paste the module and endpoint tables in `output/auto_sections.md`.

**Testing Plan** - the tests are drafted in Chapter 4; the Actual Result and Status columns stay empty until you really run each one.

| Testing stage | What it covers | Status |
|---------------|----------------|--------|
| Unit Testing | {{individual functions or components}} | [STUDENT: run and record] |
| Integration Testing | {{how modules work together}} | [STUDENT] |
| Alpha Testing | {{your own testing before showing it to users}} | [STUDENT] |
| Acceptance Testing | {{the users' sign-off that it does what they need}} | [STUDENT] |

[STUDENT: if the scan found automated test files, name them here and paste real output. If it found none, write that no automated tests exist.]

## 3.14 Implementation / Deployment Phase

**User Guide** - from the scan: draft it from the real screens and flows. Every step must match a screen that exists.

**Installation Guide** - from the README and manifest files found in the repo. [STUDENT: run the steps on a clean machine before you publish them.]
