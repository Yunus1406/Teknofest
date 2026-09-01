import { beforeEach, describe, expect, it } from "vitest";
import { useCaseStore } from "./case-store";

/** Regresyon: Aşama 9'da "Üretim Onaylandı ✓" görünüyordu ama Aşama 10'da
 * "Üretim emri bulunamadı" (404) alınıyordu. Kök neden: case-store'daki
 * kimlikler birbirine bağımlı olduğu halde (packagingRequest -> line ->
 * recipe -> productionOrder), üst seviyedeki bir kimlik değiştiğinde alt
 * seviyedekiler temizlenmiyordu -- farklı/yeni bir reçete seçildiğinde eski
 * `productionOrderId` sahipsiz kalıp backend'de artık var olmayan (ya da
 * ilgisiz) bir kayda işaret etmeye devam ediyordu. Bu testler, her üst
 * seviye setter'ın ilgili alt seviye alanları otomatik temizlediğini
 * doğrular. */
describe("useCaseStore cascading resets", () => {
  beforeEach(() => {
    useCaseStore.getState().reset();
  });

  it("setRecipeId clears a stale productionOrderId", () => {
    const { setRecipeId, setProductionOrderId } = useCaseStore.getState();
    setRecipeId("recipe-1");
    setProductionOrderId("order-from-recipe-1");
    expect(useCaseStore.getState().productionOrderId).toBe("order-from-recipe-1");

    // Kullanıcı Aşama 7'de farklı bir finalist seçti ya da Aşama 11'de yeni
    // bir versiyona geçti -- eski üretim emri artık bu reçeteyle ilgisiz.
    setRecipeId("recipe-2");

    expect(useCaseStore.getState().recipeId).toBe("recipe-2");
    expect(useCaseStore.getState().productionOrderId).toBeNull();
  });

  it("setLineId clears recipe, optimization run and production order", () => {
    const { setLineId, setRecipeId, setOptimizationRunId, setProductionOrderId } = useCaseStore.getState();
    setLineId("line-1");
    setRecipeId("recipe-1");
    setOptimizationRunId("run-1");
    setProductionOrderId("order-1");

    setLineId("line-2");

    const state = useCaseStore.getState();
    expect(state.lineId).toBe("line-2");
    expect(state.recipeId).toBeNull();
    expect(state.optimizationRunId).toBeNull();
    expect(state.productionOrderId).toBeNull();
  });

  it("setPackagingRequestId clears every downstream id (starting a new case)", () => {
    const store = useCaseStore.getState();
    store.setPackagingRequestId("req-1");
    store.setLineId("line-1");
    store.setRecipeId("recipe-1");
    store.setOptimizationRunId("run-1");
    store.setProductionOrderId("order-1");

    useCaseStore.getState().setPackagingRequestId("req-2");

    const state = useCaseStore.getState();
    expect(state.packagingRequestId).toBe("req-2");
    expect(state.lineId).toBeNull();
    expect(state.recipeId).toBeNull();
    expect(state.optimizationRunId).toBeNull();
    expect(state.productionOrderId).toBeNull();
  });

  it("setLineId resets lineEligible to false (Faz K.8 gate signal)", () => {
    const { setLineId, setLineEligible } = useCaseStore.getState();
    setLineId("line-1");
    setLineEligible(true);
    expect(useCaseStore.getState().lineEligible).toBe(true);

    // Kullanıcı Aşama 4'te FARKLI bir hat seçti -- eski hattın uygunluğu
    // yeni hat için ANLAMSIZ, Aşama 4'ün refreshMatches'i yeniden onaylamalı.
    setLineId("line-2");

    expect(useCaseStore.getState().lineEligible).toBe(false);
  });

  it("setPackagingRequestId resets lineEligible along with lineId", () => {
    const { setPackagingRequestId, setLineId, setLineEligible } = useCaseStore.getState();
    setLineId("line-1");
    setLineEligible(true);

    setPackagingRequestId("req-2");

    expect(useCaseStore.getState().lineEligible).toBe(false);
  });

  it("re-selecting the same recipe still clears productionOrderId (no stale false-positive in Aşama 9)", () => {
    // Aşama 9'un "Üretim Onaylandı" göstermesi İÇİN productionOrderId'nin
    // GEÇERLİ bir emre karşılık gelmesi gerekir; setRecipeId her çağrıldığında
    // (aynı id olsa bile) önceki emri temizlemek, yanlışlıkla eski bir emri
    // "hâlâ geçerli" göstermekten daha güvenlidir.
    const { setRecipeId, setProductionOrderId } = useCaseStore.getState();
    setRecipeId("recipe-1");
    setProductionOrderId("order-1");

    setRecipeId("recipe-1");

    expect(useCaseStore.getState().productionOrderId).toBeNull();
  });
});
