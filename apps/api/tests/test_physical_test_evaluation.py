"""Faz D.2 — Fiziksel test mantığı: boş/tanımsız kriterli bir test ASLA
'Geçti' (basarili) sayılmamalı; hiç test girilmeden doğrulama denenirse
sistem reddetmeli; gerçekten başarısız bir test hâlâ V(n)->V(n+1) versiyon
zincirini tetiklemeli; `finalize_result` tüm testler gerçekten başarılı
olmadan reçeteyi doğrulanmış işaretlememeli.

Bulunan gerçek bug'lar (bkz. app/services/production_flow_service.py):
1. `target_min`/`target_max` HİÇBİRİ tanımlı değilse eski kod `passed=True`
   varsayıyordu (Tensile=0 MPa gibi hiç ölçülmemiş testler 'Geçti'
   görünüyordu) — gerçek dev DB'de doğrulandı (bkz. migration 8bcd26372eb1
   veri geri doldurma).
2. Boş bir `tests` listesiyle `all_passed` başlangıç değeri `True` kalıyordu
   — hiç test girilmeden reçete 'doğrulandı' olabiliyordu.
3. `finalize_result`, `recipe.is_verified`'ı fiziksel test sonucuna HİÇ
   bakmadan koşulsuz `True` yapıyordu."""
import pytest

from app.models.infrastructure import ProductionLine
from app.models.knowledge import Material, Polymer
from app.models.production import PhysicalTest, ProductionOrder
from app.models.recipe import PackagingRequest, Recipe, RecipeLayer
from app.services.production_flow_service import finalize_result, submit_physical_tests


@pytest.fixture()
def order(db_session):
    polymer = Polymer(code="PE", name="Polietilen", category="poliolefin", base_properties={})
    db_session.add(polymer)
    db_session.flush()
    material = Material(
        polymer_id=polymer.id, name="PE Virgin", material_type="virgin", density_g_cm3=0.92,
        degradation_factor=0.0, food_contact_eligible=True, max_recommended_ratio_pct=100.0,
        cost_per_kg=30.0, carbon_factor_kg_co2_per_kg=1.8,
    )
    db_session.add(material)
    line = ProductionLine(
        name="Test Hat", layer_structure="A", layer_count=1, min_micron=10, max_micron=1000,
        supported_packaging_types=[],
    )
    db_session.add(line)
    req = PackagingRequest(
        packaging_type="esnek film ambalaj", usage_area="t", product="t", target_market="t",
        food_contact=True, target_volume_units=1000, dimensions={"length_mm": 100, "width_mm": 100},
    )
    db_session.add(req)
    db_session.flush()
    recipe = Recipe(
        packaging_request_id=req.id, version=1, source="sistem_uretti", status="onerildi", total_micron=70.0,
    )
    db_session.add(recipe)
    db_session.flush()
    db_session.add(
        RecipeLayer(recipe_id=recipe.id, layer_index=0, layer_label="A", material_id=material.id, ratio_pct=100.0, thickness_micron=70.0)
    )
    order = ProductionOrder(recipe_id=recipe.id, line_id=line.id, status="tamamlandi", scheduled_qty_units=1000)
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


# --- (a) Boş test listesi reddedilir ----------------------------------------

def test_empty_test_list_is_rejected(db_session, order):
    with pytest.raises(ValueError, match="En az bir"):
        submit_physical_tests(db_session, order, [])


# --- (b) Kriteri tanımsız test ASLA 'basarili' olamaz -----------------------

def test_test_without_defined_target_range_never_resolves_to_passed(db_session, order):
    """Tam olarak kullanıcının bildirdiği senaryo: Tensile=0 MPa, hedef
    aralık bilgi tabanında tanımlı değil."""
    tests = [
        {"test_type": "tensile", "value": 0.0, "unit": "MPa", "target_min": None, "target_max": None, "test_method": None},
    ]
    rows, new_version = submit_physical_tests(db_session, order, tests)

    assert rows[0].result == "beklemede"
    assert rows[0].passed is False  # asla 'basarili' -- ama 'basarisiz' de değil
    assert new_version is None  # veri boşluğu, reçete kusuru değil -- versiyon açılmaz
    db_session.refresh(order.recipe)
    assert order.recipe.status == "fiziksel_dogrulama_bekleniyor"
    assert order.recipe.is_verified is False


def test_test_with_nonzero_value_but_no_target_still_pending(db_session, order):
    """Sıfır olmayan bir değer bile -- hedef aralık yoksa yine 'beklemede'."""
    tests = [
        {"test_type": "elongation", "value": 42.5, "unit": "%", "target_min": None, "target_max": None, "test_method": None},
    ]
    rows, _ = submit_physical_tests(db_session, order, tests)
    assert rows[0].result == "beklemede"


# --- (c) Gerçekten başarısız test -> V(n)->V(n+1) ----------------------------

def test_out_of_range_mandatory_test_triggers_new_recipe_version(db_session, order):
    original_recipe_id = order.recipe_id
    tests = [
        {"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": "ISO 4593"},
    ]
    rows, new_version = submit_physical_tests(db_session, order, tests)

    assert rows[0].result == "basarisiz"
    assert new_version is not None
    assert new_version.version == 2
    assert new_version.parent_recipe_id == original_recipe_id
    assert new_version.status == "taslak_optimizasyona_geri_dondu"
    db_session.refresh(order.recipe)
    assert order.recipe.status == "revizyon_gerekli"
    assert order.recipe.is_verified is False
    # Katmanlar kopyalanmış olmalı (tüm geçmiş saklanır)
    assert len(new_version.layers) == 1


def test_mixed_failed_and_pending_still_triggers_version_bump(db_session, order):
    """Bir test başarısız, bir test kriteri tanımsız -- başarısız olan
    ağır basar, versiyon açılır (veri boşluğu değil, gerçek bir kusur var)."""
    tests = [
        {"test_type": "kalinlik", "value": 40.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
        {"test_type": "tensile", "value": 0.0, "unit": "MPa", "target_min": None, "target_max": None, "test_method": None},
    ]
    rows, new_version = submit_physical_tests(db_session, order, tests)
    assert new_version is not None
    db_session.refresh(order.recipe)
    assert order.recipe.status == "revizyon_gerekli"


# --- Tüm testler gerçekten geçerse -------------------------------------------

def test_all_genuinely_passed_marks_recipe_dogrulandi(db_session, order):
    tests = [
        {"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None},
    ]
    rows, new_version = submit_physical_tests(db_session, order, tests)
    assert rows[0].result == "basarili"
    assert new_version is None
    db_session.refresh(order.recipe)
    assert order.recipe.status == "dogrulandi"


# --- (d) finalize_result kapısı ---------------------------------------------

def test_finalize_result_rejects_recipe_with_no_physical_tests(db_session, order):
    with pytest.raises(ValueError, match="fiziksel testler"):
        finalize_result(db_session, order.recipe)


def test_finalize_result_rejects_recipe_with_pending_test(db_session, order):
    submit_physical_tests(
        db_session, order,
        [{"test_type": "tensile", "value": 0.0, "unit": "MPa", "target_min": None, "target_max": None, "test_method": None}],
    )
    db_session.refresh(order.recipe)
    with pytest.raises(ValueError, match="fiziksel testler"):
        finalize_result(db_session, order.recipe)


def test_finalize_result_rejects_recipe_with_failed_test(db_session, order):
    db_session.add(
        PhysicalTest(
            recipe_id=order.recipe_id, test_type="kalinlik", value=40.0, unit="mikron",
            target_min=63.0, target_max=77.0, result="basarisiz", passed=False,
        )
    )
    db_session.commit()
    with pytest.raises(ValueError, match="fiziksel testler"):
        finalize_result(db_session, order.recipe)


def test_finalize_result_succeeds_when_all_tests_genuinely_passed(db_session, order):
    submit_physical_tests(
        db_session, order,
        [{"test_type": "kalinlik", "value": 70.0, "unit": "mikron", "target_min": 63.0, "target_max": 77.0, "test_method": None}],
    )
    db_session.refresh(order.recipe)

    result = finalize_result(db_session, order.recipe)

    assert order.recipe.is_verified is True
    assert result.per_1000_units is not None
