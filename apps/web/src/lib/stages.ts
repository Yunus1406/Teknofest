export interface StageDef {
  no: number;
  slug: string;
  title: string;
  shortTitle: string;
  // Faz K.8 (Madde 10) — bu aşamaya girmeden önce case-store'da GERÇEKTEN
  // uyumlu bir hat seçili olmalı (K.4'ün uygunluk matrisinden gelen
  // `lineEligible` sinyali; sadece `lineId` varlığı YETMEZ). Tanımsız/
  // false = bu aşamanın böyle bir ön koşulu yok.
  requiresEligibleLine?: boolean;
}

export const STAGES: StageDef[] = [
  { no: 1, slug: "asama-1-anasayfa", title: "Ana Ekran", shortTitle: "Ana Ekran" },
  { no: 2, slug: "asama-2-ambalaj-tanimlama", title: "Ambalaj Tanımlama", shortTitle: "Ambalaj Tanımlama" },
  { no: 3, slug: "asama-3-mevzuat", title: "Mevzuat ve Tasarım Kriterleri", shortTitle: "Mevzuat" },
  { no: 4, slug: "asama-4-altyapi-eslestirme", title: "Firma Altyapısı ve Eşleştirme", shortTitle: "Altyapı Eşleştirme" },
  { no: 5, slug: "asama-5-akilli-baslangic", title: "Mevcut Reçete / Akıllı Başlangıç", shortTitle: "Akıllı Başlangıç", requiresEligibleLine: true },
  { no: 6, slug: "asama-6-optimizasyon", title: "Optimizasyon (Ana Motor)", shortTitle: "Optimizasyon", requiresEligibleLine: true },
  { no: 7, slug: "asama-7-recete-onerileri", title: "Reçete Önerileri", shortTitle: "Reçete Önerileri", requiresEligibleLine: true },
  { no: 8, slug: "asama-8-karsilastirma", title: "Mevcut ↔ Önerilen Karşılaştırması", shortTitle: "Karşılaştırma", requiresEligibleLine: true },
  { no: 9, slug: "asama-9-uretime-aktarim", title: "Üretime Aktarım", shortTitle: "Üretime Aktarım", requiresEligibleLine: true },
  { no: 10, slug: "asama-10-canli-takip", title: "Canlı Üretim Takibi", shortTitle: "Canlı Takip", requiresEligibleLine: true },
  { no: 11, slug: "asama-11-fiziksel-dogrulama", title: "Fiziksel Doğrulama", shortTitle: "Fiziksel Doğrulama", requiresEligibleLine: true },
  { no: 12, slug: "asama-12-nihai-sonuc", title: "Nihai Sonuç ve Sürdürülebilirlik Kazanımı", shortTitle: "Nihai Sonuç", requiresEligibleLine: true },
];
