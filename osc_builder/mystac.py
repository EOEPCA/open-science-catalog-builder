import json
import os.path
from typing import Any, Optional, Iterable, List
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlparse


@dataclass
class STACObject:
    path: str
    values: dict

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value

    def get(self, *args, **kwargs):
        return self.values.get(*args, **kwargs)

    def setdefault(self, *args, **kwargs):
        return self.values.setdefault(*args, **kwargs)

    @classmethod
    def from_file(cls, path):
        return cls(path, read_json(path))

    def save(self, path: Optional[str] = None, indent: int = 2):
        write_json(path or self.path, self.values, indent)

    def get_links(self, rel: Optional[str] = None) -> List[dict]:
        links = self.get("links", [])
        if rel:
            links = [link for link in links if link.get("rel") == rel]
        return links

    def get_children(self) -> Iterable["STACObject"]:
        for link in self.get_links("child"):
            yield STACObject.from_file(normpath(self.path, link["href"]))

    def get_child(self, id: str) -> Optional["STACObject"]:
        for child in self.get_children():
            if child["id"] == id:
                return child
        return None

    def get_items(self) -> Iterable["STACObject"]:
        for link in self.get_links("item"):
            yield STACObject.from_file(normpath(self.path, link["href"]))

    def add_link(self, rel: str, href: str, type: str, **kwargs) -> dict:
        link = {"rel": rel, "href": href, "type": type, **kwargs}
        self.values.setdefault("links", []).append(link)

    def add_object_link(
        self,
        other: "STACObject",
        rel: str,
        type: str = "application/json",
        **kwargs,
    ):
        self.add_link(rel, relpath(other.path, self.path), type, **kwargs)

    def add_child(self, child: "STACObject"):
        self.add_object_link(
            child, rel="child", title=child["title"], type="application/json"
        )
        child.add_object_link(
            self, rel="parent", title=self["title"], type="application/json"
        )

    def get_self_link(self) -> Optional[dict]:
        for link in self.get_links():
            if link["rel"] == "self":
                return link

    def get_self_href(self) -> Optional[str]:
        if link := self.get_self_link():
            return link["href"]

    def set_self_href(self, href):
        if link := self.get_self_link():
            link["href"] = href
        else:
            self.add_link(rel="self", href=href, type="application/json")

    def set_updated(self, dt: datetime, properties: bool = False):
        formatted = dt.isoformat().replace("+00:00", "Z")
        if properties:
            self.setdefault("properties", {})["updated"] = formatted
        else:
            self["updated"] = formatted


def read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def write_json(path: str, obj: Any, indent: int = 2):
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=False, allow_nan=False)


def get_self_link(obj: dict) -> str:
    link = next((link for link in obj["link"] if link["rel"] == "self"), None)
    if link:
        return link["href"]


def normpath(a: str, b: str) -> str:
    return os.path.normpath(os.path.join(os.path.dirname(a), b))


def relpath(to: str, from_: str) -> str:
    return os.path.relpath(to, os.path.dirname(from_))


def is_absolute_href(href: str) -> bool:
    parsed = urlparse(href)
    return parsed.scheme != "" or os.path.isabs(parsed.path)


def make_absolute_hrefs(
    self: STACObject, parent_href: str, path: str, indent: int = 2
):
    self_href = urljoin(parent_href, path)

    for child_link in self.get_links("child"):
        if is_absolute_href(child_link["href"]):
            continue

        make_absolute_hrefs(
            STACObject.from_file(normpath(self.path, child_link["href"])),
            self_href,
            child_link["href"],
            indent,
        )

    for item_link in self.get_links("item"):
        if is_absolute_href(item_link["href"]):
            continue

        make_absolute_hrefs(
            STACObject.from_file(normpath(self.path, item_link["href"])),
            self_href,
            item_link["href"],
            indent,
        )

    for link in self.get_links():
        if not is_absolute_href(link["href"]):
            link["href"] = urljoin(self_href, link["href"])

    for asset in self.get("assets", {}).values():
        if not is_absolute_href(asset["href"]):
            asset["href"] = urljoin(self_href, asset["href"])

    self.set_self_href(self_href)
    self.save(indent=indent)
