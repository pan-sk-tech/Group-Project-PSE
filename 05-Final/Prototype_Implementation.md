# Prototype Implementation and Demonstration

## Environment

| Component | Implementation |
| --- | --- |
| Browser interface | HTML, CSS and JavaScript forms, lists and responsive layout |
| Service | Python HTTP server for validation, APIs and matching |
| Storage | SQLite for reports, notices, requests and receipts |
| Windows launch | `Start.cmd` runs the bundled 64-bit Python runtime |

To run on Windows, open [Prototype](Prototype/), double-click `Start.cmd`, keep the terminal open and use the browser URL displayed by the launcher. Detailed instructions are in [Prototype/README.md](Prototype/README.md).

## Environment evidence

![Browser files loaded successfully](Evidence/Browser-Network-Load.png)

![Responsive view at 390 × 844](Evidence/Mobile-390x844.png)

![SQLite persistence evidence](Evidence/SQLite-Persistence.png)

![Windows start script](Evidence/Windows-Start-Script.png)

## Implemented modules

| Module | Requirements | Behaviour |
| --- | --- | --- |
| Report a find | FR-01–02 | Create an Available report, record a pickup point and later mark it Claimed. |
| Find an item | FR-03–05 | Search timed visits and show ranked results, explanations and pickup locations. |
| Lost notices | FR-06–08 | Publish an Open notice, then edit or resolve it from the originating browser. |
| Urgent search | FR-09–10 | Send a 30-minute request and show relevant requests to opted-in nearby volunteers. |

## Matching implementation evidence

![Available-report selection](Evidence/Available-Items-Code.jpg)

![Exact-place and visit matching](Evidence/Matching-Code.jpg)

![Ranking rules](Evidence/Ranking-Code.jpg)

## End-to-end demonstrations

### Report, search and handover

![Found-item receipt](Evidence/Found-Item-Receipt.jpg)
![Route-search result](Evidence/Route-Search-Result.jpg)
![Claimed record](Evidence/Found-Item-Claimed.jpg)

![Search before handover](Evidence/Search-Before-Handover.gif)
![Search after handover](Evidence/Search-After-Handover.gif)

### Lost-notice resolution

![Open lost notice](Evidence/Open-Lost-Notice.jpg)
![Resolved lost notice](Evidence/Resolved-Lost-Notice.jpg)
![Public board after resolution](Evidence/Public-Board-After-Resolution.gif)

### Nearby-volunteer request

![Owner urgent request](Evidence/Owner-Urgent-Request.jpg)
![Volunteer nearby request](Evidence/Volunteer-Nearby-Request.jpg)
![Volunteer reception status](Evidence/Volunteer-Receiving-Status.jpg)

For the controlled test execution, expected/actual results and requirement coverage, see [04-Test](../04-Test/README.md).

