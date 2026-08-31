"""Faz F.12 — Merkezi Veri Çözümleme Servisi testleri."""
from app.services.data_resolution import Candidate, SourceTier, resolve_value, tier_label


def test_empty_candidates_returns_none():
    assert resolve_value([]) is None


def test_all_none_values_returns_none():
    candidates = [
        Candidate(tier=SourceTier.FIRMA_OLCUM, value=None),
        Candidate(tier=SourceTier.SISTEM_REFERANS, value=None),
    ]
    assert resolve_value(candidates) is None


def test_single_candidate_resolves_to_its_own_tier():
    candidates = [Candidate(tier=SourceTier.SISTEM_REFERANS, value=42.0, unit="kg")]
    result = resolve_value(candidates)
    assert result is not None
    assert result.value == 42.0
    assert result.tier == SourceTier.SISTEM_REFERANS
    assert result.tier_label == "Sistem Referans Kütüphanesi"
    assert result.unit == "kg"


def test_higher_priority_tier_wins_even_if_listed_last():
    candidates = [
        Candidate(tier=SourceTier.VARSAYIM, value=10.0),
        Candidate(tier=SourceTier.SISTEM_REFERANS, value=20.0),
        Candidate(tier=SourceTier.FIRMA_OLCUM, value=30.0),
    ]
    result = resolve_value(candidates)
    assert result.value == 30.0
    assert result.tier == SourceTier.FIRMA_OLCUM


def test_falls_through_to_next_tier_when_higher_tier_value_is_none():
    candidates = [
        Candidate(tier=SourceTier.FIRMA_OLCUM, value=None),
        Candidate(tier=SourceTier.FIRMA_URETIM, value=None),
        Candidate(tier=SourceTier.TEDARIKCI_FOYU, value=15.5, source_text="Tedarikçi X föyü"),
        Candidate(tier=SourceTier.SISTEM_REFERANS, value=99.0),
    ]
    result = resolve_value(candidates)
    assert result.value == 15.5
    assert result.tier == SourceTier.TEDARIKCI_FOYU
    assert result.source_text == "Tedarikçi X föyü"


def test_demo_placeholder_flag_and_metadata_pass_through():
    candidates = [
        Candidate(
            tier=SourceTier.VARSAYIM,
            value=1.2,
            unit="kg_co2e_per_kg",
            source_text="DEMO/VARSAYIMSAL — kaynak yok",
            year=None,
            version="v0-demo",
            is_demo_placeholder=True,
        )
    ]
    result = resolve_value(candidates)
    assert result.is_demo_placeholder is True
    assert result.version == "v0-demo"
    assert result.source_text == "DEMO/VARSAYIMSAL — kaynak yok"


def test_tier_label_helper_matches_all_seven_tiers():
    labels = {tier: tier_label(tier) for tier in SourceTier}
    assert len(labels) == 7
    assert all(isinstance(v, str) and v for v in labels.values())
    assert labels[SourceTier.FIRMA_OLCUM] == "Firma Ölçümü"
    assert labels[SourceTier.VARSAYIM] == "Varsayım/Tahmin"
