import { detectEmergencyKeywords } from "./emergency";

test("detects life-threatening phrases as whole words", () => {
  expect(detectEmergencyKeywords("A LIVE WIRE is hanging, sparking!")).toEqual(["live wire", "sparking"]);
  expect(detectEmergencyKeywords("Gas leak in the building")).toEqual(["gas leak"]);
});

test("ignores ordinary complaints and partial words", () => {
  expect(detectEmergencyKeywords("Garbage not collected for a week")).toEqual([]);
  expect(detectEmergencyKeywords("Firecrackers till midnight")).toEqual([]);
});
