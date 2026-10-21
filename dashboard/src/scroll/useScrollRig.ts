// The scroll rig: Lenis smooth scroll driven by the GSAP ticker (one clock for the DOM and the 3D
// loop), ScrollTrigger kept in step with Lenis, and a scroll-progress value for the render loop.
// With reduced motion there is no smoothing: jumps are instant and the camera does not move.
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";
import { useEffect, type RefObject } from "react";
import { useAppStore } from "../app/appStore";
import { CHAPTERS, chapterLocal, chapterScrollY, progressFromScroll } from "./chapters";
import { scrollApi, scrollState } from "./scrollState";

gsap.registerPlugin(ScrollTrigger);

const RENDERED = CHAPTERS.filter((c) => c.rendered);

export function useScrollRig(root: RefObject<HTMLElement | null>, reducedMotion: boolean): void {
  useEffect(() => {
    // Everything made here is cleaned up below, because StrictMode runs effects twice in dev.
    const lenis = reducedMotion ? null : new Lenis({ autoRaf: false });
    const tick = (time: number) => lenis?.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    lenis?.on("scroll", ScrollTrigger.update);

    const maxScroll = () => Math.max(document.documentElement.scrollHeight - window.innerHeight, 0);
    const update = () => {
      const y = window.scrollY;
      scrollState.progress = progressFromScroll(y, maxScroll());
      const at = chapterLocal(RENDERED, y, window.innerHeight, maxScroll());
      scrollState.chapter = at.index;
      scrollState.local = at.t;
      useAppStore.getState().setChapter(at.index);
    };
    const trigger = ScrollTrigger.create({
      trigger: root.current,
      start: "top top",
      end: "bottom bottom",
      onUpdate: update,
      onRefresh: update,
    });
    // Lenis moves the page between ScrollTrigger updates, so read the position on every tick too.
    gsap.ticker.add(update);

    const jump = (y: number) => {
      if (lenis) lenis.scrollTo(y, { duration: 1.2 });
      else window.scrollTo({ top: y, behavior: "auto" });
    };
    scrollApi.toChapter = (index) => jump(chapterScrollY(RENDERED, index, window.innerHeight, maxScroll()));
    scrollApi.by = (viewports) => jump(Math.min(Math.max(window.scrollY + viewports * window.innerHeight, 0), maxScroll()));
    scrollApi.toEdge = (where) => jump(where === "start" ? 0 : maxScroll());
    update();

    return () => {
      trigger.kill();
      gsap.ticker.remove(tick);
      gsap.ticker.remove(update);
      gsap.ticker.lagSmoothing(500, 33);
      lenis?.destroy();
      scrollApi.toChapter = () => {};
      scrollApi.by = () => {};
      scrollApi.toEdge = () => {};
    };
  }, [root, reducedMotion]);
}
