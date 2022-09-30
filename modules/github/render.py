from graiax.playwright import PlaywrightBrowser
from launart import Launart

import prisma_cleanup


async def link_to_image(gh_link: str) -> bytes:
    browser = Launart.current().get_interface(PlaywrightBrowser)
    async with browser.page(viewport={"height": 800, "width": 1000}) as page:
        await page.goto(gh_link, timeout=80000, wait_until="networkidle")
        await page.evaluate(
            """
            var need_remove_cls = ['Layout-sidebar', 'js-header-wrapper', 'footer', 'gh-header-actions', 'discussion-timeline-actions', 'js-repo-nav', 'tabnav'];
            need_remove_cls.forEach( val => {
                var elem_arr = document.getElementsByClassName(val);
                    if (elem_arr.length){
                         elem_arr[0].remove();
                    }
                }
            );
            document.getElementsByClassName('Layout--flowRow-until-md')[0].classList.remove('Layout');
            """
        )
        return await page.screenshot(full_page=True)
