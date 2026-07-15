"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { BACKGROUNDS } from "@/lib/game/content";
import type { BackgroundId } from "@/lib/game/types";

interface StartScreenProps {
  hasSavedGame: boolean;
  onResume: () => void;
  onStart: (name: string, background: BackgroundId) => void;
}

export function StartScreen({ hasSavedGame, onResume, onStart }: StartScreenProps) {
  const [name, setName] = useState("");
  const [background, setBackground] = useState<BackgroundId>("journalist");
  const [introPhase, setIntroPhase] = useState<"loading" | "leaving" | "ready">("loading");

  useEffect(() => {
    const leaveTimer = window.setTimeout(() => setIntroPhase("leaving"), 2200);
    const readyTimer = window.setTimeout(() => setIntroPhase("ready"), 2700);
    return () => {
      window.clearTimeout(leaveTimer);
      window.clearTimeout(readyTimer);
    };
  }, []);

  if (introPhase !== "ready") {
    return (
      <main className={`cover-splash ${introPhase === "leaving" ? "is-leaving" : ""}`}>
        <Image
          className="cover-splash-backdrop"
          src="/og.png"
          alt=""
          fill
          priority
          sizes="100vw"
        />
        <div className="cover-splash-art">
          <Image
            className="cover-splash-image"
            src="/og.png"
            alt="Ember Vanguard 灰石庄园调查档案封面：迷雾中的哥特庄园"
            fill
            priority
            sizes="100vw"
          />
        </div>
        <div className="cover-splash-shade" aria-hidden="true" />

        <div className="cover-loader" role="status" aria-live="polite">
          <div className="cover-loader-copy">
            <span>正在调取灰石庄园档案</span>
            <strong aria-hidden="true">&gt;&gt;&gt;</strong>
          </div>
          <div className="cover-loader-track" aria-hidden="true">
            <span />
          </div>
        </div>

        <button className="cover-skip" type="button" onClick={() => setIntroPhase("ready")}>
          跳过加载
        </button>
      </main>
    );
  }

  return (
    <main className="start-screen">
      <div className="start-noise" aria-hidden="true" />
      <header className="start-header">
        <span className="eyebrow">ARKHAM COUNTY ARCHIVE · CASE 23-07</span>
        <span className="start-date">OCTOBER 17, 1923</span>
      </header>

      <section className="start-hero selection-hero">
        <div className="hero-copy selection-copy">
          <div className="case-mark" aria-hidden="true">
            <span>灰</span>
          </div>
          <p className="hero-kicker">INVESTIGATOR INTAKE / CASE 23-07</p>
          <h1>
            CHOOSE
            <span>YOUR ROLE</span>
          </h1>
          <p className="hero-chinese">登记调查者档案</p>
          <p className="hero-summary">
            身份决定你如何阅读现场、抵抗恐惧，以及在庄园最深处作出最后的判断。
          </p>
          <div className="hero-rule" />
          <p className="hero-note">背景一旦确认，本次调查将正式开始。</p>
        </div>

        <form
          className="character-card selection-card"
          onSubmit={(event) => {
            event.preventDefault();
            onStart(name, background);
          }}
        >
          <div className="card-heading">
            <div>
              <span className="eyebrow">INVESTIGATOR REGISTRY</span>
              <h2>选择调查者背景</h2>
            </div>
            <span className="file-number">FILE / 001</span>
          </div>

          <label className="name-field">
            <span>调查者姓名</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="留空使用“调查者”"
              maxLength={24}
            />
          </label>

          <div className="background-list" role="radiogroup" aria-label="角色背景">
            {(Object.keys(BACKGROUNDS) as BackgroundId[]).map((id, index) => {
              const spec = BACKGROUNDS[id];
              const selected = id === background;
              return (
                <button
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  className={`background-option ${selected ? "is-selected" : ""}`}
                  onClick={() => setBackground(id)}
                  key={id}
                >
                  <span className="option-index">0{index + 1}</span>
                  <span className="option-main">
                    <strong>{spec.label}</strong>
                    <small>{spec.english}</small>
                    <span>{spec.description}</span>
                  </span>
                  <span className="option-stats">
                    <span>HP {spec.hp}</span>
                    <span>SAN {spec.san}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="ability-note">
            <span>特殊能力</span>
            <p>{BACKGROUNDS[background].ability}</p>
          </div>

          <button className="primary-action" type="submit">
            <span>推开铁门</span>
            <kbd>ENTER</kbd>
          </button>

          {hasSavedGame && (
            <button className="resume-action" type="button" onClick={onResume}>
              <span>继续上次档案</span>
              <kbd>CONTINUE</kbd>
            </button>
          )}
        </form>
      </section>

      <footer className="start-footer">
        <span>GREYSTONE MANOR / NEW ENGLAND</span>
        <span>建议佩戴耳机 · 本局进度自动保存在浏览器</span>
      </footer>
    </main>
  );
}
