# Requirements Specification

## Stakeholders and users

| Role | Category | Interaction |
| --- | --- | --- |
| Finder | Primary end-user | Records an item, its exact location and collection point, then confirms handover. |
| Item Owner | Primary end-user | Searches a timed route, manages notices and creates urgent requests. |
| Volunteer Helper | Primary end-user | Selects a campus location and opts in to nearby urgent requests. |
| Visitor | Public viewer | Browses public Open lost notices without signing in. |

Roles describe tasks rather than registered account types. Browser-held management credentials allow the originating browser to manage its own records.

## Functional requirements

| ID | Module | Requirement | Priority |
| --- | --- | --- | --- |
| FR-01 | Found Item and Handover | Allow a finder to report category, optional colour, campus location, discovery time and collection point. | High |
| FR-02 | Found Item and Handover | Allow the originating browser to confirm handover, mark the report Claimed and exclude it from later searches. | High |
| FR-03 | Route-Based Smart Search | Allow an owner to search by category, optional colour and one or more timed campus visits. | High |
| FR-04 | Route-Based Smart Search | Reject invalid ranges, future timestamps and overlapping visit intervals. | Medium |
| FR-05 | Route-Based Smart Search | Match exact resolved places, including aliases; rank by colour, timing, time after departure and report ID; show reasons and collection points. | High |
| FR-06 | Lost Notice Board | Allow visitors to browse public Open notices without signing in. | Medium |
| FR-07 | Lost Notice Board | Allow an owner to publish item details, description, last-seen place and time. | High |
| FR-08 | Lost Notice Board | Allow the originating browser to edit an Open notice or resolve it, removing it from the public board while retaining it under My notices. | Medium |
| FR-09 | Urgent Search and Alerts | Allow an owner to post a room or landmark request active for 30 minutes and close it early from the originating tab. | High |
| FR-10 | Urgent Search and Alerts | Allow volunteers to select a location, toggle reception and retrieve active same-area requests at approximately three-second intervals. | High |

## Non-functional requirements

| ID | Attribute | Requirement |
| --- | --- | --- |
| NFR-01 | Usability | Provide clear navigation, structured campus-place selection, marked required fields and understandable validation feedback. |
| NFR-02 | Performance and latency | Display valid search results within two seconds and check for active nearby alerts approximately every three seconds. |
| NFR-03 | Persistence and reliability | Persist reports, notices, urgent requests and submission receipts in SQLite; survive restart and prevent duplicate records for a repeated valid submission key. |
| NFR-04 | Responsive compatibility | Adapt to desktop and mobile viewports without unexpected horizontal scrolling while keeping content readable and controls usable. |

## Scope constraints

- The deliverable is a web prototype for Taylor’s University Lakeside Campus.
- No registration, campus sign-in or GPS is included.
- The same service address and database are required for participants to share records.
- Browser storage controls management of found reports and notices; session storage controls urgent-request closure.
- Urgent requests expire after 30 minutes unless closed earlier.

## Verification note

The detailed testing evidence is maintained in [04-Test](../04-Test/README.md). NFR-02 and NFR-04 are reported conservatively: the available evidence measures HTTP request duration and a 390 × 844 mobile viewport, but does not fully establish click-to-render timing, exact network polling cadence or desktop viewport coverage.

