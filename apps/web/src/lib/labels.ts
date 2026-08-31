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

export function dataConfidenceLabel(v: string | null): string {
  switch (v) {
    case "yuksek":
      return "Veri Güveni: Yüksek";
    case "orta":
      return "Veri Güveni: Orta";
    case "dusuk":
      return "Veri Güveni: Düşük";
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
    default:
      return "neutral";
  }
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

export function regulatoryVerdictLabel(v: string): string {
  const map: Record<string, string> = {
    uygun_gorunuyor: "Uygun Görünüyor",
    inceleme_gerekli: "İnceleme Gerekli",
    uygun_degil: "Uygun Değil",
  };
  return map[v] ?? v;
}

export function regulatoryVerdictTone(v: string): Tone {
  const map: Record<string, Tone> = {
    uygun_gorunuyor: "pcr",
    inceleme_gerekli: "virgin",
    uygun_degil: "warn",
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

export function formatPct(v: number): string {
  return `%${v.toFixed(0)}`;
}
