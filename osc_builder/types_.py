from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Literal, Optional, Union

import pygeoif


class Status(Enum):
    PLANNED = "PLANNED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"


@dataclass
class Product:
    id: str
    website: str
    title: str
    description: str
    project: str
    variables: List[str]
    themes: List[str]
    access: str
    notebook: str
    doi: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    geometry: Optional[pygeoif.geometry._Geometry] = None
    region: Optional[str] = None
    released: Union[date, None, Literal["Planned"]] = None
    eo_missions: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    format: Optional[str] = None
    category: Optional[str] = None
    coordinate: Optional[str] = None
    spatial_resolution: Optional[str] = None
    temporal_resolution: Optional[str] = None
    # TODO new
    collection: Optional[str] = None
    provider: Optional[str] = None


@dataclass
class ProductSegmentation:
    title: Optional[str]
    project: Optional[str]
    themes: List[str]
    released: Union[date, None, Literal["Planned"]] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    geometry: Optional[pygeoif.geometry._Geometry] = None
    region: Optional[str] = None
    variables: Optional[List[str]] = None
    eo_missions: List[str] = field(default_factory=list)



@dataclass
class Contact:
    name: str
    e_mail: str


@dataclass
class Project:
    id: str
    status: Status
    name: str
    title: str
    description: str
    website: str
    consortium: List[str]
    start: datetime
    end: datetime
    technical_officer: Contact


@dataclass
class Theme:
    name: str
    description: str
    link: Optional[str]
    image: Optional[str] = None


@dataclass
class Variable:
    name: str
    description: str
    link: Optional[str]
    themes: List[str]

    @classmethod
    def from_raw(cls, **kwargs):
        theme = kwargs.pop("theme", None)
        if theme and "themes" not in kwargs:
            kwargs["themes"] = [theme]
        return cls(**kwargs)


@dataclass
class EOMission:
    name: str
    description: Optional[str]
    link: Optional[str]


@dataclass
class Benchmark(Product):
    pass