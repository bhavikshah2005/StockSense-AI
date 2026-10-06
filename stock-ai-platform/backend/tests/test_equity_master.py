from app.data_providers.india.metadata import bundled_listings


def test_equity_master_includes_pasupati_on_both_exchanges() -> None:
    rows = bundled_listings()
    matches = [row for row in rows if row.symbol == "PASUPTAC"]
    assert {row.exchange for row in matches} == {"NSE", "BSE"}
    assert {row.company_name for row in matches} == {"Pasupati Acrylon Limited"}
    assert {row.isin for row in matches} == {"INE818B01023"}


def test_equity_master_covers_nse_and_bse() -> None:
    rows = bundled_listings()
    assert len(rows) > 8000
    assert {row.exchange for row in rows} == {"NSE", "BSE"}
    assert len({(row.symbol, row.exchange) for row in rows}) == len(rows)
    tcs = next(row for row in rows if row.symbol == "TCS" and row.exchange == "NSE")
    assert tcs.company_name == "Tata Consultancy Services Limited"
    assert tcs.sector == "Information Technology"
    thejo = next(row for row in rows if row.symbol == "THEJO" and row.exchange == "NSE")
    assert thejo.company_name == "Thejo Engineering Limited"
