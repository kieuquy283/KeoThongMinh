import { useEffect, useMemo, useState } from "react";

import type { MascotEmotion, MascotStatus, MascotVisual } from "../utils/keobotMascotState";
import {
  MASCOT_STATUS_LABELS,
  getBaseVisualForStatus,
  getMascotAssetPath,
  getMascotFallbackChain,
  shouldBlink,
} from "../utils/keobotMascotState";

interface KeoBotAnimatedMascotProps {
  status: MascotStatus;
  emotion?: MascotEmotion;
  isVisible?: boolean;
  className?: string;
}

function getSpeakingFrame(index: number): MascotVisual {
  return (["speaking_1", "speaking_2", "speaking_3"] as const)[index % 3];
}

export function KeoBotAnimatedMascot({
  status,
  emotion = "neutral",
  isVisible = true,
  className,
}: KeoBotAnimatedMascotProps) {
  const [speakingFrame, setSpeakingFrame] = useState(0);
  const [blinkFrame, setBlinkFrame] = useState<0 | 1 | 2>(0);
  const [assetFailures, setAssetFailures] = useState<string[]>([]);

  useEffect(() => {
    if (status !== "speaking") {
      setSpeakingFrame(0);
      return;
    }

    const interval = window.setInterval(() => {
      setSpeakingFrame((current) => (current + 1) % 3);
    }, 150);

    return () => {
      window.clearInterval(interval);
    };
  }, [status]);

  useEffect(() => {
    if (!shouldBlink(status, emotion) || !isVisible) {
      setBlinkFrame(0);
      return;
    }

    let cancelled = false;
    let timeoutId = 0;

    const scheduleBlink = () => {
      const delay = 2400 + Math.round(Math.random() * 2600);
      timeoutId = window.setTimeout(() => {
        if (cancelled) {
          return;
        }

        setBlinkFrame(1);
        window.setTimeout(() => {
          if (cancelled) {
            return;
          }

          setBlinkFrame(2);
          window.setTimeout(() => {
            if (cancelled) {
              return;
            }

            setBlinkFrame(0);
            scheduleBlink();
          }, 80);
        }, 70);
      }, delay);
    };

    scheduleBlink();

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [emotion, isVisible, status]);

  const baseVisual = useMemo(() => getBaseVisualForStatus(status, emotion), [emotion, status]);

  const activeVisual = useMemo<MascotVisual>(() => {
    if (status === "speaking") {
      return getSpeakingFrame(speakingFrame);
    }

    if (blinkFrame === 1) {
      return "blink_1";
    }

    if (blinkFrame === 2) {
      return "blink_2";
    }

    return baseVisual;
  }, [baseVisual, blinkFrame, speakingFrame, status]);

  const src = useMemo(() => {
    const chain = getMascotFallbackChain(activeVisual);
    return chain.find((path) => !assetFailures.includes(path)) ?? getMascotAssetPath("idle");
  }, [activeVisual, assetFailures]);

  const stageClasses = [
    "keobot-stage",
    `is-${status}`,
    status === "speaking" ? "is-speaking-loop" : "",
    blinkFrame > 0 ? "is-blinking" : "",

    !isVisible ? "is-hidden" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const showThinkingDots = status === "thinking" || status === "loading";

  return (
    <section className="panel keobot-card" aria-live="polite">
      <div className="panel-inner keobot-panel">
        <div className="status-bubble mascot-status-bubble">
          <span className={`status-dot mascot-status-dot is-${status}`} />
          <span className="status-label">{MASCOT_STATUS_LABELS[status]}</span>
        </div>

        <div className={stageClasses}>
          <div className="keobot-stage-glow" />
          <div className="keobot-art">
            <img
              key={src}
              className="keobot-image"
              src={src}
              alt={`Kẹo Thông Minh mascot - ${status} - ${emotion}`}
              onError={() => {
                setAssetFailures((current) => (current.includes(src) ? current : [...current, src]));
              }}
            />
          </div>
          {showThinkingDots ? (
            <div className="keobot-thinking-indicator" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          ) : null}
          {status === "idle" && emotion === "celebrate" ? <div className="keobot-sparkles" aria-hidden="true" /> : null}
        </div>

        <div className="keobot-copy">
          <div>
            <p className="section-kicker">Desktop companion</p>
            <h2 className="keobot-name">Kẹo Thông Minh</h2>
            <p className="keobot-tagline">2D Vietnamese AI desktop assistant</p>
          </div>

          <div className="keobot-status-card">
            <span className="keobot-status-label">{status}</span>
            <strong>{MASCOT_STATUS_LABELS[status]}</strong>
            <p>
              Emotion: <span className="keobot-emotion">{emotion}</span>
            </p>
          </div>

          <div className="keobot-meta">
            <div className="meta-row">
              <span>Render mode</span>
              <strong>2D animated assets</strong>
            </div>
            <div className="meta-row">
              <span>Fallback</span>
              <strong>Safe asset chain</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
