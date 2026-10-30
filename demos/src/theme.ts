// Palette mirrors frontend/app/globals.css (light and dark tokens).
import {loadFont} from "@remotion/google-fonts/Geist";

export const {fontFamily} = loadFont("normal", {
  weights: ["400", "500", "600", "700"],
  subsets: ["latin"],
});

export const colors = {
  cream: "#FFFBEB",
  ink: "#221436",
  muted: "#6B696E",
  border: "#E1DAE6",
  card: "#FFFFFF",
  magenta: "#DD33FF",
  magentaWash: "#FFE5FF",
  purple: "#A855F7",
  purpleMuted: "#6F539E",
  orange: "#F54D02",
  teal: "#5ABAB7",
  night: "#0C0524",
  nightCard: "#160B32",
  nightInk: "#F4EFFF",
  nightMuted: "#A99CC9",
  nightBorder: "#271452",
};

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;
