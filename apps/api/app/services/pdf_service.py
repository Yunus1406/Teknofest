"""Faz C.6 — Optimizasyon Raporu'nu PDF'e döker. Girdi, `report_service.
build_optimization_report_data()`'nın ürettiği 16 bölümlük sözlüktür; bu
modül SADECE render eder, hiçbir sayı/metin burada YENİDEN hesaplanmaz ya
da uydurulmaz. Kütüphane: `reportlab` (mevcut, standart, saf-Python
kurulan bir PDF üretim kütüphanesi — yeniden icat edilmedi).

Türkçe karakter notu: reportlab'ın yerleşik 14 standart fontu (Helvetica
vb.) WinAnsi/cp1252 kodlamasını kullanır ve ğ/ş/ı/İ gibi Türkçe'ye özgü
harfleri TAŞIMAZ. Bu yüzden çalışma zamanında bir TTF font aranır
(Windows'ta Arial, Linux'ta DejaVu Sans — bkz. Dockerfile'daki
`fonts-dejavu-core` paketi) ve bulunursa kaydedilir; hiçbiri yoksa
Helvetica'ya düşülür (üretim ÇÖKMEZ, ama Türkçe karakterler bozuk
görünebilir — bu durum bilinçli bir MVP sınırlaması, sessizce geçilmiyor)."""
import base64
import os
from datetime import datetime
from io import BytesIO

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- Marka renk paleti (bkz. Faz 1 tasarım spesifikasyonu) -----------------
PETROL = colors.HexColor("#0F4A4D")
INK = colors.HexColor("#13221E")
VIRGIN = colors.HexColor("#C97A3D")
PCR = colors.HexColor("#3E8F63")
REGRANUL = colors.HexColor("#8A8F82")
WARN = colors.HexColor("#B23A48")
SURFACE = colors.HexColor("#F6F7F5")

# --- Türkçe karakter destekli TTF font (varsa) ------------------------------
_TTF_CANDIDATES = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]

BODY_FONT = "Helvetica"
BODY_FONT_BOLD = "Helvetica-Bold"

for _regular, _bold in _TTF_CANDIDATES:
    if os.path.isfile(_regular) and os.path.isfile(_bold):
        try:
            pdfmetrics.registerFont(TTFont("ReceteOS-Body", _regular))
            pdfmetrics.registerFont(TTFont("ReceteOS-Body-Bold", _bold))
            BODY_FONT = "ReceteOS-Body"
            BODY_FONT_BOLD = "ReceteOS-Body-Bold"
            break
        except Exception:
            continue  # bu aday kaydedilemedi, sıradakini dene


_STYLES = getSampleStyleSheet()
STYLE_TITLE = ParagraphStyle(
    "ROTitle", parent=_STYLES["Title"], fontName=BODY_FONT_BOLD, fontSize=20, textColor=PETROL, spaceAfter=4,
)
STYLE_SUBTITLE = ParagraphStyle(
    "ROSubtitle", parent=_STYLES["Normal"], fontName=BODY_FONT, fontSize=11, textColor=INK, spaceAfter=14,
)
STYLE_H1 = ParagraphStyle(
    "ROH1", parent=_STYLES["Heading1"], fontName=BODY_FONT_BOLD, fontSize=14, textColor=PETROL,
    spaceBefore=14, spaceAfter=6, borderColor=PETROL, borderWidth=0,
)
STYLE_H2 = ParagraphStyle(
    "ROH2", parent=_STYLES["Heading2"], fontName=BODY_FONT_BOLD, fontSize=11, textColor=INK, spaceBefore=8, spaceAfter=4,
)
STYLE_BODY = ParagraphStyle("ROBody", parent=_STYLES["Normal"], fontName=BODY_FONT, fontSize=9.5, textColor=INK, leading=13)
STYLE_SMALL = ParagraphStyle("ROSmall", parent=_STYLES["Normal"], fontName=BODY_FONT, fontSize=8, textColor=colors.HexColor("#5A6B65"))
STYLE_DISCLAIMER = ParagraphStyle(
    "RODisclaimer", parent=_STYLES["Normal"], fontName=BODY_FONT, fontSize=8, textColor=WARN, spaceBefore=6,
)
STYLE_BIG_STAT = ParagraphStyle(
    "ROBigStat", parent=_STYLES["Normal"], fontName=BODY_FONT_BOLD, fontSize=22, textColor=PETROL, alignment=TA_CENTER,
)
STYLE_BIG_STAT_LABEL = ParagraphStyle(
    "ROBigStatLabel", parent=_STYLES["Normal"], fontName=BODY_FONT, fontSize=9, textColor=INK, alignment=TA_CENTER,
)

_TABLE_HEADER_STYLE = [
    ("BACKGROUND", (0, 0), (-1, 0), PETROL),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), BODY_FONT_BOLD),
    ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8DBD6")),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SURFACE]),
]


def _p(text: str, style: ParagraphStyle = STYLE_BODY) -> Paragraph:
    return Paragraph(text if text is not None else "—", style)


def _dash(v) -> str:
    return "—" if v is None else str(v)


def _fmt_num(v, decimals: int = 2, unit: str = "") -> str:
    if v is None or not isinstance(v, (int, float)):
        return "—"
    return f"{v:.{decimals}f}{unit}"


def _fmt_pct(v) -> str:
    if v is None or not isinstance(v, (int, float)):
        return "—"
    return f"%{v:.1f}"


def _test_result_label(v: str | None) -> str:
    # Faz D.2 — ASLA sadece 'passed' bool'undan Geçti/Kaldı üretilmez;
    # 'beklemede' (kriter/ölçüm tanımsız) her zaman ayrı bir etiket alır.
    return {
        "basarili": "Geçti",
        "basarisiz": "Kaldı",
        "beklemede": "Test Edilmedi",
    }.get(v, "Test Edilmedi")


def _verdict_label(v: str | None) -> str:
    return {
        "uygun_gorunuyor": "Uygun Görünüyor",
        "inceleme_gerekli": "İnceleme Gerekli",
        "uygun_degil": "Uygun Değil",
        "veri_eksik": "Veri Eksik",
        "henuz_metodoloji_yok": "Henüz Uygulanabilir Metodoloji Bulunmuyor",
    }.get(v, v or "—")


def _table(rows: list[list], col_widths: list[float] | None = None) -> Table:
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(_TABLE_HEADER_STYLE))
    return t


def _qr_flowable(passport: dict | None) -> list:
    """QR SADECE reçetenin gerçek bir Dijital Ürün Pasaportu VARSA
    eklenir — pasaport yoksa bu blok tamamen atlanır, sahte/boş bir QR
    ASLA üretilmez."""
    if not passport or not passport.get("qr_code_data_uri") or not passport.get("passport_no"):
        return []
    try:
        raw_b64 = passport["qr_code_data_uri"].split(",", 1)[1]
        png_bytes = base64.b64decode(raw_b64)
        img = Image(BytesIO(png_bytes), width=30 * mm, height=30 * mm)
    except Exception:
        return []
    return [
        PageBreak(),
        _p("Dijital Pasaportu Görüntüle", STYLE_H1),
        img,
        _p(f"Pasaport No: {passport['passport_no']}", STYLE_SMALL),
        _p("QR kodu okutulduğunda ürünün genel Dijital Ürün Pasaportu web sayfası açılır.", STYLE_SMALL),
    ]


# --- Bölüm render fonksiyonları (16 bölüm, sırayla) -------------------------

def _section_cover(data: dict) -> list:
    kapak = data["kapak"]
    story = [
        _p("Reçete OS — Otomatik Optimizasyon Raporu", STYLE_TITLE),
        _p(
            f"{_dash(kapak.get('company_name'))} · {_dash(kapak.get('product_name'))}"
            + (f" ({kapak['sku_code']})" if kapak.get("sku_code") else ""),
            STYLE_SUBTITLE,
        ),
        _table(
            [
                ["Alan", "Değer"],
                ["Optimizasyon ID", _dash(kapak.get("optimization_run_id"))],
                ["Doğrulanmış Reçete", f"{kapak['recipe_id']} (V{kapak['recipe_version']})"],
                ["Rapor Tarihi", datetime.fromisoformat(kapak["generated_at"]).strftime("%d.%m.%Y %H:%M")],
            ],
            col_widths=[45 * mm, 120 * mm],
        ),
        Spacer(1, 10),
    ]
    return story


def _section_executive_summary(data: dict) -> list:
    ys = data["yonetici_ozeti"]
    story = [_p("2. Yönetici Özeti", STYLE_H1), _p(ys["narrative"], STYLE_BODY)]
    if ys["has_reference"] and ys["gains_pct"]:
        rows = [["Kalem", "Değişim"]]
        labels = [
            ("virgin_azalimi_pct", "Virgin ↓"), ("pcr_artisi_pct", "PCR ↑"),
            ("hammadde_azaltimi_pct", "Hammadde ↓"), ("fire_azaltimi_pct", "Fire ↓"),
            ("enerji_azaltimi_pct", "Enerji ↓"), ("karbon_azaltimi_pct", "Karbon ↓"),
            ("maliyet_azaltimi_pct", "Maliyet ↓"),
        ]
        for key, label in labels:
            rows.append([label, _fmt_pct(ys["gains_pct"].get(key))])
        story.append(Spacer(1, 6))
        story.append(_table(rows, col_widths=[60 * mm, 40 * mm]))
    elif ys.get("realized_absolute_per_1000_units"):
        p1000 = ys["realized_absolute_per_1000_units"]
        rows = [["Kalem (1.000 ambalaj başına)", "Gerçekleşen"]]
        for key, label, unit in [
            ("virgin_kg", "Virgin", " kg"), ("pcr_kg", "PCR", " kg"), ("regranul_kg", "PIR-Regranül", " kg"),
            ("karbon_kg_co2", "Karbon", " kg CO2"), ("fire_kg", "Fire", " kg"), ("enerji_kwh", "Enerji", " kWh"),
        ]:
            v = p1000.get(key)
            rows.append([label, _fmt_num(v, 2, unit) if isinstance(v, (int, float)) else "—"])
        story.append(Spacer(1, 6))
        story.append(_table(rows, col_widths=[70 * mm, 40 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_packaging_info(data: dict) -> list:
    info = data.get("ambalaj_bilgileri")
    if not info:
        return [_p("3. Ambalaj Bilgileri", STYLE_H1), _p("Ambalaj bilgisi bulunamadı.", STYLE_BODY)]
    dims = info.get("dimensions") or {}
    dims_text = ", ".join(f"{k}: {v}" for k, v in dims.items() if v is not None) or "—"
    rows = [
        ["Alan", "Değer"],
        ["Tür", _dash(info["packaging_type"])],
        ["Kullanım Alanı", _dash(info["usage_area"])],
        ["Ürün", _dash(info["product"])],
        ["Boyutlar", dims_text],
        ["Hedef Pazar", _dash(info["target_market"])],
        ["Gıda Teması", "Evet" if info["food_contact"] else "Hayır"],
        ["Hedef Üretim Miktarı", f"{info['target_volume_units']:,}".replace(",", ".")],
    ]
    return [_p("3. Ambalaj Bilgileri", STYLE_H1), _table(rows, col_widths=[45 * mm, 120 * mm]), Spacer(1, 10)]


def _section_reference(data: dict) -> list:
    ref = data["referans_recete"]
    story = [_p("4. Referans Reçete", STYLE_H1)]
    if not ref["has_reference"]:
        story.append(_p(ref["note"], STYLE_BODY))
    else:
        r = ref["reference"]
        rows = [
            ["Alan", "Değer"],
            ["Virgin / PCR / PIR-Regranül", f"{_fmt_pct(r['virgin_pct'])} / {_fmt_pct(r['pcr_pct'])} / {_fmt_pct(r['regranule_pct'])}"],
            ["Toplam Kalınlık", _fmt_num(r["total_micron"], 0, " µm")],
            ["Maliyet", _fmt_num(r["cost_per_kg"], 2, " TL/kg")],
            ["Karbon", _fmt_num(r["carbon_kg_co2_per_kg"], 3, " kg CO2/kg")],
        ]
        story.append(_table(rows, col_widths=[55 * mm, 110 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_optimization_process(data: dict) -> list:
    proc = data["optimizasyon_sureci"]
    story = [_p("5. Optimizasyon Süreci", STYLE_H1)]
    if not proc["applicable"]:
        story.append(_p(proc["note"], STYLE_BODY))
    else:
        rows = [
            ["Alan", "Değer"],
            ["Üretilen Aday Sayısı", _dash(proc.get("generated_candidate_count"))],
            ["Kısıt Motorundan Geçen", _dash(proc.get("survived_constraint_engine_count"))],
            ["Finalist Sayısı", _dash(proc.get("finalist_count"))],
            ["Oran Adımı", _fmt_num(proc.get("ratio_step_pct"), 0, "%")],
        ]
        story.append(_table(rows, col_widths=[65 * mm, 100 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_eliminated(data: dict) -> list:
    elim = data["neden_elendi"]
    story = [_p("6. Neden Elendi?", STYLE_H1)]
    if not elim["applicable"] or elim["note"]:
        story.append(_p(elim.get("note") or "—", STYLE_BODY))
    if elim["items"]:
        for item in elim["items"]:
            story.append(_p(f"• {item.get('composition_summary', '—')}", STYLE_BODY))
            story.append(_p(item.get("summary_text", ""), STYLE_SMALL))
    story.append(Spacer(1, 10))
    return story


def _section_selected_recipe(data: dict) -> list:
    sel = data["secilen_recete"]
    story = [_p("7. Seçilen Reçete", STYLE_H1)]
    rows = [
        ["Alan", "Değer"],
        ["Versiyon", f"V{sel['version']} ({sel['status']})"],
        ["Doğrulandı mı?", "Evet" if sel["is_verified"] else "Hayır"],
        ["Toplam Kalınlık", _fmt_num(sel["total_micron"], 0, " µm")],
        ["Üretim Hattı", _dash(sel.get("line_name"))],
    ]
    story.append(_table(rows, col_widths=[55 * mm, 110 * mm]))
    if sel["layers"]:
        story.append(Spacer(1, 6))
        layer_rows = [["Katman", "Malzeme", "Tür", "Oran"]]
        for layer in sel["layers"]:
            material = layer.get("material") or {}
            layer_rows.append(
                [
                    layer.get("layer_label", "—"),
                    _dash(material.get("name")),
                    _dash(material.get("material_type")),
                    _fmt_pct(layer.get("ratio_pct")),
                ]
            )
        story.append(_table(layer_rows, col_widths=[20 * mm, 75 * mm, 30 * mm, 25 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_estimated_results(data: dict) -> list:
    est = data["tahmini_sonuclar"]
    rows = [
        ["Alan", "Değer"],
        ["Virgin / PCR / PIR-Regranül", f"{_fmt_pct(est['virgin_pct'])} / {_fmt_pct(est['pcr_pct'])} / {_fmt_pct(est['regranule_pct'])}"],
        ["Maliyet (tahmini)", _fmt_num(est["cost_per_kg"], 2, " TL/kg")],
        ["Karbon (tahmini)", _fmt_num(est["carbon_kg_co2_per_kg"], 3, " kg CO2/kg")],
    ]
    return [_p("8. Tahmini Sonuçlar (Aşama 8)", STYLE_H1), _table(rows, col_widths=[55 * mm, 110 * mm]), Spacer(1, 10)]


def _section_production_results(data: dict) -> list:
    prod = data["gercek_uretim_sonuclari"]
    story = [_p("9. Gerçek Üretim Sonuçları", STYLE_H1)]
    if not prod["orders"]:
        story.append(_p("Bu reçete için henüz bir üretim emri kaydı yok.", STYLE_BODY))
        story.append(Spacer(1, 10))
        return story
    for order in prod["orders"]:
        rows = [
            ["Alan", "Değer"],
            ["Durum", _dash(order["status"])],
            ["Operatör", _dash(order["operator"])],
            ["Üretilen / Planlanan", f"{order['total_produced_units']:,} / {order['scheduled_qty_units']:,}".replace(",", ".")],
            ["Süre", _fmt_num(order["duration_minutes"], 0, " dk")],
            ["Ortalama Hat Hızı", _fmt_num(order["avg_line_speed_m_min"], 1, " m/dk")],
            ["Toplam Enerji", _fmt_num(order["total_energy_kwh"], 2, " kWh")],
            ["Toplam Fire", _fmt_num(order["total_waste_kg"], 2, " kg")],
            ["Veri Kaynağı", _dash(order["data_source"])],
        ]
        story.append(_table(rows, col_widths=[55 * mm, 110 * mm]))
        story.append(Spacer(1, 6))
    story.append(Spacer(1, 4))
    return story


def _section_physical_verification(data: dict) -> list:
    tests = data["fiziksel_dogrulama"]["tests"]
    story = [_p("10. Fiziksel Doğrulama", STYLE_H1)]
    if not tests:
        story.append(_p("Bu reçete için henüz kayıtlı bir fiziksel test yok.", STYLE_BODY))
    else:
        rows = [["Test", "Sonuç", "Hedef Aralık", "Yöntem", "Durum"]]
        for t in tests:
            target = f"{t['target_min']}–{t['target_max']} {t['unit']}" if t["target_min"] is not None and t["target_max"] is not None else "—"
            rows.append(
                [
                    t["test_type"],
                    f"{t['value']} {t['unit']}",
                    target,
                    _dash(t["test_method"]),
                    _test_result_label(t.get("result")),
                ]
            )
        story.append(_table(rows, col_widths=[28 * mm, 28 * mm, 35 * mm, 45 * mm, 20 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_sustainability(data: dict) -> list:
    per_1000 = data["surdurulebilirlik_performansi"]["per_1000_units"]
    story = [_p("11. Sürdürülebilirlik Performansı (1.000 satılabilir ambalaj başına)", STYLE_H1)]
    if not per_1000:
        story.append(_p("Sürdürülebilirlik verisi henüz hesaplanmadı.", STYLE_BODY))
        story.append(Spacer(1, 10))
        return story
    rows = [["Kalem", "Değer"]]
    for key, label, unit in [
        ("virgin_kg", "Virgin", " kg"), ("pcr_kg", "PCR", " kg"), ("regranul_kg", "PIR-Regranül", " kg"),
        ("karbon_kg_co2", "Karbon", " kg CO2"), ("fire_kg", "Fire", " kg"), ("enerji_kwh", "Enerji", " kWh"),
    ]:
        v = per_1000.get(key)
        rows.append([label, _fmt_num(v, 2, unit) if isinstance(v, (int, float)) else "—"])
    story.append(_table(rows, col_widths=[70 * mm, 60 * mm]))
    if per_1000.get("karbon_veri_kalitesi"):
        story.append(_p(f"Karbon Veri Kalitesi: {per_1000['karbon_veri_kalitesi']}", STYLE_SMALL))
    if per_1000.get("_uyari"):
        story.append(_p(per_1000["_uyari"], STYLE_DISCLAIMER))
    story.append(Spacer(1, 10))
    return story


def _section_ppwr(data: dict) -> list:
    ppwr = data["ppwr_on_uyum"]
    story = [_p("12. PPWR Ön Uyum Değerlendirmesi", STYLE_H1)]
    if not ppwr["items"]:
        story.append(_p("Bu reçete için mevzuat değerlendirmesi bulunamadı.", STYLE_BODY))
    else:
        rows = [["Madde", "Sonuç"]]
        for item in ppwr["items"]:
            rows.append([f"{_dash(item['article'])} ({_dash(item['regulation_code'])})", _verdict_label(item["verdict"])])
        story.append(_table(rows, col_widths=[110 * mm, 50 * mm]))
    story.append(_p(ppwr["disclaimer"], STYLE_DISCLAIMER))
    story.append(Spacer(1, 10))
    return story


def _section_climate(data: dict) -> list:
    c = data["iklim_dongusellik"]
    story = [_p(f"13. {c['perspective_label']}", STYLE_H1)]
    rows = [
        ["Kalem", "Değer"],
        ["Virgin / PCR / PIR-Regranül", f"{_fmt_pct(c['virgin_pct'])} / {_fmt_pct(c['pcr_pct'])} / {_fmt_pct(c['regranule_pct'])}"],
        ["Karbon Yoğunluğu", _fmt_num(c["carbon_kg_co2_per_kg"], 3, " kg CO2/kg")],
        ["Fire (1.000 ambalaj)", _fmt_num(c["fire_kg_per_1000"], 2, " kg")],
        ["Enerji (1.000 ambalaj)", _fmt_num(c["enerji_kwh_per_1000"], 2, " kWh")],
    ]
    story.append(_table(rows, col_widths=[65 * mm, 100 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_data_traceability(data: dict) -> list:
    dt = data["veri_izlenebilirligi"]
    story = [_p("14. Veri ve Hesaplama İzlenebilirliği", STYLE_H1)]
    story.append(_p(f"Üretim verisi kaynağı: {', '.join(dt['production_data_sources']) or '—'}", STYLE_BODY))
    story.append(_p(f"Fiziksel test verisi kaynağı: {', '.join(dt['physical_test_sources']) or '—'}", STYLE_BODY))
    if dt["carbon_ef_sources"]:
        rows = [["Malzeme", "EF (kg CO2e/kg)", "Kaynak"]]
        for ef in dt["carbon_ef_sources"]:
            rows.append([_dash(ef["material_name"]), _fmt_num(ef["ef_value"], 3), _dash(ef["source"])])
        story.append(Spacer(1, 4))
        story.append(_table(rows, col_widths=[55 * mm, 35 * mm, 70 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_recipe_traceability(data: dict) -> list:
    history = data["recete_izlenebilirligi"]
    story = [_p("15. Reçete İzlenebilirliği", STYLE_H1)]
    if not history:
        story.append(_p("Versiyon geçmişi bulunamadı.", STYLE_BODY))
    else:
        rows = [["Versiyon", "Durum", "Doğrulandı mı?", "Tarih"]]
        for v in history:
            created = v["created_at"]
            created_str = created.strftime("%d.%m.%Y") if hasattr(created, "strftime") else str(created)
            rows.append([f"V{v['version']}", v["status"], "Evet" if v["is_verified"] else "Hayır", created_str])
        story.append(_table(rows, col_widths=[25 * mm, 45 * mm, 35 * mm, 35 * mm]))
    story.append(Spacer(1, 10))
    return story


def _section_conclusion(data: dict) -> list:
    return [_p("16. Sonuç", STYLE_H1), _p(data["sonuc"]["summary_text"], STYLE_BODY)]


def render_technical_report(data: dict, passport: dict | None = None) -> bytes:
    """16 bölümün TAMAMI, detaylı Teknik Rapor."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
        title="Reçete OS — Optimizasyon Raporu",
    )
    story: list = []
    story += _section_cover(data)
    story += _section_executive_summary(data)
    story += _section_packaging_info(data)
    story += _section_reference(data)
    story += _section_optimization_process(data)
    story += _section_eliminated(data)
    story += _section_selected_recipe(data)
    story += _section_estimated_results(data)
    story += _section_production_results(data)
    story += _section_physical_verification(data)
    story += _section_sustainability(data)
    story += _section_ppwr(data)
    story += _section_climate(data)
    story += _section_data_traceability(data)
    story += _section_recipe_traceability(data)
    story += _section_conclusion(data)
    story += _qr_flowable(passport)
    doc.build(story)
    return buf.getvalue()


def render_executive_summary(data: dict, passport: dict | None = None) -> bytes:
    """1-2 sayfalık, sade dilli Yönetici Özeti. Aynı `data` sözlüğünü
    kullanır (rapor §2 ile birebir aynı hesap, bkz. report_service.
    build_executive_summary) — sadece çok daha kısa render edilir."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
        title="Reçete OS — Yönetici Özeti",
    )
    kapak = data["kapak"]
    ys = data["yonetici_ozeti"]
    story: list = [
        _p("Reçete OS — Yönetici Özeti", STYLE_TITLE),
        _p(
            f"{_dash(kapak.get('company_name'))} · {_dash(kapak.get('product_name'))}"
            + (f" ({kapak['sku_code']})" if kapak.get("sku_code") else ""),
            STYLE_SUBTITLE,
        ),
        _p(ys["narrative"], STYLE_BODY),
        Spacer(1, 12),
    ]

    if ys["has_reference"] and ys["gains_pct"]:
        labels = [
            ("virgin_azalimi_pct", "Virgin ↓"), ("pcr_artisi_pct", "PCR ↑"),
            ("hammadde_azaltimi_pct", "Hammadde ↓"), ("fire_azaltimi_pct", "Fire ↓"),
            ("enerji_azaltimi_pct", "Enerji ↓"), ("karbon_azaltimi_pct", "Karbon ↓"),
            ("maliyet_azaltimi_pct", "Maliyet ↓"),
        ]
        cells = []
        for key, label in labels:
            v = ys["gains_pct"].get(key)
            cells.append([_p(_fmt_pct(v), STYLE_BIG_STAT), _p(label, STYLE_BIG_STAT_LABEL)])
        rows = [[c[0] for c in cells], [c[1] for c in cells]]
        t = Table(rows, colWidths=[24 * mm] * len(cells))
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(t)
    elif ys.get("realized_absolute_per_1000_units"):
        p1000 = ys["realized_absolute_per_1000_units"]
        cells = []
        for key, label, unit in [
            ("virgin_kg", "Virgin", "kg"), ("pcr_kg", "PCR", "kg"), ("regranul_kg", "PIR-Regr.", "kg"),
            ("karbon_kg_co2", "Karbon", "kgCO2"), ("fire_kg", "Fire", "kg"), ("enerji_kwh", "Enerji", "kWh"),
        ]:
            v = p1000.get(key)
            cells.append([_p(_fmt_num(v, 1) if isinstance(v, (int, float)) else "—", STYLE_BIG_STAT), _p(label, STYLE_BIG_STAT_LABEL)])
        rows = [[c[0] for c in cells], [c[1] for c in cells]]
        t = Table(rows, colWidths=[26 * mm] * len(cells))
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(t)

    story.append(Spacer(1, 16))
    story.append(_p(data["ppwr_on_uyum"]["disclaimer"], STYLE_DISCLAIMER))
    story += _qr_flowable(passport)
    doc.build(story)
    return buf.getvalue()
