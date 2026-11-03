import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {colors, fontFamily} from "./theme";

// Slow-drifting brand gradient behind every scene.
export const Backdrop: React.FC<{dark?: boolean}> = ({dark = false}) => {
  const frame = useCurrentFrame();
  const drift = Math.sin(frame / 60) * 40;
  return (
    <AbsoluteFill
      style={{
        background: dark ? colors.night : colors.cream,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 900,
          height: 900,
          left: -200 + drift,
          top: -300,
          borderRadius: "50%",
          background: dark
            ? `radial-gradient(circle, ${colors.magenta}55 0%, transparent 65%)`
            : `radial-gradient(circle, ${colors.magentaWash} 0%, transparent 65%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 1000,
          height: 1000,
          right: -300 - drift,
          bottom: -400,
          borderRadius: "50%",
          background: dark
            ? `radial-gradient(circle, ${colors.purple}4D 0%, transparent 65%)`
            : `radial-gradient(circle, ${colors.purple}22 0%, transparent 65%)`,
        }}
      />
    </AbsoluteFill>
  );
};

// Matches the app's wordmark: "Dana" in ink, "AI" in magenta.
export const Wordmark: React.FC<{size: number; dark?: boolean}> = ({size, dark = false}) => (
  <div
    style={{
      fontFamily,
      fontSize: size,
      fontWeight: 600,
      letterSpacing: -size * 0.02,
      color: dark ? colors.nightInk : colors.ink,
      lineHeight: 1,
    }}
  >
    Dana <span style={{color: colors.magenta}}>AI</span>
  </div>
);

// Browser-style frame around a real capture with a slow Ken Burns zoom.
export const BrowserFrame: React.FC<{src: string; width: number; height: number; enterDelay?: number}> = ({
  src,
  width,
  height,
  enterDelay = 0,
}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const enter = spring({frame: frame - enterDelay, fps, config: {damping: 200}});
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.04], {extrapolateRight: "clamp"});
  const chrome = 48;
  return (
    <div
      style={{
        width,
        height: height + chrome,
        borderRadius: 18,
        overflow: "hidden",
        background: colors.card,
        border: `1px solid ${colors.border}`,
        boxShadow: "0 30px 80px rgba(76, 45, 120, 0.22)",
        opacity: enter,
        transform: `translateY(${(1 - enter) * 60}px) scale(${0.98 + enter * 0.02})`,
      }}
    >
      <div
        style={{
          height: chrome,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "0 18px",
          background: colors.cream,
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
          <div key={c} style={{width: 12, height: 12, borderRadius: 6, background: c}} />
        ))}
        <div
          style={{
            marginLeft: 18,
            fontFamily,
            fontSize: 16,
            color: colors.muted,
            background: colors.card,
            borderRadius: 8,
            padding: "6px 14px",
            border: `1px solid ${colors.border}`,
          }}
        >
          localhost:3000
        </div>
      </div>
      <div style={{width, height, overflow: "hidden", position: "relative"}}>
        <img
          src={src}
          style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "top left", transform: `scale(${zoom})`, transformOrigin: "top left"}}
        />
      </div>
    </div>
  );
};

// Fades a block in and out across the scene.
export const useSceneFade = (fadeFrames = 12) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return interpolate(frame, [0, fadeFrames, durationInFrames - fadeFrames, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
};
