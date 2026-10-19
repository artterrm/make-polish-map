
```markdown
[Русский](README.ru.md)

# Polish Map Python Library

A Python library for generating maps in **Polish Format (.mp)** for compilation into Garmin `.img` files via `mkgmap` or `cgpsmapper`.

## Features

- Generate an empty map with customizable levels (`Level0`, `Zoom0`).
- Add points (`[POI]`), lines (`[POLYLINE]`), and polygons (`[POLYGON]` or `[POLYLINE]`).
- Support for polygons with holes (inner rings).
- Support for `EndLevel` mode and progressive simplification (`SimplifyLevel`).
- Automatic generation of the `[DICTIONARY]` section.
- Garmin snap-to-grid (round half away from zero).
- Built-in Garmin type reference (`garmin_types.py`).
- Import from Shapefile (`.shp`) and GeoPackage (`.gpkg`).
- Validation of common errors before compilation.

---

## Table of Contents

1. [Installation and Dependencies](#1-installation-and-dependencies)
2. [Quick Start](#2-quick-start)
3. [Map Creation: Constructor Parameters](#3-map-creation-constructor-parameters)
4. [Adding Objects](#4-adding-objects)
5. [Reading from Shapefile](#5-reading-from-shapefile)
6. [Address Sections](#6-address-sections)
7. [Section `[DICTIONARY]`](#7-section-dictionary)
8. [Special Label Codes](#8-special-label-codes)
9. [Validation](#9-validation)
10. [Reports](#10-reports)
11. [Saving and Compilation](#11-saving-and-compilation)
12. [Integration with `garmin_types.py`](#12-integration-with-garmin_typespy)
13. [CLI](#13-cli)
14. [Full List of Methods](#14-full-list-of-methods)
15. [Full List of Header Keys](#15-full-list-of-header-keys)
16. [Common Scenarios](#16-common-scenarios)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Installation and Dependencies

**Required:**
```bash
pip install shapely
```
*Shapely is used for geometry simplification (`simplify`) and `add_geometry`.*

**Optional:**
```bash
pip install pyshp        # for add_from_shapefile()
pip install geopandas    # for dissolve, reading shapefiles
```

**Project structure:**
```text
project/
├── polish_map.py        # main library
├── garmin_types.py      # optional type reference
├── mkgmap.jar           # for compilation
└── your_script.py
```
*If `garmin_types.py` is not found, the library still works, but `type_check=True` is ignored, and `summary_types()` returns an error message.*

---

## 2. Quick Start

### Empty Map
```python
from polish_map import PolishMap

m = PolishMap("my_map", levels=[24, 23, 22], zooms=[0, 1, 2])
m.save("my_map.mp")
```

### Map with Objects
```python
from polish_map import PolishMap

m = PolishMap("forest", levels=[24, 23, 22], zooms=[0, 1, 2])

# Line
m.add_line(
    coords=[(37.60, 55.70), (37.70, 55.80), (37.80, 55.85)],
    type_code=0x06,
    label="Forest road",
)

# Point
m.add_point(
    lon=37.65, lat=55.75,
    type_code=0x2A00,
    label="Cafe",
)

# Polygon (closed ring)
m.add_polygon(
    coords=[(37.60, 55.70), (37.65, 55.70), (37.65, 55.75), (37.60, 55.75), (37.60, 55.70)],
    type_code=0x50,  # Forest
    label="Forest",
)

m.save()
m.compile()  # invokes mkgmap
```
*Result: `forest.mp` and `forest.img`.*

---

## 3. Map Creation: Constructor Parameters

```python
PolishMap(
    name,
    *,
    map_id=None,
    levels=None,
    zooms=None,
    level_ranges=None,
    codepage=1251,
    snap_to_grid=False,
    polygon_section="POLYLINE",
    data_levels=None,
    simplify_tol=0.00005,
    simplify_from_level=None,
    precision=None,
    use_end_level=False,
    data_format="02d",
    crlf=True,
    auto_uppercase=None,
    header=None,
    type_check=False,
)
```

### `name` (required)
Map name. Used as `Name=` in the header, the `.mp` filename, and the GPS description.
*(If it contains spaces or special characters, it's better to use Latin for the filename, but the `Name=` in the header can be in any language).*

### `map_id`
Unique map ID (integer). If `None`, a random value between `30000000` and `99999999` is generated.
*Rules: Must be `> 0` and `< 0x0FFFFFFF` (268435455).*

### `levels`
List of "bits per coordinate" for each map level. Default is `[24, 23, 22, 21, 20, 19, 18]`.
**Rule:** Values must **descend**. The first level is the most detailed.

| Bits | Grid Step | Approx. |
| :--- | :--- | :--- |
| 24 | ~2.4 m | Zoom 0, detailed |
| 23 | ~4.8 m | Zoom 1 |
| 22 | ~9.5 m | Zoom 2 |
| 21 | ~19 m | Zoom 3 |
| 20 | ~38 m | Zoom 4 |
| 19 | ~76 m | Zoom 5 |
| 18 | ~152 m | Zoom 6, overview |

### `zooms`
List of `Zoom#=` values in the header. Defaults to `list(range(len(levels)))`.
**Rule:** Values must **ascend**.

### `level_ranges`
Optional. List of "btBitsRangeTo" for each level. Adds `LevelRange0=22`, etc.

### `codepage`
Code page. Default is `1251` (Cyrillic). Influences the `CodePage=` header, the `.mp` file encoding, and `auto_uppercase` (defaults to `True` for all except 1252).

### `snap_to_grid`
Snap coordinates to the Garmin grid. Default `False`.
- Rounds coordinates to the grid step `360 / 2^bits`.
- Prevents GPSMapEdit from shifting vertices when loading the `.mp`.
- Increases file size (precision becomes 7 decimal places).
**Use when:** You plan to edit the `.mp` in GPSMapEdit. If using only mkgmap, it can be left False (mkgmap snaps automatically).

### `polygon_section`
How to write polygons by default: `"POLYLINE"` or `"POLYGON"`. Default `"POLYLINE"`.
Can be overridden per object via `as_polygon=`.

### `data_levels`
Default levels for objects. Default is `[0, 1, 2, 3]`.

### `simplify_tol`
Geometry simplification tolerance. Default `0.00005` (degrees).
Supports **four forms**:
- `number`: one tol for all levels after `simplify_from_level`.
- `list`: tol by index in the object's `levels`.
- `"auto"`: tol = half the grid step for each level.
- `None`: no simplification.

### `simplify_from_level`
The level from which simplification starts. If `None`, defaults to `min(levels) + 1`.

### `precision`
Decimal places. If `None`: 7 if `snap_to_grid=True`, 6 if `max(bits) >= 25`, else 5.

### `use_end_level`
Polish074 mode: writes `Data0` + `EndLevel=N` instead of `Data0..DataN`. Default `False`.
**Benefits:** Much smaller `.mp` file (no duplicated coordinates); compiler automatically simplifies progressively.
**Use when:** Compatible with `SimplifyLevel`; you want to reduce `.mp` and `.img` sizes.

### `data_format`
Key format: `"02d"` -> `Data00, Level00, Zoom00` (GPSMapEdit style) or `"d"` -> `Data0, Level0, Zoom0`.

### `crlf`
Use `\r\n` instead of `\n`. Default `True` (for Windows/GPSMapEdit).

### `auto_uppercase`
Automatically convert labels to uppercase. Default `None` (enabled if `codepage != 1252`).
*Reason: Garmin displays lowercase only for cp1252. Cyrillic (cp1251) must be uppercase.*

### `header`
Dictionary overriding any `[IMG ID]` fields.
```python
header={
    "Preprocess": "P",
    "TreSize": 1000,
    "RgnLimit": 1024,
    "SimplifyLevel": 2,
    "CustomField": "value",
}
```

### `type_check`
Enables type validation via `garmin_types.py`. Default `False`.

---

## 4. Adding Objects

### `add_point(lon, lat, type_code, label=None, *, levels=None, extra=None)`
**Point (`[POI]`).**
```python
m.add_point(37.60, 55.70, 0x2A00, label="Cafe", extra={
    "HouseNumber": "5",
    "CityName": "Moscow",
    "RegionName": "Moscow region",
    "CountryName": "Russia",
    "Zip": "101000",
    "Phone": "+7-999-1234567",
    "Text": ["Open 9:00-21:00", "Wi-Fi available"],
})
```

### `add_line(coords, type_code, label=None, *, levels=None, tol=None, direction=False, extra=None, simplify_from_level=None)`
**Line (`[POLYLINE]`).**
```python
m.add_line(
    coords=[(37.60, 55.70), (37.70, 55.80)],
    type_code=0x06,
    label="Road",
    direction=True,
    levels=[0, 1, 2],
    tol=0.00005,
)
```
*(`direction=True` adds `DirIndicator=1` to the `.mp`)*

### `add_polygon(coords, type_code, label=None, *, holes=None, levels=None, tol=None, as_polygon=None, extra=None, simplify_from_level=None)`
**Closed ring.** Can be written as `[POLYLINE]` or `[POLYGON]`.
```python
# Simple polygon
m.add_polygon(coords, type_code=0x50, label="Forest")

# Polygon with holes
m.add_polygon(coords, type_code=0x50, holes=[hole1_coords, hole2_coords])

# Force [POLYGON] (fill)
m.add_polygon(coords, 0x50, as_polygon=True)

# Force [POLYLINE] (outline)
m.add_polygon(coords, 0x50, as_polygon=False)
```

### `add_geometry(geom, type_code, label=None, **kw)`
**Universal method** for shapely geometries.
```python
from shapely.geometry import Point, LineString, Polygon
m.add_geometry(Point(37.6, 55.7), 0x2A00)
m.add_geometry(LineString([(37.6, 55.7), (37.7, 55.8)]), 0x06)
m.add_geometry(Polygon([(37.6, 55.7), (37.65, 55.7), (37.65, 55.75), (37.6, 55.7)]), 0x50)
```

### `add_raw(text, before=True)`
Adds a raw text block before or after objects.
```python
m.add_raw("[COUNTRIES]\nCountry1=Russia~[0x1d]RU\n[END-Countries]", before=True)
```

---

## 5. Reading from Shapefile

### Simple Call
```python
m.add_from_shapefile("vydely.shp", type_code=0x50, label_field="NUM")
```

### Type Priority
1. `type_map[value of type_field]`
2. `type_field` (number or hex)
3. `default_type`
4. `type_code`
5. Skip feature

```python
# Type from string using a map
m.add_from_shapefile(
    "lines.shp",
    type_field="category",
    type_map={"FOREST": 0x50, "FIELD": 0x4F, "SWAMP": 0x51},
    default_type=0x4F,
    label_field="name"
)
```

### Full Parameters
```python
m.add_from_shapefile(
    path,
    # --- type ---
    type_code=None, type_field=None, type_map=None, type_hex=False, default_type=None,
    # --- label ---
    label_field=None, label2_field=None,
    # --- address fields ---
    house_field=None, street_field=None, city_field=None, region_field=None,
    country_field=None, zip_field=None, phone_field=None, web_field=None, text_field=None,
    # --- misc ---
    subtype_field=None, dir_field=None, extra_fields=None, section=None,
    encoding="cp1251", auto_uppercase=None, geom_kw=None, verbose=False,
)
```

### Return Value
Returns a dictionary `{'added': 1523, 'skipped': 4, 'types': {80: 800, 79: 400, ...}}`.

---

## 6. Address Sections

Written to the `.mp` **before objects**. Order: Countries -> Regions -> Cities -> Dictionary -> Highways -> ZipCodes -> objects.

```python
m.add_country("Russia", abbrev="RU")
m.add_region("Moscow region", country_idx=1, abbrev="MSK")
m.add_city("Moscow", region_idx=1)
m.add_zipcode("101000")
m.add_highway("M-7", region_idx=1)
```
*(To link an object to an address, use `extra={"CityIdx": 1, "ZipIdx": 1}`).*

---

## 7. Section `[DICTIONARY]`

**What it is:** A bitmask for filtering types by levels. Allows writing an object once, but displaying it only on desired levels.

### Manually
```python
m.add_dictionary(level=1, rgn_class=40, bitmask="1111110000000000")
```
*(rgn_class: 10 = POI, 20 = City, 40 = Polyline, 80 = Polygon)*

### Automatically from Types
```python
m.add_dictionary_by_types(level=1, rgn_class=40, types=[0x01, 0x02, 0x06], max_pos=0x40)
```

### By Category (requires `garmin_types.py`)
```python
m.dictionary_by_category("roads", kind="line")
m.dictionary_by_category("water", kind="polygon")
```

---

## 8. Special Label Codes

```python
from polish_map import label_abbrev, label_with_height, shield

label_abbrev("Russia", "RU")          # "Russia~[0x1d]RU"
label_with_height("Elbrus", 5642)     # "Elbrus~[0x1f]5642"
shield("interstate", 11)              # "~[0x01]11"
```

---

## 9. Validation

### `m.validate()`
Returns a list of error strings. Empty list = OK.

**Checks:**
- `E021`: Levels do not descend
- `E025`: Zooms do not ascend
- `E032`: Level0 missing
- `E033`: Less than 2 levels
- `E036`: ID > 0x0FFFFFFF
- `W013/W015`: TreSize out of bounds
- `RgnLimit < 50`
- `SimplifyLevel` out of 0.1..10
- `DrawPriority` out of 0..31
- `Lock=Y` without valid `ProductCode`
- Object uses the last (empty) level
- `Dictionary` level out of range
- Unknown types (if `type_check=True`)

---

## 10. Reports

### `m.summary()`
Prints a brief summary of the map (levels, zooms, counts, validation warnings).

### `m.summary_types()`
Breakdown by types with names (requires `garmin_types.py`).

---

## 11. Saving and Compilation

### `m.save(path=None)`
Writes the `.mp` file. Defaults to `f"{m.name}.mp"`.

### `m.compile(...)`
Runs mkgmap.
```python
m.compile(
    mkgmap="mkgmap.jar",
    java="java",
    mp_path="my.mp",
    extra_args=["--reduce-point-density=4.0", "--route"],
)
```

---

## 12. Integration with `garmin_types.py`

Provides validation, type names, categories, and predicates.
```python
import garmin_types as gt
gt.type_name(0x50, "polygon")       # "Forest"
gt.type_category(0x50, "polygon")   # "land"
gt.known_type(0x99, "polygon")      # False
gt.is_road_line(0x06)               # True
```

---

## 13. CLI

```bash
# Empty map
python polish_map.py empty my_map --levels 24,23,22 --snap --end-level

# Map from shapefile
python polish_map.py build forest vydely.shp \
    --type 0x50 \
    --label-field NUM \
    --levels 24,23,22 \
    --snap \
    --end-level \
    --section POLYGON \
    --validate \
    --compile
```

---

## 14. Full List of Methods

### Constructor & Factory
- `PolishMap(name, **params)`
- `PolishMap.empty(name, *, levels, zooms, **kw)`

### Adding Objects
- `add_point(lon, lat, type_code, label=None, *, levels, extra)`
- `add_line(coords, type_code, label=None, *, levels, tol, direction, extra, simplify_from_level)`
- `add_polygon(coords, type_code, label=None, *, holes, levels, tol, as_polygon, extra, simplify_from_level)`
- `add_geometry(geom, type_code, label=None, **kw)`
- `add_raw(text, before=True)`

### Address Sections
- `add_country`, `add_region`, `add_city`, `add_zipcode`, `add_highway`

### Dictionary
- `add_dictionary`, `add_dictionary_by_types`, `dictionary_by_category`

### Shapefile
- `add_from_shapefile(path, type_code=None, label_field=None, **kw)`

### Service
- `validate()`, `summary()`, `summary_types()`, `save(path=None)`, `compile(...)`

### Helpers
- `label_abbrev`, `label_with_height`, `shield`

---

## 15. Full List of Header Keys

| Key | Default | Description |
| :--- | :--- | :--- |
| `CodePage` | `1251` | Code page |
| `LblCoding` | `9` | 9 = SBCS, 10 = MBCS |
| `TypeSet` | `"Garmin"` | If "Garmin", not written |
| `Elevation` | `"M"` | M -> Elevation=M, F -> not written |
| `Preprocess` | `"F"` | N / G / P / F |
| `TreSize` | `511` | Region size (rec. 1000-2000) |
| `TreMargin` | `0.0` | Margin |
| `RgnLimit` | `127` | Max elements per region (rec. 1024) |
| `Transparent` | `"N"` | N / Y / S |
| `POIIndex` | `"Y"` | Index POIs |
| `POINumberFirst` | `"Y"` | House number before street |
| `POIZipFirst` | `"Y"` | Zip before street |
| `Copyright` | `"this map cannot be sold"` | Copyright |
| `SimplifyLevel` | `1` | 0.1..10, written if != 1 |
| `DrawPriority` | `25` | 0..31, written if != 25 |
| `Marine` | `"N"` | N / Y / B / X |
| `NT` | `"N"` | Experimental NT format |
| `Preview` | `"N"` | MapSource preview map |
| `MG` | `"N"` | Lock on road |
| `Numbering` | `"N"` | House numbering |
| `Routing` | `"N"` | Routing |
| `LeftSideTraffic` | `"N"` | Left-side traffic |
| `Invisible` | `"N"` | Invisible map |
| `Lock` | `"N"` | Locking |
| `ProductCode` | `None` | 1..60 |
| `FID` | `None` | Map family |
| `CountryName` | `None` | Auto-indexing |
| `RegionName` | `None` | Auto-indexing |
| `PolygonEvaluate` | `"auto"` | auto / Y / N |

---

## 16. Common Scenarios

### Forest Map: Blocks and Quarters

```python
from polish_map import PolishMap
import geopandas as gpd

m = PolishMap("forest", levels=[24,23,22,21,20,19,18],
              zooms=list(range(7)), snap_to_grid=True,
              polygon_section="POLYLINE", data_format="d")

# Blocks (lines)
m.add_from_shapefile("vydely.shp", type_code=0x06,
                     label_field="NUM",
                     geom_kw={"levels": [0,1,2,3]})

# Block centroids (POIs)
gdf = gpd.read_file("vydely.shp", encoding="cp1251")
for _, row in gdf.iterrows():
    p = row.geometry.representative_point()
    m.add_point(p.x, p.y, 0x1E00, label=str(row["NUM"]),
                levels=[0,1,2])

# Quarters (dissolve + buffer)
dissolved = gdf.dissolve(by="KV").buffer(0.0000001).explode()
for kv, row in dissolved.items():
    for poly in ([row] if row.geom_type == "Polygon" else row.geoms):
        m.add_polygon(list(poly.exterior.coords), 0x05, levels=[0,1,2,3,4,5])

m.save()
m.compile()
```

### Routing Map

```python
m = PolishMap("roads", levels=[24,23,22], header={"Routing": "Y", "RgnLimit": 1024})

m.add_from_shapefile("roads.shp",
                     type_field="type",
                     label_field="name",
                     dir_field="oneway",
                     extra_fields={
                         "RoadID": "road_id",
                         "RouteParam": "route_param",  # "60,3,1"
                     })
m.save()
```

### Progressive Simplification Export

```python
m = PolishMap("forest", levels=[24,23,22,21,20],
              simplify_tol="auto",  # tol = half grid step per level
              use_end_level=True,
              header={"SimplifyLevel": 2, "Preprocess": "P"})

m.add_from_shapefile("vydely.shp", type_code=0x50,
                     geom_kw={"levels": [0,1,2,3,4]})
m.save()
```

---

## 17. Troubleshooting

### `ModuleNotFoundError: No module named 'polish_map'`
The file `polish_map.py` is not in the same folder as your script, or it has the wrong extension (like `.pyc` or `.txt`).
**Solution:** Make sure it is exactly `polish_map.py` (Windows -> View -> File name extensions).

### `IndentationError: unexpected indent`
Indentation broke in `polish_map.py` (usually due to copy-pasting).
**Solution:** Open the file, show whitespace characters, ensure `def` is at 4 spaces and the body is at 8/12.

### `E036: ID=... > 0x0FFFFFFF`
`map_id` is too large. **Solution:** Use `map_id <= 268435455`.

### Object uses the last (empty) level
You added an object to a level that must be empty.
**Solution:** Decrease `levels=[...]` or add another level. `Levels=N` means levels `0..N-2` are available, and `N-1` is the empty switching level.

### `Type=0x99 unknown for polygon`
With `type_check=True`, the type is not in `garmin_types.py`. **Solution:** Fix the type or set `type_check=False`.

### Labels do not show on the navigator
Usually because of lowercase Cyrillic. For `codepage != 1252`, **all labels must be UPPERCASE**.
**Solution:** Use `auto_uppercase=True` (default for cp1251).

### Snap to grid doesn't help, GPSMapEdit still shifts
`precision` is too small. For `snap_to_grid=True`, use 7 decimal places (`precision=7`).
```

---

