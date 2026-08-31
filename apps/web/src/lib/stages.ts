export interface StageDef {
  no: number;
  slug: string;
  title: string;
  shortTitle: string;
}

export const STAGES: StageDef[] = [
  { no: 1, slug: "asama-1-anasayfa", title: "Ana Ekran", shortTitle: "Ana Ekran" },
  { no: 2, slug: "asama-2-ambalaj-tanimlama", title: "Ambalaj Tanımlama", shortTitle: "Ambalaj Tanımlama" },
  { no: 3, slug: "asama-3-mevzuat", title: "Mevzuat ve Tasarım Kriterleri", shortTitle: "Mevzuat" },
  { no: 4, slug: "asama-4-altyapi-eslestirme", title: "Firma Altyapısı ve Eşleştirme", shortTitle: "Altyapı Eşleştirme" },
  { no: 5, slug: "asama-5-akilli-baslangic", title: "Mevcut Reçete / Akıllı Başlangıç", shortTitle: "Akıllı Başlangıç" },
  { no: 6, slug: "asama-6-optimizasyon", title: "Optimizasyon (Ana Motor)", shortTitle: "Optimizasyon" },
  { no: 7, slug: "asama-7-recete-onerileri", title: "Reçete Önerileri", shortTitle: "Reçete Önerileri" },
  { no: 8, slug: "asama-8-karsilastirma", title: "Mevcut ↔ Önerilen Karşılaştırması", shortTitle: "Karşılaştırma" },
  { no: 9, slug: "asama-9-uretime-aktarim", title: "Üretime Aktarım", shortTitle: "Üretime Aktarım" },
  { no: 10, slug: "asama-10-canli-takip", title: "Canlı Üretim Takibi", shortTitle: "Canlı Takip" },
  { no: 11, slug: "asama-11-fiziksel-dogrulama", title: "Fiziksel Doğrulama", shortTitle: "Fiziksel Doğrulama" },
  { no: 12, slug: "asama-12-nihai-sonuc", title: "Nihai Sonuç ve Sürdürülebilirlik Kazanımı", shortTitle: "Nihai Sonuç" },
];
