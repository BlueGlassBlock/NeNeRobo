from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

from graiax.playwright import PlaywrightBrowser
from kayaku import config, create
from launart import Launart
from playwright.async_api import Page


@config("render.playwright")
class RenderConfig:
    color_scheme: Literal["dark", "light"] = "dark"


@asynccontextmanager
async def get_page() -> AsyncGenerator[Page, None]:
    browser = Launart.current().get_interface(PlaywrightBrowser)
    async with browser.page(
        viewport={"height": 800, "width": 1000},
        color_scheme=create(RenderConfig).color_scheme,
    ) as page:
        yield page
