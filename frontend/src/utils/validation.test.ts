import { validateEmail, validateFullName, validatePassword } from "./validation";

test.each([
  ["short1", "Password must be at least 8 characters."],
  ["lettersonly", "Password must contain at least one letter and one number."],
  ["12345678", "Password must contain at least one letter and one number."],
  ["secret123", null],
])("validatePassword(%s)", (input, expected) => {
  expect(validatePassword(input)).toBe(expected);
});

test("validateEmail", () => {
  expect(validateEmail("ravi@example.com")).toBeNull();
  expect(validateEmail("not-an-email")).not.toBeNull();
});

test("validateFullName collapses whitespace before checking length", () => {
  expect(validateFullName("  A  ")).not.toBeNull();
  expect(validateFullName("Ravi   Kumar")).toBeNull();
});
