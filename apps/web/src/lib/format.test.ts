import { describe, expect, it } from "vitest";
import { formatOptionalKg } from "./format";

/** Regresyon: Aşama 8'de "Cannot read properties of undefined (reading
 * 'toFixed')" hatası alınıyordu. Kök neden: SideCard, virgin_kg/pcr_kg/
 * regranul_kg/fire_kg/enerji_kwh alanlarını `!== null ? v.toFixed(2) : null`
 * ile kontrol ediyordu -- API bu alanları bazen `null` değil TAMAMEN
 * ATLAYARAK (undefined) döndürüyor, ve `!== null` bunu yakalamıyor. Bu
 * testler, `formatOptionalKg`'nin hem null hem undefined'ı güvenle "—"
 * (StatRow'da gizlenecek null) olarak ele aldığını doğrular. */
describe("formatOptionalKg", () => {
  it("returns null for null (alan API'de açıkça null döndü)", () => {
    expect(formatOptionalKg(null, "kg")).toBeNull();
  });

  it("returns null for undefined (alan API yanıtında hiç yok)", () => {
    expect(formatOptionalKg(undefined, "kg")).toBeNull();
  });

  it("formats a real number with 2 decimals and the given unit", () => {
    expect(formatOptionalKg(12.3456, "kg")).toBe("12.35 kg");
  });

  it("formats zero correctly (falsy but valid)", () => {
    expect(formatOptionalKg(0, "kWh")).toBe("0.00 kWh");
  });
});
