# Indian market news

News is stored in PostgreSQL. The React app reads `/api/news` and does not call a publisher. Page loads do not wait for a feed.

## Provider

The built-in provider is `rss`. Set both variables on the server:

```bash
NEWS_PROVIDER=rss
NEWS_RSS_FEEDS=https://publisher.example/markets.xml
```

Use only feeds you are allowed to store. The app keeps the headline, publisher name, canonical URL, publication time, author when the feed includes one, and a plain-text excerpt of at most 400 characters. It does not store the full article, and it does not display images. Tracking parameters are removed from the URL. HTML in the feed is stripped and rendered as text.

If `NEWS_RSS_FEEDS` is empty, the provider is unconfigured. The news page says so and does not invent headlines.

An article with no publication time is skipped. RSS feeds do not report withdrawals, so a story that disappears from a feed stays stored as `active`.

## Ingest

From `backend`:

```bash
python -m app.news.worker
```

`NEWS_INGEST_INTERVAL_SECONDS` defaults to 900 (allowed 60–86400). One PostgreSQL advisory lock (`81411012`) skips a second worker during a pass. The same canonical URL is updated in place instead of inserted again. This is not a live feed. The UI shows the last successful ingest time.

There is no manual refresh route, because the app has no separate admin role.

## Stock links

Links use the stock master. A headline links to a stock when it contains the NSE/BSE symbol as an uppercase token, or the distinctive part of the company name. Legal suffixes and generic words are ignored. The longest company phrase wins, so a story about one company is not also attached to a shorter name inside it. Ambiguous or common-word matches are left unlinked. Sector filters use the sector already stored on the stock, not a guess from the headline.

## Sentiment

`lexicon-1` counts a fixed word list in the headline and excerpt.

- Positive or negative when only one side matches.
- Neutral when neither side matches.
- Uncertain when the text is very short or contains both sides.

The explanation names the matched words. There is no confidence score. The label is not a forecast and not a buy, hold, or sell instruction.

## API

All routes require the session cookie.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/news/status` | Whether a feed is configured, the last ingest, and a freshness message. |
| GET | `/api/news/facets` | Stored sources and stock-master sectors. |
| GET | `/api/news` | Recent articles. Filters: `stock_id`, `sector`, `source`, `sentiment`, `window_days`, `published_from`, `published_to`, `limit`, `offset`. |
| GET | `/api/news/{id}` | One article. |
| GET | `/api/news/{id}/sentiment` | Classifier, label, explanation, and methodology. |

Sentiment filters are `positive`, `negative`, `neutral`, `uncertain`, and `unavailable`.

## Checks

```bash
alembic upgrade head
pytest tests/test_news.py
```

Frontend:

```bash
npx vitest run tests/NewsFeed.test.tsx --pool=threads
```
