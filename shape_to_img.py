"""
shape_to_img.py (v3) — сборка карты выделов и кварталов на базе polish_map.

Два режима работы (переключается переменной MODE):
  MODE = "legacy"  — 1:1 повторяет оригинальный shape_to_img.py:
                     Data0..Data3 для выделов, Data0..Data5 для кварталов,
                     ручное упрощение в Python.
  MODE = "modern"  — современный режим cGPSmapper:
                     Data0 + EndLevel=N + SimplifyLevel,
                     без ручного упрощения — компилятор сам,
                     [DICTIONARY] для фильтрации по уровням.

Имена полей DBF задаются в блоке «Настройки полей DBF» ниже.
Если KV_FIELD или SKNR_FIELD пустые — скрипт спросит в интерактиве.
"""

from __future__ import annotations

import codecs
import os
import subprocess
import sys
import time
from tkinter import filedialog

import geopandas
import shapefile
from osgeo import ogr
from shapely.geometry import shape as shp_tool

from polish_map import PolishMap


# ============================================================
# РЕЖИМ РАБОТЫ
# ============================================================

MODE = "modern"          # "legacy" | "modern"


# ============================================================
# Настройки полей DBF
# ============================================================
#
# Смотри имена полей в QGIS → правый клик на слое → Open Attribute Table.
# Если оставить пустыми — скрипт спросит в интерактиве при запуске.
#
KV_FIELD   = "KV"        # ← поле с номером КВАРТАЛА
SKNR_FIELD = "SKNR"      # ← поле с номером ВЫДЕЛА


# ============================================================
# Параметры карты
# ============================================================

WORK_PERIOD_END  = 1761723404 + 61402996

MAP_LEVELS   = [24, 23, 22, 21, 20, 19, 18]
MAP_ZOOMS    = [0, 1, 2, 3, 4, 5, 6]
MAP_CODEPAGE = 1251

# --- Типы объектов ---
VYD_TYPE_LINE = 0x6          # линия выдела
VYD_TYPE_POI  = 0x1E00       # POI выдела (номер)
KV_TYPE_LINE  = 0x5          # линия квартала
KV_TYPE_POI   = 0x1400       # POI квартала (номер)

# --- Уровни видимости объектов ---
#   Data0 + EndLevel=max(levels) — объект виден на всех уровнях 0..max
VYD_LEVELS     = [0, 1, 2, 3]        # линии выделов: 0..3
VYD_POI_LEVELS = [0, 1, 2]           # POI выделов:   0..2
KV_LEVELS      = [0, 1, 2, 3, 4, 5]  # линии кварталов: 0..5
KV_POI_LEVELS  = [0, 1, 2, 3, 4]     # POI кварталов: 0..4

# --- Упрощение (только legacy) ---
VYD_SIMPLIFY_TOL  = 0.00005
VYD_SIMPLIFY_FROM = 1        # Data0 оригинал, Data1..3 упрощённые
KV_SIMPLIFY_TOL   = 0.00005
KV_SIMPLIFY_FROM  = 2        # Data0..1 оригинал, Data2..5 упрощённые

# --- Modern ---
MODERN_SIMPLIFY_LEVEL = 1     # 1..10 (больше = слабее сжатие)
MODERN_PREPROCESS     = "P"   # P — с полигонами, F — только линии
MODERN_USE_DICTIONARY = True  # генерировать [DICTIONARY]

# --- Обработка кварталов ---
KV_BUFFER = 0.0000001


# ============================================================
# Утилиты
# ============================================================

def resolve_fields(kv=None, sknr=None):
    """Возвращает (KV, SKNR), при необходимости — спрашивает."""
    if not kv:
        kv = input("имя поля с номером КВАРТАЛА (KV):   ").strip()
    if not sknr:
        sknr = input("имя поля с номером ВЫДЕЛА   (SKNR): ").strip()
    if not kv or not sknr:
        print("Ошибка: имена полей не могут быть пустыми")
        sys.exit(1)
    return kv, sknr


def check_work_period():
    if time.time() > WORK_PERIOD_END:
        print("рабочий период закончился")
        time.sleep(5)
        sys.exit()


def fix_geometry(path):
    """Проверка и исправление геометрии через ogr. Перезаписывает файл."""
    print("проверка файла на ошибки геометрии")
    print("в случае обнаружения, будет попытка внести исправления")
    print("и файл будет перезаписан")
    time.sleep(3)

    driver = ogr.GetDriverByName("ESRI Shapefile")
    ds = driver.Open(path, 1)
    layer = ds.GetLayer()

    error = 0
    for feature in layer:
        geom = feature.GetGeometryRef()
        if geom and not geom.IsValid():
            print("error")
            fixed = geom.MakeValid()
            error = 1
            if fixed:
                feature.SetGeometry(fixed)
                layer.SetFeature(feature)
            else:
                print(f"Could not fix geometry for feature FID: "
                      f"{feature.GetFID()}")
                error = 2
        else:
            print(f"Geometry for feature FID: {feature.GetFID()} "
                  f"is valid or empty.")

    if error == 1:
        print("были обнаружены ошибки, ошибки исправлены")
    elif error == 0:
        print("ошибок не обнаружено")
    else:
        print("были обнаружены ошибки, некоторые не исправлены")
    time.sleep(3)
    ds = None


def open_shapefile(path):
    """Открывает shapefile с явной кодировкой."""
    try:
        sf = shapefile.Reader(path, encoding="cp1251",
                              encodingErrors="ignore")
        print("загрузка 1")
    except UnicodeDecodeError:
        codecs.open(path, mode="r", encoding="cp1251")
        sf = shapefile.Reader(path, encoding="cp1251")
        print("загрузка 2")
    return sf


def shape_to_rings(shape):
    """Разбивает shape.points на кольца по shape.parts."""
    pts = shape.points
    parts = list(shape.parts) + [len(pts)]
    rings = []
    for i in range(len(parts) - 1):
        seg = pts[parts[i]:parts[i + 1]]
        rings.append([(float(x), float(y)) for x, y in seg])
    return rings


def iter_polygons(geom):
    """Возвращает список Polygon из geom (Polygon или MultiPolygon)."""
    if geom is None or geom.is_empty:
        return []
    gt = geom.geom_type
    if gt == "Polygon":
        return [geom]
    if gt == "MultiPolygon":
        return list(geom.geoms)
    return []


# ============================================================
# Создание карты
# ============================================================

def make_map(name, mode):
    """Создаёт PolishMap с настройками под режим."""

    if mode == "legacy":
        return PolishMap(
            name,
            levels=MAP_LEVELS,
            zooms=MAP_ZOOMS,
            codepage=MAP_CODEPAGE,
            polygon_section="POLYLINE",
            data_format="d",            # Data0, Level0, Zoom0
            crlf=True,
            snap_to_grid=False,
            use_end_level=False,
            header={
                "TypeSet":    "NG",
                "Preprocess": "F",
                "TreSize":    511,
                "RgnLimit":   127,
                "Copyright":  "this map cannot be sold",
                "LblCoding":  9,
            },
        )

    elif mode == "modern":
        return PolishMap(
            name,
            levels=MAP_LEVELS,
            zooms=MAP_ZOOMS,
            codepage=MAP_CODEPAGE,
            polygon_section="POLYLINE",
            data_format="d",            # Data0, Level0, Zoom0
            crlf=True,
            snap_to_grid=False,
            use_end_level=True,
            header={
                "TypeSet":       "NG",
                "Preprocess":    MODERN_PREPROCESS,
                "SimplifyLevel": MODERN_SIMPLIFY_LEVEL,
                "TreSize":       1000,
                "RgnLimit":      1024,
                "Copyright":     "this map cannot be sold",
                "LblCoding":     9,
            },
        )

    raise ValueError(f"Unknown mode: {mode}")


# ============================================================
# Добавление выделов
# ============================================================

def add_vydely(m, sf, shapes, SKNR, mode):
    """Добавляет выделы (линии + POI-центроиды)."""
    print(f"количество полигонов выделов - {len(shapes)}")

    # --- Линии выделов ---
    for shape in shapes:
        for ring in shape_to_rings(shape):
            if mode == "legacy":
                m.add_polygon(
                    ring,
                    type_code=VYD_TYPE_LINE,
                    levels=VYD_LEVELS,
                    tol=VYD_SIMPLIFY_TOL,
                    as_polygon=False,
                    simplify_from_level=VYD_SIMPLIFY_FROM,
                )
            else:  # modern
                m.add_polygon(
                    ring,
                    type_code=VYD_TYPE_LINE,
                    levels=VYD_LEVELS,       # [0,1,2,3] → EndLevel=3
                    as_polygon=False,
                )

    # --- Центроиды выделов (POI) ---
    for i, shape in enumerate(shapes):
        rec = sf.record(i)
        try:
            label = rec[SKNR]
        except (IndexError, KeyError) as e:
            print(f"  ⚠ не могу прочитать поле {SKNR!r} у feature {i}: {e}")
            continue

        geom = shp_tool(shape.__geo_interface__)
        if not geom.is_valid:
            geom = geom.buffer(0)
        p = geom.representative_point()

        if mode == "legacy":
            for lvl in VYD_POI_LEVELS:
                m.add_point(p.x, p.y,
                            type_code=VYD_TYPE_POI,
                            label=label,
                            levels=[lvl])
        else:
            m.add_point(p.x, p.y,
                        type_code=VYD_TYPE_POI,
                        label=label,
                        levels=VYD_POI_LEVELS)    # [0,1,2] → EndLevel=2


# ============================================================
# Добавление кварталов
# ============================================================

def add_kvartaly(m, file, KV, mode):
    """Dissolve по KV + добавить линии + POI-центроиды."""
    gdf = geopandas.read_file(file, encoding="cp1251")

    if KV not in gdf.columns:
        print(f"\n⚠ поле {KV!r} не найдено в шейпе!")
        print(f"  доступные поля: {list(gdf.columns)}")
        print(f"  поправь KV_FIELD в настройках или введи при запуске")
        sys.exit(1)

    dissolved = gdf.dissolve(by=KV)

    print("делаем маленький буфер для кварталов чтобы сгладить возможные "
          "промежутки в их геометрии")
    print("будет выведено предупреждение\n")

    dissolved["geometry"] = dissolved["geometry"].buffer(KV_BUFFER)
    dissolved = dissolved.explode()

    print(f"\nколичество полигонов кварталов - {len(dissolved)}")

    # --- Линии кварталов ---
    for kv_value, row in dissolved.iterrows():
        for poly in iter_polygons(row.geometry):
            if mode == "legacy":
                m.add_polygon(
                    list(poly.exterior.coords),
                    type_code=KV_TYPE_LINE,
                    levels=KV_LEVELS,
                    tol=KV_SIMPLIFY_TOL,
                    as_polygon=False,
                    simplify_from_level=KV_SIMPLIFY_FROM,
                )
            else:
                m.add_polygon(
                    list(poly.exterior.coords),
                    type_code=KV_TYPE_LINE,
                    levels=KV_LEVELS,        # [0,1,2,3,4,5] → EndLevel=5
                    as_polygon=False,
                )

    # --- Центроиды кварталов (POI) ---
    for kv_value, row in dissolved.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        p = geom.representative_point()

        if mode == "legacy":
            for lvl in KV_POI_LEVELS:
                m.add_point(p.x, p.y,
                            type_code=KV_TYPE_POI,
                            label=kv_value,
                            levels=[lvl])
        else:
            m.add_point(p.x, p.y,
                        type_code=KV_TYPE_POI,
                        label=kv_value,
                        levels=KV_POI_LEVELS)    # [0,1,2,3,4] → EndLevel=4


# ============================================================
# Dictionary (только modern)
# ============================================================

def add_dictionary(m, mode):
    """Генерирует [DICTIONARY] для фильтрации по уровням (modern)."""
    if mode != "modern" or not MODERN_USE_DICTIONARY:
        return

    try:
        # Полилинии — уровни 1..5
        for lvl in range(1, 6):
            m.add_dictionary_by_types(
                lvl, 40,                      # RGN40 = polylines
                [VYD_TYPE_LINE, KV_TYPE_LINE],
                max_pos=0x40,
            )

        # POI — по группе (старший байт)
        poi_types = [VYD_TYPE_POI, KV_TYPE_POI]
        max_pos = max((t >> 8) & 0xFF for t in poi_types)
        for lvl in range(1, 5):
            m.add_dictionary_by_types(lvl, 10, poi_types, max_pos=max_pos)

        print("  [DICTIONARY] сгенерирован")
    except Exception as e:
        print(f"  [DICTIONARY] пропущен: {e}")


# ============================================================
# main
# ============================================================

def main():
    print("=" * 60)
    print(f"shape_to_img v3   (режим: {MODE})")
    print("=" * 60)

    check_work_period()

    # --- поля DBF ---
    KV, SKNR = resolve_fields(KV_FIELD, SKNR_FIELD)
    print(f"поля: KV={KV!r}, SKNR={SKNR!r}")

    # --- ввод ---
    gpsfilename = input("как файл карты будет называться в gps? ").strip()
    if not gpsfilename:
        print("имя карты не может быть пустым")
        sys.exit(1)

    file = filedialog.askopenfilename(
        title="Выберите shapefile с выделами",
        filetypes=[("Shapefile", "*.shp"), ("Все файлы", "*.*")],
    )
    if not file:
        print("файл не выбран")
        sys.exit(1)

    fix = int(input("проверить геометрию? 0-нет, 1-да "))

    if fix == 1:
        fix_geometry(file)

    # --- открытие ---
    sf = open_shapefile(file)
    shapes = sf.shapes()

    # --- создание карты ---
    m = make_map(gpsfilename, MODE)
    print(f"\nкарта: {m.name!r}  id={m.map_id}  режим={MODE}")

    # --- выделы ---
    add_vydely(m, sf, shapes, SKNR, MODE)
    sf.close()

    # --- кварталы ---
    add_kvartaly(m, file, KV, MODE)

    # --- dictionary ---
    add_dictionary(m, MODE)

    # --- валидация ---
    errs = m.validate()
    if errs:
        print("\n⚠ validate() обнаружил проблемы:")
        for e in errs:
            print("  -", e)
    else:
        print("\nvalidate(): OK")

    # --- отчёт ---
    print()
    print(m.summary())

    # --- отчёт по типам (если есть garmin_types.py) ---
    try:
        st = m.summary_types()
        if st and "не подключён" not in st:
            print(st)
    except Exception:
        pass

    # --- сохранение ---
    mp_path = m.save()
    print(f"\nсохранено: {mp_path}")

    # --- компиляция ---
    print("\nок\n")
    print("запуск компиляции карты программой mkgmap")
    print(f"под именем {m.map_id}.img файл будет записан в папку с программой")
    print(f"карта в навигаторе будет отображаться как {gpsfilename}\n")

    subprocess.call([
        "java", "-jar", "mkgmap.jar",
        f"--mapname={m.map_id}",
        f"--code-page={MAP_CODEPAGE}",
        "--transparent",
        f"--description={gpsfilename}",
        mp_path,
    ])
    print("\nпроцесс создания карты завершен")
    os.system("pause")


if __name__ == "__main__":
    main()