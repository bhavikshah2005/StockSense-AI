import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ResearchPanel } from "../src/components/research/ResearchPanel.tsx";
import { ApiError } from "../src/services/http.ts";
import { getLatestResearch, getResearchMethodology, listResearch, requestResearch } from "../src/services/research.ts";

vi.mock("../src/services/research.ts", () => ({
  getResearchMethodology: vi.fn(),
  getLatestResearch: vi.fn(),
  requestResearch: vi.fn(),
  listResearch: vi.fn(),
}));

const method = {
  prompt_version: "prompts-1",
  scoring_version: "coverage-1",
  scoring_note: "coverage-1 does not assign a numeric stock score.",
  ai_note: "No narrative is invented when the provider is unconfigured.",
  configured: false,
  provider: "unconfigured",
};

function run(status: string, explanation: ResearchExplanation | null) {
  return {
    id: "run-1",
    stock_id: "stock-1",
    symbol: "TCS",
    exchange: "NSE",
    status,
    analysis_timestamp: "2026-09-24T04:00:00Z",
    evidence: {
      fundamental: [{ metric_name: "P/E", state: "met", explanation: "Stored comparison.", as_of: "2026-09-24T04:00:00Z" }],
      technical: { category: "no_clear_direction", text: "Detector fixture.", freshness: "stale", price_as_of: "2026-09-24T04:00:00Z" },
      patterns: [],
      news: [{ title: "Test fixture headline", url: "https://example.com/tcs", source: "example.com", published_at: "2026-09-24T03:00:00Z", sentiment: "uncertain" }],
      gaps: ["Dividend yield is not stored."],
    },
    explanation,
    score: {
      version: "coverage-1",
      aggregate: "partial",
      numeric_score: null,
      note: "No numeric stock score is calculated.",
      categories: {},
    },
    provider: status === "ai_unavailable" ? "unconfigured" : "openai",
    model_name: status === "ai_unavailable" ? "none" : "test-model",
    prompt_version: "prompts-1",
    scoring_version: "coverage-1",
    error_message: status === "ai_unavailable" ? "ai_unavailable" : null,
    created_at: "2026-09-24T04:00:00Z",
  };
}

type ResearchExplanation = {
  summary: string;
  fundamental: string;
  technical: string;
  patterns: string;
  news: string;
  limitations: string;
  conflicts: string[];
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("research panel shows an empty state before a run exists", async () => {
  vi.mocked(getResearchMethodology).mockResolvedValue(method);
  vi.mocked(listResearch).mockResolvedValue({ results: [], total: 0, limit: 5, offset: 0 });
  vi.mocked(getLatestResearch).mockRejectedValue(new ApiError(404, "Analysis not found"));
  render(<ResearchPanel stockId="stock-1" />);
  expect(await screen.findByText("No analysis has been stored for this stock.")).toBeTruthy();
  expect(screen.getByText(/coverage-1 does not assign a numeric stock score/)).toBeTruthy();
});

test("unavailable provider does not show a generated narrative", async () => {
  vi.mocked(getResearchMethodology).mockResolvedValue(method);
  vi.mocked(listResearch).mockResolvedValue({ results: [run("ai_unavailable", null)], total: 1, limit: 5, offset: 0 });
  vi.mocked(getLatestResearch).mockResolvedValue(run("ai_unavailable", null));
  render(<ResearchPanel stockId="stock-1" />);
  expect(await screen.findByText("No model is configured, so this run has no generated narrative.")).toBeTruthy();
  expect(screen.queryByText(/Interpretation/)).toBeNull();
  expect(screen.getByText(/Aggregate partial/)).toBeTruthy();
  expect(screen.getByText("Dividend yield is not stored.")).toBeTruthy();
  expect(screen.getByText(/technical reading is stale/)).toBeTruthy();
});

test("partial analysis labels detector output and interpretation separately", async () => {
  const explanation = {
    summary: "Stored evidence only.",
    fundamental: "One comparison is listed.",
    technical: "The detector has no clear direction.",
    patterns: "No confirmed pattern is stored.",
    news: "One article is linked.",
    limitations: "This is not a forecast.",
    conflicts: [],
  };
  vi.mocked(getResearchMethodology).mockResolvedValue({ ...method, configured: true, provider: "openai" });
  vi.mocked(listResearch).mockResolvedValue({ results: [run("partial", explanation)], total: 1, limit: 5, offset: 0 });
  vi.mocked(getLatestResearch).mockResolvedValue(run("partial", explanation));
  render(<ResearchPanel stockId="stock-1" />);
  expect(await screen.findByText(/Stored evidence only/)).toBeTruthy();
  expect(screen.getByText(/Detector output/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Test fixture headline" }).getAttribute("href")).toBe("https://example.com/tcs");
  expect(screen.queryByText(/Buy/)).toBeNull();
});

test("a failed request shows an error and leaves the page usable", async () => {
  vi.mocked(getResearchMethodology).mockResolvedValue(method);
  vi.mocked(listResearch).mockResolvedValue({ results: [], total: 0, limit: 5, offset: 0 });
  vi.mocked(getLatestResearch).mockRejectedValue(new ApiError(404, "Analysis not found"));
  vi.mocked(requestResearch).mockRejectedValue(new ApiError(429, "Analysis limit reached. Try again later."));
  render(<ResearchPanel stockId="stock-1" />);
  expect(await screen.findByRole("button", { name: "Request analysis" })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Request analysis" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("Analysis limit reached");
});
