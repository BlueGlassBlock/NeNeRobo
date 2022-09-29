from colorsys import rgb_to_hls

from githubkit.rest import (
    FullRepository,
    GitHubRestModel,
    Issue,
    PullRequest,
    TimelineCommentEvent,
    TimelineReviewedEvent,
)
from launart import Launart
from unidiff import PatchSet

from ..service import GitHub

REACTION_EMOJIS = {
    "plus_one": "👍",
    "minus_one": "👎",
    "laugh": "😄",
    "confused": "😕",
    "hooray": "🎉",
    "heart": "❤️",
    "rocket": "🚀",
    "eyes": "👀",
}


async def _get_issue_repo(repo_url: str) -> FullRepository:
    github = Launart.current().get_interface(GitHub)
    resp = await github.arequest("GET", repo_url, response_model=FullRepository)
    return resp.parsed_data


async def get_issue_repo(issue: Issue) -> FullRepository:
    return await _get_issue_repo(issue.repository_url)


async def get_issue_timeline(issue: Issue):
    github = Launart.current().get_interface(GitHub)
    repo = await get_issue_repo(issue)
    return github.paginate(
        github.rest.issues.async_list_events_for_timeline,
        owner=repo.owner.login,
        repo=repo.name,
        issue_number=issue.number,
    )


async def _get_pull_request(owner: str, repo: str, number: int) -> PullRequest:
    github = Launart.current().get_interface(GitHub)
    resp = await github.rest.pulls.async_get(owner=owner, repo=repo, pull_number=number)
    return resp.parsed_data


async def get_pull_request(issue: Issue) -> PullRequest:
    repo = await get_issue_repo(issue)
    return await _get_pull_request(repo.owner.login, repo.name, issue.number)


async def _get_pull_request_diff(diff_url: str) -> PatchSet:
    github = Launart.current().get_interface(GitHub)
    resp = await github.arequest("GET", diff_url)
    return PatchSet.from_string(resp.text)


async def get_pull_request_diff(pr: PullRequest) -> PatchSet:
    return await _get_pull_request_diff(pr.diff_url)


def get_comment_reactions(event: TimelineCommentEvent) -> dict[str, int]:
    result: dict[str, int] = {}

    if not event.reactions:
        return result

    for reaction in (
        "plus_one",
        "minus_one",
        "laugh",
        "confused",
        "hooray",
        "heart",
        "rocket",
        "eyes",
    ):
        if count := getattr(event.reactions, reaction, None):
            result[reaction] = count
    return result


def get_issue_label_color(color: str) -> tuple[int, int, int, int, int, int]:
    color = color.removeprefix("#")
    r = int(color[:2], 16)
    g = int(color[2:4], 16)
    b = int(color[4:6], 16)
    h, l, s = rgb_to_hls(r / 255, g / 255, b / 255)
    return r, g, b, int(h * 100), int(l * 100), int(s * 100)


def find_dismissed_review(
    past_timeline: list[GitHubRestModel], review_id: int
) -> TimelineReviewedEvent | None:
    for event in past_timeline:
        if isinstance(event, TimelineReviewedEvent) and event.id == review_id:
            return event
