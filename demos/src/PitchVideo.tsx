import {
  Audio,
  AbsoluteFill,
  Easing,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {Backdrop, Wordmark, useSceneFade} from "./components";
import {colors, fontFamily, FPS, WIDTH} from "./theme";
import script from "./script.json";
import timingJson from "./timing.json";

// Measured with ffprobe-style output on public/footage; the training clip is played at TRAIN_SPEED.
const FOOTAGE_SECONDS = {train: 60.84, lookup: 17.8, jobs: 13.88};
const TRAIN_SPEED = 1.6;
const PAD = 1.2;
const timing = timingJson as Record<string, number>;

const sceneSeconds: Record<string, number> = {
  intro: Math.max(timing.intro + PAD, 6),
  problem: timing.problem + PAD,
  solution: timing.solution + PAD,
  train: Math.max(timing.train + 1.4, FOOTAGE_SECONDS.train / TRAIN_SPEED + 0.5),
  lookup: Math.max(timing.lookup + PAD, FOOTAGE_SECONDS.lookup + 0.5),
  jobs: Math.max(timing.jobs + PAD, FOOTAGE_SECONDS.jobs + 0.5),
  outro: timing.outro + 2.5,
};

type SceneSlot = {id: string; caption: string; from: number; frames: number};

export const SCENES: SceneSlot[] = (() => {
  let from = 0;
  return (script as {id: string; caption: string}[]).map(({id, caption}) => {
    const frames = Math.round(sceneSeconds[id] * FPS);
    const slot = {id, caption, from, frames};
    from += frames;
    return slot;
  });
})();

export const pitchDurationInFrames = () => SCENES.reduce((sum, scene) => sum + scene.frames, 0);

const scene = (id: string) => {
  const found = SCENES.find((slot) => slot.id === id);
  if (!found) throw new Error(`Unknown scene ${id}`);
  return found;
};

const sec = (seconds: number) => Math.round(seconds * FPS);
// The run is queued as the recording ends, near the end of the sped-up training clip.
const TRAIN_QUEUED_AT = sec(35);

const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rotate = interpolate(frame, [0, 170], [-80, 20], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const logo = spring({frame: frame - 14, fps, config: {damping: 14}});
  const tagline = interpolate(frame, [44, 70], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const cards = [colors.magenta, colors.purple, colors.teal, colors.orange];
  return (
    <>
      <Backdrop dark />
      <AbsoluteFill style={{perspective: 1600, justifyContent: "center", alignItems: "center"}}>
        <div style={{position: "relative", width: 0, height: 0, transformStyle: "preserve-3d", transform: `rotateX(-10deg) rotateY(${rotate}deg)`}}>
          {cards.map((c, i) => (
            <div
              key={c}
              style={{
                position: "absolute",
                width: 560,
                height: 340,
                left: -280,
                top: -170,
                borderRadius: 36,
                background: `linear-gradient(135deg, ${c}99, ${colors.night}EE)`,
                border: `1px solid ${c}`,
                transform: `rotateY(${i * 90}deg) translateZ(440px)`,
                boxShadow: `0 0 90px ${c}55`,
              }}
            />
          ))}
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 36}}>
        <div style={{transform: `scale(${0.7 + 0.3 * logo})`, opacity: logo}}>
          <Wordmark size={200} dark />
        </div>
        <div style={{fontFamily, fontSize: 36, color: colors.nightMuted, letterSpacing: 4, textTransform: "uppercase", opacity: tagline}}>
          Marketing mix models · in minutes
        </div>
      </AbsoluteFill>
    </>
  );
};

const Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const steps = [
    ["Export the data", "Day 1"],
    ["Queue for an analyst", "Day 2"],
    ["Build and review", "Day 3"],
    ["Results arrive", "Day 4+"],
  ];
  const title = spring({frame, fps, config: {damping: 200}});
  return (
    <>
      <Backdrop />
      <AbsoluteFill style={{padding: "150px 200px", fontFamily, color: colors.ink}}>
        <div style={{fontSize: 96, fontWeight: 700, letterSpacing: -2, opacity: title, transform: `translateY(${(1 - title) * 30}px)`}}>
          Waiting days for one model
        </div>
        <div style={{display: "flex", gap: 28, marginTop: 130, alignItems: "center"}}>
          {steps.map(([label, day], i) => {
            const p = spring({frame: frame - 24 - i * 18, fps, config: {damping: 16}});
            return (
              <div key={label} style={{display: "flex", alignItems: "center", gap: 28}}>
                <div
                  style={{
                    width: 300,
                    padding: "44px 32px",
                    borderRadius: 26,
                    background: colors.card,
                    border: `1px solid ${colors.border}`,
                    boxShadow: "0 24px 60px rgba(76,45,120,0.16)",
                    opacity: p,
                    transform: `translateY(${(1 - p) * 40}px)`,
                  }}
                >
                  <div style={{display: "inline-block", fontSize: 26, fontWeight: 600, color: colors.orange, background: "#FFF1EA", padding: "6px 16px", borderRadius: 999}}>
                    {day}
                  </div>
                  <div style={{fontSize: 38, fontWeight: 600, marginTop: 22, lineHeight: 1.2}}>{label}</div>
                </div>
                {i < steps.length - 1 && (
                  <div style={{width: interpolate(p, [0, 1], [0, 40]), height: 4, background: colors.border, borderRadius: 2}} />
                )}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </>
  );
};

const Solution: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const title = spring({frame, fps, config: {damping: 200}});
  const steps = [
    ["01", "Describe", "Say which model you need, in plain language.", colors.magenta],
    ["02", "Approve", "Dana asks only for the choices that matter.", colors.purple],
    ["03", "Track", "Check progress in the chat or on the Jobs page.", colors.teal],
  ];
  return (
    <>
      <Backdrop />
      <AbsoluteFill style={{padding: "150px 200px", fontFamily, color: colors.ink}}>
        <div style={{fontSize: 96, fontWeight: 700, letterSpacing: -2, opacity: title, transform: `translateY(${(1 - title) * 30}px)`}}>
          Describe it. Approve it. Track it.
        </div>
        <div style={{display: "flex", gap: 44, marginTop: 120}}>
          {steps.map(([num, head, body, tone], i) => {
            const p = spring({frame: frame - 20 - i * 16, fps, config: {damping: 14}});
            return (
              <div
                key={num}
                style={{
                  flex: 1,
                  padding: 50,
                  borderRadius: 30,
                  background: colors.card,
                  border: `1px solid ${colors.border}`,
                  borderTop: `8px solid ${tone}`,
                  boxShadow: "0 24px 60px rgba(76,45,120,0.16)",
                  opacity: p,
                  transform: `scale(${0.9 + 0.1 * p})`,
                }}
              >
                <div style={{fontSize: 30, color: tone, fontWeight: 700}}>{num}</div>
                <div style={{fontSize: 60, fontWeight: 700, marginTop: 14}}>{head}</div>
                <div style={{fontSize: 30, color: colors.muted, marginTop: 18, lineHeight: 1.4}}>{body}</div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </>
  );
};

// Browser frame around a real capture, with a live video inside.
const BrowserVideo: React.FC<{file: string; playbackRate?: number}> = ({file, playbackRate = 1}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 200}});
  const frameWidth = 1400;
  const frameHeight = 875;
  const chrome = 48;
  return (
    <div
      style={{
        position: "absolute",
        left: (WIDTH - frameWidth) / 2,
        top: 40,
        width: frameWidth,
        height: frameHeight + chrome,
        borderRadius: 18,
        overflow: "hidden",
        background: colors.card,
        border: `1px solid ${colors.border}`,
        boxShadow: "0 30px 80px rgba(76, 45, 120, 0.22)",
        opacity: enter,
        transform: `translateY(${(1 - enter) * 60}px)`,
      }}
    >
      <div style={{height: chrome, display: "flex", alignItems: "center", gap: 10, padding: "0 18px", background: colors.cream, borderBottom: `1px solid ${colors.border}`}}>
        {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
          <div key={c} style={{width: 12, height: 12, borderRadius: 6, background: c}} />
        ))}
        <div style={{marginLeft: 18, fontFamily, fontSize: 16, color: colors.muted, background: colors.card, borderRadius: 8, padding: "6px 14px", border: `1px solid ${colors.border}`}}>
          localhost:3000
        </div>
      </div>
      <div style={{width: frameWidth, height: frameHeight, overflow: "hidden"}}>
        <OffthreadVideo
          src={staticFile(`footage/${file}`)}
          playbackRate={playbackRate}
          muted
          style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "top left"}}
        />
      </div>
    </div>
  );
};

// Popup that springs in at a given local frame.
const Callout: React.FC<{at: number; x: number; y: number; title: string; body?: string; tone?: string}> = ({at, x, y, title, body, tone = colors.magenta}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: frame - at, fps, config: {damping: 12, stiffness: 140}});
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: 440,
        padding: "18px 24px",
        borderRadius: 16,
        background: colors.card,
        border: `1px solid ${colors.border}`,
        borderLeft: `6px solid ${tone}`,
        boxShadow: "0 20px 50px rgba(76,45,120,0.25)",
        fontFamily,
        opacity: p,
        transform: `translateY(${(1 - p) * 24}px) scale(${0.9 + 0.1 * p})`,
      }}
    >
      <div style={{fontSize: 26, fontWeight: 600, color: colors.ink}}>{title}</div>
      {body && <div style={{fontSize: 20, color: colors.muted, marginTop: 6, lineHeight: 1.35}}>{body}</div>}
    </div>
  );
};

const Caption: React.FC<{text: string}> = ({text}) => {
  const opacity = useSceneFade(14);
  return (
    <div style={{position: "absolute", left: 0, right: 0, bottom: 30, textAlign: "center", fontFamily, fontSize: 34, fontWeight: 500, color: colors.ink, opacity}}>
      {text}
    </div>
  );
};

const TrainScene: React.FC = () => (
  <>
    <Backdrop />
    <BrowserVideo file="train-agent.webm" playbackRate={TRAIN_SPEED} />
    <Callout at={sec(2)} x={1440} y={150} title="You approve each choice" body="Dana asks; nothing runs on a guess." tone={colors.magenta} />
    <Callout at={TRAIN_QUEUED_AT} x={1440} y={420} title="Run queued" body="Dana reports the run ID in the chat." tone={colors.teal} />
  </>
);

const LookupScene: React.FC = () => (
  <>
    <Backdrop />
    <BrowserVideo file="lookup-agent.webm" />
    <Callout at={sec(2)} x={1440} y={150} title="Same chat, live status" body="Ask for the job; get the KPI and dates." tone={colors.purple} />
  </>
);

const JobsScene: React.FC = () => (
  <>
    <Backdrop />
    <BrowserVideo file="jobs-ui.webm" />
    <Callout at={sec(2)} x={1440} y={150} title="One table for every run" body="Progress and status at a glance." tone={colors.teal} />
    <Callout at={sec(5)} x={1440} y={420} title="Click a row for details" body="Inputs, artifacts and the run log." tone={colors.magenta} />
  </>
);

const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const logo = spring({frame, fps, config: {damping: 14}});
  const points = ["Transparent", "Approved by you", "In minutes"];
  return (
    <>
      <Backdrop dark />
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 48, fontFamily}}>
        <div style={{transform: `scale(${0.8 + 0.2 * logo})`, opacity: logo}}>
          <Wordmark size={180} dark />
        </div>
        <div style={{display: "flex", gap: 28}}>
          {points.map((text, i) => {
            const p = spring({frame: frame - 20 - i * 12, fps, config: {damping: 14}});
            return (
              <div key={text} style={{padding: "16px 30px", borderRadius: 999, border: `1px solid ${colors.nightBorder}`, background: colors.nightCard, color: colors.nightInk, fontSize: 30, opacity: p, transform: `translateY(${(1 - p) * 20}px)`}}>
                ✓ {text}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </>
  );
};

const sceneView = (id: string) => {
  switch (id) {
    case "intro":
      return <Intro />;
    case "problem":
      return <Problem />;
    case "solution":
      return <Solution />;
    case "train":
      return <TrainScene />;
    case "lookup":
      return <LookupScene />;
    case "jobs":
      return <JobsScene />;
    case "outro":
      return <Outro />;
    default:
      throw new Error(`No view for scene ${id}`);
  }
};

export const PitchVideo: React.FC = () => {
  const trainQueued = scene("train").from + TRAIN_QUEUED_AT;
  return (
    <AbsoluteFill style={{background: colors.cream}}>
      {SCENES.map((slot) => (
        <Sequence key={slot.id} from={slot.from} durationInFrames={slot.frames}>
          <AbsoluteFill>
            {sceneView(slot.id)}
            {!["intro", "outro"].includes(slot.id) && <Caption text={slot.caption} />}
          </AbsoluteFill>
        </Sequence>
      ))}
      {SCENES.map((slot) => (
        <Sequence key={`vo-${slot.id}`} from={slot.from + 12}>
          <Audio src={staticFile(`audio/narration/${slot.id}.wav`)} />
        </Sequence>
      ))}
      <Sequence from={sec(0.2)}>
        <Audio src={staticFile("audio/sfx/chime.wav")} volume={0.5} />
      </Sequence>
      {SCENES.slice(1).map((slot) => (
        <Sequence key={`whoosh-${slot.id}`} from={slot.from}>
          <Audio src={staticFile("audio/sfx/whoosh.wav")} volume={0.4} />
        </Sequence>
      ))}
      <Sequence from={scene("train").from + sec(2)}>
        <Audio src={staticFile("audio/sfx/pop.wav")} volume={0.5} />
      </Sequence>
      <Sequence from={trainQueued}>
        <Audio src={staticFile("audio/sfx/success.wav")} volume={0.6} />
      </Sequence>
      <Sequence from={scene("jobs").from + sec(5)}>
        <Audio src={staticFile("audio/sfx/click.wav")} volume={0.6} />
      </Sequence>
    </AbsoluteFill>
  );
};
