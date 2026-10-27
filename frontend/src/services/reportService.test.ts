import { vi } from "vitest";

import { api } from "./api";
import { fetchReport, saveBlob } from "./reportService";

afterEach(() => vi.restoreAllMocks());

test("fetchReport requests a blob with only non-empty filters", async () => {
  const blob = new Blob(["%PDF"]);
  const get = vi.spyOn(api, "get").mockResolvedValue({
    data: blob, headers: { "content-disposition": 'attachment; filename="complaints-2026-10-10.pdf"' },
  });

  const report = await fetchReport("pdf", { date_from: "2026-10-01", status: "", category_id: 3, search: "  " });

  expect(get).toHaveBeenCalledWith("/reports/complaints.pdf", expect.objectContaining({
    params: { date_from: "2026-10-01", category_id: 3 },
    responseType: "blob",
  }));
  expect(report).toEqual({ blob, filename: "complaints-2026-10-10.pdf" });
});

test("fetchReport falls back to a dated file name when the header is not exposed", async () => {
  vi.spyOn(api, "get").mockResolvedValue({ data: new Blob(["x"]), headers: {} });
  const report = await fetchReport("xlsx", {});
  expect(report.filename).toMatch(/^complaints-\d{4}-\d{2}-\d{2}\.xlsx$/);
});

test("saveBlob clicks a temporary download link", () => {
  const createObjectURL = vi.fn(() => "blob:report");
  vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

  saveBlob({ blob: new Blob(["x"]), filename: "complaints-2026-10-10.xlsx" });

  expect(createObjectURL).toHaveBeenCalled();
  expect(click).toHaveBeenCalledTimes(1);
  const anchor = click.mock.instances[0] as unknown as HTMLAnchorElement;
  expect(anchor.download).toBe("complaints-2026-10-10.xlsx");
  vi.unstubAllGlobals();
});
