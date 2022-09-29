from githubkit.rest import Issue
from graiax.playwright.interface import PlaywrightBrowser
from launart import Launart

from .render import issue_to_html


async def _gen_image(html: str, width: int, height: int) -> bytes:
    browser = Launart.current().get_interface(PlaywrightBrowser)
    async with browser.page(viewport={"width": width, "height": height}) as page:
        await page.set_content(html)
        return await page.screenshot(full_page=True)


async def issue_to_image(issue: Issue, width: int = 800, height: int = 300) -> bytes:
    html = await issue_to_html(issue)
    return await _gen_image(html, width, height)
