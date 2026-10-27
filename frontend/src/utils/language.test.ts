import { appendText, containsTelugu, detectLanguage } from "./language";

const TELUGU = "మా వీధిలో మూడు రోజులుగా నీళ్ళు రావడం లేదు";

test("detects Telugu, English and unknown text by script", () => {
  expect(detectLanguage(TELUGU)).toBe("te");
  expect(detectLanguage(`Ameerpet: ${TELUGU}`)).toBe("te");
  expect(detectLanguage("No water for three days")).toBe("en");
  expect(detectLanguage("123 !!")).toBe("unknown");
  expect(containsTelugu("road " + TELUGU)).toBe(true);
  expect(containsTelugu("road")).toBe(false);
});

test("appendText joins with a separator and respects the maximum length", () => {
  expect(appendText("", "  hello ", 100)).toBe("hello");
  expect(appendText("Drain blocked.  ", "Water on road", 100)).toBe("Drain blocked. Water on road");
  expect(appendText("abc", "defgh", 6)).toBe("abc de");
  expect(appendText("abc", "   ", 100)).toBe("abc");
});
