#!/usr/bin/env python3
"""Probe the public Avanza fund search page without using authentication.

This is an investigation aid, not a production data collector. It prints the
rendered information for one fund and the public fetch/XHR responses that may
contain the fund's identifier or price data.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from urllib.parse import urlencode

from playwright.async_api import Response, async_playwright


@dataclass(frozen=True)
class Fund:
    isin: str
    name: str


DEFAULT_FUND = Fund(isin="NO0010827280", name="DNB Global Indeks S")


def search_url(fund: Fund) -> str:
    query = urlencode(
        {
            "sortField": "developmentThreeYears",
            "sortDirection": "DESCENDING",
            "selectedTab": "development",
            "nameQuery": fund.name,
        }
    )
    return f"https://www.avanza.se/fonder/handla-fonder.html/list?{query}"


def looks_relevant(response: Response, isin: str) -> bool:
    request = response.request
    return request.resource_type in {"fetch", "xhr"} and (
        isin.lower() in response.url.lower()
        or any(term in response.url.lower() for term in ("fund", "search", "instrument"))
    )


async def probe(fund: Fund) -> int:
    responses: list[Response] = []

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="sv-SE", viewport={"width": 1440, "height": 1100})

        def collect(response: Response) -> None:
            if looks_relevant(response, fund.isin):
                responses.append(response)

        page.on("response", collect)
        response = await page.goto(search_url(fund), wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(8_000)

        body_text = await page.locator("body").inner_text()
        matching_lines = [
            line.strip()
            for line in body_text.splitlines()
            if line.strip() and (fund.name.lower() in line.lower() or fund.isin.lower() in line.lower())
        ]

        print(f"Page status: {response.status if response else 'no response'}")
        print(f"Page URL: {page.url}")
        print(f"Fund: {fund.name} ({fund.isin})")
        print("\nRendered matches:")
        print("\n".join(matching_lines[:20]) or "No matching rendered text found.")

        print("\nRelevant public XHR/fetch responses:")
        if not responses:
            print("No relevant responses observed.")
        for item in responses:
            content_type = item.headers.get("content-type", "")
            print(
                f"{item.status} {item.request.method} {item.request.resource_type} "
                f"{item.url} [{content_type}]"
            )
            if item.request.post_data:
                print(f"  Request body: {item.request.post_data[:800]}")
            if "json" not in content_type.lower():
                continue
            try:
                body = await item.text()
            except Exception as error:  # Network responses can disappear during navigation.
                print(f"  Could not read body: {error}")
                continue
            if fund.isin.lower() in body.lower():
                payload = json.loads(body)
                fund_rows = payload.get("fundListViews", [])
                matching_fund = next(
                    (row for row in fund_rows if row.get("isin") == fund.isin), None
                )
                if matching_fund:
                    print(
                        "  Matching fund: "
                        f"{matching_fund.get('name')} | {matching_fund.get('isin')} | "
                        f"NAV {matching_fund.get('nav')} {matching_fund.get('currencyCode')} | "
                        f"NAV date {matching_fund.get('navDate')} | "
                        f"orderbook {matching_fund.get('orderbookId')}"
                    )

        await browser.close()
        return 0 if matching_lines else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isin", default=DEFAULT_FUND.isin)
    parser.add_argument("--name", default=DEFAULT_FUND.name)
    args = parser.parse_args()
    return asyncio.run(probe(Fund(isin=args.isin, name=args.name)))


if __name__ == "__main__":
    raise SystemExit(main())
