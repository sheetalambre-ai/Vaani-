"""ExecutorAgent: creates tasks in Trello, GitHub, or mock. ONLY writes externally on approved items."""
import httpx
from app.config import settings
from app import models


async def create_task(item: models.ActionItem) -> str:
    """Returns external_ref URL/ID. Raises if item not approved."""
    if item.status != "approved":
        raise ValueError(f"ActionItem {item.id} is not approved — cannot create external task.")

    tracker = settings.TRACKER.lower()
    if tracker == "mock":
        return await _mock_create(item)
    elif tracker == "trello":
        return await _trello_create(item)
    elif tracker == "github":
        return await _github_create(item)
    else:
        raise ValueError(f"Unknown TRACKER: {tracker}")


async def _mock_create(item: models.ActionItem) -> str:
    ref = f"mock://task/{item.id}"
    print(f"[MOCK TRACKER] Would create task: task='{item.task}' owner={item.owner} due={item.due_date} → {ref}")
    return ref


async def _trello_create(item: models.ActionItem) -> str:
    if not settings.TRELLO_KEY or not settings.TRELLO_TOKEN or not settings.TRELLO_LIST_ID:
        raise ValueError("TRELLO_KEY, TRELLO_TOKEN, and TRELLO_LIST_ID are required")
    # Get first list from board — simplified for demo
    async with httpx.AsyncClient(timeout=30) as client:
        # You'd normally store the list ID; for demo we create a card on a known list
        resp = await client.post(
            "https://api.trello.com/1/cards",
            params={
                "key": settings.TRELLO_KEY,
                "token": settings.TRELLO_TOKEN,
                "name": item.task,
                "desc": f"Owner: {item.owner}\nDue: {item.due_date}\n\nEvidence: {item.evidence_quote}",
                "due": item.due_date,
                "idList": settings.TRELLO_LIST_ID,
            }
        )
        resp.raise_for_status()
        return resp.json()["shortUrl"]


async def _github_create(item: models.ActionItem) -> str:
    if not settings.GITHUB_TOKEN or not settings.GITHUB_REPO:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPO required")
    headers = {"Authorization": f"token {settings.GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    body = f"**Owner:** {item.owner}\n**Due:** {item.due_date}\n\n> {item.evidence_quote}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{settings.GITHUB_REPO}/issues",
            json={"title": item.task, "body": body},
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()["html_url"]
