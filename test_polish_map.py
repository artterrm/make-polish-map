"""
test_polish_map.py — проверка библиотеки polish_map.

Запуск:
    python test_polish_map.py
или через pytest:
    pytest test_polish_map.py -v

Проверяет:
  • Snap to grid
  • Форматирование координат
  • Auto-uppercase
  • Data00 / EndLevel
  • [POLYGON] / [POLYLINE]
  • Multi-ring полигоны
  • [DICTIONARY]
  • Валидацию
  • Экспорт из shapefile
  • Интеграцию с garmin_types
  • Производительность
"""

import os
import tempfile
import shutil
import time

from polish_map import (
    PolishMap,
    label_abbrev, label_with_height, shield,
    _round_half_away,
)


PASSED = 0
FAILED = 0


def check(cond, msg):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ✓ {msg}")
    else:
        FAILED += 1
        print(f"  ✗ FAIL: {msg}")


def section(title):
    print(f"\n=== {title} ===")


# ================================================================
# 1. Snap to grid
# ================================================================

def test_snap():
    section("Snap to grid")

    check(_round_half_away(0.5) == 1.0, "round(0.5) = 1")
    check(_round_half_away(1.5) == 2.0, "round(1.5) = 2")
    check(_round_half_away(-0.5) == -1.0, "round(-0.5) = -1")
    check(_round_half_away(-1.5) == -2.0, "round(-1.5) = -2")
    check(_round_half_away(2.4) == 2.0, "round(2.4) = 2")

    m = PolishMap("t", levels=[24, 23, 22], snap_to_grid=True)
    step = 360.0 / (1 << 24)
    val = 37.123456789
    snapped = m._snap(val, 24)
    k = snapped / step
    check(abs(k - round(k)) < 1e-6,
          f"snap: {snapped} кратно шагу {step}")
    check(abs(snapped - val) < step,
          "snap: результат рядом с исходным")

    m2 = PolishMap("t2", levels=[24], snap_to_grid=False)
    check(m2._snap(37.123456, 24) == 37.123456,
          "без snap значение не меняется")


# ================================================================
# 2. Форматирование координат
# ================================================================

def test_coords_format():
    section("Форматирование координат")

    m = PolishMap("t", levels=[24], data_format="02d")
    s = m._fmt_pt(37.123456, 55.123456, 0)
    check(s == "(55.12346,37.12346)", f"precision=5 → {s}")

    m2 = PolishMap("t2", levels=[26], data_format="02d")
    check(m2.precision == 6, "bits>=25 → precision=6")

    m3 = PolishMap("t3", levels=[24], data_format="02d", snap_to_grid=True)
    check(m3.precision == 7, "snap_to_grid → precision=7")


# ================================================================
# 3. Auto-uppercase
# ================================================================

def test_uppercase():
    section("Auto-uppercase")

    m = PolishMap("t", levels=[24], codepage=1251)
    check(m.auto_uppercase is True, "cp1251 → auto_uppercase=True")

    m2 = PolishMap("t", levels=[24], codepage=1252)
    check(m2.auto_uppercase is False, "cp1252 → auto_uppercase=False")

    m3 = PolishMap("t", levels=[24], codepage=1251, auto_uppercase=False)
    check(m3.auto_uppercase is False, "явное отключение работает")

    m4 = PolishMap("t", levels=[24], codepage=1251)
    m4.add_point(37.6, 55.7, 0x2A00, label="кафе ромашка")
    obj = m4._objects[0]
    check(obj["label"] == "КАФЕ РОМАШКА", "label → upper для cp1251")

    m5 = PolishMap("t", levels=[24], codepage=1252)
    m5.add_point(37.6, 55.7, 0x2A00, label="Cafe")
    check(m5._objects[0]["label"] == "Cafe",
          "label не меняется для cp1252")


# ================================================================
# 4. Data00 + EndLevel
# ================================================================

def test_end_level():
    section("Data00 + EndLevel")

    m = PolishMap("t", levels=[24, 23, 22, 21],
                  use_end_level=True, data_format="02d")
    m.add_line([(37.6, 55.7), (37.7, 55.8)], 0x06, label="дорога",
               levels=[0])
    p = m.save(os.path.join(tempfile.gettempdir(), "t_end.mp"))
    with open(p, encoding="cp1251") as f:
        txt = f.read()
    check("EndLevel=0" in txt, "EndLevel присутствует")
    check("Data00=" in txt, "Data00 присутствует")
    check("Data01=" not in txt, "Data01 отсутствует (end_level режим)")

    m2 = PolishMap("t", levels=[24, 23, 22, 21],
                   use_end_level=False, data_format="02d")
    m2.add_line([(37.6, 55.7), (37.7, 55.8)], 0x06, levels=[0, 1, 2])
    p2 = m2.save(os.path.join(tempfile.gettempdir(), "t_norm.mp"))
    with open(p2, encoding="cp1251") as f:
        txt2 = f.read()
    check("Data00=" in txt2 and "Data01=" in txt2 and "Data02=" in txt2,
          "обычный режим: Data00..Data02")


# ================================================================
# 5. POLYLINE vs POLYGON
# ================================================================

def test_sections():
    section("[POLYGON] vs [POLYLINE]")

    coords = [(37.6, 55.7), (37.7, 55.7), (37.7, 55.8), (37.6, 55.7)]

    m = PolishMap("t", levels=[24], polygon_section="POLYLINE")
    m.add_polygon(coords, 0x50, label="лес")
    p = m.save(os.path.join(tempfile.gettempdir(), "t_pl.mp"))
    with open(p, encoding="cp1251") as f:
        txt = f.read()
    check("[POLYLINE]" in txt and "[POLYGON]" not in txt,
          "polygon_section=POLYLINE → POLYLINE")

    m2 = PolishMap("t", levels=[24], polygon_section="POLYGON")
    m2.add_polygon(coords, 0x50)
    p2 = m2.save(os.path.join(tempfile.gettempdir(), "t_pg.mp"))
    with open(p2, encoding="cp1251") as f:
        txt2 = f.read()
    check("[POLYGON]" in txt2, "polygon_section=POLYGON → POLYGON")

    m3 = PolishMap("t", levels=[24], polygon_section="POLYLINE")
    m3.add_polygon(coords, 0x50, as_polygon=True)
    p3 = m3.save(os.path.join(tempfile.gettempdir(), "t_ov.mp"))
    with open(p3, encoding="cp1251") as f:
        txt3 = f.read()
    check("[POLYGON]" in txt3, "per-object as_polygon=True работает")


# ================================================================
# 6. Multi-ring
# ================================================================

def test_multi_ring():
    section("Multi-ring (outer + hole)")

    outer = [(37.6, 55.7), (37.7, 55.7), (37.7, 55.8),
             (37.6, 55.8), (37.6, 55.7)]
    hole = [(37.63, 55.73), (37.65, 55.73), (37.65, 55.75), (37.63, 55.73)]

    m = PolishMap("t", levels=[24], polygon_section="POLYGON")
    m.add_polygon(outer, 0x50, holes=[hole])
    p = m.save(os.path.join(tempfile.gettempdir(), "t_mr.mp"))
    with open(p, encoding="cp1251") as f:
        txt = f.read()
    check(txt.count("Data00=") == 2, "два Data00 (outer + hole)")
    check("PolygonEvaluate=Y" in txt, "PolygonEvaluate=Y авто")


# ================================================================
# 7. Dictionary
# ================================================================

def test_dictionary():
    section("[DICTIONARY]")

    m = PolishMap("t", levels=[24, 23, 22, 21])
    m.add_dictionary_by_types(1, 40, [1, 2, 3, 6], max_pos=8)
    m.add_dictionary_by_types(2, 40, [1, 2], max_pos=8)
    p = m.save(os.path.join(tempfile.gettempdir(), "t_dct.mp"))
    with open(p, encoding="cp1251") as f:
        txt = f.read()
    check("[DICTIONARY]" in txt, "секция [DICTIONARY] есть")
    check("Level01RGN40=11100100" in txt,
          "bitmask корректен (1,2,3,6 → 11100100)")
    check("Level02RGN40=11000000" in txt,
          "bitmask корректен (1,2 → 11000000)")


# ================================================================
# 8. Валидация
# ================================================================

def test_validate():
    section("validate()")

    m = PolishMap("t", levels=[24, 23, 22], zooms=[0, 1, 2],
                  data_levels=[0])
    errs = m.validate()
    check(len(errs) == 0,
          f"нормальная карта OK ({len(errs)} ошибок): {errs}")

    m2 = PolishMap("t", levels=[22, 23, 24], zooms=[0, 1, 2])
    errs2 = m2.validate()
    check(any("E021" in e for e in errs2),
          "E021: Level не убывают → ловится")

    m3 = PolishMap("t", levels=[24, 23, 22], zooms=[2, 1, 0])
    errs3 = m3.validate()
    check(any("E025" in e for e in errs3),
          "E025: Zoom не возрастают → ловится")

    m4 = PolishMap("t", levels=[24, 23, 22], header={"RgnLimit": 30})
    errs4 = m4.validate()
    check(any("RgnLimit" in e for e in errs4),
          "RgnLimit<50 → ловится")

    m5 = PolishMap("t", levels=[24, 23, 22], data_levels=[0])
    m5.add_point(0, 0, 0x0100, levels=[2])
    errs5 = m5.validate()
    check(any("последний уровень" in e for e in errs5),
          "объект на последнем уровне → ловится")


# ================================================================
# 9. Хелперы label
# ================================================================

def test_label_helpers():
    section("Хелперы label")

    check(label_abbrev("Россия", "RU") == "Россия~[0x1d]RU",
          "label_abbrev")
    check(label_with_height("Эльбрус", 5642) == "Эльбрус~[0x1f]5642",
          "label_with_height")
    check(shield("interstate", 11) == "~[0x01]11",
          "shield interstate")
    check(shield("small", 5) == "~[0x06]5",
          "shield small")


# ================================================================
# 10. Экспорт из shapefile
# ================================================================

def test_shapefile():
    section("add_from_shapefile")

    try:
        import shapefile as pyshp
    except ImportError:
        print("  (пропущено — pyshp не установлен)")
        return

    tmpdir = tempfile.mkdtemp()
    try:
        # --- line.shp ---
        w = pyshp.Writer(os.path.join(tmpdir, "lines.shp"),
                          shapeType=pyshp.POLYLINE)
        w.encoding = "cp1251"          # ← важно: писатель тоже cp1251
        w.field("name", "C", 50)
        w.field("type", "N", 5, 0)
        w.line([[(37.6, 55.7), (37.7, 55.8)]])
        w.record(name="Лесная дорога", type=6)
        w.line([[(37.7, 55.7), (37.8, 55.8)]])
        w.record(name="", type=22)
        w.close()

        m = PolishMap("shp_test", levels=[24, 23, 22],
                      polygon_section="POLYLINE")
        res = m.add_from_shapefile(
            os.path.join(tmpdir, "lines.shp"),
            type_field="type", label_field="name",
            type_hex=False)

        check(res["added"] == 2,
              f"добавлено 2 линии (got {res['added']})")
        check(res["types"] == {6: 1, 22: 1},
              f"типы распределены: {res['types']}")

        p = m.save(os.path.join(tmpdir, "out.mp"))
        with open(p, encoding="cp1251") as f:
            txt = f.read()
        check("Type=0x6" in txt, "Type=0x6 есть")
        check("Type=0x16" in txt, "Type=0x16 (=22 decimal) есть")
        check("Label=ЛЕСНАЯ ДОРОГА" in txt, "label upper")

        blocks = txt.split("[POLYLINE]")
        second = blocks[2].split("[END]")[0]
        check("Label=" not in second,
              "вторая линия без Label (пустое имя)")

        # --- polygon.shp ---
        w2 = pyshp.Writer(os.path.join(tmpdir, "polys.shp"),
                          shapeType=pyshp.POLYGON)
        w2.encoding = "cp1251"         # ← важно
        w2.field("kateg", "C", 20)
        # clockwise = exterior ring (по часовой стрелке)
        w2.poly([[(37.6, 55.7), (37.6, 55.8),
                  (37.7, 55.8), (37.7, 55.7), (37.6, 55.7)]])
        w2.record(kateg="ЛЕС")
        w2.poly([[(38.0, 56.0), (38.0, 56.1),
                  (38.1, 56.1), (38.1, 56.0), (38.0, 56.0)]])
        w2.record(kateg="БОЛОТО")
        w2.close()

        m2 = PolishMap("shp_test2", levels=[24, 23, 22],
                       polygon_section="POLYGON")
        res2 = m2.add_from_shapefile(
            os.path.join(tmpdir, "polys.shp"),
            type_field="kateg",
            type_map={"ЛЕС": 0x50, "БОЛОТО": 0x51},
            default_type=0x4F)

        check(res2["added"] == 2, "добавлено 2 полигона")
        check(0x50 in res2["types"] and 0x51 in res2["types"],
              f"type_map сработал: {res2['types']}")

    finally:
        shutil.rmtree(tmpdir)


# ================================================================
# 11. Интеграция с garmin_types.py
# ================================================================

def test_garmin_types():
    section("Интеграция garmin_types.py")

    try:
        import garmin_types as gt
    except ImportError:
        print("  (пропущено — garmin_types.py не найден)")
        return

    check(gt.type_name(0x50, "polygon") == "Forest",
          "type_name(0x50, polygon) = Forest")
    check(gt.type_category(0x50, "polygon") == "land",
          "type_category(0x50, polygon) = land")
    check(gt.type_name(0x2A00, "point") == "Dining",
          "type_name(0x2A00, point) = Dining")
    check(gt.known_type(0x06, "line") is True,
          "known_type(0x06, line) = True")
    check(gt.known_type(0x99, "polygon") is False,
          "known_type(0x99, polygon) = False")

    m = PolishMap("gt_test", levels=[24, 23, 22],
                  type_check=True, data_levels=[0])
    m.add_polygon([(0, 0), (1, 0), (1, 1), (0, 0)], 0x50)
    m.add_polygon([(0, 0), (1, 0), (1, 1), (0, 0)], 0x99)
    errs = m.validate()
    check(any("0x99" in e for e in errs),
          "type_check поймал 0x99 (несуществующий)")

    s = m.summary_types()
    check("Forest" in s and "Unknown" in s,
          "summary_types показывает Forest и Unknown")


# ================================================================
# 12. Производительность
# ================================================================

def test_perf():
    section("Производительность")

    t0 = time.time()
    m = PolishMap("perf", levels=[24, 23, 22, 21, 20], data_levels=[0])
    for i in range(1000):
        x = 30.0 + i * 0.001
        y = 50.0 + i * 0.001
        m.add_point(x, y, 0x2A00, label=f"poi_{i}")
    dt = time.time() - t0
    check(dt < 2.0, f"1000 add_point за {dt:.3f} сек (< 2 сек)")

    t0 = time.time()
    m.save(os.path.join(tempfile.gettempdir(), "perf.mp"))
    dt = time.time() - t0
    check(dt < 3.0, f"save() за {dt:.3f} сек (< 3 сек)")


# ================================================================
# main
# ================================================================

def main():
    print("=" * 60)
    print("Тесты polish_map")
    print("=" * 60)

    test_snap()
    test_coords_format()
    test_uppercase()
    test_end_level()
    test_sections()
    test_multi_ring()
    test_dictionary()
    test_validate()
    test_label_helpers()
    test_shapefile()
    test_garmin_types()
    test_perf()

    print("\n" + "=" * 60)
    print(f"Пройдено: {PASSED}   Провалено: {FAILED}")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())