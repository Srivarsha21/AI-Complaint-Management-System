import { noteRequired, transitionLabel } from "./complaintLabels";

test("noteRequired mirrors the backend workflow rules", () => {
  expect(noteRequired("in_progress", "resolved")).toBe(true);
  expect(noteRequired("resolved", "in_progress")).toBe(true);
  expect(noteRequired("submitted", "closed")).toBe(true);
  expect(noteRequired("resolved", "closed")).toBe(false);
  expect(noteRequired("submitted", "assigned")).toBe(false);
});

test("transitionLabel words the owner's confirmation differently", () => {
  expect(transitionLabel("resolved", "closed", true)).toBe("Confirm resolved & close");
  expect(transitionLabel("resolved", "closed", false)).toBe("Close complaint");
  expect(transitionLabel("submitted", "closed", false)).toBe("Close early");
});
