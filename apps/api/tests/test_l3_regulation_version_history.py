"""Faz L.3 (Madde 16) — mevzuatların daima en güncel sürümü kullanılmalı;
her `RegulationRequirement` satırı versiyon/tarih alanları taşımalı
(version, effective_date, source, last_reviewed_at zaten Faz F.2'den vardı
-- eksik olan previous_version/changed_at/change_summary). Bir satır
YENİDEN yüklendiğinde (loader'ın sil+yeniden-yaz mekanizması) gerçek bir
fark varsa bu 3 alan otomatik doldurulmalı; fark yoksa dokunulmamalı."""
from app.knowledge_base.loader import load_all, load_regulation_requirements
from app.models.regulation_requirement import RegulationRequirement
from app.services.packaging_service import _current_requirement_version, assess_regulations
from app.knowledge_base.loader import _snapshot_requirement_change
from app.models.recipe import PackagingRequest


def test_snapshot_requirement_change_detects_version_bump():
    old = {"version": "1.0", "threshold_value": 10.0, "requirement_text": "eski metin"}
    prev_version, changed_at, summary = _snapshot_requirement_change(old, "2.0", 10.0, "eski metin")
    assert prev_version == "1.0"
    assert changed_at is not None
    assert "sürüm 1.0 → 2.0" in summary


def test_snapshot_requirement_change_detects_threshold_change():
    old = {"version": "1.0", "threshold_value": 10.0, "requirement_text": "metin"}
    prev_version, changed_at, summary = _snapshot_requirement_change(old, "1.0", 15.0, "metin")
    assert prev_version == "1.0"
    assert "eşik değeri 10.0 → 15.0" in summary


def test_snapshot_requirement_change_none_when_nothing_changed():
    old = {"version": "1.0", "threshold_value": 10.0, "requirement_text": "metin"}
    prev_version, changed_at, summary = _snapshot_requirement_change(old, "1.0", 10.0, "metin")
    assert (prev_version, changed_at, summary) == (None, None, None)


def test_snapshot_requirement_change_none_when_no_previous_row():
    prev_version, changed_at, summary = _snapshot_requirement_change(None, "1.0", 10.0, "metin")
    assert (prev_version, changed_at, summary) == (None, None, None)


def test_reload_with_real_version_bump_populates_history_fields(db_session):
    """Gerçekçi entegrasyon senaryosu: KB bir kez yüklenir, bir satırın
    version/threshold_value'su ELDE (simüle edilmiş bir önceki sürüm gibi)
    değiştirilir, sonra AYNI regulation_requirements.yaml TEKRAR yüklenir --
    yeniden yazılan satırın previous_version/changed_at/change_summary'si
    GERÇEKTEN dolmalı (loader satırı silmeden önce eski hâli snapshot'ladı)."""
    ids = load_all(db_session)
    reg_id = ids["regulations"]["PPWR-ART-7"]

    row_2030 = (
        db_session.query(RegulationRequirement)
        .filter_by(regulation_id=reg_id, target_year=2030)
        .one()
    )
    assert row_2030.previous_version is None  # ilk yüklemede geçmiş yok
    # Bir önceki sürümü simüle et: gerçek YAML'da %10/"1.0" var, burada
    # DB'deki satırı elle eski bir duruma ("0.9", eşik %8) çekiyoruz.
    row_2030.version = "0.9"
    row_2030.threshold_value = 8.0
    db_session.commit()

    load_regulation_requirements(db_session, ids["regulations"])

    reloaded = (
        db_session.query(RegulationRequirement)
        .filter_by(regulation_id=reg_id, target_year=2030)
        .one()
    )
    assert reloaded.version == "1.0"  # YAML'daki güncel değer
    assert reloaded.previous_version == "0.9"
    assert reloaded.changed_at is not None
    assert "sürüm 0.9 → 1.0" in reloaded.change_summary
    assert "eşik değeri 8.0 → 10.0" in reloaded.change_summary


def test_reload_without_change_leaves_history_fields_none(db_session):
    ids = load_all(db_session)
    load_regulation_requirements(db_session, ids["regulations"])  # aynı YAML, değişiklik yok

    rows = db_session.query(RegulationRequirement).filter_by(regulation_id=ids["regulations"]["PPWR-ART-10"]).all()
    assert all(r.previous_version is None and r.change_summary is None for r in rows)


def test_regulatory_assessment_snapshots_current_version(db_session):
    ids = load_all(db_session)
    req = PackagingRequest(
        packaging_type="plastik tabak", usage_area="test l3", product="test", target_market="AB",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 200, "width_mm": 200},
    )
    db_session.add(req)
    db_session.commit()
    db_session.refresh(req)

    overall, assessments = assess_regulations(db_session, req)

    art7 = next(a for a in assessments if a.regulation.code == "PPWR-ART-7")
    assert art7.regulation_version_snapshot == "1.0"
    assert _current_requirement_version(db_session, ids["regulations"]["PPWR-ART-7"]) == "1.0"
