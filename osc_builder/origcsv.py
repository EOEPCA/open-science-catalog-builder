from datetime import date, datetime, time, timezone
from typing import List, Literal, TextIO, Union, cast, Optional
import csv
import json
from urllib.parse import urlparse

from pygeoif import geometry
from dateutil.parser import parse as parse_datetime
from slugify import slugify

from .types import Contact, Product, Project, Status, Theme, Variable, EOMission
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
            depth = get_depth(raw_geom)
            if depth == 1:
                geom = geometry.Point(*raw_geom)
            elif depth == 3:
                shell, *holes = raw_geom
                geom = geometry.Polygon(shell, holes or None)
        except ValueError:
            pass

    return geom


def parse_released(value: str) -> Union[date, None, Literal["Planned"]]:
    if not value:
        return None

    if value == "Planned":
        return "Planned"

    return parse_datetime(value).date()


def parse_list(value: str, delimiter: str = ";") -> List[str]:
    return [
        stripped
        for item in value.split(delimiter)
        if (stripped := item.strip())
    ]


def parse_date(value: str, is_max: bool) -> Optional[datetime]:
    if not value:
        return None

    return datetime.combine(
        cast(datetime, parse_decimal_date(value)),
        time.max.replace(microsecond=0) if is_max else time.min,
        timezone.utc,
    )


def load_orig_products(file: TextIO) -> List[Product]:
    products = [
        Product(
            id=line["Short_Name"],
            status=Status(line["Status"].upper()),
            website=line.get("Website"),
            title=line["Product"],
            description=line["Description"],
            project=line["Project"],
            variables=parse_list(line["Variables"]),
            themes=get_themes(line),
            access=line["Access"],
            documentation=line["Documentation"] or None,
            doi=urlparse(line["DOI"]).path[1:] if line["DOI"] else None,
            version=line["Version"] or None,
            start=parse_date(line["Start"], False),
            end=parse_date(line["End"], True),
            geometry=parse_geometry(line["Polygon"]),
            region=line["Region"] or None,
            released=parse_released(line["Released"]),
            eo_missions=parse_list(line["EO_Missions"]),
            keywords=parse_list(line["Keywords"]),
            standard_name=line.get("Standard_Name")
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
            consortium=parse_list(line["Consortium"], ","),
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
            image=line.get("image"),
        )
        for line in csv.DictReader(file)
    ]


def load_orig_variables(file: TextIO) -> List[Variable]:
    return [
        Variable(
            name=line["variable"],
            description=line["variable description"],
            link=line["link"],
            themes=parse_list(line["themes"]),
        )
        for line in csv.DictReader(file)
    ]


def load_orig_eo_missions(file: TextIO) -> List[EOMission]:
    return [
        EOMission(
            name=line["EO_Missions"],
            description=line["Description"],
            link=line["Link"]
        )
        for line in csv.DictReader(file)
    ]


def validate_csvs(
    variables_file: TextIO,
    themes_file: TextIO,
    missions_file: TextIO,
    projects_file: TextIO,
    products_file: TextIO,
) -> List[str]:
    THEMES = {
        line["theme"].strip(): line for line in csv.DictReader(themes_file)
    }
    VARIABLES = {
        line["variable"].strip(): line
        for line in csv.DictReader(variables_file)
    }
    MISSIONS = {
        line["EO_Missions"].strip(): line
        for line in csv.DictReader(missions_file)
    }
    PROJECTS = {
        line["Project_Name"].strip(): line
        for line in csv.DictReader(projects_file)
    }
    PRODUCTS = {
        line["Product"].strip(): line for line in csv.DictReader(products_file)
    }

    issues = []

    for name, variable in VARIABLES.items():
        for theme in parse_list(
            variable.get("themes") or variable.get("theme")
        ):
            if theme not in THEMES:
                issues.append(
                    f"Variable '{name}' references non-existing theme '{theme}'"
                )

    for name, project in PROJECTS.items():
        for theme in get_themes(project):
            if theme not in THEMES:
                issues.append(
                    f"Project '{name}' references non-existing theme '{theme}'"
                )

    for name, product in PRODUCTS.items():
        project = product["Project"]
        if product["Project"] not in PROJECTS:
            issues.append(
                f"Product '{name}' references non-existing project '{project}'"
            )

        for theme in get_themes(product):
            if theme not in THEMES:
                issues.append(
                    f"Product '{name}' references non-existing theme '{theme}'"
                )

        for variable in parse_list(product["Variables"]):
            if variable not in VARIABLES:
                issues.append(
                    f"Product '{name}' references non-existing variable '{variable}'"
                )

        for mission in parse_list(product["EO_Missions"]):
            if mission not in MISSIONS:
                issues.append(
                    f"Product '{name}' references non-existing mission '{mission}'"
                )

    return issues
