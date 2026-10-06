import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { NewsFeed } from "../src/components/news/NewsFeed.tsx";
import { ApiError } from "../src/services/http.ts";
import { getNewsFacets, getNewsStatus, listNews } from "../src/services/news.ts";

vi.mock("../src/services/news.ts", () => ({
  getNewsStatus: vi.fn(),
  getNewsFacets: vi.fn(),
  listNews: vi.fn(),
}));

const article = {
  id: "n1",
  title: "Test fixture headline",
  summary: "Test fixture excerpt",
  source: "example.com",
  url: "https://example.com/story",
  author: null,
  published_at: "2026-09-24T03:30:00Z",
  ingested_at: "2026-09-24T04:00:00Z",
  language: "en",
  sentiment: "uncertain",
  sentiment_explanation: "The text contains both positive and negative words.",
  stocks: [{ stock_id: "s1", symbol: "TCS", exchange: "NSE", company_name: "Tata Consultancy Services", match_method: "symbol" }],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

test("news feed shows an unconfigured empty state", async () => {
  vi.mocked(getNewsStatus).mockResolvedValue({
    configured: false,
    provider: "unconfigured",
    last_success_at: null,
    last_status: "not_configured",
    last_error: null,
    stale: true,
    message: "News feeds are not configured.",
  });
  vi.mocked(getNewsFacets).mockResolvedValue({ sources: [], sectors: ["Information Technology"] });
  vi.mocked(listNews).mockResolvedValue({ results: [], total: 0, limit: 20, offset: 0 });
  render(
    <MemoryRouter>
      <NewsFeed />
    </MemoryRouter>,
  );
  expect(await screen.findByText("No news provider is configured.")).toBeTruthy();
  expect(screen.getByText("News feeds are not configured.")).toBeTruthy();
});

test("news feed renders sentiment and a safe original link", async () => {
  vi.mocked(getNewsStatus).mockResolvedValue({
    configured: true,
    provider: "rss",
    last_success_at: "2026-09-24T04:00:00Z",
    last_status: "success",
    last_error: null,
    stale: false,
    message: "Headlines come from the last completed ingest.",
  });
  vi.mocked(getNewsFacets).mockResolvedValue({ sources: ["example.com"], sectors: ["Information Technology"] });
  vi.mocked(listNews).mockResolvedValue({ results: [article], total: 1, limit: 20, offset: 0 });
  render(
    <MemoryRouter>
      <NewsFeed />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Test fixture headline")).toBeTruthy();
  expect(screen.getByText(/Automated sentiment: uncertain/)).toBeTruthy();
  const link = screen.getByRole("link", { name: "Original article" });
  expect(link.getAttribute("href")).toBe("https://example.com/story");
  expect(link.getAttribute("rel")).toContain("noreferrer");
  fireEvent.change(screen.getByLabelText("Sector"), { target: { value: "Information Technology" } });
  expect(listNews).toHaveBeenCalledWith(expect.objectContaining({ sector: "Information Technology" }));
});

test("news feed shows an error without inventing headlines", async () => {
  vi.mocked(getNewsStatus).mockRejectedValue(new ApiError(500, "Could not load news"));
  vi.mocked(getNewsFacets).mockRejectedValue(new ApiError(500, "Could not load news"));
  vi.mocked(listNews).mockRejectedValue(new ApiError(500, "Could not load news"));
  render(
    <MemoryRouter>
      <NewsFeed />
    </MemoryRouter>,
  );
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load news");
  expect(screen.queryByText("Test fixture headline")).toBeNull();
});

test("unsafe article links are not opened", async () => {
  vi.mocked(getNewsStatus).mockResolvedValue({
    configured: true,
    provider: "rss",
    last_success_at: null,
    last_status: null,
    last_error: null,
    stale: true,
    message: "Stored headlines.",
  });
  vi.mocked(getNewsFacets).mockResolvedValue({ sources: [], sectors: [] });
  vi.mocked(listNews).mockResolvedValue({
    results: [{ ...article, url: "javascript:alert(1)", sentiment: null, sentiment_explanation: null }],
    total: 1,
    limit: 20,
    offset: 0,
  });
  render(
    <MemoryRouter>
      <NewsFeed />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Original link unavailable")).toBeTruthy();
  expect(screen.getByText("Sentiment unavailable")).toBeTruthy();
});
