from yarl import URL

from library.render import get_page

from .service import SearchResult


async def results_to_images(
    results: list[SearchResult], max_height: int
) -> dict[str, bytes | int]:
    merged: dict[str, list[str]] = {}
    result: dict[str, bytes | int] = {}
    for r in results:
        u = URL(r.uri)
        merged.setdefault(str(u.with_fragment(None)), []).append(u.fragment)

    for base_url, frags in merged.items():
        async with get_page() as page:
            await page.goto(base_url, wait_until="networkidle")
            for frag in frags:
                elem = await page.locator(
                    f"""//*[@href="#{frag}" and @class="headerlink"]/../.."""
                ).element_handle()
                height = await elem.evaluate("element => element.scrollHeight")
                result[str(URL(base_url).with_fragment(frag))] = (
                    (await elem.screenshot()) if height <= max_height else height
                )
    return result
