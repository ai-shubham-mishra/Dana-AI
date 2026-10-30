import {Composition} from "remotion";
import {DanaAiDemo, totalDurationInFrames} from "./DanaAiDemo";
import {FeatureSlide} from "./slides";
import {FPS, HEIGHT, WIDTH} from "./theme";
import {featureScenes} from "./scenes";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="DanaAiDemo" component={DanaAiDemo} durationInFrames={totalDurationInFrames()} fps={FPS} width={WIDTH} height={HEIGHT} />
    {featureScenes.map((scene) => (
      <Composition
        key={scene.id}
        id={`feature-${scene.id}`}
        component={() => <FeatureSlide scene={scene} />}
        durationInFrames={scene.seconds * FPS}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    ))}
  </>
);
