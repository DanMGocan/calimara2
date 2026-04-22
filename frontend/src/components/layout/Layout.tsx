import { Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Navbar } from "./Navbar";
import { SideMenu } from "./SideMenu";
import { Footer } from "./Footer";
import { BackgroundAtmosphere } from "./BackgroundAtmosphere";

export function Layout() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="site" data-logged={isAuthenticated ? "in" : "out"}>
      <BackgroundAtmosphere />
      <Navbar />
      <Outlet />
      <Footer />
      <SideMenu />
    </div>
  );
}
