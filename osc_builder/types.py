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
    status: Status
    website: str
    title: str
    description: str
    project: str
    variable: str
    themes: List[str]
    access: str
    documentation: Optional[str] = None
    doi: Optional[str] = None
    version: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    geometry: Optional[pygeoif.geometry._Geometry] = None
    region: Optional[str] = None
    released: Union[date, None, Literal["Planned"]] = None
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
    eo4_society_link: str
    consortium: List[str]
    start: datetime
    end: datetime
    technical_officer: Contact
    themes: List[str]


@dataclass
class Theme:
    name: str
    description: str
    link: str
    image: Optional[str] = None


@dataclass
class Variable:
    name: str
    description: str
    link: str
    theme: str


@dataclass
class EOMission:
    name: str
