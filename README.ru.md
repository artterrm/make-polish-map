
```markdown
[English](README.md) | **Русский**

# Библиотека Polish Map Python

Библиотека на Python для генерации карт в формате **Polish Format (.mp)** для компиляции в Garmin `.img` через `mkgmap` или `cgpsmapper`.

## Возможности

- Генерация пустой карты с настройкой уровней (`Level0`, `Zoom0`).
- Добавление точек (`[POI]`), линий (`[POLYLINE]`), полигонов (`[POLYGON]` или `[POLYLINE]`).
- Полигоны с внутренними кольцами (дырками).
- Поддержка режима `EndLevel` и прогрессивного упрощения (`SimplifyLevel`).
- Автоматическая генерация секции `[DICTIONARY]`.
- Snap-to-grid Garmin (round half away from zero).
- Встроенный справочник Garmin-типов (`garmin_types.py`).
- Импорт из Shapefile (`.shp`) и поддержка GeoPackage (`.gpkg`).
- Валидация ошибок перед компиляцией.

---

## Оглавление

1. [Установка и зависимости](#1-установка-и-зависимости)
2. [Быстрый старт](#2-быстрый-старт)
3. [Создание карты: параметры конструктора](#3-создание-карты-параметры-конструктора)
4. [Добавление объектов](#4-добавление-объектов)
5. [Чтение из shapefile](#5-чтение-из-shapefile)
6. [Адресные секции](#6-адресные-секции)
7. [Секция `[DICTIONARY]`](#7-секция-dictionary)
8. [Специальные коды Label](#8-специальные-коды-label)
9. [Валидация](#9-валидация)
10. [Отчёты](#10-отчёты)
11. [Сохранение и компиляция](#11-сохранение-и-компиляция)
12. [Интеграция с `garmin_types.py`](#12-интеграция-с-garmin_typespy)
13. [CLI](#13-cli)
14. [Полный список методов](#14-полный-список-методов)
15. [Полный список ключей заголовка](#15-полный-список-ключей-заголовка)
16. [Частые сценарии](#16-частые-сценарии)
17. [Типичные ошибки и как их решать](#17-типичные-ошибки-и-как-их-решать)

---

## 1. Установка и зависимости

**Обязательные:**
```bash
pip install shapely
```
*Shapely нужен для упрощения геометрии (`simplify`) и для `add_geometry`.*

**Опциональные:**
```bash
pip install pyshp        # для add_from_shapefile()
pip install geopandas    # для dissolve, чтения shapefile
```

**Структура проекта:**
```text
project/
├── polish_map.py        # основная библиотека
├── garmin_types.py      # опциональный справочник типов
├── mkgmap.jar           # для компиляции
└── ваш_скрипт.py
```
*Если `garmin_types.py` не найден — библиотека работает, но `type_check=True` игнорируется, `summary_types()` вернёт сообщение об ошибке.*

---

## 2. Быстрый старт

### Пустая карта
```python
from polish_map import PolishMap

m = PolishMap("my_map", levels=[24, 23, 22], zooms=[0, 1, 2])
m.save("my_map.mp")
```

### Карта с объектами
```python
from polish_map import PolishMap

m = PolishMap("forest", levels=[24, 23, 22], zooms=[0, 1, 2])

# Линия
m.add_line(
    coords=[(37.60, 55.70), (37.70, 55.80), (37.80, 55.85)],
    type_code=0x06,
    label="Лесная дорога",
)

# Точка
m.add_point(
    lon=37.65, lat=55.75,
    type_code=0x2A00,
    label="Кафе",
)

# Полигон (замкнутое кольцо)
m.add_polygon(
    coords=[(37.60, 55.70), (37.65, 55.70), (37.65, 55.75), (37.60, 55.75), (37.60, 55.70)],
    type_code=0x50,  # Forest
    label="Лес",
)

m.save()
m.compile()  # вызовет mkgmap
```
*Результат: `forest.mp` и `forest.img`.*

---

## 3. Создание карты: параметры конструктора

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

### `name` (обязательный)
Имя карты. Используется как `Name=` в заголовке, имя `.mp` файла и описание для GPS.
*(Если содержит пробелы/спецсимволы — лучше заменить на латиницу для имени файла, но `Name=` в шапке может быть на русском).*

### `map_id`
Уникальный ID карты (десятичное число). Если `None` — генерируется случайно в диапазоне `30000000..99999999`.
*Правила: должен быть `> 0` и `< 0x0FFFFFFF` (268435455).*

### `levels`
Список «бит на уровень» — точнее, `bits per coordinate` для каждого уровня карты. По умолчанию `[24, 23, 22, 21, 20, 19, 18]`.
**Правило:** значения должны **убывать**. Первый уровень — самый детальный.

| bits | шаг сетки | примерно |
| :--- | :--- | :--- |
| 24 | ~2.4 м | зум 0, детально |
| 23 | ~4.8 м | зум 1 |
| 22 | ~9.5 м | зум 2 |
| 21 | ~19 м | зум 3 |
| 20 | ~38 м | зум 4 |
| 19 | ~76 м | зум 5 |
| 18 | ~152 м | зум 6, обзорно |

### `zooms`
Список значений `Zoom#=` в заголовке. По умолчанию `list(range(len(levels)))`.
**Правило:** значения должны **возрастать**.

### `level_ranges`
Опционально. Список «btBitsRangeTo» для каждого уровня. Если не указан — не пишется в `.mp`.

### `codepage`
Кодовая страница. По умолчанию `1251` (кириллица).
Влияет на `CodePage=` в шапке, на кодировку самого `.mp` файла и на `auto_uppercase` (по умолчанию `True` для всех кроме 1252).

### `snap_to_grid`
Привязать координаты к сетке Garmin. По умолчанию `False`.
- координаты округляются к шагу `360 / 2^bits`
- GPSMapEdit не сдвинет вершины при загрузке `.mp`
- увеличение размера файла (precision = 7 знаков вместо 5)
**Когда использовать:** если дальше правишь `.mp` в GPSMapEdit → **да**. Если всё через mkgmap → можно и без (mkgmap сам снапит).

### `polygon_section`
Как по умолчанию писать полигоны — `[POLYLINE]` или `[POLYGON]`. По умолчанию `"POLYLINE"`.
Можно переопределить для каждого объекта через `as_polygon=`.

### `data_levels`
Список уровней, на которых объект виден по умолчанию. По умолчанию `[0, 1, 2, 3]`.

### `simplify_tol`
Допуск упрощения геометрии. По умолчанию `0.00005` (в градусах).
Поддерживает **четыре формы**:
- `число`: один tol для всех уровней после `simplify_from_level`
- `список`: tol по индексу в `levels` объекта
- `"auto"`: tol = половина шага сетки для каждого уровня
- `None`: без упрощения

### `simplify_from_level`
С какого уровня начинать упрощение. Если `None` — автоматически `min(levels) + 1`.

### `precision`
Знаков после запятой. Если `None` — автоматически: 7 при `snap_to_grid=True`, 6 если максимальный `bits >= 25`, 5 иначе.

### `use_end_level`
Режим Polish074: вместо `Data0..DataN` писать `Data0` + `EndLevel=N`. По умолчанию `False`.
**Что даёт:** `.mp` файл **в разы меньше** (нет дублирования координат); компилятор сам прогрессивно упрощает (если `SimplifyLevel` в шапке).
**Когда использовать:** совместимость с `SimplifyLevel`; уменьшение размера `.mp` и `.img`.

### `data_format`
Формат ключей: `"02d"` → `Data00, Level00, Zoom00` (стиль GPSMapEdit) или `"d"` → `Data0, Level0, Zoom0` (стиль твоего исходного скрипта).

### `crlf`
Использовать `\r\n` вместо `\n`. По умолчанию `True` (для Windows/GPSMapEdit).

### `auto_uppercase`
Автоматически переводить labels в верхний регистр. По умолчанию `None` — включается, если `codepage != 1252`.
*Причина: Garmin показывает нижний регистр только для cp1252. Для cp1251 (кириллица) метки должны быть в верхнем регистре.*

### `header`
Словарь с переопределением любых полей `[IMG ID]`.
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
Включить валидацию типов через `garmin_types.py`. По умолчанию `False`.

---

## 4. Добавление объектов

### `add_point(lon, lat, type_code, label=None, *, levels=None, extra=None)`
**Точка (`[POI]`).**
```python
m.add_point(37.60, 55.70, 0x2A00, label="Кафе", extra={
    "HouseNumber": "5",
    "CityName": "Москва",
    "RegionName": "Московская область",
    "CountryName": "Россия",
    "Zip": "101000",
    "Phone": "+7-999-1234567",
    "Text": ["Работает 9:00-21:00", "Wi-Fi есть"],
})
```

### `add_line(coords, type_code, label=None, *, levels=None, tol=None, direction=False, extra=None, simplify_from_level=None)`
**Линия (`[POLYLINE]`).**
```python
m.add_line(
    coords=[(37.60, 55.70), (37.70, 55.80)],
    type_code=0x06,
    label="Лесная дорога",
    direction=True,
    levels=[0, 1, 2],
    tol=0.00005,
)
```
*(`direction=True` добавляет `DirIndicator=1` в `.mp`)*

### `add_polygon(coords, type_code, label=None, *, holes=None, levels=None, tol=None, as_polygon=None, extra=None, simplify_from_level=None)`
**Замкнутое кольцо.** Может писаться как `[POLYLINE]` или `[POLYGON]`.
```python
# Простой полигон
m.add_polygon(coords, type_code=0x50, label="Лес")

# Полигон с дырками
m.add_polygon(coords, type_code=0x50, holes=[hole1_coords, hole2_coords])

# Явно [POLYGON] (заливка)
m.add_polygon(coords, 0x50, as_polygon=True)

# Явно [POLYLINE] (контур)
m.add_polygon(coords, 0x50, as_polygon=False)
```

### `add_geometry(geom, type_code, label=None, **kw)`
**Универсальный метод** — принимает любую shapely-геометрию.
```python
from shapely.geometry import Point, LineString, Polygon
m.add_geometry(Point(37.6, 55.7), 0x2A00)
m.add_geometry(LineString([(37.6, 55.7), (37.7, 55.8)]), 0x06)
m.add_geometry(Polygon([(37.6, 55.7), (37.65, 55.7), (37.65, 55.75), (37.6, 55.7)]), 0x50)
```

### `add_raw(text, before=True)`
Добавляет произвольный текстовый блок до или после объектов.
```python
m.add_raw("[COUNTRIES]\nCountry1=Россия~[0x1d]RU\n[END-Countries]", before=True)
```

---

## 5. Чтение из shapefile

### Простой вызов
```python
m.add_from_shapefile("vydely.shp", type_code=0x50, label_field="NUM")
```

### Откуда взять тип
Приоритет:
1. `type_map[значение type_field]`
2. `type_field` (число или hex)
3. `default_type`
4. `type_code`
5. пропустить фичу

```python
# Тип из строки через map
m.add_from_shapefile(
    "lines.shp",
    type_field="kateg",
    type_map={"ЛЕС": 0x50, "ПОЛЕ": 0x4F, "БОЛОТО": 0x51},
    default_type=0x4F,
    label_field="name"
)
```

### Все параметры
```python
m.add_from_shapefile(
    path,
    # --- тип ---
    type_code=None, type_field=None, type_map=None, type_hex=False, default_type=None,
    # --- label ---
    label_field=None, label2_field=None,
    # --- адресные поля ---
    house_field=None, street_field=None, city_field=None, region_field=None,
    country_field=None, zip_field=None, phone_field=None, web_field=None, text_field=None,
    # --- прочее ---
    subtype_field=None, dir_field=None, extra_fields=None, section=None,
    encoding="cp1251", auto_uppercase=None, geom_kw=None, verbose=False,
)
```

### Возвращаемое значение
Возвращает словарь `{'added': 1523, 'skipped': 4, 'types': {80: 800, 79: 400, ...}}`.

---

## 6. Адресные секции

Пишутся в `.mp` **до объектов**. Порядок: Countries → Regions → Cities → Dictionary → Highways → ZipCodes → объекты.

```python
m.add_country("Россия", abbrev="RU")
m.add_region("Московская область", country_idx=1, abbrev="MSK")
m.add_city("Москва", region_idx=1)
m.add_zipcode("101000")
m.add_highway("М-7", region_idx=1)
```
*(Для связи объекта с адресом используйте `extra={"CityIdx": 1, "ZipIdx": 1}`).*

---

## 7. Секция `[DICTIONARY]`

**Что это:** bitmask для фильтрации типов по уровням. Позволяет писать объект один раз, а виден он только на нужных уровнях.

### Вручную
```python
m.add_dictionary(level=1, rgn_class=40, bitmask="1111110000000000")
```
*(rgn_class: 10 = POI, 20 = City, 40 = Polyline, 80 = Polygon)*

### Автоматически из списка типов
```python
m.add_dictionary_by_types(level=1, rgn_class=40, types=[0x01, 0x02, 0x06], max_pos=0x40)
```

### По категориям (нужен `garmin_types.py`)
```python
m.dictionary_by_category("roads", kind="line")
m.dictionary_by_category("water", kind="polygon")
```

---

## 8. Специальные коды Label

```python
from polish_map import label_abbrev, label_with_height, shield

label_abbrev("Россия", "RU")          # "Россия~[0x1d]RU"
label_with_height("Эльбрус", 5642)     # "Эльбрус~[0x1f]5642"
shield("interstate", 11)              # "~[0x01]11"
```

---

## 9. Валидация

### `m.validate()`
Возвращает список строк с ошибками. Пустой список = всё ок.

**Что проверяется:**
- `E021`: Level# не убывают
- `E025`: Zoom# не возрастают
- `E032`: Level0 отсутствует
- `E033`: меньше 2 уровней
- `E036`: ID > 0x0FFFFFFF
- `W013/W015`: TreSize вне границ
- `RgnLimit < 50`
- `SimplifyLevel` вне 0.1..10
- `DrawPriority` вне 0..31
- `Lock=Y` без валидного `ProductCode`
- объект использует последний (пустой) уровень
- `Dictionary level` вне диапазона
- неизвестный тип (при `type_check=True`)

---

## 10. Отчёты

### `m.summary()`
Краткая сводка по карте (уровни, зумы, количество объектов, предупреждения валидации).

### `m.summary_types()`
Разбивка по типам с именами (нужен `garmin_types.py`).

---

## 11. Сохранение и компиляция

### `m.save(path=None)`
Записывает `.mp`. По умолчанию `f"{m.name}.mp"`.

### `m.compile(...)`
Запускает mkgmap.
```python
m.compile(
    mkgmap="mkgmap.jar",
    java="java",
    mp_path="my.mp",
    extra_args=["--reduce-point-density=4.0", "--route"],
)
```

---

## 12. Интеграция с `garmin_types.py`

Даёт валидацию, имена типов, категории и предикаты.
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
# Пустая карта
python polish_map.py empty my_map --levels 24,23,22 --snap --end-level

# Карта из shapefile
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

## 14. Полный список методов

### Конструктор и фабрика
- `PolishMap(name, **params)`
- `PolishMap.empty(name, *, levels, zooms, **kw)`

### Добавление объектов
- `add_point(lon, lat, type_code, label=None, *, levels, extra)`
- `add_line(coords, type_code, label=None, *, levels, tol, direction, extra, simplify_from_level)`
- `add_polygon(coords, type_code, label=None, *, holes, levels, tol, as_polygon, extra, simplify_from_level)`
- `add_geometry(geom, type_code, label=None, **kw)`
- `add_raw(text, before=True)`

### Адресные секции
- `add_country`, `add_region`, `add_city`, `add_zipcode`, `add_highway`

### Dictionary
- `add_dictionary`, `add_dictionary_by_types`, `dictionary_by_category`

### Shapefile
- `add_from_shapefile(path, type_code=None, label_field=None, **kw)`

### Служебные
- `validate()`, `summary()`, `summary_types()`, `save(path=None)`, `compile(...)`

### Хелперы (вне класса)
- `label_abbrev`, `label_with_height`, `shield`

---

## 15. Полный список ключей заголовка

| Ключ | По умолчанию | Что |
| :--- | :--- | :--- |
| `CodePage` | `1251` | кодовая страница |
| `LblCoding` | `9` | 9 = SBCS, 10 = MBCS |
| `TypeSet` | `"Garmin"` | если "Garmin" — не пишется |
| `Elevation` | `"M"` | M → Elevation=M, F → не пишется |
| `Preprocess` | `"F"` | N / G / P / F |
| `TreSize` | `511` | размер региона (реком. 1000-2000) |
| `TreMargin` | `0.0` | отступ |
| `RgnLimit` | `127` | макс. элементов в регионе (реком. 1024) |
| `Transparent` | `"N"` | N / Y / S |
| `POIIndex` | `"Y"` | индексировать POI |
| `POINumberFirst` | `"Y"` | номер дома перед улицей |
| `POIZipFirst` | `"Y"` | индекс перед улицей |
| `Copyright` | `"this map cannot be sold"` | копирайт |
| `SimplifyLevel` | `1` | 0.1..10, если ≠ 1 → пишется |
| `DrawPriority` | `25` | 0..31, если ≠ 25 → пишется |
| `Marine` | `"N"` | N / Y / B / X |
| `NT` | `"N"` | эксперимент. NT-формат |
| `Preview` | `"N"` | карта для MapSource |
| `MG` | `"N"` | lock on road |
| `Numbering` | `"N"` | нумерация домов |
| `Routing` | `"N"` | роутинг |
| `LeftSideTraffic` | `"N"` | левостороннее движение |
| `Invisible` | `"N"` | невидимая карта |
| `Lock` | `"N"` | блокировка |
| `ProductCode` | `None` | 1..60 |
| `FID` | `None` | семейство карт |
| `CountryName` | `None` | для автоиндексации городов |
| `RegionName` | `None` | для автоиндексации |
| `PolygonEvaluate` | `"auto"` | auto / Y / N |

---

## 16. Частые сценарии

### Лесная карта: выделы + кварталы

```python
from polish_map import PolishMap
import geopandas as gpd

m = PolishMap("forest", levels=[24,23,22,21,20,19,18],
              zooms=list(range(7)), snap_to_grid=True,
              polygon_section="POLYLINE", data_format="d")

# Выделы — линии
m.add_from_shapefile("vydely.shp", type_code=0x06,
                     label_field="NUM",
                     geom_kw={"levels": [0,1,2,3]})

# Центроиды выделов — POI
gdf = gpd.read_file("vydely.shp", encoding="cp1251")
for _, row in gdf.iterrows():
    p = row.geometry.representative_point()
    m.add_point(p.x, p.y, 0x1E00, label=str(row["NUM"]),
                levels=[0,1,2])

# Кварталы — dissolve + буфер
dissolved = gdf.dissolve(by="KV").buffer(0.0000001).explode()
for kv, row in dissolved.items():
    for poly in ([row] if row.geom_type == "Polygon" else row.geoms):
        m.add_polygon(list(poly.exterior.coords), 0x05, levels=[0,1,2,3,4,5])

m.save()
m.compile()
```

### Роутинговая карта

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

### Экспорт с прогрессивным упрощением

```python
m = PolishMap("forest", levels=[24,23,22,21,20],
              simplify_tol="auto",  # tol = полшага сетки на каждом уровне
              use_end_level=True,
              header={"SimplifyLevel": 2, "Preprocess": "P"})

m.add_from_shapefile("vydely.shp", type_code=0x50,
                     geom_kw={"levels": [0,1,2,3,4]})
m.save()
```

---

## 17. Типичные ошибки и как их решать

### `ModuleNotFoundError: No module named 'polish_map'`
Файл `polish_map.py` не лежит рядом со скриптом, либо у него расширение `.pyc` / `.txt`.
**Решение:** убедиться, что файл называется ровно `polish_map.py` (Windows → Вид → Расширения имён файлов).

### `IndentationError: unexpected indent`
Съехал отступ в `polish_map.py` — обычно после копипаста.
**Решение:** открыть файл, включить показ пробелов, убедиться что `def` на 4 пробела, тело — на 8/12.

### `E036: ID=... > 0x0FFFFFFF`
`map_id` слишком большой. **Решение:** использовать `map_id <= 268435455`.

### Объект использует level=N, но последний уровень ... пустой
Ты добавил объект на уровне, который должен быть **пустым**.
**Решение:** уменьшить `levels=[...]` или добавить ещё уровень. `Levels=N` означает, что доступны уровни `0..N-2`, а `N-1` — пустой.

### `Type=0x99 неизвестен для polygon`
При `type_check=True` — тип не найден в таблице `garmin_types.py`. **Решение:** либо исправить тип, либо отключить `type_check=False`.

### Метки не отображаются на навигаторе
Наиболее частая причина — кириллица в нижнем регистре. Для `codepage != 1252` **все labels должны быть ЗАГЛАВНЫМИ**.
**Решение:** `auto_uppercase=True` (по умолчанию для cp1251).

### Snap to grid не помогает, GPSMapEdit всё равно сдвигает
`precision` слишком маленькая. Для `snap_to_grid=True` нужно 7 знаков — ставь `precision=7`.
```

---
### Что в итоге получится на GitHub
Когда ты зальешь оба этих файла в репозиторий:
1. Открывая репозиторий, GitHub по умолчанию покажет `README.md` (на английском).
2. В самой первой строке будет написано: **English** | [Русский]. Если нажать на "Русский", откроется русская версия.
3. В русской версии сверху будет ссылка обратно на английскую. Это стандартный и очень удобный подход в Open Source.