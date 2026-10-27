import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import type { ImageAnalysis } from "../../types/ai";
import ImageAnalysisResult, { ImageAnalysisToggle } from "./ImageAnalysisResult";

const BASE: ImageAnalysis = {
  valid: true,
  width: 640,
  height: 480,
  blur_score: 450.2,
  is_blurry: false,
  brightness: 120,
  too_dark: false,
  too_bright: false,
  detections: [{ label: "dog", confidence: 0.91, box: [1, 2, 30, 40] }],
  category_hints: [{ slug: "stray-animals", reason: "Animal detected (dog). 'Stray Animals' may fit." }],
  detector_available: true,
  model: "yolov8n (COCO)",
  disclaimer: "It cannot recognise potholes, garbage or other civic problems.",
};

test("renders detections, hints labelled as hints, and the disclaimer", () => {
  render(<ImageAnalysisResult result={BASE} />);
  expect(screen.getByText("Photo quality looks fine.")).toBeInTheDocument();
  expect(screen.getByText("dog 91%")).toBeInTheDocument();
  expect(screen.getByText("Hints (not applied automatically):")).toBeInTheDocument();
  expect(screen.getByText(/Stray Animals' may fit/)).toBeInTheDocument();
  expect(screen.getByText(/cannot recognise potholes/)).toBeInTheDocument();
});

test("shows quality warnings and the detector-unavailable note", () => {
  render(
    <ImageAnalysisResult
      result={{ ...BASE, is_blurry: true, too_dark: true, detections: [], category_hints: [], detector_available: false }}
    />,
  );
  expect(screen.getByText(/looks blurry/)).toBeInTheDocument();
  expect(screen.getByText(/very dark/)).toBeInTheDocument();
  expect(screen.getByText(/Object detection is unavailable/)).toBeInTheDocument();
  expect(screen.queryByText(/Hints/)).not.toBeInTheDocument();
});

test("toggle loads the analysis once and can hide it", async () => {
  const load = vi.fn().mockResolvedValue(BASE);
  render(<ImageAnalysisToggle name="photo.jpg" load={load} />);
  fireEvent.click(screen.getByRole("button", { name: "Analyse photo" }));
  expect(await screen.findByText("dog 91%")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Hide analysis" }));
  expect(screen.queryByText("dog 91%")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Analyse photo" }));
  expect(await screen.findByText("dog 91%")).toBeInTheDocument();
  expect(load).toHaveBeenCalledTimes(1);
});
