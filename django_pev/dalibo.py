import json
import urllib
import urllib.request
from dataclasses import dataclass

API_URL = "https://explain.dalibo.com/new.json"


@dataclass
class PevResponse:
    id: str
    delete_key: str

    @property
    def url(self) -> str:
        return f"https://explain.dalibo.com/plan/{self.id}"

    @property
    def delete_url(self) -> str:
        return f"{self.url}/{self.delete_key}"

    def delete(self) -> None:
        """Deletes the plan from explain.dalibo"""
        urllib.request.urlopen(urllib.request.Request(self.delete_url))

    def __repr__(self) -> str:
        return f"PevResult(url={self.url})"


def upload_sql_plan(query: str, plan: str, title: str) -> PevResponse:
    """Uploads a sql plan to explain.dalibo for visualization"""
    payload = json.dumps({"title": title, "plan": json.dumps(plan), "query": query}).encode()
    with urllib.request.urlopen(
        urllib.request.Request(
            API_URL,
            headers={
                "Content-Type": "application/json",
            },
            data=payload,
        )
    ) as response:
        data = json.loads(response.read())
        return PevResponse(id=data["id"], delete_key=data["deleteKey"])
