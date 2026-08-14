<template>
  <aside class="min-w-0 bg-[#f4f4f4] lg:h-full lg:min-h-0 lg:overflow-hidden">
    <div class="flex min-w-0 flex-col gap-2 pr-1 lg:h-full lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain">
      <AnalysisAreaCard />
      <OsmFeatureSidebar />
      <PolygonStatistics />
      <FastFacts />
      <ViewportOsmSummary />
      <IndustryChart />
      <RentTable />
    </div>
  </aside>
</template>
