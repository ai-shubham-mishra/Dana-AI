import {AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {BrowserFrame, Backdrop, Wordmark, useSceneFade} from "./components";
import {colors, fontFamily} from "./theme";
import {FeatureScene} from "./scenes";

// Words rise in one by one so long copy reads like it is being typed.
const RevealText: React.FC<{text: string; delay: number; style: React.CSSProperties}> = ({text, delay, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={style}>
      {text.split(" ").map((word, i) => {
        const p = spring({frame: frame - delay - i * 2, fps, config: {damping: 200}});
        return (
          <span key={i} style={{display: "inline-block", opacity: p, transform: `translateY(${(1 - p) * 14}px)`, marginRight: "0.28em"}}>
            {word}
          </span>
        );
      })}
    </div>
  );
};

// Prompt typed into a chat-style pill, mirroring the composer.
const TypedPrompt: React.FC<{text: string; start: number}> = ({text, start}) => {
  const frame = useCurrentFrame();
  const chars = Math.max(0, Math.min(text.length, Math.floor((frame - start) * 1.1)));
  const visible = text.slice(0, chars);
  const done = chars >= text.length;
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 12,
        background: colors.orange,
        color: "#FFFFFF",
        fontFamily,
        fontSize: 26,
        fontWeight: 500,
        padding: "16px 26px",
        borderRadius: 999,
        boxShadow: "0 14px 30px rgba(245, 77, 2, 0.28)",
        maxWidth: 620,
      }}
    >
      <span>{visible}</span>
      {!done && <span style={{width: 2, height: 28, background: "#FFFFFF", opacity: frame % 20 < 10 ? 1 : 0}} />}
    </div>
  );
};

export const FeatureSlide: React.FC<{scene: FeatureScene}> = ({scene}) => {
  const frame = useCurrentFrame();
  const fade = useSceneFade();
  const kickerIn = interpolate(frame, [0, 14], [0, 1], {extrapolateRight: "clamp"});
  const promptStart = 40;
  return (
    <AbsoluteFill style={{opacity: fade}}>
      <Backdrop />
      <AbsoluteFill style={{flexDirection: "row", alignItems: "center", padding: "0 120px", gap: 80}}>
        <div style={{width: 560, flexShrink: 0}}>
          <div
            style={{
              fontFamily,
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: 2.5,
              color: colors.magenta,
              opacity: kickerIn,
              marginBottom: 24,
            }}
          >
            {scene.kicker}
          </div>
          <RevealText
            text={scene.title}
            delay={6}
            style={{fontFamily, fontSize: 68, fontWeight: 600, lineHeight: 1.08, letterSpacing: -1.5, color: colors.ink, marginBottom: 28}}
          />
          <RevealText
            text={scene.body}
            delay={18}
            style={{fontFamily, fontSize: 26, lineHeight: 1.5, color: colors.muted, marginBottom: 40}}
          />
          {scene.prompt && <TypedPrompt text={scene.prompt} start={promptStart} />}
        </div>
        <BrowserFrame src={staticFile(`captures/${scene.image}`)} width={1100} height={690} enterDelay={4} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const IntroSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fade = useSceneFade(14);
  const logo = spring({frame: frame - 4, fps, config: {damping: 14, stiffness: 120}});
  const tag = spring({frame: frame - 26, fps, config: {damping: 200}});
  return (
    <AbsoluteFill style={{opacity: fade}}>
      <Backdrop dark />
      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 36}}>
        <div style={{transform: `scale(${0.8 + logo * 0.2})`, opacity: logo}}>
          <Wordmark size={190} dark />
        </div>
        <div
          style={{
            fontFamily,
            fontSize: 38,
            color: colors.nightMuted,
            opacity: tag,
            transform: `translateY(${(1 - tag) * 20}px)`,
            letterSpacing: -0.4,
          }}
        >
          Agentic marketing-model training, end to end.
        </div>
        <div style={{width: 360, height: 4, borderRadius: 2, background: colors.nightBorder, overflow: "hidden", opacity: tag}}>
          <div style={{width: `${interpolate(frame, [30, 120], [0, 100], {extrapolateRight: "clamp"})}%`, height: "100%", background: `linear-gradient(90deg, ${colors.magenta}, ${colors.purple}, ${colors.teal})`}} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

export const OutroSlide: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fade = useSceneFade(14);
  const lines = ["Connect your data.", "Ask Dana.", "Ship a model."];
  return (
    <AbsoluteFill style={{opacity: fade}}>
      <Backdrop dark />
      <AbsoluteFill style={{alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 18}}>
        {lines.map((line, i) => {
          const p = spring({frame: frame - 6 - i * 12, fps, config: {damping: 200}});
          return (
            <div
              key={line}
              style={{
                fontFamily,
                fontSize: i === 2 ? 96 : 72,
                fontWeight: 600,
                letterSpacing: -2,
                color: i === 2 ? colors.magenta : colors.nightInk,
                opacity: p,
                transform: `translateY(${(1 - p) * 30}px)`,
              }}
            >
              {line}
            </div>
          );
        })}
        <div style={{marginTop: 40, opacity: interpolate(frame, [60, 80], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}}>
          <Wordmark size={44} dark />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
