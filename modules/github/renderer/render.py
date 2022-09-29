from pathlib import Path
from typing import Literal

import jinja2
from githubkit.rest import Issue

from .filters import (
    debug_event,
    markdown_emoji,
    markdown_gfm,
    markdown_title,
    relative_time,
    review_state,
)
from .globals import (
    REACTION_EMOJIS,
    find_dismissed_review,
    get_comment_reactions,
    get_issue_label_color,
    get_issue_repo,
    get_issue_timeline,
    get_pull_request,
    get_pull_request_diff,
)

env = jinja2.Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    extensions=["jinja2.ext.loopcontrols"],
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    enable_async=True,
)

env.filters["markdown_title"] = markdown_title
env.filters["markdown_gfm"] = markdown_gfm
env.filters["markdown_emoji"] = markdown_emoji
env.filters["relative_time"] = relative_time
env.filters["debug_event"] = debug_event
env.filters["review_state"] = review_state

env.globals["get_issue_repo"] = get_issue_repo
env.globals["get_issue_timeline"] = get_issue_timeline
env.globals["get_pull_request"] = get_pull_request
env.globals["get_pull_request_diff"] = get_pull_request_diff
env.globals["get_comment_reactions"] = get_comment_reactions
env.globals["REACTION_EMOJIS"] = REACTION_EMOJIS
env.globals["get_issue_label_color"] = get_issue_label_color
env.globals["find_dismissed_review"] = find_dismissed_review


async def issue_to_html(issue: Issue, theme: Literal["light", "dark"] = "light") -> str:
    template = env.get_template("views/issue.html.jinja")
    return await template.render_async(issue=issue, theme=theme)


async def pr_diff_to_html(
    issue: Issue, theme: Literal["light", "dark"] = "light"
) -> str:
    template = env.get_template("views/diff.html.jinja")
    return await template.render_async(issue=issue, theme=theme)
