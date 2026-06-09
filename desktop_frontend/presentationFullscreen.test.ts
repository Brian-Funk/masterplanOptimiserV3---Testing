import { afterEach, describe, expect, it, vi } from "vitest";
import {
  getPresentationFullscreenState,
  setPresentationFullscreen,
  togglePresentationFullscreen,
} from "@/lib/presentationFullscreen";

function setDocumentFullscreenElement(value: Element | null) {
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true,
    value,
  });
}

afterEach(() => {
  delete window.electron;
  vi.restoreAllMocks();
  setDocumentFullscreenElement(null);
});

describe("presentation fullscreen helper", () => {
  it("uses the Electron window bridge when available", async () => {
    const setWindowFullscreen = vi.fn().mockResolvedValue({
      success: true,
      isFullscreen: true,
    });
    window.electron = {
      isElectron: true,
      getWindowFullscreenState: vi.fn().mockResolvedValue({
        success: true,
        isFullscreen: false,
      }),
      setWindowFullscreen,
    };

    const result = await togglePresentationFullscreen();

    expect(setWindowFullscreen).toHaveBeenCalledWith(true);
    expect(result).toEqual({ success: true, isFullscreen: true });
  });

  it("reads native fullscreen state from Electron when available", async () => {
    window.electron = {
      isElectron: true,
      getWindowFullscreenState: vi.fn().mockResolvedValue({
        success: true,
        isFullscreen: true,
      }),
    };

    await expect(getPresentationFullscreenState()).resolves.toBe(true);
  });

  it("falls back to browser requestFullscreen outside Electron", async () => {
    const requestFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document.documentElement, "requestFullscreen", {
      configurable: true,
      value: requestFullscreen,
    });
    setDocumentFullscreenElement(null);

    const result = await setPresentationFullscreen(true);

    expect(requestFullscreen).toHaveBeenCalledTimes(1);
    expect(result).toEqual({ success: true, isFullscreen: true });
  });

  it("falls back to browser exitFullscreen outside Electron", async () => {
    const exitFullscreen = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(document, "exitFullscreen", {
      configurable: true,
      value: exitFullscreen,
    });
    setDocumentFullscreenElement(document.documentElement);

    const result = await setPresentationFullscreen(false);

    expect(exitFullscreen).toHaveBeenCalledTimes(1);
    expect(result).toEqual({ success: true, isFullscreen: false });
  });
});
