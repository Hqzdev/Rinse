import { ArchitectureSection } from "./components/architecture-section";
import { FinalCta } from "./components/final-cta";
import { Hero } from "./components/hero";
import { ObjectBlocks } from "./components/object-blocks";
import { ProcessStrip } from "./components/process-strip";
import { SiteHeader } from "./components/site-header";

export default function Page() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <ProcessStrip />
        <ObjectBlocks />
        <ArchitectureSection />
        <FinalCta />
      </main>
    </>
  );
}
