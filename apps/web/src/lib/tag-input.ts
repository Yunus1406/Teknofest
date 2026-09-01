// Faz K.5 (Madde 7) — TagListField'ın chip-commit mantığı, DOM'dan bağımsız
// saf bir fonksiyon olarak: baştaki/sondaki boşlukları temizler, boş bir
// girdiyi hiç eklemez, aynı etiketi ikinci kez eklemez.
export function addTag(existing: string[], raw: string): string[] {
  const tag = raw.trim();
  if (!tag || existing.includes(tag)) return existing;
  return [...existing, tag];
}
