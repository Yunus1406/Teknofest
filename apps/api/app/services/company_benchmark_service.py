"""Faz N.2 (Madde 15) — kullanıcının/firmanın kendi girdiği gerçek benchmark
verisi (bkz. app/models/company.py::CompanyBenchmark modül docstring'i).
Basit CRUD: karmaşık bir iş kuralı yok, tek doğrulama `packaging_category`/
`metric_name`'in bilinen sabit kümelerden biri olması (serbest metin kabul
edilmez, ki Aşama 12/Rapor'daki karşılaştırma gerçekten aynı büyüklüğü
kıyaslasın)."""
from sqlalchemy.orm import Session

from app.models.company import CompanyBenchmark
from app.schemas.company import COMPANY_BENCHMARK_METRICS
from app.services.common import CANONICAL_PACKAGING_CATEGORIES


def create_benchmark(db: Session, company_id: str, data: dict) -> CompanyBenchmark:
    if data["packaging_category"] not in CANONICAL_PACKAGING_CATEGORIES:
        raise ValueError(
            f"'{data['packaging_category']}' bilinmeyen bir ambalaj kategorisi. "
            f"Geçerli kategoriler: {', '.join(CANONICAL_PACKAGING_CATEGORIES)}"
        )
    if data["metric_name"] not in COMPANY_BENCHMARK_METRICS:
        raise ValueError(
            f"'{data['metric_name']}' bilinmeyen bir metrik. "
            f"Geçerli metrikler: {', '.join(COMPANY_BENCHMARK_METRICS)}"
        )
    benchmark = CompanyBenchmark(company_id=company_id, **data)
    db.add(benchmark)
    db.commit()
    db.refresh(benchmark)
    return benchmark


def list_benchmarks(db: Session, company_id: str) -> list[CompanyBenchmark]:
    return (
        db.query(CompanyBenchmark)
        .filter_by(company_id=company_id)
        .order_by(CompanyBenchmark.packaging_category, CompanyBenchmark.metric_name)
        .all()
    )


def delete_benchmark(db: Session, company_id: str, benchmark_id: str) -> bool:
    """Döner: satır bulunup silindiyse True, bu firmaya ait değilse/yoksa
    False (çağıran 404 kararını verir)."""
    benchmark = (
        db.query(CompanyBenchmark).filter_by(id=benchmark_id, company_id=company_id).one_or_none()
    )
    if benchmark is None:
        return False
    db.delete(benchmark)
    db.commit()
    return True
