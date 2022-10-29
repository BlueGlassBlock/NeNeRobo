from graiax.playwright import PlaywrightBrowser
from launart import Launart


async def PEP_to_image(pep: int) -> bytes:
    browser = Launart.current().get_interface(PlaywrightBrowser)
    async with browser.page(
        color_scheme="dark", viewport={"height": 800, "width": 1000}
    ) as page:
        await page.goto(
            f"https://peps.python.org/pep-{pep}/",
            timeout=5000,
            wait_until="networkidle",
        )
        await page.locator("details").evaluate("node => node.open = true")
        return await page.locator("article").screenshot(type="jpeg")
