from githubkit.rest.models import Event

from library.render import get_page


async def link_to_image(gh_link: str) -> bytes:
    async with get_page() as page:
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


async def files_changed_image(gh_link: str) -> list[bytes]:
    async with get_page() as page:
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
        return [
            await elem.screenshot() for elem in await page.query_selector_all(".file")
        ]


def format_event(event: Event) -> str | None:
    actor = event.actor.login
    repo = event.repo.name
    payload = event.payload.dict()
    match event.type:
        case "PushEvent":
            ref_full: str = payload["ref"]
            if (branch := ref_full.removeprefix("refs/heads/")) == ref_full:
                return
            size: int = payload["distinct_size"]
            if size == 1:
                return (
                    f'{actor} pushed {payload["head"][:7]} to {repo} on branch {branch}\n'
                    f'https://github.com/{repo}/commit/{payload["head"]}'
                )
            else:
                return (
                    f"{actor} pushed {size} commits to {repo} on branch {branch}\n"
                    f'https://github.com/{repo}/compare/{payload["before"][:10]}..{payload["head"][:10]}'
                )
        case "ReleaseEvent":
            if payload["action"] == "created" and payload["release"]["draft"] == False:
                return (
                    f'{actor} released {payload["release"]["name"]} on {repo}\n'
                    f'{payload["release"]["url"]}'
                )
        case "IssuesEvent":
            if payload["action"] not in ("opened", "closed", "reopened"):
                return
            title = payload["issue"]["title"]
            number = payload["issue"]["number"]
            return (
                f'{actor} {payload["action"]} issue\n'
                f"{repo}#{number}: {title}\n"
                f'{payload["issue"]["html_url"]}'
            )
        case "PullRequestEvent":
            title = payload["pull_request"]["title"]
            number = payload["pull_request"]["number"]
            if payload["action"] in ("opened", "closed", "reopened"):
                return (
                    f'{actor} {payload["action"]} PR\n'
                    f"{repo}#{number}: {title}\n"
                    f'{payload["pull_request"]["html_url"]}'
                )
            elif payload["action"] == "review_requested":
                return (
                    f"{actor} requested an review on {repo}#{number}\n"
                    f'{payload["pull_request"]["html_url"]}'
                )
        case "PullRequestReviewEvent":
            number = payload["pull_request"]["number"]
            return (
                f"{actor} {payload['review']['state'].lower()} {repo}#{number}\n"
                f'{payload["review"]["html_url"]}'
            )
