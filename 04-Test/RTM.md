# Requirements Traceability Matrix

| Requirement | Test cases | Evidence | Verification status |
|---|---|---|---|
| FR-01 | TC-F01 | Bag 11 receipt | Verified |
| FR-02 | TC-F02, TC-F08 | Claimed state and exclusion from later search | Verified |
| FR-03 | TC-F03 | Two-stop route search | Verified |
| FR-04 | TC-F05, TC-F06, TC-F07 | Overlap, invalid-order and future-time validation | Verified |
| FR-05 | TC-F03, TC-F04 | Four ranked matches with explanations and collection points | Verified |
| FR-06 | TC-F09 | Public notice board without login | Verified |
| FR-07 | TC-F10 | Electronics notice 2 | Verified |
| FR-08 | TC-F11, TC-F12 | Edited and resolved owner-managed notice | Verified |
| FR-09 | TC-F13, TC-F16 | 30-minute expiry and early closure | Verified |
| FR-10 | TC-F14, TC-F15, TC-F17 | Same-floor feed, reception controls and refresh observation | Verified |
| NFR-01 | TC-N01 | Mobile navigation and validation feedback | Verified |
| NFR-02 | TC-N02, TC-N03 | 56 ms HTTP request and approximately 3.52-second feed observation; complete render latency not instrumented | Partially verified |
| NFR-03 | TC-N04, TC-N05, TC-N06 | SQLite storage, idempotent retry and fresh-process retrieval | Verified |
| NFR-04 | TC-N07 | 390 × 844 mobile test; documented desktop test not executed | Partially verified |

Twelve requirements are fully verified and two requirements are partially verified.

