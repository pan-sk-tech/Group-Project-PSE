# Campus Lost & Found

A web-based lost-and-found prototype for Taylor’s University Lakeside Campus. The system supports finder, item owner, volunteer helper and visitor tasks without requiring account registration.

## Core functions

1. Report found items and confirm handover.
2. Search timed campus routes and review ranked matches with explanations.
3. Publish, edit and resolve public lost notices.
4. Send 30-minute urgent requests to opted-in volunteers in the relevant area.

## Repository structure

```text
Group-Project-PSE/
├── 01-Planning/       Methodology, timeline, team roles, user stories and Trello evidence
├── 02-Requirements/   FR/NFR specification, use cases and UML diagram
├── 03-Design/         Architecture, matching, urgent workflow and UI/UX evidence
├── 04-Test/           24 test cases, results, regression record, screenshots and RTM
├── 05-Final/          Complete report, implementation evidence and runnable prototype
└── README.md          Project overview and navigation
```

## Quick links

- [Planning](01-Planning/README.md)
- [Requirements](02-Requirements/README.md)
- [Design](03-Design/README.md)
- [Testing](04-Test/README.md)
- [Final submission](05-Final/README.md)
- [Run the prototype](05-Final/Prototype/README.md)
- [Complete group report](05-Final/Group_Project_PSE.docx)

## Team

| Member | Student ID | Primary responsibility |
| --- | --- | --- |
| Peng Zihao | 0392878 | Group leadership, system design and diagrams |
| Fu Jiacheng | 0376148 | Topic, objectives and report compilation |
| Ayman Ahmed | 0388002 | Requirements and development process |
| Zhang Fengrui | 0376811 | Prototype development and demonstration |
| Bu Zihang | 0373619 | Testing and quality assurance |

## Technology and methodology

The team used Agile development with iterative prototyping. The prototype uses HTML, CSS and JavaScript in the browser, a Python HTTP service and SQLite persistence. Trello, GitHub, Figma, Draw.io and Visual Studio Code supported planning, version control, design and implementation.

## Test status

The repository includes 24 executed test cases and a complete requirements traceability matrix. Functional workflows and data persistence are evidenced. NFR-02 and NFR-04 remain conservatively reported where the current measurements cover HTTP request duration and a 390 × 844 mobile viewport rather than full click-to-render timing, exact network polling cadence and desktop viewport coverage.
