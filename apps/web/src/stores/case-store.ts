"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

/** Aktif "case" (o an akıştaki ambalaj talebi) — 12 aşama arasında taşınan
 * kimlikler. localStorage'da tutulur ki sayfa yenilense de akış korunsun.
 *
 * Kimlikler birbirine bağımlıdır (packagingRequest -> line -> recipe ->
 * productionOrder): üst seviyedeki bir kimlik değiştiğinde, ona bağlı alt
 * seviyedeki kimlikler OTOMATİK temizlenir. Aksi halde (önceki hata) örn.
 * farklı bir reçete seçildiğinde eski `productionOrderId` sahipsiz kalır;
 * Aşama 9 onu hâlâ "onaylandı" gibi gösterir ama Aşama 10'da o üretim emri
 * artık bu reçeteyle ilgisiz (ya da backend'de hiç yoktur) -> 404. */
interface CaseState {
  packagingRequestId: string | null;
  lineId: string | null;
  // Faz K.8 (Madde 10) — `lineId` sadece "bir hat seçili" demektir, "bu hat
  // GERÇEKTEN bu ambalaj talebiyle uyumlu" demek DEĞİLDİR (K.4'ün uygunluk
  // matrisinden gelen sinyal). Aşama 5/6'nın geçiş kontrolü (gate) bu ayrı
  // bayrağa bakar -- `lineId` varlığına değil.
  lineEligible: boolean;
  recipeId: string | null;
  optimizationRunId: string | null;
  productionOrderId: string | null;

  setPackagingRequestId: (id: string | null) => void;
  setLineId: (id: string | null) => void;
  setLineEligible: (eligible: boolean) => void;
  setRecipeId: (id: string | null) => void;
  setOptimizationRunId: (id: string | null) => void;
  setProductionOrderId: (id: string | null) => void;
  reset: () => void;
}

const EMPTY_DOWNSTREAM_OF_PACKAGING_REQUEST = {
  lineId: null,
  lineEligible: false,
  recipeId: null,
  optimizationRunId: null,
  productionOrderId: null,
} as const;

const EMPTY_DOWNSTREAM_OF_LINE = {
  recipeId: null,
  optimizationRunId: null,
  productionOrderId: null,
} as const;

export const useCaseStore = create<CaseState>()(
  persist(
    (set) => ({
      packagingRequestId: null,
      lineId: null,
      lineEligible: false,
      recipeId: null,
      optimizationRunId: null,
      productionOrderId: null,

      setPackagingRequestId: (id) => set({ packagingRequestId: id, ...EMPTY_DOWNSTREAM_OF_PACKAGING_REQUEST }),
      // `lineEligible` her yeni/değişen hat seçiminde false'a döner --
      // gerçek uygunluk yalnızca `setLineEligible` ile (Aşama 4'ün
      // refreshMatches'i K.4 sonucunu okuyup) açıkça onaylanır.
      setLineId: (id) => set({ lineId: id, lineEligible: false, ...EMPTY_DOWNSTREAM_OF_LINE }),
      setLineEligible: (eligible) => set({ lineEligible: eligible }),
      // Farklı/yeni bir reçete seçilmesi (Aşama 5/6/7/11), ona bağlı olan
      // önceki üretim emrini geçersiz kılar -- yeni reçete için ayrıca
      // Aşama 9'dan yeni bir üretim emri açılmalı.
      setRecipeId: (id) => set({ recipeId: id, productionOrderId: null }),
      setOptimizationRunId: (id) => set({ optimizationRunId: id }),
      setProductionOrderId: (id) => set({ productionOrderId: id }),
      reset: () =>
        set({
          packagingRequestId: null,
          lineId: null,
          lineEligible: false,
          recipeId: null,
          optimizationRunId: null,
          productionOrderId: null,
        }),
    }),
    { name: "recete-os-case" }
  )
);
