import Nav from "../components/Nav";
import Footer from "../components/Footer";
import Hero from "./landing/Hero";
import Problem from "./landing/Problem";
import LoopSection from "./landing/LoopSection";
import RegistryVerify from "./landing/RegistryVerify";
import SignalsSection from "./landing/SignalsSection";
import Uncertainty from "./landing/Uncertainty";
import TrustSection from "./landing/TrustSection";
import ProductPreview from "./landing/ProductPreview";
import Architecture from "./landing/Architecture";
import FinalCta from "./landing/FinalCta";

export default function Landing() {
  return (
    <>
      <Nav />
      <main id="main">
        <Hero />
        <Problem />
        <LoopSection />
        <RegistryVerify />
        <SignalsSection />
        <Uncertainty />
        <TrustSection />
        <ProductPreview />
        <Architecture />
        <FinalCta />
      </main>
      <Footer />
    </>
  );
}
