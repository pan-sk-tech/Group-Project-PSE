"""Public Taylor's Lakeside Campus wayfinding references. IDs stay stable if labels change."""

import re
import unicodedata

from listed_rooms import ROOM_ROWS, SOURCE_YEARS


CAMPUS = "https://university.taylors.edu.my"
FACILITIES = CAMPUS + "/en/student-life/campus-facilities.html"
ICT = CAMPUS + "/en/student-life/support-and-services/ict-support-and-services.html"
SECURITY = CAMPUS + "/en/student-life/support-and-services/safety-and-security.html"
DESIGN = CAMPUS + "/en/study/explore-all-programmes/design.html"
CENTRAL = CAMPUS + "/en/student-life/your-taylors-journey/graduation/reprint-of-academic-transcript-and-certificate.html"
LIBRARY = "https://college.taylors.edu.my/en/student-life/news/2022/taylors-library-10-facilities-all-taylorians-should-know.html"
LECTURE = (CAMPUS + "/content/dam/taylorsrevamp/university/student-life/events/2025/"
           "research-and-innovation-festival-2025/taylors-reseach-fair-schedule-v080925.pdf#page=1")
DINING = (CAMPUS + "/content/dam/taylorsrevamp/university/discover-us/sustainability/"
          "documents/2026/taylors-university-sustainability-disclosure-2025.pdf#page=24")


def venue(place_id, name, building, level, source, room=""):
    # Routing uses a building and floor, or an individual landmark for outdoors.
    zone = f"{building} · {level}" if level else place_id
    return {"id": place_id, "name": name, "building": building, "level": level,
            "room": room, "zone": zone, "source": source}


PLACES = [
    venue("university-placement-office", "University Placement Services Office", "Block A", "Level 1",
          CAMPUS + "/en/student-life/support-and-services/university-placement-service.html"),
    venue("corporate-communications", "Corporate Communications Department", "Block A", "Level 3",
          CAMPUS + "/en/get-in-touch/enquire-now.html"),
    venue("campus-central","Campus Central","Block A","Level 2",CENTRAL),
    venue("ict-service-desk","ICT Service Desk","Block A","Level 2",ICT),
    venue("mayamode","Mayamode","Block A","Level G",DESIGN),
    venue("dance-studio", "Dance Studio", "Block B", "Level G", FACILITIES),
    venue("security-control-room","Security Control Room","Block B","Level 1",SECURITY),
    venue("student-life-centre","Student Life Centre","Block B","Level 1",FACILITIES),
    venue("grand-hall","The Grand Hall","Block B","Level 2",FACILITIES),
    venue("experimental-theatre","Experimental Theatre","Block B","Level 2",FACILITIES),
    venue("wine-lab", "Wine Laboratory", "Block C", "Level G", FACILITIES),
    venue("trading-room", "Taylor’s Trading Room", "Block C", "Level 1", FACILITIES),
    venue("library-silent-study", "Library silent study area", "Block C", "Level 5", LIBRARY),
    venue("architecture-studio-c5", "Next-Gen Architecture Studio", "Block C", "Level 5", FACILITIES),
    venue("library-study-room","Library Study Room","Block C","Level 2",ICT),
    venue("library-counter","Library counter","Block C","Level 2",LIBRARY),
    venue("library-print-level-3","Library printers and plotters","Block C","Level 3",ICT),
    venue("library-print-level-4","Library printer","Block C","Level 4",ICT),
    venue("vx-learning-theatre","Taylor’s VX Learning Theatre","Block C","Level 6",FACILITIES),
    venue("computer-lab-8","Computer Lab 8","Block C","Level 7",ICT,"C7.09"),
    venue("cybersecurity-lab","Cybersecurity Lab","Block C","Level 7",FACILITIES),
    venue("huawei-lab","Huawei Lab","Block C","Level 7",FACILITIES),
    venue("coffee-essence","Coffee Essence","Block D","Level G",FACILITIES),
    venue("tea-essence","Tea Essence","Block D","Level G",FACILITIES),
    venue("robotic-hub","Robotic Hub","Block D","Level 1",FACILITIES),
    venue("printmaking-room","Printmaking Room","Block D","Level 2",DESIGN),
    venue("audio-recording-studio", "Audio Recording Studio", "Block D", "Level 3", FACILITIES),
    venue("x-space-d4", "X-Space classrooms (room unspecified)", "Block D", "Level 4", FACILITIES),
    venue("anatomy-lab", "Anatomy Lab", "Block D", "Level 6", FACILITIES),
    venue("x-space-d8", "X-Space classrooms (room unspecified)", "Block D", "Level 8", FACILITIES),
    venue("mac-lab","Mac Lab","Block D","Level 7",FACILITIES),
    venue("makerspace","Taylor’s Makerspace","Block E","Level G",FACILITIES,"EG.01"),
    venue("vortex-xr","Vortex Extended Reality Lab","Block E","Level G",FACILITIES),
    venue("photography-studio","Photography Studio","Block E","Level 1",DESIGN),
    venue("lecture-theatre-17","Lecture Theatre 17","Block E","Level 1",LECTURE),
    venue("gg-cafe","G&G Café","Block E","Level 1",DINING),
    venue("knowledge-transfer-office", "Knowledge Transfer and Commercialisation Office", "Block E", "Level 2",
          CAMPUS + "/en/research-and-enterprise/collaborate-with-us/knowledge-transfers-commercialisation.html"),
    venue("architecture-studio-e3", "Next-Gen Architecture Studio", "Block E", "Level 3", FACILITIES),
    venue("design-studio-e5", "Design Studio", "Block E", "Level 5", FACILITIES),
    venue("x-space-e6", "X-Space classrooms (room unspecified)", "Block E", "Level 6", FACILITIES),
    venue("x-space-e7", "X-Space classrooms (room unspecified)", "Block E", "Level 7", FACILITIES),
    venue("moot-court","Moot Court","Block E","Level 8",FACILITIES),
    venue("pg-commons","PG Commons","Syopz Mall","Level LG",FACILITIES),
    venue("xoxo-cafe","XOXO Café","Syopz Mall","Level G",DINING,"G2"),
    venue("salad-atelier","Salad Atelier","Syopz Mall","Level G",DINING,"G16"),
    venue("unigym","UniGym","Syopz Mall","Level 1",FACILITIES),
    venue("bizpod","BizPod","Syopz Mall","Level 1",FACILITIES),
    venue("main-roundabout","Main entrance e-hailing roundabout","Outdoor landmarks","",FACILITIES),
    venue("pedestrian-gate","Pedestrian gate","Outdoor landmarks","",FACILITIES),
]
# The catalogue is evidence-based. Unlisted doors can still be entered for one search or report.
for code, name, source in ROOM_ROWS:
    block, floor = code[0], code[1:].split(".", 1)[0]
    place = venue("room:" + code, name, f"Block {block}", f"Level {floor}", source, code)
    if source in SOURCE_YEARS:
        place["sourceYear"] = SOURCE_YEARS[source]
    PLACES.append(place)

# Existing reports from the original prototype recorded a generic label only.
# Do not invent a floor or room for an old user's report.
for old_label in ("Library", "Cafeteria", "Lecture hall", "Sports centre", "Student centre", "Bus stop"):
    PLACES.append(venue(old_label, old_label, "Earlier records", "", ""))

PLACE_BY_ID = {place["id"]: place for place in PLACES}
LOCATIONS = tuple(PLACE_BY_ID)


ROOM_DOOR = re.compile(
    r"([A-E])(?:\s*-\s*|\s*)(LG[1-9]?|G|B[1-9]|[0-9]{1,2})"
    r"(?:\s*[.\-]\s*|\s+)([0-9]{1,3})([A-Z]?)"
)
ROOM_ALIASES = {p["room"]:p["id"] for p in PLACES if ROOM_DOOR.fullmatch(p["room"])}


def lookup_place(value):
    """Resolve listed places, spelling variants and manually transcribed door signs."""
    if not isinstance(value, str) or len(value) > 90:
        return None
    if value in PLACE_BY_ID:
        return PLACE_BY_ID[value]
    text = unicodedata.normalize("NFKC", value).strip().upper()
    if text.startswith("ROOM:"):
        text = text[5:].strip()
    parts = ROOM_DOOR.fullmatch(text)
    if not parts:
        return None
    block, floor, door, suffix = parts.groups()
    if int(door) == 0:
        return None
    if floor.isdigit():
        floor = str(int(floor)) if int(floor) else "G"
    code = f"{block}{floor}.{int(door):02d}{suffix}"
    if code in ROOM_ALIASES:
        return PLACE_BY_ID[ROOM_ALIASES[code]]
    return venue("room:" + code, "Room " + code, "Block " + block, "Level " + floor, "", code)


def describe_place(place_id):
    place = lookup_place(place_id)
    if not place:
        return str(place_id)
    if place["building"] == "Earlier records":
        return place["name"]
    room = place["room"]
    if room and room in place["name"]:
        room = ""
    return " · ".join(part for part in (place["name"], place["building"], place["level"], room) if part)
