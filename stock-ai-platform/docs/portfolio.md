# Portfolios

Portfolios belong to the signed-in user. The React app calls `/api/portfolios`. It does not read the database directly and it does not store holdings in browser storage.

This module records transactions and values them. It does not place orders, connect to a broker, or support derivatives, short sales, or leverage.

## Records

Transactions are the source of truth. A holding row is rewritten from those transactions after each change. Cash starts at zero. It changes only when you record a deposit, a withdrawal, a buy, or a sell.

At the same timestamp, records are applied as deposit, then buy, then sell, then withdrawal.

Deleting a portfolio removes its transactions, cash records, and derived holdings. Archive keeps the records and blocks new ones until you unarchive. There is no separate retention archive beyond that.

Currency is INR. Only active NSE and BSE listings can be added. Quantity is a whole number of shares.

## Cost and P&L

The method is weighted-average cost, versioned here as `average-cost-1`.

* A buy adds `quantity × price + charges` to cost.
* A sell removes the average cost of the shares sold. Charges reduce the proceeds. If charges are larger than the proceeds, the sell is rejected.
* Realized P&L is proceeds minus the cost removed.
* Unrealized P&L is market value minus the remaining cost. It is omitted when a price is missing or stale.
* Total P&L is realized plus unrealized, and only when every open holding has a usable price.
* Market value is the holdings only. Cash is shown separately and is not added into market value.

A quote older than seven days, using the same window as technical analysis, is stale. A stale price is shown with that state and is not included in market value. A missing quote is `unavailable`. Delayed quotes stay labeled delayed. Nothing is filled with zero.

No index series is stored, so there is no benchmark comparison.

Value history uses stored daily closes only. If any day with an open holding has no stored close, the history is `insufficient_data` and no points are returned.

## Position size

`POST /api/portfolios/position-size` is a calculator. It does not create a transaction.

* Per-share risk = entry price − stop price. The stop must be below the entry.
* Risk-limited shares = floor(risk amount ÷ per-share risk).
* Capital-limited shares = floor(capital ÷ entry price).
* An allocation percent or share cap, when set, adds another floor limit.
* If both an INR risk amount and a risk percent are set, the smaller risk amount is used.
* The result is the smallest limit. Fewer than one share is rejected.

A stop price is not an order. Gaps, slippage, and fees can make the loss larger. Saved risk settings are planning inputs you type. They are not inferred from the portfolio or from AI research.

## API

All routes require the session cookie. Another user's portfolio id is `404`.

| Method | Path | Behavior |
| --- | --- | --- |
| GET, POST | `/api/portfolios` | List or create. At most 20 portfolios. |
| GET, PATCH, DELETE | `/api/portfolios/{id}` | Read, rename, or delete. |
| POST | `/api/portfolios/{id}/archive` and `/unarchive` | Archive state. |
| GET, POST | `/api/portfolios/{id}/transactions` | Ledger. |
| PATCH, DELETE | `/api/portfolios/{id}/transactions/{transaction_id}` | Edit or remove, then recalculate. |
| GET, POST | `/api/portfolios/{id}/cash` | Deposits and withdrawals. |
| DELETE | `/api/portfolios/{id}/cash/{movement_id}` | Remove a cash record, then recalculate. |
| GET | `/api/portfolios/{id}/valuation` | Holdings, P&L, and allocation. |
| GET | `/api/portfolios/{id}/holdings` | Derived holdings. |
| GET | `/api/portfolios/{id}/allocation` | Stock and sector weights. |
| GET | `/api/portfolios/{id}/history` | Stored-close history, or `insufficient_data`. |
| GET, PUT | `/api/portfolios/risk-settings` | Optional planning limits. |
| POST | `/api/portfolios/position-size` | Hypothetical quantity. |

Buy example:

```json
{
  "stock_id": "10c53c6a-609d-4663-b02f-71d741b22439",
  "side": "buy",
  "quantity": "10",
  "price": "100",
  "charges": "20",
  "traded_at": "2026-09-24T04:00:00Z"
}
```

A buy without enough cash returns `422`. Cash is not created automatically.

## Local commands

From `backend`, with `DATABASE_URL` unset in the shell so `.env` is used:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\pytest.exe tests/test_portfolio.py
```

From `frontend`:

```powershell
npx vitest run tests/PortfolioPages.test.tsx --pool=threads
```
