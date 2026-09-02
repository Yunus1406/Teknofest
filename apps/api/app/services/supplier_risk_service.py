"""Faz R.3 (Madde 28) — Tedarikçi ve Hammadde Risk Radarı. Yeni bir DB
alanı YOK -- `Material` modelinde ZATEN var olan 5 gerçek alan
(`technical_datasheet_ref`/`source`/`carbon_ef_id`/`compliance_documents_ref`/
`lot_number`) + `certification_status` (gıda temas kanıtı) kontrol edilir.

DÜRÜSTLÜK NOTU: kullanıcının istediği CoA (Certificate of Analysis) ve SDS
(Safety Data Sheet) için AYRI bir DB alanı YOK -- sadece genel
`compliance_documents_ref` var. Bu ikisi UYDURULMAZ; radar bunları
"Uygunluk Belgeleri (DoC/Kimyasal/CoA/SDS)" tek, açıkça birleşik bir kalem
olarak gösterir."""
from app.models.knowledge import Material
from app.services.carbon import TANIMLI_GERCEK, resolve_carbon_ef, status_label


def build_supplier_evidence_radar(material: Material) -> dict:
    _, carbon_status, _ = resolve_carbon_ef(material)

    signals = {
        "teknik_veri": {
            "mevcut": material.technical_datasheet_ref is not None,
            "aciklama": material.technical_datasheet_ref or "Teknik veri föyü referansı girilmedi.",
        },
        "kaynak_tedarikci_kaniti": {
            "mevcut": material.source is not None,
            "aciklama": material.source or "Kaynak/tedarikçi bilgisi girilmedi.",
        },
        "karbon_ef_kaynagi": {
            "mevcut": carbon_status == TANIMLI_GERCEK,
            "aciklama": status_label(carbon_status),
        },
        # DoC/Kimyasal/CoA/SDS bu sistemde AYRI izlenmiyor -- tek bir genel
        # referans alanı var (bkz. modül docstring'i).
        "uygunluk_belgeleri": {
            "mevcut": material.compliance_documents_ref is not None,
            "aciklama": material.compliance_documents_ref or (
                "Uygunluk belgesi (DoC/Kimyasal/CoA/SDS) referansı girilmedi -- "
                "bu sistemde bu belge türleri ayrı ayrı izlenmiyor, tek bir genel referans alanı var."
            ),
        },
        "lot_izlenebilirligi": {
            "mevcut": material.lot_number is not None,
            "aciklama": material.lot_number or "Lot numarası girilmedi.",
        },
        "gida_temas_kaniti": {
            "mevcut": material.certification_status is not None,
            "aciklama": material.certification_status or "Gıda teması sertifikasyon durumu girilmedi.",
        },
    }
    dolu = sum(1 for s in signals.values() if s["mevcut"])
    tamlik_pct = round((dolu / len(signals)) * 100, 1)
    return {
        "material_id": material.id,
        "material_name": material.name,
        "signals": signals,
        "tamlik_pct": tamlik_pct,
    }
