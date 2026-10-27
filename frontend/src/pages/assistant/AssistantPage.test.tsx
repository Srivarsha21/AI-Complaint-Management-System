import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import * as assistantService from "../../services/assistantService";
import type { ChatResponse, OfficeInfo } from "../../types/assistant";
import AssistantPage from "./AssistantPage";

vi.mock("../../services/assistantService");
// Leaflet needs a real browser layout engine; the map is replaced in tests.
vi.mock("../../components/assistant/OfficeMap", () => ({
  default: ({ offices }: { offices: OfficeInfo[] }) => <div data-testid="office-map">{offices.length} markers</div>,
}));

const OFFICE: OfficeInfo = {
  id: 1,
  name: "HMWSSB Head Office",
  organisation: "Hyderabad Metropolitan Water Supply and Sewerage Board (HMWSSB)",
  channel_type: "office",
  category_slugs: ["water-supply", "drainage-sewerage"],
  address: "Administrative Office Building, Khairatabad, Hyderabad - 4, Telangana",
  locality: "Khairatabad",
  pincode: null,
  city: "Hyderabad",
  latitude: 17.410859,
  longitude: 78.4638293,
  coordinates_source: "Google Maps embed on the official HMWSSB website",
  phone: "040-23433933",
  email: null,
  website: "https://www.hyderabadwater.gov.in/",
  source_url: "https://www.hyderabadwater.gov.in/en/index.php/contact-us",
  source_type: "official",
  verified_on: "2026-10-10",
  notes: null,
  distance_m: null,
  map_url: "https://www.openstreetmap.org/?mlat=17.410859&mlon=78.463829#map=17/17.410859/78.463829",
  directions_url: "https://www.google.com/maps/dir/?api=1&destination=17.410859%2C78.463829",
  osm_directions_url: null,
};

const PORTAL: OfficeInfo = {
  ...OFFICE,
  id: 2,
  name: "HMWSSB Register Grievances",
  channel_type: "online_portal",
  address: null,
  latitude: null,
  longitude: null,
  coordinates_source: null,
  phone: null,
  source_type: "third_party",
  website: "https://www.hyderabadwater.gov.in/en/index.php/services/customers-services/register-grievances",
  map_url: null,
  directions_url: null,
};

function response(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    reply: "This looks like a Drainage & Sewerage problem.",
    intent: "issue",
    category: { id: 3, slug: "drainage-sewerage", name: "Drainage & Sewerage" },
    needs_location: true,
    location: null,
    location_status: "not_provided",
    offices: [OFFICE],
    channels: [PORTAL],
    steps: ["Note the exact location: street or colony, a nearby landmark and the PIN code."],
    suggestions: [],
    disclaimer: "Contact details shown here come only from official government websites.",
    file_complaint: { category_id: 3 },
    generated_by: "template",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/app/assistant"]}>
      <Routes>
        <Route path="/app/assistant" element={<AssistantPage />} />
        <Route path="/app/complaints/new" element={<p>New complaint page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockGeolocation(impl: (success: PositionCallback, error: PositionErrorCallback) => void) {
  Object.defineProperty(navigator, "geolocation", {
    configurable: true,
    value: { getCurrentPosition: vi.fn(impl) },
  });
}

afterEach(() => vi.resetAllMocks());

test("suggestion chip sends a message and shows verified office cards", async () => {
  vi.mocked(assistantService.sendChatMessage).mockResolvedValue(response());
  renderPage();

  fireEvent.click(screen.getByRole("button", { name: "Drainage problem in my area" }));

  expect(await screen.findByText("This looks like a Drainage & Sewerage problem.")).toBeInTheDocument();
  expect(assistantService.sendChatMessage).toHaveBeenCalledWith(
    [{ role: "user", content: "Drainage problem in my area" }],
    null,
  );
  expect(screen.getByRole("log")).toHaveAttribute("aria-live", "polite");
  expect(screen.getByRole("heading", { name: "HMWSSB Head Office" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "040-23433933" })).toHaveAttribute("href", "tel:04023433933");
  expect(screen.getByRole("link", { name: /Directions/ })).toHaveAttribute("href", OFFICE.directions_url);
  expect(screen.getByText("Official")).toBeInTheDocument();
  expect(screen.getByText("Third-party")).toBeInTheDocument();
  expect(screen.getAllByText(/Verified on/)).toHaveLength(2);
  expect(await screen.findByTestId("office-map")).toHaveTextContent("1 markers");
  expect(screen.getByText(/Share your location or type your locality/)).toBeInTheDocument();
});

test("phone is not shown when the record has none", async () => {
  vi.mocked(assistantService.sendChatMessage).mockResolvedValue(response({ offices: [], channels: [PORTAL] }));
  renderPage();
  fireEvent.change(screen.getByLabelText("Describe your problem"), { target: { value: "drain blocked" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(await screen.findByRole("heading", { name: "HMWSSB Register Grievances" })).toBeInTheDocument();
  expect(screen.queryByText("Phone:")).not.toBeInTheDocument();
  expect(screen.queryByTestId("office-map")).not.toBeInTheDocument();
});

test("file-a-complaint button links to the form with the category preselected", async () => {
  vi.mocked(assistantService.sendChatMessage).mockResolvedValue(response());
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Drainage problem in my area" }));

  const link = await screen.findByRole("link", { name: "File a complaint in this category" });
  expect(link).toHaveAttribute("href", "/app/complaints/new?category=3");
});

test("sharing location refreshes guidance with coordinates", async () => {
  vi.mocked(assistantService.sendChatMessage)
    .mockResolvedValueOnce(response())
    .mockResolvedValueOnce(response({ reply: "Nearest listed office: HMWSSB Head Office", needs_location: false }));
  mockGeolocation((success) =>
    success({ coords: { latitude: 17.41261, longitude: 78.45944, accuracy: 20 } } as GeolocationPosition),
  );
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Drainage problem in my area" }));
  await screen.findByText("This looks like a Drainage & Sewerage problem.");

  fireEvent.click(screen.getByRole("button", { name: "Share my location" }));

  expect(await screen.findByText("Nearest listed office: HMWSSB Head Office")).toBeInTheDocument();
  const [history, location] = vi.mocked(assistantService.sendChatMessage).mock.calls[1];
  expect(history).toEqual([{ role: "user", content: "Drainage problem in my area" }]);
  expect(location).toEqual({ latitude: 17.41261, longitude: 78.45944 });
});

test("permission denied falls back to typed locality", async () => {
  vi.mocked(assistantService.sendChatMessage).mockResolvedValue(response());
  mockGeolocation((_success, error) =>
    error({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "denied" } as GeolocationPositionError),
  );
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Drainage problem in my area" }));
  await screen.findByText("This looks like a Drainage & Sewerage problem.");

  fireEvent.click(screen.getByRole("button", { name: "Share my location" }));

  expect(await screen.findByText(/Location permission was denied/)).toBeInTheDocument();
  const localityInput = screen.getByLabelText("Locality or PIN code");
  expect(localityInput).toHaveFocus();

  fireEvent.change(localityInput, { target: { value: "500016" } });
  fireEvent.click(screen.getByRole("button", { name: "Use" }));

  await waitFor(() => expect(assistantService.sendChatMessage).toHaveBeenCalledTimes(2));
  expect(vi.mocked(assistantService.sendChatMessage).mock.calls[1][1]).toEqual({ text: "500016" });
});

test("shows an error when the assistant cannot be reached", async () => {
  vi.mocked(assistantService.sendChatMessage).mockRejectedValue(new Error("network"));
  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "Street light not working" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
});
