import { describe, expect, it } from "vitest";
import { addTag } from "./tag-input";

/** Regresyon: Firma Profili'nin "Ana İhracat Pazarları"/"Ana Üretim
 * Prosesleri" alanlarında yazarken kelimeler birleşiyordu ("AlmanyaFransa").
 * Kök neden: eski TagListField her keystroke'ta `value.join(", ")` ile TEK
 * bir string üretip split/trim/filter ederek geri yazıyordu -- henüz
 * yazılmakta olan ayraç (virgül+boşluk) anında siliniyordu. Artık `addTag`
 * SADECE bir etiket TAMAMLANDIĞINDA (Enter/virgül/blur) çağrılır; bu testler
 * o saf fonksiyonu doğrular. */
describe("addTag", () => {
  it("trims whitespace before adding", () => {
    expect(addTag([], "  Almanya  ")).toEqual(["Almanya"]);
  });

  it("does not add an empty/whitespace-only tag", () => {
    expect(addTag(["Almanya"], "   ")).toEqual(["Almanya"]);
  });

  it("does not add a duplicate tag", () => {
    expect(addTag(["Almanya"], "Almanya")).toEqual(["Almanya"]);
  });

  it("appends to existing tags without mutating the original array", () => {
    const existing = ["Almanya"];
    const result = addTag(existing, "Fransa");
    expect(result).toEqual(["Almanya", "Fransa"]);
    expect(existing).toEqual(["Almanya"]);
  });
});
