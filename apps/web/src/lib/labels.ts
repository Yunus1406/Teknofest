// Backend enum değerlerini (İngilizce/slug olmayan ama kod-dostu Türkçe
// snake_case) kullanıcıya gösterilecek etikete ve rozet tonuna çevirir.

export type Tone = "petrol" | "virgin" | "pcr" | "regranul" | "warn" | "neutral";

// Karbon Emisyon Faktörü (EF) veri kalitesi — bkz. backend app/services/carbon.py.
// Bu sistemde şu an gerçek/kaynaklı bir LCA veritabanı entegrasyonu YOK; tüm
// seed EF'leri "tanimli_demo" durumundadır ve UI'da bunu ASLA gizlememelidir.
export function carbonEfStatusLabel(v: string | null | undefined): string {
  switch (v) {
    case "tanimli_gercek":
      return "Kaynaklı EF";
    case "tanimli_demo":
      return "DEMO / VARSAYIMSAL EF";
    case "tanimlanmadi":
      return "EF TANIMLANMADI";
    default:
      return "EF TANIMLANMADI";
  }
}

export function carbonEfStatusTone(v: string | null | undefined): Tone {
  switch (v) {
    case "tanimli_gercek":
      return "pcr";
    case "tanimli_demo":
      return "virgin";
    default:
      return "warn";
  }
}

// Faz I.4 — "varsayimsal" 4. durum olarak eklendi (Aşama 7'nin
// RecipeEvaluation.data_confidence'ı hâlâ sadece yuksek/orta/dusuk üretir;
// "varsayimsal" SADECE dataConfidenceFromSourceKind()'ın türettiği
// senaryolarda ortaya çıkar). Mevcut 3 durum DEĞİŞMEDİ, üzerine eklendi.
export function dataConfidenceLabel(v: string | null): string {
  switch (v) {
    case "yuksek":
      return "Veri Güveni: Yüksek";
    case "orta":
      return "Veri Güveni: Orta";
    case "dusuk":
      return "Veri Güveni: Düşük";
    case "varsayimsal":
      return "Veri Güveni: Varsayımsal";
    default:
      return "Veri Güveni: —";
  }
}

export function dataConfidenceTone(v: string | null): Tone {
  switch (v) {
    case "yuksek":
      return "pcr";
    case "orta":
      return "virgin";
    case "dusuk":
      return "warn";
    case "varsayimsal":
      return "regranul";
    default:
      return "neutral";
  }
}

// Faz I.4 — Sistem geneli "Veri Güveni" göstergesi. AYRI bir hesaplama
// DEĞİL: backend'in app/services/report_service.py::_CONFIDENCE_BY_KIND
// ile AYNI 4 kademeli eşleme, aynı `kind` girdi kümesi (H.5'in 10 kelimelik
// kaynak sözlüğü + DataSourceType/carbon_ef_status takma adları) üzerinde.
// Kaynak gerçekten belirlenemiyorsa (null/tanınmıyor) null döner — rozet
// HİÇ gösterilmez, "Veri Güveni: —" bile basılmaz.
const _CONFIDENCE_BY_SOURCE_KIND: Record<string, string> = {
  makineden_alinan: "yuksek",
  laboratuvar: "yuksek",
  firma_verisi: "yuksek",
  laboratuvar_testi: "yuksek",
  kullanici_girisi: "yuksek",
  // Faz N.1a — Faz G.4'ün 5 kademeli firma hafızası taramasının tier'ları
  // (bkz. packaging_service.find_reference_recipe_with_evidence). Kademe
  // SIRASI zaten güven sırasına karşılık gelir: 1-2 (aynı SKU/ambalaj türü)
  // en güçlü kanıt, 3-4 (benzer kullanım/teknik şart) orta, 5 (sadece aynı
  // hat -- ambalaj türü/teknik şartlar hiç eşleşmeyebilir) en zayıf kanıt.
  ayni_sku: "yuksek",
  ayni_ambalaj_turu: "yuksek",
  benzer_kullanim_alani: "orta",
  benzer_teknik_sartlar: "orta",
  ayni_hat: "dusuk",
  gecmis_uretim: "orta",
  teknik_veri_foyu: "orta",
  hesaplanan: "orta",
  gecmis_uretim_verisi: "orta",
  mevzuat: "dusuk",
  sistem_referansi: "dusuk",
  simulasyon: "dusuk",
  simulasyon_verisi: "dusuk",
  tanimli_gercek: "dusuk",
  // Faz P.1 (Madde 20) — Senaryo Laboratuvarı'nın hipotetik what-if çıktısı.
  // `simulasyon_verisi`'den KASITLI OLARAK ayrı (bkz. backend
  // report_service.py::_CONFIDENCE_BY_KIND aynı yorum).
  senaryo_simulasyonu: "dusuk",
  varsayimsal: "varsayimsal",
  tanimli_demo: "varsayimsal",
};

export function dataConfidenceFromSourceKind(kind: string | null | undefined): string | null {
  if (!kind) return null;
  return _CONFIDENCE_BY_SOURCE_KIND[kind] ?? null;
}

export function dataSourceLabel(v: string): string {
  const map: Record<string, string> = {
    hesaplanan: "Hesaplanan",
    gecmis_uretim_verisi: "Geçmiş Üretim Verisi",
    makineden_alinan: "Makineden Alınan",
    laboratuvar_testi: "Laboratuvar Testi",
    kullanici_girisi: "Kullanıcı Girişi",
    // Gerçek PLC/SCADA entegrasyonu bağlanana kadar 'Makineden Alınan' ile
    // asla aynı anda gösterilmez -- ikisi çelişkili bir iddia olurdu.
    simulasyon_verisi: "Simülasyon Verisi",
  };
  return map[v] ?? v;
}

export function dataSourceTone(v: string): Tone {
  return v === "simulasyon_verisi" ? "virgin" : "petrol";
}

export function tierLabel(v: string): string {
  const map: Record<string, string> = {
    kesin_teknik_kisit: "Kesin Teknik Kısıt",
    malzeme_proses_kisiti: "Malzeme-Proses Kısıtı",
    tahmini_fiziksel_performans: "Tahmini Fiziksel Performans",
  };
  return map[v] ?? v;
}

export function verdictLabel(v: string): string {
  return v === "elendi" ? "Elendi" : "Geçti";
}

// Faz D.2 — fiziksel test 3 durumu. ASLA sadece `passed` bool'undan
// üretilmemeli: hedef/kabul kriteri tanımsız bir test (`beklemede`)
// "Kaldı" ile karıştırılmamalı, "Test Edilmedi" olarak ayrı gösterilir.
export function physicalTestResultLabel(v: string | null | undefined): string {
  switch (v) {
    case "basarili":
      return "Geçti";
    case "basarisiz":
      return "Kaldı";
    case "beklemede":
      return "Test Edilmedi";
    default:
      return "Test Edilmedi";
  }
}

export function physicalTestResultTone(v: string | null | undefined): Tone {
  switch (v) {
    case "basarili":
      return "pcr";
    case "basarisiz":
      return "warn";
    default:
      return "virgin";
  }
}

// Faz G.2 — eskiden 3 durumdu (uygun_gorunuyor/inceleme_gerekli/uygun_degil).
// veri_eksik/henuz_metodoloji_yok bir onay/red İDDİASI taşımaz -- sadece
// "bunu otomatik değerlendiremedik" bilgisidir (bkz. app/services/
// packaging_service.py _overall_verdict).
export function regulatoryVerdictLabel(v: string): string {
  const map: Record<string, string> = {
    uygun_gorunuyor: "Uygun Görünüyor",
    inceleme_gerekli: "İnceleme Gerekli",
    uygun_degil: "Uygun Değil",
    veri_eksik: "Veri Eksik",
    henuz_metodoloji_yok: "Henüz Uygulanabilir Metodoloji Bulunmuyor",
  };
  return map[v] ?? v;
}

export function regulatoryVerdictTone(v: string): Tone {
  const map: Record<string, Tone> = {
    uygun_gorunuyor: "pcr",
    inceleme_gerekli: "virgin",
    uygun_degil: "warn",
    veri_eksik: "neutral",
    henuz_metodoloji_yok: "regranul",
  };
  return map[v] ?? "neutral";
}

export function materialTypeLabel(v: string): string {
  // "regranul" dahili/pre-consumer fire geri kazanımını (PIR) temsil eder —
  // post-tüketici PCR ile AYNI mevzuat kategorisi DEĞİLDİR (PPWR Md.7'nin
  // geri dönüştürülmüş içerik hesabına dahil edilmez); etiket bunu açıkça
  // yansıtır ki kullanıcı ikisini karıştırmasın.
  const map: Record<string, string> = { virgin: "Virgin", pcr: "PCR", regranul: "PIR-Regranül" };
  return map[v] ?? v;
}

export function materialTypeTone(v: string): Tone {
  const map: Record<string, Tone> = { virgin: "virgin", pcr: "pcr", regranul: "regranul" };
  return map[v] ?? "neutral";
}

export function recipeSourceLabel(v: string): string {
  return v === "referans_receteden" ? "Referans Reçeteden" : "Sistem Üretti";
}

// Faz G.4 — Aşama 5'in 5 kademeli firma hafızası taraması hangi kademede
// eşleşme bulduğunu gösterir (bkz. app/services/packaging_service.py
// find_reference_recipe_with_evidence).
export function referenceSearchTierLabel(tier: string): string {
  const map: Record<string, string> = {
    ayni_sku: "Aynı SKU'nun Doğrulanmış Reçetesi",
    ayni_ambalaj_turu: "Aynı Ambalaj Türü",
    benzer_kullanim_alani: "Benzer Kullanım Alanı",
    benzer_teknik_sartlar: "Benzer Teknik Şartlar (±%20 tolerans)",
    ayni_hat: "Aynı Üretim Hattı",
  };
  return map[tier] ?? tier;
}

// Faz G.5 — Aşama 7'nin ÇOKLU-etiket "Veri Kaynağı" listesi
// (`Recipe.data_source_tags`). Mevcut TEK-değerli `dataSourceLabel`/
// `DataSourceType` ile KARIŞTIRILMAZ — o modelin (PhysicalTest.source vb.)
// üzerinde, bu ise bir reçeteye katkıda bulunan TÜM kaynakların kümesi
// üzerinde çalışır. Sabit 8 değerli kelime dağarcığı, bkz.
// app/models/recipe.py Recipe.data_source_tags modül yorumu.
export function dataSourceTagLabel(v: string): string {
  const map: Record<string, string> = {
    firma_verisi: "Firma Verisi",
    gecmis_uretim: "Geçmiş Üretim",
    makineden_alinan: "Makineden Alınan",
    teknik_veri_foyu: "Teknik Veri Föyü",
    laboratuvar: "Laboratuvar",
    mevzuat: "Mevzuat",
    hesaplanan: "Hesaplanan",
    varsayimsal: "Varsayımsal",
  };
  return map[v] ?? v;
}

export function dataSourceTagTone(v: string): Tone {
  const map: Record<string, Tone> = {
    firma_verisi: "pcr",
    gecmis_uretim: "pcr",
    makineden_alinan: "pcr",
    teknik_veri_foyu: "petrol",
    laboratuvar: "petrol",
    mevzuat: "petrol",
    hesaplanan: "neutral",
    varsayimsal: "warn",
  };
  return map[v] ?? "neutral";
}

export function scoreCriterionLabel(v: string): string {
  // Fiziksel test henüz yapılmadan verilen bir sayı (ör. "Teknik Performans: 96")
  // yanlışlıkla kesin bir ölçüm gibi okunabilir -- bu yüzden "Tahmini" ön eki
  // ve "Veri Güveni" rozetiyle tutarlı bir çerçeveleme kullanılıyor.
  const map: Record<string, string> = {
    teknik_performans: "Tahmini Teknik Performans",
    uretilebilirlik: "Üretilebilirlik",
    mevzuat_marji: "Mevzuat Marjı",
    karbon: "Karbon",
    fire_riski: "Fire Riski",
    maliyet: "Maliyet",
  };
  return map[v] ?? v;
}

// Faz K.1 — Aşama 2'nin "Alanları Çıkar" çıktısındaki her alan için
// (yuksek/orta/dusuk) bir güven YÜZDESİ gösterilir; sabit, kaba bir eşleme
// (gerçek bir olasılık modeli değil, sadece 3 kademeyi kullanıcıya daha
// somut anlatan bir gösterim). "dusuk" için ayrıca UI'da "Kontrol Ediniz"
// uyarısı eklenir (bkz. asama-2-ambalaj-tanimlama/page.tsx ConfidenceBadge).
export function fieldConfidencePct(v: string | undefined): number | null {
  switch (v) {
    case "yuksek":
      return 98;
    case "orta":
      return 78;
    case "dusuk":
      return 50;
    default:
      return null;
  }
}

export function formatPct(v: number): string {
  return `%${v.toFixed(0)}`;
}

// Faz F.9 — geri dönüştürülebilirlik değerlendirmesinin çok boyutlu kırılımı
// (SADECE PPWR Md.6 kartında görünür, bkz. RegulatoryAssessmentOut.recyclability_breakdown).
// Faz F.13 — Referans Merkezi Ekranı'nda TÜM kategoriler için tek, ortak
// bir "bu rakamı nereden aldın?" rozeti. Karbon EF'inin 3 durumlu
// (tanimli_gercek/tanimli_demo/tanimlanmadi) modelinden FARKLI olarak
// F.1-F.11'in referans tabloları sadece is_demo_placeholder taşır (bkz.
// app/models/*.py — hepsi aynı boolean disiplini kullanır).
export function referenceDataQualityLabel(isDemoPlaceholder: boolean): string {
  return isDemoPlaceholder ? "DEMO / VARSAYIMSAL" : "Kaynaklı";
}
export function referenceDataQualityTone(isDemoPlaceholder: boolean): Tone {
  return isDemoPlaceholder ? "virgin" : "pcr";
}

// Faz K.4 — Aşama 4'ün uygunluk matrisindeki 5 kriterin kısa Türkçe etiketi.
export function matchCriterionLabel(key: string): string {
  const map: Record<string, string> = {
    proses: "Proses",
    malzeme_uyumu: "Malzeme Uyumu",
    mikron_araligi: "Mikron Aralığı",
    katman_yapisi: "Katman Yapısı",
    ambalaj_turu: "Ambalaj Türü",
  };
  return map[key] ?? key;
}

// Faz L.2 — gıda teması kanıt yönetim listesi durumları.
export function evidenceStatusLabel(v: string): string {
  switch (v) {
    case "mevcut":
      return "Mevcut ✓";
    case "eksik":
      return "Eksik ⚠";
    case "gerekli_degil":
      return "Gerekli Değil";
    default:
      return v;
  }
}

export function evidenceStatusTone(v: string): Tone {
  switch (v) {
    case "mevcut":
      return "pcr";
    case "eksik":
      return "warn";
    default:
      return "neutral";
  }
}

// Faz M.2 (Madde 12) — huni görselleştirmesinin yanındaki eleme nedeni
// kategorileri (bkz. apps/api/app/constraint_engine/rules.py
// REASON_CODE_CATEGORIES).
export function eliminationCategoryLabel(v: string): string {
  const map: Record<string, string> = {
    malzeme_uyumsuzlugu: "Malzeme Uyumsuzluğu",
    mevzuat: "Mevzuat",
    makine_hat_kisiti: "Makine/Hat Kısıtı",
    // Faz Q.2 (Madde 25) — geçmişte AYNI hatta denenip fiziksel testi
    // GERÇEKTEN başarısız olmuş bir kombinasyona benzerlik (bkz. backend
    // constraint_engine/rules.py::rule_similar_to_failed_history).
    gecmis_basarisizlik: "Geçmiş Başarısızlığa Benzerlik",
    diger: "Diğer",
  };
  return map[v] ?? v;
}

export function eliminationCategoryTone(v: string): Tone {
  const map: Record<string, Tone> = {
    malzeme_uyumsuzlugu: "virgin",
    mevzuat: "petrol",
    makine_hat_kisiti: "warn",
    gecmis_basarisizlik: "warn",
    diger: "neutral",
  };
  return map[v] ?? "neutral";
}

// Faz O.2 (Madde 19) — Sürdürülebilirlik Karnesi'nin bazı boyutları
// (malzeme_verimliligi/karbon/enerji/fire "henüz üretilmedi" gibi, ya da
// dongusellik/mevzuat_hazirligi'nin değerlendirilmediği) ham durum kodu
// taşır; zaten Türkçe serbest metin olan durumlar (ör. "3/5 madde uygun
// görünüyor") ya da bilinen bir RegulatoryVerdict kodu (dongusellik'in
// PPWR Md.6 verdict'i) OLDUĞU GİBİ/`regulatoryVerdictLabel` ile ele alınır
// -- bu sadece geri kalan sabit kelime dağarcığı içindir.
export function scorecardStatusLabel(v: string): string {
  const map: Record<string, string> = {
    henuz_uretilmedi: "Henüz Üretilmedi",
    kutle_verisi_eksik: "Kütle Verisi Eksik",
    degerlendirilmedi: "Değerlendirilmedi",
    gida_temasi_yok: "Gıda Teması Yok — Gerekli Değil",
  };
  return map[v] ?? v;
}

// Faz Q.1 (Madde 23) — Üretim Öncesi Risk Skoru (bkz. apps/api/app/
// services/risk_service.py). Veri Güveni'nden (dataConfidenceLabel/Tone)
// KASITLI OLARAK AYRI bir sözlük -- bu bir "veri ne kadar güvenilir"
// değil, "bu reçete üretime geçerse ne kadar risk taşıyor" göstergesi.
export function riskLevelLabel(v: string): string {
  switch (v) {
    case "dusuk":
      return "Düşük Risk";
    case "orta":
      return "Orta Risk";
    case "yuksek":
      return "Yüksek Risk";
    default:
      return v;
  }
}

export function riskLevelTone(v: string): Tone {
  switch (v) {
    case "dusuk":
      return "pcr";
    case "orta":
      return "virgin";
    case "yuksek":
      return "warn";
    default:
      return "neutral";
  }
}

// Faz Q.1'in 7 risk bileşeninin kısa Türkçe başlığı.
export function riskComponentLabel(key: string): string {
  const map: Record<string, string> = {
    yeni_hammadde: "Yeni Hammadde",
    pcr_seviyesi: "PCR Seviyesi",
    kalinlik_azaltimi: "Kalınlık Azaltımı",
    makine_uyumu: "Makine Uyumu",
    gecmis_uretim_benzerligi: "Geçmiş Üretim Benzerliği",
    teknik_performans: "Teknik Performans Tahmini",
    mevzuat_kanit_eksikleri: "Mevzuat/Kanıt Eksikleri",
  };
  return map[key] ?? key;
}

export function recyclabilityDimensionLabel(v: string): string {
  const map: Record<string, string> = {
    tasarim_uyumu: "Tasarım Uyumu",
    ayirma_altyapisi: "Ayrıştırma Altyapısı",
    toplama_altyapisi: "Toplama Altyapısı",
  };
  return map[v] ?? v;
}
