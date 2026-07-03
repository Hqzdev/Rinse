import { ArchitectureSection } from "./components/architecture-section";
import { FinalCta } from "./components/final-cta";
import { Hero } from "./components/hero";
import { ObjectBlocks } from "./components/object-blocks";
import { ProcessStrip } from "./components/process-strip";
import { SiteHeader } from "./components/site-header";
import { WebDemo } from "./components/web-demo";

export default function Page() {
  return (
    <>
      <SiteHeader />
      <main>
        <WebDemo />
        <Hero />
        <ProcessStrip />
        <ObjectBlocks />
        <ArchitectureSection />
        <FinalCta />
      </main>
    </>
  );
}
