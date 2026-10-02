import { AnnouncementBar } from "@/components/landing/AnnouncementBar";
import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { IntegrationStrip } from "@/components/landing/IntegrationStrip";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { ValueSection } from "@/components/landing/ValueSection";
import { HowItWorksSection } from "@/components/landing/HowItWorksSection";
import { FeatureSections } from "@/components/landing/FeatureSections";
import { UseCasesSection } from "@/components/landing/UseCasesSection";
import { SecuritySection } from "@/components/landing/SecuritySection";
import { FAQSection, FinalCTA } from "@/components/landing/FAQSection";
import { Footer } from "@/components/landing/Footer";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white text-[#111111] font-sans selection:bg-[#F3E8FF] selection:text-[#581C87]">
      <AnnouncementBar />
      <Navbar />
      <main>
        <HeroSection />
        <IntegrationStrip />
        <ProblemSection />
        <ValueSection />
        <HowItWorksSection />
        <FeatureSections />
        <UseCasesSection />
        <SecuritySection />
        <FAQSection />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  );
}

