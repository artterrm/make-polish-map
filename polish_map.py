"""
polish_map.py — universal library for building maps in Polish format (.mp)
for mkgmap / cGPSmapper / GPSMapEdit.

Features
--------
• [IMG ID] with a full set of keys: CodePage, LblCoding, TypeSet, Elevation,
  Preprocess, TreSize, TreMargin, RgnLimit, Transparent, POIIndex,
  POINumberFirst, POIZipFirst, MG, Numbering, Routing, LeftSideTraffic,
  Invisible, Lock, ProductCode, FID, CountryName, RegionName, Copyright,
  SimplifyLevel, DrawPriority, Marine, NT, Preview, PolygonEvaluate,
  Level#, LevelRange#, Zoom#, any extras.

• CRLF, two-digit levels (Level00, Zoom00, Data00) — 1:1 with GPSMapEdit.

• EndLevel-mode (Polish074): Data00 + EndLevel=N instead of Data00..DataNN.

• Garmin snap-to-grid (round half away from zero).

• auto_uppercase for codepage != 1252.

• Validation: E021/E025/E032/E033/E036, W013/W015, SimplifyLevel 0.1..10,
  DrawPriority 0..31, Lock+ProductCode, RgnLimit<50, last level
  empty, Dictionary in range, optionally type_check with garmin_types.

• [DICTIONARY] — bitmask by types per level, with auto-generation from type list
  and dictionary_by_category method.

• Sections [COUNTRIES], [REGIONS], [CITIES], [HIGHWAYS], [ZIPCODES] —
  in the correct order according to the cGPSmapper manual 4.2.

• [POI], [POLYLINE], [POLYGON]. Multi-ring polygons (outer + holes).

• Extra fields: HouseNumber, StreetDesc, CityName, RegionName, CountryName,
  Zip, Phone, Fax, Email, WebPage, Text (list), Background, DontFind, City,
  DirIndicator, SubType, Label2, RoadID, RouteParam, EntryPoint, raw.

• Helpers: label_abbrev(), label_with_height(), shield().

• add_from_shapefile() — full DBF support:
    label_field, label2_field, type_field, type_map, type_hex, default_type,
    subtype_field, dir_field, house_field, street_field, city_field,
    region_field, country_field, zip_field, phone_field, web_field,
    text_field, extra_fields, section override, auto_uppercase, geom_kw,
    verbose, statistics.

• CLI: polish_map empty / polish_map build.

Dependencies: shapely. For add_from_shapefile — pyshp.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import subprocess
from collections import OrderedDict


# ================================================================
# Optional integration with garmin_types.py
# ================================================================

try:
    from garmin_types import (
        type_name as _gt_name,
        type_category as _gt_cat,
        known_type as _gt_known,
        types_by_category as _gt_types_by_cat,
        CATEGORY_LEVELS_DEFAULT as _GT_CAT_LVL,
    )
    _GT_AVAILABLE = True
except ImportError:
    _GT_AVAILABLE = False


# ================================================================
# Default header [IMG ID]
# ================================================================

DEFAULT_HEADER = OrderedDict([
    ("CodePage",        1251),
    ("LblCoding",       9),
    ("TypeSet",         "Garmin"),
    ("Elevation",       "M"),
    ("Preprocess",      "F"),
    ("TreSize",         511),
    ("TreMargin",       0.0),
    ("RgnLimit",        127),
    ("Transparent",     "N"),
    ("POIIndex",        "Y"),
    ("POINumberFirst",  "Y"),
    ("POIZipFirst",     "Y"),
    ("Copyright",       "this map cannot be sold"),
    ("SimplifyLevel",   1),
    ("DrawPriority",    25),
    ("Marine",          "N"),
    ("NT",              "N"),
    ("Preview",         "N"),
    ("MG",              "N"),
    ("Numbering",       "N"),
    ("Routing",         "N"),
    ("LeftSideTraffic", "N"),
    ("Invisible",       "N"),
    ("Lock",            "N"),
    ("ProductCode",     None),
    ("FID",             None),
    ("CountryName",     None),
    ("RegionName",      None),
    ("PolygonEvaluate", "auto"),
])


# ================================================================
# Geometry helpers
# ================================================================

def _fmt_code(code):
    return code if isinstance(code, str) else hex(code)


def _round_half_away(x):
    return math.floor(x + 0.5) if x >= 0 else math.ceil(x - 0.5)


def _simplify_polygon_rings(rings, tol):
    if tol <= 0 or len(rings[0]) < 4:
        return rings
    try:
        from shapely.geometry import Polygon
        outer = rings[0]
        holes = rings[1:] if len(rings) > 1 else None
        p = Polygon(outer, holes)
        if not p.is_valid:
            p = p.buffer(0)
        s = p.simplify(tol, preserve_topology=True)
        out = [list(s.exterior.coords)]
        for interior in s.interiors:
            out.append(list(interior.coords))
        return out
    except Exception:
        return rings


def _simplify_line(coords, tol):
    if tol <= 0 or len(coords) < 3:
        return coords
    try:
        from shapely.geometry import LineString
        return list(LineString(coords).simplify(tol).coords)
    except Exception:
        return coords


# ================================================================
# Helpers for special Label codes
# ================================================================

def label_abbrev(name, abbrev):
    return f"{name}~[0x1d]{abbrev}"


def label_with_height(name, height):
    return f"{name}~[0x1f]{height}"


def shield(kind, number):
    codes = {
        "interstate": 0x01, "us_shield": 0x02, "us_round": 0x03,
        "big": 0x04, "medium": 0x05, "small": 0x06,
    }
    if kind not in codes:
        raise ValueError(f"unknown shield kind: {kind}")
    return f"~[0x{codes[kind]:02x}]{number}"


# ================================================================
# pyshp.shapeType → .mp section
# ================================================================

_SHAPE_SECTION = {
    1: "point", 8: "point", 11: "point", 18: "point", 21: "point", 28: "point",
    3: "line", 13: "line", 23: "line",
    5: "polygon", 15: "polygon", 25: "polygon",
}


# ================================================================
# PolishMap
# ================================================================

class PolishMap:
    """Map in Polish format (see module description)."""

    def __init__(
        self,
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
    ):
        self.name = name
        self.map_id = (map_id if map_id is not None
                       else random.randint(30000000, 99999999))

        self.levels = list(levels) if levels else [24, 23, 22, 21, 20, 19, 18]
        self.zooms = list(zooms) if zooms else list(range(len(self.levels)))

        if level_ranges is not None and len(level_ranges) != len(self.levels):
            raise ValueError("level_ranges length != levels length")
        self.level_ranges = level_ranges

        self.codepage = codepage
        self.snap_to_grid = snap_to_grid

        sec = polygon_section.upper()
        if sec not in ("POLYLINE", "POLYGON"):
            raise ValueError("polygon_section must be POLYLINE or POLYGON")
        self.polygon_section = sec

        self.data_levels = list(data_levels) if data_levels else [0, 1, 2, 3]
        self.simplify_tol = simplify_tol
        self.simplify_from_level = simplify_from_level
        self.use_end_level = bool(use_end_level)

        if precision is not None:
            self.precision = int(precision)
        else:
            max_bits = max(self.levels) if self.levels else 24
            if snap_to_grid:
                self.precision = 7
            elif max_bits >= 25:
                self.precision = 6
            else:
                self.precision = 5

        if data_format not in ("02d", "d"):
            raise ValueError("data_format must be '02d' or 'd'")
        self.data_format = data_format
        self.crlf = bool(crlf)
        self.nl = "\r\n" if crlf else "\n"

        if auto_uppercase is None:
            self.auto_uppercase = (codepage not in (1252, None))
        else:
            self.auto_uppercase = bool(auto_uppercase)

        self.header = dict(DEFAULT_HEADER)
        if header:
            self.header.update(header)

        self.type_check = bool(type_check) and _GT_AVAILABLE

        # Data
        self._objects = []
        self._raw_before = []
        self._raw_after = []
        self._countries = []
        self._regions = []
        self._cities = []
        self._zipcodes = []
        self._highways = []
        self._dictionary = []

    # ============================================================
    # Factory
    # ============================================================

    @classmethod
    def empty(cls, name, *, levels=None, zooms=None, **kw):
        return cls(name, levels=levels, zooms=zooms, **kw)

    # ============================================================
    # Adding objects
    # ============================================================

    def _prep_label(self, label):
        if label is None:
            return None
        s = str(label).strip()
        if not s:
            return None
        if self.auto_uppercase:
            s = s.upper()
        return s

    def add_point(self, lon, lat, type_code, label=None, *,
                  levels=None, extra=None):
        self._objects.append({
            "kind": "point",
            "coords": [(float(lon), float(lat))],
            "type": type_code,
            "label": self._prep_label(label),
            "levels": self._norm_levels(levels),
            "tol": 0.0,
            "as_polygon": None,
            "direction": False,
            "extra": dict(extra or {}),
            "simplify_from_level": None,
        })

    def add_line(self, coords, type_code, label=None, *,
                 levels=None, tol=None, direction=False, extra=None,
                 simplify_from_level=None):
        self._objects.append({
            "kind": "line",
            "coords": self._to_coords(coords),
            "type": type_code,
            "label": self._prep_label(label),
            "levels": self._norm_levels(levels),
            "tol": self.simplify_tol if tol is None else tol,
            "as_polygon": None,
            "direction": bool(direction),
            "extra": dict(extra or {}),
            "simplify_from_level": simplify_from_level,
        })

    def add_polygon(self, coords, type_code, label=None, *,
                    holes=None, levels=None, tol=None,
                    as_polygon=None, extra=None, simplify_from_level=None):
        outer = self._to_coords(coords)
        rings = [outer]
        if holes:
            for h in holes:
                rings.append(self._to_coords(h))
        self._objects.append({
            "kind": "polygon",
            "rings": rings,
            "coords": outer,
            "type": type_code,
            "label": self._prep_label(label),
            "levels": self._norm_levels(levels),
            "tol": self.simplify_tol if tol is None else tol,
            "as_polygon": as_polygon,
            "direction": False,
            "extra": dict(extra or {}),
            "simplify_from_level": simplify_from_level,
        })

    def add_geometry(self, geom, type_code, label=None, **kw):
        gt = getattr(geom, "geom_type", None)
        if gt == "Point":
            self.add_point(geom.x, geom.y, type_code, label, **kw)
        elif gt == "LineString":
            self.add_line(list(geom.coords), type_code, label, **kw)
        elif gt == "Polygon":
            holes = [list(i.coords) for i in geom.interiors]
            self.add_polygon(list(geom.exterior.coords), type_code, label,
                             holes=holes if holes else None, **kw)
        elif gt in ("MultiPoint", "MultiLineString", "MultiPolygon"):
            for g in geom.geoms:
                self.add_geometry(g, type_code, label, **kw)
        else:
            raise ValueError(f"Unsupported geometry: {gt}")

    def add_raw(self, text, before=True):
        (self._raw_before if before else self._raw_after).append(text)

    # ============================================================
    # Declarations
    # ============================================================

    def add_country(self, name, abbrev=None):
        self._countries.append({"name": name, "abbrev": abbrev})

    def add_region(self, name, country_idx=1, abbrev=None):
        self._regions.append({"name": name, "abbrev": abbrev,
                              "country_idx": country_idx})

    def add_city(self, name, region_idx=1, extra=None):
        self._cities.append({"name": name, "region_idx": region_idx,
                             "extra": dict(extra or {})})

    def add_zipcode(self, name):
        self._zipcodes.append({"name": name})

    def add_highway(self, name, region_idx=1):
        self._highways.append({"name": name, "region_idx": region_idx})

    # ============================================================
    # Dictionary
    # ============================================================

    def add_dictionary(self, level, rgn_class, bitmask):
        if rgn_class not in (10, 20, 40, 80):
            raise ValueError("rgn_class must be 10, 20, 40 or 80")
        self._dictionary.append((int(level), int(rgn_class), str(bitmask)))

    def add_dictionary_by_types(self, level, rgn_class, types,
                                 max_pos=None):
        if rgn_class in (40, 80):
            positions = [int(t) for t in types]
        elif rgn_class in (10, 20):
            positions = [(int(t) >> 8) & 0xFF for t in types]
        else:
            raise ValueError("rgn_class must be 10, 20, 40 or 80")
        if not positions:
            positions = [1]
        m = max_pos if max_pos is not None else max(positions)
        mask = ["0"] * m
        for p in positions:
            if 1 <= p <= m:
                mask[p - 1] = "1"
        self._dictionary.append((int(level), int(rgn_class), "".join(mask)))

    def dictionary_by_category(self, category, kind,
                                levels=None, max_pos=None):
        """Auto-[DICTIONARY] by Garmin type category."""
        if not _GT_AVAILABLE:
            raise RuntimeError("garmin_types.py не найден")
        k = kind.lower()
        rgn_map = {"point": 10, "line": 40, "polygon": 80}
        if k not in rgn_map:
            raise ValueError("kind must be point/line/polygon")
        types = _gt_types_by_cat(category, k)
        if not types:
            return
        if levels is None:
            levels = _GT_CAT_LVL.get(category, [0, 1, 2, 3])
        for lvl in levels:
            self.add_dictionary_by_types(lvl, rgn_map[k], types,
                                          max_pos=max_pos)

    # ============================================================
    # Shapefile
    # ============================================================

    def add_from_shapefile(
        self,
        path,
        type_code=None,
        label_field=None,
        *,
        type_field=None,
        default_type=None,
        type_map=None,
        type_hex=False,
        subtype_field=None,
        label2_field=None,
        dir_field=None,
        house_field=None,
        street_field=None,
        city_field=None,
        region_field=None,
        country_field=None,
        zip_field=None,
        phone_field=None,
        web_field=None,
        text_field=None,
        extra_fields=None,
        section=None,
        encoding="cp1251",
        auto_uppercase=None,
        geom_kw=None,
        verbose=False,
    ):
        """
        Import objects from ESRI shapefile.

        Type is determined by priority:
          1) type_map[value of type_field]
          2) type_field → hex/decimal
          3) default_type
          4) type_code (scalar)
          5) feature is skipped

        Section ([POI]/[POLYLINE]/[POLYGON]) — auto by shape.shapeType,
        if section=None.

        Returns dict {"added": n, "skipped": n, "types": {type: count}}.
        """
        try:
            import shapefile as pyshp
        except ImportError:
            raise RuntimeError("pyshp is required: pip install pyshp")
        from shapely.geometry import shape as shp_shape

        _auto_upper = (self.auto_uppercase if auto_uppercase is None
                       else auto_uppercase)
        geom_kw = dict(geom_kw or {})

        def _get(rec, fields, spec):
            if spec is None:
                return None
            idx = spec if isinstance(spec, int) else fields.index(spec)
            v = rec[idx]
            if isinstance(v, str):
                v = v.strip()
            return v

        def _parse_type_value(raw):
            if raw is None:
                return None
            if isinstance(raw, (int, float)):
                return int(raw)
            s = str(raw).strip()
            if not s:
                return None
            try:
                if type_hex or s.lower().startswith("0x"):
                    return int(s, 16)
                if all(c in "0123456789abcdefABCDEF" for c in s):
                    return int(s, 16)
                return int(s)
            except (ValueError, TypeError):
                return None

        def _label(v):
            if v is None:
                return None
            s = str(v)
            if _auto_upper:
                s = s.upper()
            return s

        sf = pyshp.Reader(path, encoding=encoding, encodingErrors="ignore")
        fields = [f[0] for f in sf.fields[1:]]

        n_added = 0
        n_skipped = 0
        type_stats = {}

        for shp, rec in zip(sf.shapes(), sf.records()):
            geom = shp_shape(shp.__geo_interface__)
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty:
                n_skipped += 1
                continue

            if section is None:
                sec = _SHAPE_SECTION.get(shp.shapeType)
                if sec is None:
                    n_skipped += 1
                    continue
            else:
                sec = section.lower()
                if sec not in ("point", "line", "polygon"):
                    raise ValueError("section must be point/line/polygon")

            resolved_type = None
            if type_field is not None:
                raw = _get(rec, fields, type_field)
                if type_map:
                    resolved_type = type_map.get(raw)
                    if resolved_type is None and isinstance(raw, str):
                        resolved_type = type_map.get(raw.strip().upper())
                if resolved_type is None:
                    resolved_type = _parse_type_value(raw)

            if resolved_type is None:
                resolved_type = default_type
            if resolved_type is None:
                resolved_type = type_code
            if resolved_type is None:
                n_skipped += 1
                if verbose:
                    print(f"  skip feature: нет типа (rec={rec})")
                continue

            lbl = _label(_get(rec, fields, label_field))
            lbl2 = _label(_get(rec, fields, label2_field))

            extra = {}

            def _put(key, spec):
                if spec is None:
                    return
                v = _get(rec, fields, spec)
                if v is None or v == "":
                    return
                extra[key] = v

            _put("HouseNumber", house_field)
            _put("StreetDesc",  street_field)
            _put("CityName",    city_field)
            _put("RegionName",  region_field)
            _put("CountryName", country_field)
            _put("Zip",         zip_field)
            _put("Phone",       phone_field)
            _put("WebPage",     web_field)

            if text_field is not None:
                v = _get(rec, fields, text_field)
                if v:
                    lines = str(v).splitlines()
                    extra["Text"] = lines if len(lines) > 1 else [str(v)]

            if extra_fields:
                for mp_key, spec in extra_fields.items():
                    _put(mp_key, spec)

            if lbl2 is not None:
                extra["Label2"] = lbl2

            if dir_field is not None:
                d = _get(rec, fields, dir_field)
                if d not in (None, "", 0, "0"):
                    extra["DirIndicator"] = 1

            if subtype_field is not None:
                sub = _get(rec, fields, subtype_field)
                try:
                    sub = int(sub)
                except (ValueError, TypeError):
                    sub = None
                if sub is not None:
                    extra["SubType"] = sub

            kw = dict(geom_kw)
            if extra:
                kw["extra"] = {**(kw.get("extra") or {}), **extra}

            self.add_geometry(geom, resolved_type, lbl, **kw)
            n_added += 1
            type_stats[resolved_type] = type_stats.get(resolved_type, 0) + 1

        sf.close()

        if verbose:
            print(f"add_from_shapefile: {n_added} added, {n_skipped} skipped")
            for t, n in sorted(type_stats.items()):
                print(f"  Type=0x{t:04X}  {n}")

        return {"added": n_added, "skipped": n_skipped, "types": type_stats}

    # ============================================================
    # Internal helpers
    # ============================================================

    def _norm_levels(self, levels):
        return (list(self.data_levels) if levels is None
                else [int(x) for x in levels])

    @staticmethod
    def _to_coords(coords):
        if hasattr(coords, "exterior"):
            return [(float(x), float(y)) for x, y in coords.exterior.coords]
        if hasattr(coords, "coords"):
            return [(float(x), float(y)) for x, y in coords.coords]
        return [(float(x), float(y)) for x, y in coords]

    def _bits_for_level(self, lvl):
        return self.levels[lvl] if 0 <= lvl < len(self.levels) else 24

    def _snap(self, value, bits):
        if not self.snap_to_grid:
            return value
        step = 360.0 / (1 << bits)
        return _round_half_away(value / step) * step

    def _fmt_pt(self, x, y, lvl):
        bits = self._bits_for_level(lvl)
        p = self.precision
        return (f"({self._snap(y, bits):.{p}f},"
                f"{self._snap(x, bits):.{p}f})")

    def _fmt_coords(self, coords, lvl):
        return ",".join(self._fmt_pt(x, y, lvl) for x, y in coords)

    def _data_key(self, lvl):
        return f"Data{lvl:02d}" if self.data_format == "02d" else f"Data{lvl}"

    def _lvl_key(self, prefix, i):
        return f"{prefix}{i:02d}" if self.data_format == "02d" else f"{prefix}{i}"

    def _has_multi_ring(self):
        return any(o["kind"] == "polygon" and len(o.get("rings", [])) > 1
                   for o in self._objects)

    def _tol_for_level(self, obj, lvl):
        tol = obj.get("tol", self.simplify_tol)
        if tol == "auto":
            bits = self._bits_for_level(lvl)
            return (360.0 / (1 << bits)) * 0.5
        if isinstance(tol, (list, tuple)):
            levels = obj["levels"]
            idx = levels.index(lvl) if lvl in levels else 0
            return tol[idx] if idx < len(tol) else tol[-1]
        if tol is None:
            return 0.0
        return float(tol)

    def _simplify_from(self, obj):
        s = obj.get("simplify_from_level")
        if s is not None:
            return s
        if self.simplify_from_level is not None:
            return self.simplify_from_level
        levels = obj["levels"]
        return (min(levels) + 1) if levels else 1

    # ============================================================
    # Validation
    # ============================================================

    def validate(self):
        """
        Check key constraints of cGPSmapper / mkgmap.
        Returns a list of strings (empty = OK).
        """
        errs = []

        if len(self.levels) < 2:
            errs.append("E033: Levels must be >= 2")
        if not self.levels:
            errs.append("E032: Level0 must exist")

        for i in range(len(self.levels) - 1):
            if self.levels[i] <= self.levels[i + 1]:
                errs.append(
                    f"E021: Level{i}={self.levels[i]} must be > "
                    f"Level{i+1}={self.levels[i+1]} (descending)")
        for i in range(len(self.zooms) - 1):
            if self.zooms[i] >= self.zooms[i + 1]:
                errs.append(
                    f"E025: Zoom{i}={self.zooms[i]} must be < "
                    f"Zoom{i+1}={self.zooms[i+1]} (ascending)")

        if self.map_id <= 0:
            errs.append("ID must be positive")
        if self.map_id > 0x0FFFFFFF:
            errs.append(f"E036: ID={self.map_id} > 0x0FFFFFFF")

        h = self.header

        # Real RgnLimit threshold according to cGPSmapper manual: <50 doesn't make sense.
        # 500 is just a recommendation (not an error).
        rgn = h.get("RgnLimit")
        if isinstance(rgn, int) and rgn < 50:
            errs.append(
                f"RgnLimit={rgn} < 50 (значения меньше 50 не имеют смысла)")

        tre = h.get("TreSize")
        if isinstance(tre, int):
            if tre > 5000:
                errs.append(f"W015: TreSize={tre} > 5000 (обрежется до 5000)")
            if tre < 100:
                errs.append(f"W013: TreSize={tre} < 100")

        sl = h.get("SimplifyLevel")
        if isinstance(sl, (int, float)) and (sl < 0.1 or sl > 10):
            errs.append(f"SimplifyLevel={sl} вне диапазона 0.1..10")

        dp = h.get("DrawPriority")
        if isinstance(dp, int) and (dp < 0 or dp > 31):
            errs.append(f"DrawPriority={dp} вне 0..31")

        if h.get("Lock") == "Y":
            pc = h.get("ProductCode")
            if not isinstance(pc, int) or not (1 <= pc <= 60):
                errs.append(f"Lock=Y требует ProductCode 1..60 "
                            f"(сейчас {pc})")

        max_usable = max(0, len(self.levels) - 2)
        for o in self._objects:
            for lvl in o["levels"]:
                if lvl > max_usable:
                    errs.append(
                        f"Объект использует level={lvl}, но последний "
                        f"уровень {len(self.levels)-1} должен быть пустым "
                        f"(макс. {max_usable})")
                    break

        for lvl, rgn_, mask in self._dictionary:
            if lvl < 0 or lvl >= len(self.levels):
                errs.append(
                    f"Dictionary level={lvl} вне 0..{len(self.levels)-1}")

        # Type checking (if garmin_types.py is connected)
        if self.type_check:
            for o in self._objects:
                kind = o["kind"]
                t = int(o["type"])
                if not _gt_known(t, kind):
                    errs.append(
                        f"Type=0x{t:02X} неизвестен для {kind} "
                        f"(возможная опечатка)")
                if kind == "point" and t < 0x100:
                    errs.append(
                        f"Type=0x{t:02X} слишком мал для точки "
                        f"(POI обычно ≥ 0x0100)")
                if kind in ("line", "polygon") and t >= 0x100:
                    errs.append(
                        f"Type=0x{t:02X} слишком велик для {kind}")

        return errs

    # ============================================================
    # Header
    # ============================================================

    def _build_header(self):
        h = self.header
        L = ["[IMG ID]"]
        if h.get("CodePage"):
            L.append(f"CodePage={h['CodePage']}")
        if h.get("LblCoding"):
            L.append(f"LblCoding={h['LblCoding']}")
        L.append(f"ID={self.map_id}")
        L.append(f"Name={self.name}")

        ts = h.get("TypeSet")
        if ts and str(ts).lower() != "garmin":
            L.append(f"TypeSet={ts}")
        if h.get("Elevation") == "M":
            L.append("Elevation=M")
        if h.get("Preprocess"):
            L.append(f"Preprocess={h['Preprocess']}")

        L.append(f"TreSize={h.get('TreSize', 511)}")
        L.append(f"TreMargin={float(h.get('TreMargin', 0.0)):.6f}")
        L.append(f"RgnLimit={h.get('RgnLimit', 127)}")

        tr = h.get("Transparent", "N")
        if tr in ("Y", "S"):
            L.append(f"Transparent={tr}")

        L.append(f"POIIndex={h.get('POIIndex', 'Y')}")
        if h.get("POINumberFirst", "Y") != "Y":
            L.append(f"POINumberFirst={h['POINumberFirst']}")
        if h.get("POIZipFirst", "Y") != "Y":
            L.append(f"POIZipFirst={h['POIZipFirst']}")

        for k in ("MG", "Numbering", "Routing", "LeftSideTraffic", "Invisible"):
            if h.get(k) == "Y":
                L.append(f"{k}=Y")

        if h.get("Lock") == "Y":
            L.append("Lock=Y")
            if h.get("ProductCode") is not None:
                L.append(f"ProductCode={h['ProductCode']}")
            if h.get("FID") is not None:
                L.append(f"FID={h['FID']}")

        if h.get("CountryName"):
            L.append(f"CountryName={h['CountryName']}")
        if h.get("RegionName"):
            L.append(f"RegionName={h['RegionName']}")
        if h.get("Copyright"):
            L.append(f"Copyright={h['Copyright']}")

        sl = h.get("SimplifyLevel")
        if sl is not None and sl != 1:
            L.append(f"SimplifyLevel={sl}")
        dp = h.get("DrawPriority")
        if dp is not None and dp != 25:
            L.append(f"DrawPriority={dp}")

        marine = h.get("Marine", "N")
        if marine and marine != "N":
            L.append(f"Marine={marine}")
        if h.get("NT") == "Y":
            L.append("NT=Y")
        if h.get("Preview") == "Y":
            L.append("Preview=Y")

        pe = h.get("PolygonEvaluate", "auto")
        if pe == "Y" or (pe == "auto" and self._has_multi_ring()):
            L.append("PolygonEvaluate=Y")

        known = set(DEFAULT_HEADER) | {"ID", "Name"}
        for k, v in h.items():
            if k not in known and v is not None:
                L.append(f"{k}={v}")

        L.append(f"Levels={len(self.levels)}")
        for i, b in enumerate(self.levels):
            L.append(f"{self._lvl_key('Level', i)}={b}")
            if self.level_ranges is not None and self.level_ranges[i] != b:
                L.append(f"{self._lvl_key('LevelRange', i)}="
                         f"{self.level_ranges[i]}")
        for i, z in enumerate(self.zooms):
            L.append(f"{self._lvl_key('Zoom', i)}={z}")

        L.append("[END-IMG ID]")
        return self.nl.join(L) + self.nl

    # ============================================================
    # Declarations
    # ============================================================

    def _build_declarations(self):
        out = []
        if self._countries:
            out.append("[COUNTRIES]")
            for i, c in enumerate(self._countries, 1):
                s = c["name"]
                if c.get("abbrev"):
                    s += "~[0x1d]" + c["abbrev"]
                out.append(f"Country{i}={s}")
            out.append("[END-Countries]")
            out.append("")
        if self._regions:
            out.append("[REGIONS]")
            for i, r in enumerate(self._regions, 1):
                s = r["name"]
                if r.get("abbrev"):
                    s += "~[0x1d]" + r["abbrev"]
                out.append(f"Region{i}={s}")
                out.append(f"CountryIdx{i}={r.get('country_idx', 1)}")
            out.append("[END-Regions]")
            out.append("")
        if self._cities:
            out.append("[CITIES]")
            for i, c in enumerate(self._cities, 1):
                out.append(f"City{i}={c['name']}")
                out.append(f"RegionIdx{i}={c.get('region_idx', 1)}")
                for k, v in (c.get("extra") or {}).items():
                    out.append(f"{k}{i}={v}")
            out.append("[END-Cities]")
            out.append("")
        return self.nl.join(out)

    def _build_dictionary(self):
        if not self._dictionary:
            return ""
        out = ["[DICTIONARY]"]
        for lvl, rgn, mask in sorted(self._dictionary,
                                     key=lambda x: (x[0], x[1])):
            out.append(f"Level{lvl:02d}RGN{rgn}={mask}")
        out.append("[END-DICTIONARY]")
        return self.nl.join(out)

    def _build_advanced(self):
        out = []
        if self._highways:
            out.append("[HIGHWAYS]")
            for i, hg in enumerate(self._highways, 1):
                out.append(f"Highway{i}={hg['name']}")
                out.append(f"RegionIdx{i}={hg.get('region_idx', 1)}")
            out.append("[END-Highways]")
            out.append("")
        if self._zipcodes:
            out.append("[ZIPCODES]")
            for i, z in enumerate(self._zipcodes, 1):
                out.append(f"ZipCode{i}={z['name']}")
            out.append("[END-ZipCodes]")
            out.append("")
        return self.nl.join(out)

    # ============================================================
    # Extra fields
    # ============================================================

    _SPECIAL_EXTRA_KEYS = {
        "Background", "DontFind", "City", "DirIndicator", "SubType",
        "Label2", "Text", "raw",
    }

    def _write_extra_fields(self, f, obj):
        extra = obj.get("extra") or {}
        for key, val in extra.items():
            if key in self._SPECIAL_EXTRA_KEYS:
                continue
            if isinstance(val, (list, tuple)):
                for v in val:
                    f.write(f"{key}={v}{self.nl}")
            else:
                f.write(f"{key}={val}{self.nl}")

    def _write_common_fields(self, f, obj):
        extra = obj.get("extra") or {}
        if extra.get("Background") == "Y":
            f.write(f"Background=Y{self.nl}")
        if obj.get("label") is not None:
            f.write(f"Label={obj['label']}{self.nl}")
        if "Label2" in extra:
            f.write(f"Label2={extra['Label2']}{self.nl}")
        if obj.get("direction"):
            f.write(f"DirIndicator=1{self.nl}")
        elif extra.get("DirIndicator"):
            f.write(f"DirIndicator={extra['DirIndicator']}{self.nl}")
        if extra.get("DontFind") == "Y":
            f.write(f"DontFind=Y{self.nl}")
        if extra.get("City") == "Y":
            f.write(f"City=Y{self.nl}")
        if "SubType" in extra:
            f.write(f"SubType=0x{int(extra['SubType']):02x}{self.nl}")
        if "Text" in extra:
            lines = extra["Text"]
            if not isinstance(lines, (list, tuple)):
                lines = [lines]
            for line in lines:
                f.write(f"Text={line}{self.nl}")
        self._write_extra_fields(f, obj)
        if "raw" in extra:
            s = str(extra["raw"])
            if not s.endswith(self.nl):
                s += self.nl
            f.write(s)

    # ============================================================
    # Writing objects
    # ============================================================

    def _write_point(self, f, obj):
        code = _fmt_code(obj["type"])
        levels = obj["levels"]
        x, y = obj["coords"][0]
        f.write(f"[POI]{self.nl}")
        f.write(f"Type={code}{self.nl}")
        self._write_common_fields(f, obj)
        min_lvl = min(levels) if levels else 0
        if self.use_end_level and levels:
            f.write(f"EndLevel={max(levels)}{self.nl}")
            f.write(f"{self._data_key(min_lvl)}="
                    f"{self._fmt_pt(x, y, min_lvl)}{self.nl}")
        else:
            for lvl in levels:
                f.write(f"{self._data_key(lvl)}="
                        f"{self._fmt_pt(x, y, lvl)}{self.nl}")
        f.write(f"[END]{self.nl}")

    def _write_line(self, f, obj):
        code = _fmt_code(obj["type"])
        levels = obj["levels"]
        coords = obj["coords"]
        f.write(f"[POLYLINE]{self.nl}")
        f.write(f"Type={code}{self.nl}")
        self._write_common_fields(f, obj)
        min_lvl = min(levels) if levels else 0
        if self.use_end_level and levels:
            f.write(f"EndLevel={max(levels)}{self.nl}")
            f.write(f"{self._data_key(min_lvl)}="
                    f"{self._fmt_coords(coords, min_lvl)}{self.nl}")
        else:
            simplify_from = self._simplify_from(obj)
            for lvl in levels:
                c = (coords if lvl < simplify_from
                     else _simplify_line(coords, self._tol_for_level(obj, lvl)))
                f.write(f"{self._data_key(lvl)}="
                        f"{self._fmt_coords(c, lvl)}{self.nl}")
        f.write(f"[END]{self.nl}")

    def _write_polygon(self, f, obj):
        code = _fmt_code(obj["type"])
        levels = obj["levels"]
        as_poly = obj.get("as_polygon")
        if as_poly is None:
            as_poly = (self.polygon_section == "POLYGON")
        section = "POLYGON" if as_poly else "POLYLINE"
        f.write(f"[{section}]{self.nl}")
        f.write(f"Type={code}{self.nl}")
        self._write_common_fields(f, obj)
        min_lvl = min(levels) if levels else 0
        rings0 = obj["rings"]
        if self.use_end_level and levels:
            f.write(f"EndLevel={max(levels)}{self.nl}")
            for ring in rings0:
                f.write(f"{self._data_key(min_lvl)}="
                        f"{self._fmt_coords(ring, min_lvl)}{self.nl}")
        else:
            simplify_from = self._simplify_from(obj)
            for lvl in levels:
                rings = (rings0 if lvl < simplify_from
                         else _simplify_polygon_rings(
                             rings0, self._tol_for_level(obj, lvl)))
                for ring in rings:
                    f.write(f"{self._data_key(lvl)}="
                            f"{self._fmt_coords(ring, lvl)}{self.nl}")
        f.write(f"[END]{self.nl}")

    # ============================================================
    # Saving
    # ============================================================

    def save(self, path=None):
        if path is None:
            path = f"{self.name}.mp"
        with open(path, "w", encoding="cp1251", errors="replace",
                  newline="") as f:
            f.write(self._build_header())
            f.write(self.nl)
            decl = self._build_declarations()
            if decl:
                f.write(decl)
                f.write(self.nl)
            dct = self._build_dictionary()
            if dct:
                f.write(dct)
                f.write(self.nl)
            adv = self._build_advanced()
            if adv:
                f.write(adv)
                f.write(self.nl)
            for block in self._raw_before:
                f.write(block.rstrip(self.nl) + self.nl)
            for obj in self._objects:
                k = obj["kind"]
                if k == "point":
                    self._write_point(f, obj)
                elif k == "line":
                    self._write_line(f, obj)
                elif k == "polygon":
                    self._write_polygon(f, obj)
                f.write(self.nl)
            for block in self._raw_after:
                f.write(block.rstrip(self.nl) + self.nl)
        return path

    # ============================================================
    # Compilation
    # ============================================================

    def compile(self, *, mkgmap="mkgmap.jar", java="java",
                extra_args=None, mp_path=None, wait=True):
        if mp_path is None:
            mp_path = f"{self.name}.mp"
        if not os.path.exists(mp_path):
            self.save(mp_path)
        args = [java, "-jar", mkgmap,
                f"--mapname={self.map_id}",
                f"--code-page={self.codepage}",
                "--transparent",
                f"--description={self.name}"]
        if extra_args:
            args.extend(extra_args)
        args.append(mp_path)
        if wait:
            subprocess.call(args)
            return None
        return subprocess.Popen(args)

    # ============================================================
    # Information
    # ============================================================

    def summary(self):
        p = sum(1 for o in self._objects if o["kind"] == "point")
        l = sum(1 for o in self._objects if o["kind"] == "line")
        g = sum(1 for o in self._objects if o["kind"] == "polygon")
        multi = sum(1 for o in self._objects
                    if o["kind"] == "polygon" and len(o.get("rings", [])) > 1)
        lines = [
            f"PolishMap {self.name!r}  id={self.map_id}",
            f"  levels={self.levels}",
            f"  zooms={self.zooms}",
            f"  codepage={self.codepage}, "
            f"auto_uppercase={self.auto_uppercase}",
            f"  snap_to_grid={self.snap_to_grid}, precision={self.precision}",
            f"  section={self.polygon_section}, "
            f"use_end_level={self.use_end_level}, "
            f"data_format={self.data_format!r}, crlf={self.crlf}",
            f"  type_check={self.type_check}",
            f"  points={p}, lines={l}, polygons={g} (multi-ring: {multi})",
        ]
        if self._dictionary:
            lines.append(f"  dictionary entries: {len(self._dictionary)}")
        if (self._countries or self._regions or self._cities
                or self._zipcodes or self._highways):
            lines.append(
                f"  declarations: countries={len(self._countries)}, "
                f"regions={len(self._regions)}, cities={len(self._cities)}, "
                f"highways={len(self._highways)}, "
                f"zips={len(self._zipcodes)}")
        errs = self.validate()
        if errs:
            lines.append(f"  ⚠ validate(): {len(errs)} issue(s)")
        return "\n".join(lines)

    def summary_types(self):
        from collections import Counter
        if not _GT_AVAILABLE:
            return "garmin_types.py не подключён"
        lines = []
        for kind in ("point", "line", "polygon"):
            objs = [o for o in self._objects if o["kind"] == kind]
            if not objs:
                continue
            c = Counter(int(o["type"]) for o in objs)
            lines.append(f"\n{kind.upper()} ({len(objs)}):")
            w = 4 if kind == "point" else 2
            for t, n in sorted(c.items(), key=lambda kv: -kv[1]):
                name = _gt_name(t, kind)
                cat = _gt_cat(t, kind) or "?"
                lines.append(f"  0x{t:0{w}X}  {n:>6}  [{cat}]  {name}")
        return "\n".join(lines)

    def __repr__(self):
        return (f"PolishMap({self.name!r}, levels={self.levels}, "
                f"zooms={self.zooms}, snap={self.snap_to_grid}, "
                f"section={self.polygon_section})")


# ================================================================
# CLI
# ================================================================

def _cli():
    ap = argparse.ArgumentParser(prog="polish_map")
    sub = ap.add_subparsers(dest="cmd")

    p_empty = sub.add_parser("empty")
    p_empty.add_argument("name")
    p_empty.add_argument("--levels", default="24,23,22,21,20,19,18")
    p_empty.add_argument("--zooms", default=None)
    p_empty.add_argument("--out", default=None)
    p_empty.add_argument("--snap", action="store_true")
    p_empty.add_argument("--end-level", action="store_true")
    p_empty.add_argument("--simplify-level", type=float, default=None)
    p_empty.add_argument("--type-check", action="store_true")

    p_shp = sub.add_parser("build")
    p_shp.add_argument("name")
    p_shp.add_argument("shp")
    p_shp.add_argument("--type", default=None)
    p_shp.add_argument("--label-field", default=None)
    p_shp.add_argument("--type-field", default=None)
    p_shp.add_argument("--default-type", default=None)
    p_shp.add_argument("--levels", default="24,23,22,21,20,19,18")
    p_shp.add_argument("--zooms", default=None)
    p_shp.add_argument("--section", choices=["POLYLINE", "POLYGON"],
                       default="POLYLINE")
    p_shp.add_argument("--snap", action="store_true")
    p_shp.add_argument("--end-level", action="store_true")
    p_shp.add_argument("--data-format", choices=["02d", "d"], default="02d")
    p_shp.add_argument("--out", default=None)
    p_shp.add_argument("--compile", action="store_true")
    p_shp.add_argument("--mkgmap", default="mkgmap.jar")
    p_shp.add_argument("--validate", action="store_true")
    p_shp.add_argument("--type-check", action="store_true")

    args = ap.parse_args()

    if args.cmd == "empty":
        levels = [int(x) for x in args.levels.split(",")]
        zooms = ([int(x) for x in args.zooms.split(",")]
                 if args.zooms else None)
        hdr = {}
        if args.simplify_level is not None:
            hdr["SimplifyLevel"] = args.simplify_level
        m = PolishMap.empty(args.name, levels=levels, zooms=zooms,
                            snap_to_grid=args.snap,
                            use_end_level=args.end_level,
                            header=hdr,
                            type_check=args.type_check)
        out = m.save(args.out or f"{args.name}.mp")
        print(f"saved {out}")
        print(m.summary())
        for e in m.validate():
            print(" -", e)

    elif args.cmd == "build":
        levels = [int(x) for x in args.levels.split(",")]
        zooms = ([int(x) for x in args.zooms.split(",")]
                 if args.zooms else None)
        code = None
        if args.type:
            code = (int(args.type, 16) if args.type.lower().startswith("0x")
                    else int(args.type, 16))
        default_t = (int(args.default_type, 16)
                     if args.default_type else None)
        m = PolishMap(args.name, levels=levels, zooms=zooms,
                      snap_to_grid=args.snap,
                      polygon_section=args.section,
                      use_end_level=args.end_level,
                      data_format=args.data_format,
                      type_check=args.type_check)
        m.add_from_shapefile(args.shp,
                             type_code=code,
                             label_field=args.label_field,
                             type_field=args.type_field,
                             default_type=default_t)
        out = m.save(args.out or f"{args.name}.mp")
        print(f"saved {out}")
        print(m.summary())
        if args.type_check:
            print(m.summary_types())
        if args.validate:
            for e in m.validate():
                print(" -", e)
        if args.compile:
            m.compile(mkgmap=args.mkgmap, mp_path=out)
    else:
        ap.print_help()


if __name__ == "__cli__" or __name__ == "__main__":
    _cli()