from datetime import date, datetime, time, timezone
from typing import List, Literal, TextIO, Union, cast
import csv
import json
from urllib.parse import urlparse

from pygeoif import geometry
from dateutil.parser import parse as parse_datetime
from slugify import slugify

from .types import (
    Contact, Product, Project, Status, Theme, Variable, EOMission
)
from .util import parse_decimal_date, get_depth


def get_themes(obj: dict) -> List[str]:
    return [obj[f"Theme{i}"] for i in range(1, 7) if obj[f"Theme{i}"]]


def parse_geometry(source: str) -> geometry._Geometry:
    geom = None
    if not source:
        pass
    elif source.startswith("Multipolygon"):
        # TODO: figure out a way to parse this
        pass
    else:
        try:
            raw_geom = json.loads(source)
        except ValueError:
            pass
        depth = get_depth(raw_geom)
        if depth == 1:
            geom = geometry.Point(*raw_geom)
        elif depth == 3:
            shell, *holes = raw_geom
            geom = geometry.Polygon(shell, holes or None)

    return geom


def parse_released(value: str) -> Union[date, None, Literal["Planned"]]:
    if not value:
        return None

    if value == "Planned":
        return "Planned"

    return parse_datetime(value).date()


def load_orig_products(file: TextIO) -> List[Product]:
    products = [
        Product(
            id=line["Short_Name"],
            status=Status(line["Status"].upper()),
            website=line["Website"],
            title=line["Product"],
            description=line["Description"],
            project=line["Project"],
            variable=line["Variable"],
            themes=get_themes(line),
            access=line["Access"],
            documentation=line["Documentation"] or None,
            doi=urlparse(line["DOI"]).path[1:] if line["DOI"] else None,
            version=line["Version"] or None,
            start=datetime.combine(
                cast(datetime, parse_decimal_date(line["Start"])),
                time.min,
                timezone.utc,
            )
            if line["Start"]
            else None,
            end=datetime.combine(
                cast(datetime, parse_decimal_date(line["End"])),
                time.max.replace(microsecond=0),
                timezone.utc,
            )
            if line["End"]
            else None,
            geometry=parse_geometry(line["Polygon"]),
            region=line["Region"] or None,
            released=parse_released(line["Released"]),
            eo_missions=[
                stripped_mission
                for mission in line["EO_Missions"].split(";")
                if (stripped_mission := mission.strip())
            ],
        )
        for line in csv.DictReader(file)
    ]
    return products


def load_orig_projects(file: TextIO) -> List[Project]:
    projects = [
        Project(
            id=slugify(line["Short_Name"]),
            status=Status(line["Status"].upper()),
            name=line["Project_Name"],
            title=line["Short_Name"],
            description=line["Short_Description"],
            website=line["Website"],
            eo4_society_link=line["Eo4Society_link"],
            consortium=[
                stripped
                for member in line["Consortium"].split(",")
                if (stripped := member.strip())
            ],
            start=datetime.combine(
                parse_datetime(line["Start_Date_Project"]).date(),
                time.min,
                tzinfo=timezone.utc,
            ),
            end=datetime.combine(
                parse_datetime(line["End_Date_Project"]).date(),
                time.max.replace(microsecond=0),
                tzinfo=timezone.utc,
            ),
            technical_officer=Contact(
                line["TO"],
                line["TO_E-mail"],
            ),
            themes=get_themes(line),
        )
        for line in csv.DictReader(file)
    ]
    return projects


def load_orig_themes(file: TextIO) -> List[Theme]:
    return [
        Theme(
            name=line["theme"],
            description=line["description"],
            link=line["link"],
        )
        for line in csv.DictReader(file)
    ]


def load_orig_variables(file: TextIO) -> List[Variable]:
    return [
        Variable(
            name=line["variable"],
            description=line["variable description"],
            link=line["link"],
            theme=line["theme"],
        )
        for line in csv.DictReader(file)
    ]


def load_orig_eo_missions(file: TextIO) -> List[EOMission]:
    return [
        EOMission(
            name=line["name"],
        )
        for line in csv.DictReader(file, fieldnames=["name"])
    ]
