import {Series} from "remotion";
import {FPS} from "./theme";
import {featureScenes} from "./scenes";
import {IntroSlide, OutroSlide, FeatureSlide} from "./slides";

export const INTRO_SECONDS = 6;
export const OUTRO_SECONDS = 6;

export const totalDurationInFrames = (): number =>
  (INTRO_SECONDS + OUTRO_SECONDS + featureScenes.reduce((sum, s) => sum + s.seconds, 0)) * FPS;

export const DanaAiDemo: React.FC = () => (
  <Series>
    <Series.Sequence durationInFrames={INTRO_SECONDS * FPS}>
      <IntroSlide />
    </Series.Sequence>
    {featureScenes.map((scene) => (
      <Series.Sequence key={scene.id} durationInFrames={scene.seconds * FPS}>
        <FeatureSlide scene={scene} />
      </Series.Sequence>
    ))}
    <Series.Sequence durationInFrames={OUTRO_SECONDS * FPS}>
      <OutroSlide />
    </Series.Sequence>
  </Series>
);
