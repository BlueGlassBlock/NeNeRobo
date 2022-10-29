from library.render import get_page


async def PEP_to_image(pep: int) -> bytes:
    async with get_page() as page:
        await page.goto(
            f"https://peps.python.org/pep-{pep}/",
            timeout=5000,
            wait_until="networkidle",
        )
        await page.locator("details").evaluate("node => node.open = true")
        return await page.locator("article").screenshot(type="jpeg")
