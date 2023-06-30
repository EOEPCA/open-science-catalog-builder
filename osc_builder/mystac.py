import json
import os.path
from typing import Any, Optional, Iterable, List
from dataclasses import dataclass


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

    @classmethod
    def from_file(cls, path):
        return cls(path, read_json(path))

    def save(self, path: Optional[str] = None):
        write_json(path or self.path, self.values)

    def get_links(self, rel: Optional[str] = None) -> List[dict]:
        links = self.get("links", [])
        if rel:
            links = [
                link for link in links if link.get("rel") == rel
            ]
        return links

    def get_children(self) -> Iterable["STACObject"]:
        for link in self.get_links("child"):
            yield STACObject.from_file(normpath(self.path, link["href"]))

    def get_items(self) -> Iterable["STACObject"]:
        for link in self.get_links("item"):
            yield STACObject.from_file(normpath(self.path, link["href"]))

    def add_link(self, other: "STACObject", **kwargs):
        link = {
            "href": relpath(other.path, self.path),
            **kwargs
        }
        self.values.setdefault("links", []).append(link)


def read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def write_json(path: str, values: Any, indent: int = 2):
    with open(path, "w") as f:
        json.dump(values, f, indent=indent)


def get_self_href(obj: dict) -> str:
    link = next(
        (link for link in obj["link"] if link["rel"] == "self"),
        None
    )
    if link:
        return link["href"]


def get_child_hrefs(obj: dict) -> list:
    return [link for link in obj["link"] if link["rel"] == "child"]


def get_item_hrefs(obj: dict) -> list:
    return [link for link in obj["link"] if link["rel"] == "item"]


def normpath(a: str, b: str) -> str:
    return os.path.normpath(os.path.join(os.path.dirname(a), b))


def relpath(to: str, from_: str) -> str:
    return os.path.relpath(to, os.path.dirname(from_))
