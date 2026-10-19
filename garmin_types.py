"""
garmin_types.py — справочник Garmin-типов из GarminTypes.cpp (GPSMapEdit).

Используется опционально:
  • валидация кодов типов при сохранении
  • имена типов в отчётах
  • авто-[DICTIONARY] по категориям
  • предупреждения о несоответствии типа и геометрии
"""

# ================================================================
# Типы: код → (имя, категория)
# ================================================================

POINT_TYPES = {
    0x0100: ("Large city (over 10M)",  "cities"),
    0x0200: ("Large city (5-10M)",     "cities"),
    0x0300: ("Large city (2-5M)",      "cities"),
    0x0400: ("Large city (1-2M)",      "cities"),
    0x0500: ("Medium city (0.5-1M)",   "cities"),
    0x0600: ("Medium city (200-500K)", "cities"),
    0x0700: ("Medium city (100-200K)", "cities"),
    0x0800: ("Small city (50-100K)",   "cities"),
    0x0900: ("Small city (20-50K)",    "cities"),
    0x0A00: ("Small city/town (10-20K)","cities"),
    0x0B00: ("Small city/town (5-10K)","cities"),
    0x0C00: ("Settlement (2-5K)",      "cities"),
    0x0D00: ("Settlement (1-2K)",      "cities"),
    0x0E00: ("Settlement (500-1K)",    "cities"),
    0x0F00: ("Settlement (200-500)",   "cities"),
    0x1000: ("Settlement (100-200)",   "cities"),
    0x1100: ("Settlement (less 100)",  "cities"),
    0x1200: ("Marina with facilities", "marine"),
    0x1300: ("Marine unknown",         "marine"),
    0x1400: ("Major country name",     "labels"),
    0x1500: ("Minor country name",     "labels"),
    0x1E00: ("State/province/region name", "labels"),
    0x1F00: ("County/parish name",     "labels"),
    0x2800: ("Label",                  "labels"),
    0x1C00: ("Obstruction",            "marine_danger"),
    0x1C01: ("Wreck",                  "marine_danger"),
    0x1C02: ("Submerged wreck, dangerous", "marine_danger"),
    0x1C03: ("Submerged wreck, non-dangerous", "marine_danger"),
    0x1C04: ("Wreck, cleared by wire-drag", "marine_danger"),
    0x1C05: ("Obstr., visible at high water", "marine_danger"),
    0x1C06: ("Obstruction, awash",     "marine_danger"),
    0x1C07: ("Obstruction, submerged","marine_danger"),
    0x1C08: ("Obstr., cleared by wire-drag", "marine_danger"),
    0x1C09: ("Rock, awash",            "marine_danger"),
    0x1C0A: ("Rock, submerged at low water", "marine_danger"),
    0x1C0B: ("Possible grounding risk","marine_danger"),
    0x1D00: ("Tide prediction",        "marine"),
    0x2000: ("HW Exit",                "auto"),
    0x2100: ("HW Exit with facilities","auto"),
    0x210F: ("HW Exit (service)",      "auto"),
    0x2200: ("HW Exit (restroom)",     "auto"),
    0x2300: ("HW Exit (convenience store)", "auto"),
    0x2400: ("HW Exit (weight station)", "auto"),
    0x2500: ("HW Exit (toll booth)",   "auto"),
    0x2600: ("HW Exit (information)",  "auto"),
    0x2700: ("HW Exit",                "auto"),
    0x2900: ("Uncategorized business", "services"),
    0x2A00: ("Dining",                 "food"),
    0x2A01: ("Dining (American)",      "food"),
    0x2A02: ("Dining (Asian)",         "food"),
    0x2A03: ("Dining (barbecue)",      "food"),
    0x2A04: ("Dining (Chinese)",       "food"),
    0x2A05: ("Dining (Deli/Bakery)",   "food"),
    0x2A06: ("Dining (international)", "food"),
    0x2A07: ("Fast food",              "food"),
    0x2A08: ("Dining (Italian)",       "food"),
    0x2A09: ("Dining (Mexican)",       "food"),
    0x2A0A: ("Dining (pizza)",         "food"),
    0x2A0B: ("Dining (sea food)",      "food"),
    0x2A0C: ("Dining (steak/grill)",   "food"),
    0x2A0D: ("Dining (bagel/donut)",   "food"),
    0x2A0E: ("Dining (cafe/diner)",    "food"),
    0x2A0F: ("Dining (French)",        "food"),
    0x2A10: ("Dining (German)",        "food"),
    0x2A11: ("Dining (British Isles)", "food"),
    0x2A12: ("Special food products",  "food"),
    0x2B00: ("Lodging",                "lodging"),
    0x2B01: ("Hotel/Motel",            "lodging"),
    0x2B02: ("Bed&Breakfast inn",      "lodging"),
    0x2B03: ("Camping/RV-Park",        "lodging"),
    0x2B04: ("Resort",                 "lodging"),
    0x2C00: ("Attraction",             "attractions"),
    0x2C01: ("Amusement/Theme park",   "attractions"),
    0x2C02: ("Museum/History",         "attractions"),
    0x2C03: ("Library",                "attractions"),
    0x2C04: ("Landmark",               "attractions"),
    0x2C05: ("School",                 "education"),
    0x2C06: ("Park/Garden",            "attractions"),
    0x2C07: ("Zoo/Aquarium",           "attractions"),
    0x2C08: ("Arena/Track",            "attractions"),
    0x2C09: ("Hall/Auditorium",        "attractions"),
    0x2C0A: ("Winery",                 "attractions"),
    0x2C0B: ("Place of worship",       "religion"),
    0x2D00: ("Entertainment",          "entertainment"),
    0x2D01: ("Live theatre",           "entertainment"),
    0x2D02: ("Bar/Nightclub",          "entertainment"),
    0x2D03: ("Cinema",                 "entertainment"),
    0x2D04: ("Casino",                 "entertainment"),
    0x2D05: ("Golf course",            "sports"),
    0x2D06: ("Skiing center/resort",   "sports"),
    0x2D07: ("Bowling center",         "sports"),
    0x2D08: ("Ice skating",            "sports"),
    0x2D09: ("Swimming pool",          "sports"),
    0x2D0A: ("Sports/Fitness Center",  "sports"),
    0x2D0B: ("Public sports airport",  "sports"),
    0x2E00: ("Shopping",               "shopping"),
    0x2E01: ("Department store",       "shopping"),
    0x2E02: ("Grocery store",          "shopping"),
    0x2E03: ("General merchandiser",   "shopping"),
    0x2E04: ("Shopping center",        "shopping"),
    0x2E05: ("Pharmacy",               "shopping"),
    0x2E06: ("Convenience store",      "shopping"),
    0x2E07: ("Apparel",                "shopping"),
    0x2E08: ("House and garden",       "shopping"),
    0x2E09: ("Home furnishing",        "shopping"),
    0x2E0A: ("Speciality retail",      "shopping"),
    0x2E0B: ("Computer/Software",      "shopping"),
    0x2F00: ("Generic services",       "services"),
    0x2F01: ("Auto fuel",              "auto"),
    0x2F02: ("Auto rental",            "auto"),
    0x2F03: ("Auto repair",            "auto"),
    0x2F04: ("Air transportation",     "transport"),
    0x2F05: ("Post office",            "services"),
    0x2F06: ("Bank/ATM",               "services"),
    0x2F07: ("Dealer/Auto parts",      "auto"),
    0x2F08: ("Ground transportation",  "transport"),
    0x2F09: ("Marina/Boat repair",     "marine"),
    0x2F0A: ("Wrecker service",        "services"),
    0x2F0B: ("Parking",                "auto"),
    0x2F0C: ("Rest area/Tourist info", "services"),
    0x2F0D: ("Automobile club",        "auto"),
    0x2F0E: ("Car wash",               "auto"),
    0x2F0F: ("Garmin dealer",          "shopping"),
    0x2F10: ("Personal services",      "services"),
    0x2F11: ("Business service",       "services"),
    0x2F12: ("Communication service",  "services"),
    0x2F13: ("Repair service",         "services"),
    0x2F14: ("Social service",         "services"),
    0x2F15: ("Public utilities",       "services"),
    0x2F16: ("Truck stop",             "auto"),
    0x2F17: ("Transit service",        "transport"),
    0x3000: ("Emergency/Governmental", "emergency"),
    0x3001: ("Police station",         "emergency"),
    0x3002: ("Hospital",               "emergency"),
    0x3003: ("City hall",              "emergency"),
    0x3004: ("Court house",            "emergency"),
    0x3005: ("Community center",       "emergency"),
    0x3006: ("Border crossing",        "emergency"),
    0x3007: ("Government office",      "emergency"),
    0x3008: ("Fire department",        "emergency"),
    0x4000: ("Golf",                   "sports"),
    0x4100: ("Fishing spot",           "recreation"),
    0x4200: ("Wreck",                  "auto"),
    0x4300: ("Marina",                 "marine"),
    0x4400: ("Gas station",            "auto"),
    0x4500: ("Restaurant",             "food"),
    0x4600: ("Bar",                    "food"),
    0x4700: ("Boat ramp",              "marine"),
    0x4800: ("Camping",                "recreation"),
    0x4900: ("Park",                   "recreation"),
    0x4A00: ("Picnic area",            "recreation"),
    0x4B00: ("First aid station",      "emergency"),
    0x4C00: ("Information",            "recreation"),
    0x4D00: ("Parking",                "auto"),
    0x4E00: ("Restroom",               "recreation"),
    0x4F00: ("Shower",                 "recreation"),
    0x5000: ("Drinking water",         "recreation"),
    0x5100: ("Telephone",              "services"),
    0x5200: ("Scenic area",            "recreation"),
    0x5300: ("Skiing",                 "sports"),
    0x5400: ("Swimming area",          "recreation"),
    0x5500: ("Dam",                    "man_made"),
    0x5600: ("Controlled area",        "others"),
    0x5700: ("Danger area",            "others"),
    0x5800: ("Restricted area",        "others"),
    0x5900: ("Generic airport",        "aviation"),
    0x5901: ("Large airport",          "aviation"),
    0x5902: ("Medium airport",         "aviation"),
    0x5903: ("Small airport",          "aviation"),
    0x5904: ("Heliport",               "aviation"),
    0x5905: ("Airport",                "aviation"),
    0x5A00: ("Mile marker",            "others"),
    0x5B00: ("Bell",                   "others"),
    0x5C00: ("Diving area",            "others"),
    0x5D00: ("Daymark, green square",  "others"),
    0x5E00: ("Daymark, red triangle",  "others"),
    0x6000: ("Horn",                   "others"),
    0x6100: ("House",                  "others"),
    0x6200: ("Depth spot",             "elevation"),
    0x6300: ("Elevation spot",         "elevation"),
    0x6400: ("Man-made place",         "man_made"),
    0x6401: ("Bridge",                 "man_made"),
    0x6402: ("Building",               "man_made"),
    0x6403: ("Cemetery",               "man_made"),
    0x6404: ("Church/mosque/etc",      "religion"),
    0x6405: ("Civil bulding",          "man_made"),
    0x6406: ("Crossing",               "man_made"),
    0x6407: ("Dam",                    "man_made"),
    0x6408: ("Hospital",               "man_made"),
    0x6409: ("Levee",                  "man_made"),
    0x640A: ("Locale",                 "man_made"),
    0x640B: ("Military",               "man_made"),
    0x640C: ("Mine",                   "man_made"),
    0x640D: ("Oil field",              "man_made"),
    0x640E: ("Park",                   "man_made"),
    0x640F: ("Post office",            "services"),
    0x6410: ("School",                 "education"),
    0x6411: ("Tower",                  "man_made"),
    0x6412: ("Trailhead",              "man_made"),
    0x6413: ("Tunnel",                 "man_made"),
    0x6414: ("Well",                   "man_made"),
    0x6415: ("Historical (ghost) town","man_made"),
    0x6416: ("Subdivision of housing", "man_made"),
    0x6500: ("Water feature",          "water"),
    0x6501: ("Arroyo",                 "water"),
    0x6502: ("Sand bar",               "water"),
    0x6503: ("Bay",                    "water"),
    0x6504: ("Bend",                   "water"),
    0x6505: ("Canal",                  "water"),
    0x6506: ("Channel",                "water"),
    0x6507: ("Cove",                   "water"),
    0x6508: ("Falls",                  "water"),
    0x6509: ("Geyser",                 "water"),
    0x650A: ("Glacier",                "water"),
    0x650B: ("Harbor",                 "water"),
    0x650C: ("Island",                 "water"),
    0x650D: ("Lake",                   "water"),
    0x650E: ("Rapids",                 "water"),
    0x650F: ("Reservoir",              "water"),
    0x6510: ("Sea",                    "water"),
    0x6511: ("Spring",                 "water"),
    0x6512: ("Stream",                 "water"),
    0x6513: ("Swamp",                  "water"),
    0x6600: ("Land feature",           "land"),
    0x6601: ("Arch",                   "land"),
    0x6602: ("Area",                   "land"),
    0x6603: ("Basin",                  "land"),
    0x6604: ("Beach",                  "land"),
    0x6605: ("Bench",                  "land"),
    0x6606: ("Cape",                   "land"),
    0x6607: ("Cliff",                  "land"),
    0x6608: ("Crater",                 "land"),
    0x6609: ("Flat",                   "land"),
    0x660A: ("Forest",                 "land"),
    0x660B: ("Gap",                    "land"),
    0x660C: ("Gut",                    "land"),
    0x660D: ("Isthmus",                "land"),
    0x660E: ("Lava",                   "land"),
    0x660F: ("Pillar",                 "land"),
    0x6610: ("Plain",                  "land"),
    0x6611: ("Range",                  "land"),
    0x6612: ("Reserve",                "land"),
    0x6613: ("Ridge",                  "land"),
    0x6614: ("Rock",                   "land"),
    0x6615: ("Slope",                  "land"),
    0x6616: ("Summit",                 "land"),
    0x6617: ("Valley",                 "land"),
    0x6618: ("Wooded area",            "land"),
}

POLYLINE_TYPES = {
    0x00: ("Road",                       "roads"),
    0x01: ("Major highway",              "roads"),
    0x02: ("Principal highway",          "roads"),
    0x03: ("Other highway road",         "roads"),
    0x04: ("Arterial road",              "roads"),
    0x05: ("Collector road",             "roads"),
    0x06: ("Residential street",         "roads"),
    0x07: ("Alleyway/private driveway",  "roads"),
    0x08: ("Highway ramp, low-speed",    "roads"),
    0x09: ("Highway ramp, high-speed",   "roads"),
    0x0A: ("Unpaved road",               "roads"),
    0x0B: ("Major highway connector",    "roads"),
    0x0C: ("Roundabout",                 "roads"),
    0x14: ("Railroad",                   "roads"),
    0x15: ("Shoreline of water body",    "water"),
    0x16: ("Walkway/trail",              "roads"),
    0x18: ("Stream",                     "water"),
    0x19: ("Time-zone",                  "boundaries"),
    0x1A: ("Water or rail ferry",        "roads"),
    0x1B: ("Water or rail ferry",        "roads"),
    0x1C: ("State/province boundary",    "boundaries"),
    0x1D: ("County/parish boundary",     "boundaries"),
    0x1E: ("International boundary",     "boundaries"),
    0x1F: ("River",                      "water"),
    0x20: ("Minor land contour (1/10)",  "elevation"),
    0x21: ("Interm. land contour (1/2)", "elevation"),
    0x22: ("Major land contour (1/1)",   "elevation"),
    0x23: ("Minor depth contour (1/10)", "elevation"),
    0x24: ("Interm. depth contour (1/2)","elevation"),
    0x25: ("Major depth contour (1/1)",  "elevation"),
    0x26: ("Intermittent stream/ditch",  "water"),
    0x27: ("Airport runway centerline",  "man_made"),
    0x28: ("Oil or water pipeline",      "man_made"),
    0x29: ("Power line",                 "man_made"),
    0x2A: ("Marine boundary (no line)",  "water"),
    0x2B: ("Marine hazard (no line)",    "water"),
}

POLYGON_TYPES = {
    0x01: ("Large urban area (>200K)",   "cities"),
    0x02: ("Small urban area (<200K)",   "cities"),
    0x03: ("Rural housing area",         "cities"),
    0x04: ("Military base",              "man_made"),
    0x05: ("Parking lot",                "man_made"),
    0x06: ("Parking garage",             "building"),
    0x07: ("Airport",                    "man_made"),
    0x08: ("Shopping center",            "man_made"),
    0x09: ("Marina",                     "man_made"),
    0x0A: ("University/College",         "man_made"),
    0x0B: ("Hospital",                   "man_made"),
    0x0C: ("Industrial complex",         "man_made"),
    0x0D: ("Reservation",                "man_made"),
    0x0E: ("Airport runway",             "man_made"),
    0x13: ("Building/Man-made area",     "building"),
    0x14: ("National park",              "land"),
    0x15: ("National park",              "land"),
    0x16: ("National park",              "land"),
    0x17: ("City park",                  "man_made"),
    0x18: ("Golf course",                "sports"),
    0x19: ("Sports complex",             "sports"),
    0x1A: ("Cemetery",                   "man_made"),
    0x1E: ("State park",                 "land"),
    0x1F: ("State park",                 "land"),
    0x20: ("State park",                 "land"),
    0x28: ("Sea/Ocean",                  "water"),
    0x29: ("Blue-Unknown",               "water"),
    0x32: ("Sea",                        "water"),
    0x3B: ("Blue-Unknown",               "water"),
    0x3C: ("Large lake (250-600 km2)",   "water"),
    0x3D: ("Large lake (77-250 km2)",    "water"),
    0x3E: ("Medium lake (25-77 km2)",    "water"),
    0x3F: ("Medium lake (11-25 km2)",    "water"),
    0x40: ("Small lake (0.25-11 km2)",   "water"),
    0x41: ("Small lake (<0.25 km2)",     "water"),
    0x42: ("Major lake (>3.3 tkm2)",     "water"),
    0x43: ("Major lake (1.1-3.3 tkm2)",  "water"),
    0x44: ("Large lake (0.6-1.1 tkm2)",  "water"),
    0x45: ("Blue-Unknown",               "water"),
    0x46: ("Major river (>1 km)",        "water"),
    0x47: ("Large river (200 m-1 km)",   "water"),
    0x48: ("Medium river (40-200 m)",    "water"),
    0x49: ("Small river (<40 m)",        "water"),
    0x4A: ("Map selection area",         "others"),
    0x4B: ("Map coverage area",          "others"),
    0x4C: ("Intermittent water",         "water"),
    0x4D: ("Glacier",                    "land"),
    0x4E: ("Orchard/plantation",         "man_made"),
    0x4F: ("Scrub",                      "land"),
    0x50: ("Forest",                     "land"),
    0x51: ("Wetland/swamp",              "water"),
    0x52: ("Tundra",                     "land"),
    0x53: ("Sand/tidal/mud flat",        "water"),
}

# ================================================================
# API
# ================================================================

_KIND_TABLE = {
    "point":   POINT_TYPES,
    "line":    POLYLINE_TYPES,
    "polygon": POLYGON_TYPES,
}


def _norm_kind(kind):
    k = kind.lower()
    if k in ("poi", "points", "pts"):  return "point"
    if k in ("polyline", "lines", "lns"): return "line"
    if k in ("polygon", "polygons", "pgns"): return "polygon"
    return k


def type_name(code, kind):
    tbl = _KIND_TABLE.get(_norm_kind(kind), {})
    code = int(code)
    k = _norm_kind(kind)
    if k == "point":
        code &= 0xFFFF00
    if code in tbl:
        return tbl[code][0]
    if k == "point":
        for c, (n, _cat) in tbl.items():
            if c <= code < (c + 0x100):
                return n
    return f"Unknown (0x{code:02X})"


def type_category(code, kind):
    tbl = _KIND_TABLE.get(_norm_kind(kind), {})
    code = int(code)
    k = _norm_kind(kind)
    if k == "point":
        code &= 0xFFFF00
    if code in tbl:
        return tbl[code][1]
    if k == "point":
        for c, (_n, cat) in tbl.items():
            if c <= code < (c + 0x100):
                return cat
    return None


def known_type(code, kind):
    tbl = _KIND_TABLE.get(_norm_kind(kind), {})
    code = int(code)
    k = _norm_kind(kind)
    if k == "point":
        code &= 0xFFFF00
    if code in tbl:
        return True
    if k == "point":
        for c in tbl:
            if c <= code < (c + 0x100):
                return True
    return False


def types_by_category(category, kind):
    tbl = _KIND_TABLE.get(_norm_kind(kind), {})
    return [c for c, (_n, cat) in tbl.items() if cat == category]


# -------- предикаты (по GarminTypes.cpp) --------

def is_city_point(code):
    c = int(code) & 0xFFFF00
    return 0x0100 <= c <= 0x1100

def is_hw_exit_point(code):
    c = int(code) & 0xFFFF00
    return 0x2000 <= c <= 0x2700

def is_height_point(code):
    c = int(code) & 0xFFFF00
    return c in (0x6200, 0x6300)

def is_feature_point(code):
    c = int(code) & 0xFFFF00
    return 0x6400 <= c <= 0x6600

def has_address_point(code):
    c = int(code) & 0xFFFF00
    return (0x2900 <= c <= 0x3000) or c == 0x1200

def is_road_line(code):
    c = int(code)
    return (0x00 <= c <= 0x13) or c in (0x16, 0x1A, 0x1B)

def is_water_line(code):
    return int(code) in (0x15, 0x18, 0x1F, 0x26)

def is_boundary_line(code):
    return int(code) in (0x1C, 0x1D, 0x1E)

def is_contour_line(code):
    return 0x20 <= int(code) <= 0x25

def is_background_polygon(code):
    return int(code) == 0x4B

def is_water_polygon(code):
    return int(code) in (
        0x28, 0x29, 0x32, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
        0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
        0x48, 0x49, 0x4C, 0x51, 0x53,
    )

def is_land_polygon(code):
    return int(code) in (
        0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A,
        0x1E, 0x1F, 0x20, 0x4D, 0x4E, 0x4F, 0x50, 0x52,
    )


# ================================================================
# Категории → уровни (для авто-[DICTIONARY])
# ================================================================

CATEGORY_LEVELS_DEFAULT = {
    "roads":         [0, 1, 2, 3, 4],
    "water":         [0, 1, 2, 3, 4, 5],
    "boundaries":    [0, 1, 2, 3, 4],
    "elevation":     [0, 1, 2, 3],
    "land":          [0, 1, 2, 3, 4],
    "man_made":      [0, 1, 2, 3],
    "building":      [0, 1, 2, 3],
    "cities":        [0, 1, 2, 3, 4, 5],
    "labels":        [0, 1, 2, 3, 4, 5],
    "sports":        [0, 1, 2, 3],
    "auto":          [0, 1, 2, 3],
    "emergency":     [0, 1, 2, 3],
    "recreation":    [0, 1, 2, 3],
    "services":      [0, 1, 2, 3],
    "shopping":      [0, 1, 2, 3],
    "food":          [0, 1, 2, 3],
    "lodging":       [0, 1, 2, 3],
    "attractions":   [0, 1, 2, 3],
    "entertainment": [0, 1, 2, 3],
    "education":     [0, 1, 2, 3],
    "religion":      [0, 1, 2, 3],
    "transport":     [0, 1, 2, 3],
    "aviation":      [0, 1, 2, 3],
    "marine":        [0, 1, 2, 3, 4, 5],
    "marine_danger": [0, 1, 2, 3, 4, 5],
    "others":        [0, 1, 2, 3],
}